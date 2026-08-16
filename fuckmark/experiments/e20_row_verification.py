from __future__ import annotations

import re
from collections.abc import Sequence

from ..adapters import WatermarkAdapter
from ..alignment import AlignmentResult, align_tokens
from ..corpus import CorpusManifest, CorpusSample, TextOnlyTokenRecord
from ..detectors import (
    CalibratedDetectorResult,
    CalibrationBundle,
    DetectorFamily,
    UncalibratedDetectorEvidence,
    verify_calibrated_detector_result,
    verify_uncalibrated_detector_evidence,
)
from ..hashing import sha256_json, sha256_text
from ..native_observations import NativeObservationBatch
from ..observation_verification import verify_native_observation_batch
from ..observations import StructuralObservationState, structural_observation_diff
from ..transforms import KeyBlindScheduleInput, ScheduleResult
from ..transforms.trace import TransformResult
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20Condition, E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    E20RunState,
    derive_e20_condition_seed,
    verify_e20_run_ledger,
)
from .e20_rows import (
    E20AlignmentFields,
    E20AuditFields,
    E20DetectorFields,
    E20FidelityFields,
    E20GValueFields,
    E20GenerationFields,
    E20HumanFidelityStatus,
    E20IdentityFields,
    E20ModelFields,
    E20ObservationFields,
    E20OutcomeRow,
    E20SourceFields,
    E20StatisticsFields,
    E20TextFields,
    E20TransformFields,
    E20WatermarkFields,
    ExperimentReasonCode,
)


E20_ROW_REPLAY_ALGORITHM_VERSION = "e20-row-replay-v1"
E20_ALIGNMENT_ALGORITHM_VERSION = "canonical-token-levenshtein-v1"
E20_TEXT_METRIC_ALGORITHM_VERSION = "unicode-word-levenshtein-v1"
_WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)


class E20RowVerificationError(ValueError):
    pass


def _levenshtein(left: Sequence[object], right: Sequence[object]) -> int:
    a = tuple(left)
    b = tuple(right)
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    masks: dict[object, int] = {}
    for index, value in enumerate(a):
        masks[value] = masks.get(value, 0) | (1 << index)
    score = len(a)
    high_bit = 1 << (len(a) - 1)
    positive = ~0
    negative = 0
    for value in b:
        char_mask = masks.get(value, 0)
        x = char_mask | negative
        d0 = (((x & positive) + positive) ^ positive) | x
        hp = negative | ~(d0 | positive)
        hn = d0 & positive
        if hp & high_bit:
            score += 1
        elif hn & high_bit:
            score -= 1
        hp = (hp << 1) | 1
        hn <<= 1
        positive = hn | ~(d0 | hp)
        negative = hp & d0
    return score


def _word_tokens(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return tuple(match.group(0) for match in _WORD_RE.finditer(text))


def _observation_and_gvalue_fields(
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    alignment: AlignmentResult,
) -> tuple[E20ObservationFields, E20GValueFields]:
    if original_batch.ngram_len != transformed_batch.ngram_len:
        raise E20RowVerificationError("original and transformed observation batches use different n-gram lengths")
    if original_batch.depth != transformed_batch.depth:
        raise E20RowVerificationError("original and transformed observation batches use different watermark depths")
    if (
        original_batch.adapter_id != transformed_batch.adapter_id
        or original_batch.adapter_algorithm_version != transformed_batch.adapter_algorithm_version
        or original_batch.adapter_config_hash != transformed_batch.adapter_config_hash
        or original_batch.source_id != transformed_batch.source_id
        or original_batch.source_commit != transformed_batch.source_commit
    ):
        raise E20RowVerificationError("original and transformed observation batches use different adapter identity")
    diffs = structural_observation_diff(
        original_batch.token_ids,
        transformed_batch.token_ids,
        original_batch.ngram_len,
        alignment,
    )
    preserved = 0
    replaced = 0
    dropped = 0
    mapped_transformed_valid: set[int] = set()
    per_depth_hamming = [0] * original_batch.depth
    for diff in diffs:
        original_record = original_batch.records[diff.original_index]
        if not original_record.valid:
            continue
        if diff.transformed_index is None:
            dropped += 1
            continue
        transformed_record = transformed_batch.records[diff.transformed_index]
        if not transformed_record.valid:
            dropped += 1
            continue
        mapped_transformed_valid.add(diff.transformed_index)
        if diff.state is StructuralObservationState.PRESERVED:
            preserved += 1
        elif diff.state is StructuralObservationState.REPLACED:
            replaced += 1
        else:
            raise E20RowVerificationError("mapped valid observation cannot have UNMAPPED structural state")
        for depth, (before, after) in enumerate(zip(original_record.g_values, transformed_record.g_values)):
            per_depth_hamming[depth] += int(before != after)
    transformed_valid_indices = {
        index for index, record in enumerate(transformed_batch.records) if record.valid
    }
    added = len(transformed_valid_indices - mapped_transformed_valid)
    original_valid = sum(record.valid for record in original_batch.records)
    transformed_valid = sum(record.valid for record in transformed_batch.records)
    observation = E20ObservationFields(
        original_valid,
        transformed_valid,
        preserved,
        replaced,
        dropped,
        added,
        len(original_batch.records) - original_valid,
        len(transformed_batch.records) - transformed_valid,
    )
    matched = preserved + replaced
    gvalues = E20GValueFields(
        original_batch.depth,
        sha256_json(
            {
                "algorithm_version": E20_ROW_REPLAY_ALGORITHM_VERSION,
                "matched_observation_count": matched,
                "per_depth_hamming_difference_count": tuple(per_depth_hamming),
            }
        ),
        matched,
        sum(per_depth_hamming),
    )
    return observation, gvalues


def _require_detector_pair(
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    original_result: CalibratedDetectorResult,
    transformed_result: CalibratedDetectorResult,
    calibration_bundle: CalibrationBundle,
    condition: E20Condition,
) -> E20DetectorFields:
    if original_evidence.detector_family is DetectorFamily.BAYESIAN:
        raise E20RowVerificationError("Bayesian E20 row replay requires the future source-grounded Bayesian evidence path")
    if original_evidence.detector_family is not transformed_evidence.detector_family:
        raise E20RowVerificationError("original and transformed detector evidence use different detector families")
    if original_evidence.detector_config_hash != transformed_evidence.detector_config_hash:
        raise E20RowVerificationError("original and transformed detector evidence use different detector configuration")
    if original_evidence.normalized_weights != transformed_evidence.normalized_weights:
        raise E20RowVerificationError("original and transformed detector evidence use different normalized weights")
    if original_result.target_fpr != condition.target_fpr or transformed_result.target_fpr != condition.target_fpr:
        raise E20RowVerificationError("detector results do not use the condition-plan target FPR")
    if original_result.calibration_bundle_hash != calibration_bundle.bundle_hash or transformed_result.calibration_bundle_hash != calibration_bundle.bundle_hash:
        raise E20RowVerificationError("detector results do not use the supplied calibration bundle")
    if original_result.threshold_hash != transformed_result.threshold_hash:
        raise E20RowVerificationError("original and transformed detector results use different fixed thresholds")
    if original_result.threshold_value != transformed_result.threshold_value:
        raise E20RowVerificationError("original and transformed detector results use different threshold values")
    if original_result.robust_scale != transformed_result.robust_scale:
        raise E20RowVerificationError("original and transformed detector results use different robust scales")
    if original_result.comparison_operator is not transformed_result.comparison_operator:
        raise E20RowVerificationError("original and transformed detector results use different comparison operators")
    return E20DetectorFields(
        original_evidence.detector_family,
        original_evidence.detector_config_hash,
        None,
        calibration_bundle.bundle_hash,
        original_result.threshold_hash,
        original_result.comparison_operator,
        condition.target_fpr,
        original_result.threshold_value,
        original_result.robust_scale,
        original_result.raw_score,
        transformed_result.raw_score,
        original_result.standardized_margin,
        transformed_result.standardized_margin,
        original_result.decision,
        transformed_result.decision,
    )


def _artifact_hashes(
    source_sample: CorpusSample,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    calibration_bundle: CalibrationBundle,
    alignment: AlignmentResult,
) -> tuple[str, ...]:
    values = {
        source_sample.record_hash,
        transformed_tokens.record_hash,
        schedule_input.input_artifact_hash,
        schedule_result.result_hash,
        transform_result.result_hash,
        transform_result.trace.trace_hash,
        sha256_json(original_batch),
        sha256_json(transformed_batch),
        sha256_json(original_evidence),
        sha256_json(transformed_evidence),
        original_detector_result.result_hash,
        transformed_detector_result.result_hash,
        calibration_bundle.bundle_hash,
        sha256_json(alignment),
    }
    return tuple(sorted(values))


def build_e20_outcome_row(
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    calibration_bundle: CalibrationBundle,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    *,
    condition_id: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus = E20HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
) -> E20OutcomeRow:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(ledger, E20RunLedger):
        raise TypeError("ledger must be an E20RunLedger")
    verify_e20_run_ledger(ledger, authorization)
    if ledger.state is not E20RunState.STARTED:
        raise E20RowVerificationError("E20 outcome rows may be built only while the sealed run is STARTED")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    verify_e20_condition_plan(condition_plan, preregistration)
    condition = condition_plan.condition(condition_id)
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if corpus_manifest.manifest_hash != authorization.corpus_manifest_hash:
        raise E20RowVerificationError("corpus manifest does not match E20 authorization")
    matching_samples = tuple(value for value in corpus_manifest.samples if value.sample_id == source_sample.sample_id)
    if len(matching_samples) != 1 or matching_samples[0] != source_sample:
        raise E20RowVerificationError("source sample does not replay exactly from the authorized corpus manifest")
    if source_sample.model not in preregistration.model_tokenizers:
        raise E20RowVerificationError("source sample model/tokenizer is not preregistered")
    if transformed_tokens.model_tokenizer_identity_hash != source_sample.model.identity_hash:
        raise E20RowVerificationError("transformed token record uses a different model/tokenizer identity")
    if transformed_tokens.source_text_sha256 != sha256_text(transform_result.output_text):
        raise E20RowVerificationError("transformed token record does not bind to transform output text")
    if transform_result.trace.input_hash != source_sample.text_sha256:
        raise E20RowVerificationError("transform input hash does not match exact source sample text")
    if transform_result.trace.ruleset_hash != preregistration.transform_ruleset_hash:
        raise E20RowVerificationError("transform trace ruleset does not match preregistration")
    if schedule_input.input_hash != source_sample.text_sha256:
        raise E20RowVerificationError("scheduler input hash does not match exact source sample text")
    if schedule_input.enumeration_hash != transform_result.trace.enumeration_hash:
        raise E20RowVerificationError("scheduler and transform trace use different candidate enumeration")
    if schedule_result.input_artifact_hash != schedule_input.input_artifact_hash:
        raise E20RowVerificationError("schedule result does not bind to supplied scheduler input")
    if schedule_result.policy is not condition.schedule_policy:
        raise E20RowVerificationError("schedule result policy does not match sealed condition")
    if schedule_result.budget != condition.budget or schedule_result.budget_unit != condition.budget_unit:
        raise E20RowVerificationError("schedule result budget does not match sealed condition")
    expected_seed = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        source_sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
    if schedule_result.seed != expected_seed:
        raise E20RowVerificationError("schedule result seed does not match sealed deterministic transform seed derivation")
    if transform_result.trace.seed != schedule_result.seed:
        raise E20RowVerificationError("transform trace seed does not match schedule seed")
    if transform_result.trace.selected_candidate_ids != schedule_result.selected_candidate_ids:
        raise E20RowVerificationError("transform trace candidate selection does not match schedule result")
    if schedule_result.total_cost != sum(
        candidate.edit_cost
        for candidate in schedule_input.candidates
        if candidate.candidate_id in set(schedule_result.selected_candidate_ids)
    ):
        raise E20RowVerificationError("schedule total cost does not replay from selected scheduler candidates")
    original_tokens = source_sample.generation_tokens.continuation_token_ids
    transformed_token_ids = transformed_tokens.token_ids
    if original_batch.sample_id != source_sample.sample_id or original_batch.token_ids != original_tokens:
        raise E20RowVerificationError("original observation batch does not bind to source generation tokens")
    expected_transformed_batch_id = f"{source_sample.sample_id}:{condition.transform_condition_id}:transformed"
    if transformed_batch.sample_id != expected_transformed_batch_id or transformed_batch.token_ids != transformed_token_ids:
        raise E20RowVerificationError("transformed observation batch does not use the canonical transform-bound identity and token sequence")
    verify_native_observation_batch(original_batch, adapter)
    verify_native_observation_batch(transformed_batch, adapter)
    verify_uncalibrated_detector_evidence(original_batch, original_evidence)
    verify_uncalibrated_detector_evidence(transformed_batch, transformed_evidence)
    verify_calibrated_detector_result(original_evidence, calibration_bundle, original_detector_result)
    verify_calibrated_detector_result(transformed_evidence, calibration_bundle, transformed_detector_result)
    if calibration_bundle not in preregistration.calibration_bundles:
        raise E20RowVerificationError("calibration bundle is not part of the frozen preregistration")
    alignment = align_tokens(original_tokens, transformed_token_ids)
    if alignment.ambiguous_ties != 0:
        raise E20RowVerificationError("complete E20 outcome requires unambiguous canonical token alignment")
    observation, gvalues = _observation_and_gvalue_fields(original_batch, transformed_batch, alignment)
    detector = _require_detector_pair(
        original_evidence,
        transformed_evidence,
        original_detector_result,
        transformed_detector_result,
        calibration_bundle,
        condition,
    )
    source_words = _word_tokens(source_sample.text)
    transformed_words = _word_tokens(transform_result.output_text)
    eligible = bool(schedule_result.selected_candidate_ids)
    if eligible != bool(transform_result.trace.operations):
        raise E20RowVerificationError("scheduler eligibility does not match transform operation trace")
    if not eligible:
        reason = ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM
    elif human_status is E20HumanFidelityStatus.MATERIAL_CHANGE:
        reason = ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE
    else:
        reason = ExperimentReasonCode.OK
    identity = E20IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E20",
        condition.condition_id,
        source_sample.sample_id,
        source_sample.match_id,
    )
    source = E20SourceFields(
        original_batch.adapter_id,
        original_batch.source_commit,
        original_batch.adapter_config_hash,
    )
    model = E20ModelFields(
        source_sample.model.model_id,
        source_sample.model.model_revision,
        source_sample.model.tokenizer_id,
        source_sample.model.tokenizer_revision,
    )
    watermark = E20WatermarkFields(
        source_sample.watermark.watermark_config_hash,
        source_sample.watermark.key_split,
        source_sample.watermark.key_id,
    )
    generation = E20GenerationFields(
        source_sample.generation.seed,
        source_sample.generation.temperature,
        source_sample.generation.top_k,
        source_sample.generation.top_p,
        source_sample.generation_realized_length,
    )
    text = E20TextFields(
        source_sample.text_sha256,
        sha256_text(transform_result.output_text),
        len(source_sample.text),
        len(transform_result.output_text),
        len(source_words),
        len(transformed_words),
        len(original_tokens),
        len(transformed_token_ids),
    )
    transform = E20TransformFields(
        preregistration.transform_ruleset_hash,
        schedule_result.policy,
        schedule_result.seed,
        schedule_result.budget,
        schedule_result.budget_unit,
        schedule_result.total_cost,
        schedule_input.enumeration_hash,
        schedule_input.input_artifact_hash,
        schedule_result.result_hash,
        transform_result.trace.trace_hash,
        eligible,
    )
    fidelity = E20FidelityFields(
        True,
        (reason,),
        _levenshtein(tuple(source_sample.text), tuple(transform_result.output_text)),
        _levenshtein(source_words, transformed_words),
        alignment.distance,
        human_status,
        human_adjudication_hash,
    )
    alignment_fields = E20AlignmentFields(
        E20_ALIGNMENT_ALGORITHM_VERSION,
        sha256_json(alignment.steps),
        alignment.ambiguous_ties,
    )
    statistics = E20StatisticsFields(
        sha256_json(
            {
                "model_tokenizer_identity_hash": source_sample.model.identity_hash,
                "domain": source_sample.domain.value,
                "target_length": source_sample.target_length,
                "key_id": source_sample.watermark.key_id,
                "detector_config_hash": original_evidence.detector_config_hash,
                "target_fpr": condition.target_fpr,
            }
        ),
        source_sample.sample_id,
        condition.hypothesis_class,
    )
    audit = E20AuditFields(
        authorization.worker_version,
        timestamp_utc,
        authorization.environment_snapshot_hash,
        authorization.authorization_hash,
        ledger.ledger_hash,
        _artifact_hashes(
            source_sample,
            transformed_tokens,
            schedule_input,
            schedule_result,
            transform_result,
            original_batch,
            transformed_batch,
            original_evidence,
            transformed_evidence,
            original_detector_result,
            transformed_detector_result,
            calibration_bundle,
            alignment,
        ),
    )
    return E20OutcomeRow.create(
        identity,
        source,
        model,
        watermark,
        generation,
        text,
        transform,
        fidelity,
        alignment_fields,
        observation,
        gvalues,
        detector,
        statistics,
        audit,
    )


def verify_e20_outcome_row(
    row: E20OutcomeRow,
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    calibration_bundle: CalibrationBundle,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    *,
    condition_id: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus = E20HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
) -> None:
    if not isinstance(row, E20OutcomeRow):
        raise TypeError("row must be an E20OutcomeRow")
    expected = build_e20_outcome_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        corpus_manifest,
        source_sample,
        adapter,
        transformed_tokens,
        schedule_input,
        schedule_result,
        transform_result,
        original_batch,
        transformed_batch,
        original_evidence,
        transformed_evidence,
        calibration_bundle,
        original_detector_result,
        transformed_detector_result,
        condition_id=condition_id,
        timestamp_utc=timestamp_utc,
        human_status=human_status,
        human_adjudication_hash=human_adjudication_hash,
    )
    if row != expected:
        raise E20RowVerificationError("E20 outcome row does not replay exactly from sealed source artifacts")
