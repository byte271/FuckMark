from __future__ import annotations

from ..adapters import WatermarkAdapter
from ..alignment import align_tokens
from ..corpus import CorpusManifest, CorpusSample, TextOnlyTokenRecord
from ..detectors import (
    CalibratedDetectorResult,
    CalibrationBundle,
    DetectorFamily,
    UncalibratedDetectorEvidence,
    verify_calibrated_detector_result,
    verify_uncalibrated_detector_evidence,
)
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..hashing import sha256_json, sha256_text
from ..native_observations import NativeObservationBatch
from ..observation_verification import verify_native_observation_batch
from ..transforms import KeyBlindScheduleInput, ScheduleResult
from ..transforms.trace import TransformResult
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_row_verification import (
    E20_ALIGNMENT_ALGORITHM_VERSION,
    _levenshtein,
    _observation_and_gvalue_fields,
    _word_tokens,
)
from .e20_rows import (
    E20AlignmentFields,
    E20AuditFields,
    E20DetectorFields,
    E20FidelityFields,
    E20GenerationFields,
    E20HumanFidelityStatus,
    E20ModelFields,
    E20SourceFields,
    E20StatisticsFields,
    E20TextFields,
    E20TransformFields,
    E20WatermarkFields,
    ExperimentReasonCode,
)


class ConfirmatoryOutcomeReplayError(ValueError):
    pass


def _require_generation_track(
    preregistration: ConfirmatoryPreregistration,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    calibration_bundle: CalibrationBundle,
) -> None:
    try:
        track = preregistration.watermark_tracks.track_for(
            source_sample.watermark.watermark_config_hash
        )
    except KeyError as error:
        raise ConfirmatoryOutcomeReplayError(
            "source sample watermark configuration is outside the sealed generation tracks"
        ) from error
    if (
        adapter.adapter_id != track.adapter_id
        or adapter.algorithm_version != track.adapter_algorithm_version
        or adapter.configuration_fingerprint() != track.adapter_config_hash
        or adapter.source_pin.source_id != track.source_pin.source_id
        or adapter.source_pin.commit != track.source_pin.commit
    ):
        raise ConfirmatoryOutcomeReplayError(
            "observation adapter does not match the source sample sealed generation track"
        )
    if not track.matches_detector_identity(calibration_bundle.detector_identity):
        raise ConfirmatoryOutcomeReplayError(
            "runtime detector bundle is not source/config compatible with the source sample generation track"
        )


def _detector_fields(
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    original_result: CalibratedDetectorResult,
    transformed_result: CalibratedDetectorResult,
    calibration_bundle: CalibrationBundle,
    target_fpr: float,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None,
) -> E20DetectorFields:
    if original_evidence.detector_family is not transformed_evidence.detector_family:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector evidence use different detector families"
        )
    if original_evidence.detector_config_hash != transformed_evidence.detector_config_hash:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector evidence use different detector configuration"
        )
    if original_evidence.normalized_weights != transformed_evidence.normalized_weights:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector evidence use different normalized weights"
        )
    if original_evidence.detector_artifact_hashes != transformed_evidence.detector_artifact_hashes:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector evidence use different detector artifacts"
        )
    if original_evidence.detector_family is DetectorFamily.BAYESIAN:
        if bayesian_artifacts is None:
            raise ConfirmatoryOutcomeReplayError(
                "Bayesian confirmatory rows require the complete readiness artifact bundle"
            )
        checkpoint_hash = bayesian_artifacts.checkpoint.checkpoint_hash
        expected_artifacts = tuple(
            sorted(
                {
                    bayesian_artifacts.checkpoint.checkpoint_hash,
                    bayesian_artifacts.readiness.readiness_hash,
                    bayesian_artifacts.provenance.provenance_hash,
                    bayesian_artifacts.sanity.evidence_hash,
                }
            )
        )
        if original_evidence.detector_artifact_hashes != expected_artifacts:
            raise ConfirmatoryOutcomeReplayError(
                "Bayesian detector evidence does not bind the supplied readiness artifacts"
            )
    else:
        if bayesian_artifacts is not None:
            raise ConfirmatoryOutcomeReplayError(
                "non-Bayesian confirmatory rows cannot carry Bayesian readiness artifacts"
            )
        checkpoint_hash = None
    if original_result.target_fpr != target_fpr or transformed_result.target_fpr != target_fpr:
        raise ConfirmatoryOutcomeReplayError(
            "detector results do not use the frozen condition target FPR"
        )
    if (
        original_result.calibration_bundle_hash != calibration_bundle.bundle_hash
        or transformed_result.calibration_bundle_hash != calibration_bundle.bundle_hash
    ):
        raise ConfirmatoryOutcomeReplayError(
            "detector results do not use the supplied calibration bundle"
        )
    if original_result.threshold_hash != transformed_result.threshold_hash:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector results use different fixed thresholds"
        )
    if original_result.threshold_value != transformed_result.threshold_value:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector results use different threshold values"
        )
    if original_result.robust_scale != transformed_result.robust_scale:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector results use different robust scales"
        )
    if original_result.comparison_operator is not transformed_result.comparison_operator:
        raise ConfirmatoryOutcomeReplayError(
            "original and transformed detector results use different comparison operators"
        )
    return E20DetectorFields(
        original_evidence.detector_family,
        original_evidence.detector_config_hash,
        checkpoint_hash,
        calibration_bundle.bundle_hash,
        original_result.threshold_hash,
        original_result.comparison_operator,
        target_fpr,
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
    alignment,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None,
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
    if bayesian_artifacts is not None:
        values.add(bayesian_artifacts.bundle_hash)
    return tuple(sorted(values))


def build_confirmatory_outcome_fields(
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    authorized_corpus_manifest_hash: str,
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
    expected_schedule_seed: int,
    worker_version: str,
    environment_snapshot_hash: str,
    authorization_hash: str,
    ledger_hash: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus = E20HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> tuple[object, ...]:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    verify_e20_condition_plan(condition_plan, preregistration)
    condition = condition_plan.condition(condition_id)
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if corpus_manifest.manifest_hash != authorized_corpus_manifest_hash:
        raise ConfirmatoryOutcomeReplayError(
            "corpus manifest does not match the sealed execution authorization"
        )
    matching_samples = tuple(
        value for value in corpus_manifest.samples if value.sample_id == source_sample.sample_id
    )
    if len(matching_samples) != 1 or matching_samples[0] != source_sample:
        raise ConfirmatoryOutcomeReplayError(
            "source sample does not replay exactly from the authorized corpus manifest"
        )
    if source_sample.model not in preregistration.model_tokenizers:
        raise ConfirmatoryOutcomeReplayError(
            "source sample model/tokenizer is not preregistered"
        )
    if condition.calibration_bundle_hash != calibration_bundle.bundle_hash:
        raise ConfirmatoryOutcomeReplayError(
            "runtime calibration bundle does not match the detector bundle frozen in the condition"
        )
    _require_generation_track(
        preregistration,
        source_sample,
        adapter,
        calibration_bundle,
    )
    if transformed_tokens.model_tokenizer_identity_hash != source_sample.model.identity_hash:
        raise ConfirmatoryOutcomeReplayError(
            "transformed token record uses a different model/tokenizer identity"
        )
    if transformed_tokens.source_text_sha256 != sha256_text(transform_result.output_text):
        raise ConfirmatoryOutcomeReplayError(
            "transformed token record does not bind to transform output text"
        )
    if transform_result.trace.input_hash != source_sample.text_sha256:
        raise ConfirmatoryOutcomeReplayError(
            "transform input hash does not match exact source sample text"
        )
    if transform_result.trace.ruleset_hash != preregistration.transform_ruleset_hash:
        raise ConfirmatoryOutcomeReplayError(
            "transform trace ruleset does not match preregistration"
        )
    if schedule_input.input_hash != source_sample.text_sha256:
        raise ConfirmatoryOutcomeReplayError(
            "scheduler input hash does not match exact source sample text"
        )
    if schedule_input.enumeration_hash != transform_result.trace.enumeration_hash:
        raise ConfirmatoryOutcomeReplayError(
            "scheduler and transform trace use different candidate enumeration"
        )
    if schedule_result.input_artifact_hash != schedule_input.input_artifact_hash:
        raise ConfirmatoryOutcomeReplayError(
            "schedule result does not bind to supplied scheduler input"
        )
    if schedule_result.policy is not condition.schedule_policy:
        raise ConfirmatoryOutcomeReplayError(
            "schedule result policy does not match sealed condition"
        )
    if schedule_result.budget != condition.budget or schedule_result.budget_unit != condition.budget_unit:
        raise ConfirmatoryOutcomeReplayError(
            "schedule result budget does not match sealed condition"
        )
    if schedule_result.seed != expected_schedule_seed:
        raise ConfirmatoryOutcomeReplayError(
            "schedule result seed does not match sealed deterministic transform seed derivation"
        )
    if transform_result.trace.seed != schedule_result.seed:
        raise ConfirmatoryOutcomeReplayError(
            "transform trace seed does not match schedule seed"
        )
    if transform_result.trace.selected_candidate_ids != schedule_result.selected_candidate_ids:
        raise ConfirmatoryOutcomeReplayError(
            "transform trace candidate selection does not match schedule result"
        )
    selected = set(schedule_result.selected_candidate_ids)
    if schedule_result.total_cost != sum(
        candidate.edit_cost
        for candidate in schedule_input.candidates
        if candidate.candidate_id in selected
    ):
        raise ConfirmatoryOutcomeReplayError(
            "schedule total cost does not replay from selected scheduler candidates"
        )
    original_tokens = source_sample.generation_tokens.continuation_token_ids
    transformed_token_ids = transformed_tokens.token_ids
    if original_batch.sample_id != source_sample.sample_id or original_batch.token_ids != original_tokens:
        raise ConfirmatoryOutcomeReplayError(
            "original observation batch does not bind to source generation tokens"
        )
    expected_transformed_batch_id = (
        f"{source_sample.sample_id}:{condition.transform_condition_id}:transformed"
    )
    if (
        transformed_batch.sample_id != expected_transformed_batch_id
        or transformed_batch.token_ids != transformed_token_ids
    ):
        raise ConfirmatoryOutcomeReplayError(
            "transformed observation batch does not use the canonical transform-bound identity and token sequence"
        )
    verify_native_observation_batch(original_batch, adapter)
    verify_native_observation_batch(transformed_batch, adapter)
    verify_uncalibrated_detector_evidence(
        original_batch,
        original_evidence,
        bayesian_artifacts=bayesian_artifacts,
    )
    verify_uncalibrated_detector_evidence(
        transformed_batch,
        transformed_evidence,
        bayesian_artifacts=bayesian_artifacts,
    )
    verify_calibrated_detector_result(
        original_evidence,
        calibration_bundle,
        original_detector_result,
    )
    verify_calibrated_detector_result(
        transformed_evidence,
        calibration_bundle,
        transformed_detector_result,
    )
    if calibration_bundle not in preregistration.calibration_bundles:
        raise ConfirmatoryOutcomeReplayError(
            "calibration bundle is not part of the frozen preregistration"
        )
    alignment = align_tokens(original_tokens, transformed_token_ids)
    if alignment.ambiguous_ties != 0:
        raise ConfirmatoryOutcomeReplayError(
            "complete confirmatory outcome requires unambiguous canonical token alignment"
        )
    observation, gvalues = _observation_and_gvalue_fields(
        original_batch,
        transformed_batch,
        alignment,
    )
    detector = _detector_fields(
        original_evidence,
        transformed_evidence,
        original_detector_result,
        transformed_detector_result,
        calibration_bundle,
        condition.target_fpr,
        bayesian_artifacts,
    )
    source_words = _word_tokens(source_sample.text)
    transformed_words = _word_tokens(transform_result.output_text)
    eligible = bool(schedule_result.selected_candidate_ids)
    if eligible != bool(transform_result.trace.operations):
        raise ConfirmatoryOutcomeReplayError(
            "scheduler eligibility does not match transform operation trace"
        )
    if not eligible:
        reason = ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM
    elif human_status is E20HumanFidelityStatus.MATERIAL_CHANGE:
        reason = ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE
    else:
        reason = ExperimentReasonCode.OK
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
        worker_version,
        timestamp_utc,
        environment_snapshot_hash,
        authorization_hash,
        ledger_hash,
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
            bayesian_artifacts,
        ),
    )
    return (
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
