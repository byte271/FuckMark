from __future__ import annotations

from typing import Any

from ..corpus.mid_dev import MidDevAttackArtifact
from ..corpus.schema import WatermarkLabel
from ..corpus.tiny_dev import TinyDevCorpusArtifact
from ..detectors import weighted_mean_evidence
from ..hashing import sha256_json
from ..native_observations import build_native_observations
from ..tiny_dev_transform_hf import (
    PRIMARY_TARGET_FPR,
    _encode_text,
    _text_only_calibration,
    _text_only_weighted_evidence,
    _threshold,
)
from .mid_dev_freeze import MidDevDeterministicFrozenPlan
from .mid_dev_scored_schema import MidDevScoredPlanRow, MidDevScoringArtifact
from .mid_dev_scoring_io import validate_mid_dev_scoring_plan_trace_binding
from .mid_dev_trace_schema import MidDevSelectionTraceArtifact


def _validate_plan_against_corpus(
    corpus: MidDevAttackArtifact,
    plan: MidDevDeterministicFrozenPlan,
) -> dict[str, Any]:
    if plan.corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("frozen MidDev plan does not bind the supplied MidDev corpus")
    if plan.source_profile_hash != corpus.source_profile_hash:
        raise ValueError("frozen MidDev plan source profile does not match corpus")
    if plan.analysis_split_hash != corpus.analysis_split_hash:
        raise ValueError("frozen MidDev plan analysis split does not match corpus")
    sample_by_id = {sample.sample_id: sample for sample in corpus.manifest.samples}
    if len(sample_by_id) != 72:
        raise ValueError("MidDev corpus must contain exactly 72 source samples")
    for row in plan.rows:
        sample = sample_by_id.get(row.sample_id)
        if sample is None:
            raise ValueError("MidDev plan row references an unknown source sample")
        if (
            row.source_group_id != sample.match_id
            or row.prompt_id != sample.prompt_id
            or row.source_label is not sample.label
            or row.prompt_family_id != sample.prompt_family_id
            or row.domain is not sample.domain
            or row.target_length != sample.target_length
            or row.source_text_hash != sample.text_sha256
        ):
            raise ValueError("MidDev plan row metadata does not replay corpus source metadata")
    return sample_by_id


def _score_text(source: Any, text: str, tokenizer: Any, adapter: Any) -> float:
    tokens = _encode_text(tokenizer, text)
    eos = source.model.eos_token_id
    if eos is None:
        raise ValueError("MidDev source tokenizer must define eos_token_id")
    batch = build_native_observations(
        f"{source.sample_id}-middev-scored-{sha256_json(tokens)[:12]}",
        tokens,
        eos,
        adapter,
    )
    return float(weighted_mean_evidence(batch).raw_score)


def score_mid_dev_frozen_plan(
    mid_dev_corpus: MidDevAttackArtifact,
    calibration_corpus: TinyDevCorpusArtifact,
    tokenizer: Any,
    plan: MidDevDeterministicFrozenPlan,
    traces: MidDevSelectionTraceArtifact,
    adapter: Any,
) -> MidDevScoringArtifact:
    validate_mid_dev_scoring_plan_trace_binding(plan, traces)
    sample_by_id = _validate_plan_against_corpus(mid_dev_corpus, plan)
    mid_model_hashes = {sample.model.identity_hash for sample in mid_dev_corpus.manifest.samples}
    if mid_model_hashes != {calibration_corpus.model_identity_hash}:
        raise ValueError("MidDev and calibration corpora must use the same model/tokenizer identity")
    mid_watermark_hashes = {
        sample.watermark.condition_hash for sample in mid_dev_corpus.manifest.samples
    }
    if mid_watermark_hashes != {calibration_corpus.watermark_condition_hash}:
        raise ValueError("MidDev and calibration corpora must use the same watermark condition")
    if int(plan.ngram_len) != int(adapter.ngram_len):
        raise ValueError("MidDev plan ngram_len does not match scoring adapter")

    calibration = _text_only_calibration(calibration_corpus, adapter)
    threshold = _threshold(calibration, PRIMARY_TARGET_FPR)
    detector_identity_hash = calibration.detector_identity.identity_hash
    pristine = {
        sample_id: float(_text_only_weighted_evidence(source, adapter).raw_score)
        for sample_id, source in sample_by_id.items()
    }
    cache: dict[tuple[str, str], float] = {}
    scored_rows: list[MidDevScoredPlanRow] = []
    for plan_row in plan.rows:
        source = sample_by_id[plan_row.sample_id]
        cache_key = (plan_row.sample_id, plan_row.transformed_text_hash)
        transformed_score = cache.get(cache_key)
        if transformed_score is None:
            transformed_score = _score_text(source, plan_row.transformed_text, tokenizer, adapter)
            cache[cache_key] = transformed_score
        scored_rows.append(
            MidDevScoredPlanRow.create(
                plan_row=plan_row,
                detector_identity_hash=detector_identity_hash,
                threshold_hash=threshold.threshold_hash,
                threshold_value=threshold.value,
                pristine_score=pristine[plan_row.sample_id],
                transformed_score=transformed_score,
            )
        )
    row_tuple = tuple(scored_rows)
    positive_ids = {
        sample.sample_id
        for sample in mid_dev_corpus.manifest.samples
        if sample.label is WatermarkLabel.WATERMARKED
    }
    control_ids = {
        sample.sample_id
        for sample in mid_dev_corpus.manifest.samples
        if sample.label is WatermarkLabel.UNWATERMARKED
    }
    payload = {
        "algorithm_version": "mid-dev-scoring-artifact-v1",
        "mid_dev_corpus_artifact_hash": mid_dev_corpus.artifact_hash,
        "source_profile_hash": mid_dev_corpus.source_profile_hash,
        "analysis_split_hash": mid_dev_corpus.analysis_split_hash,
        "plan_hash": plan.plan_hash,
        "trace_artifact_hash": traces.artifact_hash,
        "calibration_corpus_artifact_hash": calibration_corpus.artifact_hash,
        "calibration_bundle_hash": calibration.bundle_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold.threshold_hash,
        "threshold_value": threshold.value,
        "target_fpr": PRIMARY_TARGET_FPR,
        "independent_source_group_count": 36,
        "independent_watermarked_source_count": len(positive_ids),
        "independent_control_source_count": len(control_ids),
        "pristine_watermarked_detected_count": sum(
            pristine[sample_id] >= threshold.value for sample_id in positive_ids
        ),
        "pristine_control_detected_count": sum(
            pristine[sample_id] >= threshold.value for sample_id in control_ids
        ),
        "row_hashes": tuple(row.scored_row_hash for row in row_tuple),
    }
    return MidDevScoringArtifact(
        mid_dev_corpus.artifact_hash,
        mid_dev_corpus.source_profile_hash,
        mid_dev_corpus.analysis_split_hash,
        plan.plan_hash,
        traces.artifact_hash,
        calibration_corpus.artifact_hash,
        calibration.bundle_hash,
        detector_identity_hash,
        threshold.threshold_hash,
        threshold.value,
        PRIMARY_TARGET_FPR,
        36,
        len(positive_ids),
        len(control_ids),
        payload["pristine_watermarked_detected_count"],
        payload["pristine_control_detected_count"],
        row_tuple,
        sha256_json(payload),
    )
