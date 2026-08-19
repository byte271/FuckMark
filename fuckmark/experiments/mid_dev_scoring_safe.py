from __future__ import annotations

from typing import Any

from ..corpus.mid_dev import MidDevAttackArtifact
from ..corpus.mid_dev_calibration import MidDevCalibrationArtifact
from ..corpus.schema import WatermarkLabel
from ..detector_calibration import encode_text, text_only_weighted_evidence
from ..detectors import weighted_mean_evidence
from ..hashing import sha256_json
from ..native_observations import build_native_observations
from .mid_dev_length_calibration import build_mid_dev_length_calibrations
from .mid_dev_scored_schema import (
    MID_DEV_SCORING_ARTIFACT_VERSION,
    MidDevScoredPlanRow,
    MidDevScoringArtifact,
)
from .mid_dev_scoring_contracts import MidDevFrozenPlanView
from .mid_dev_scoring_io import validate_mid_dev_scoring_plan_trace_binding
from .mid_dev_trace_schema import MidDevSelectionTraceArtifact


def _validate_plan_against_corpus(
    corpus: MidDevAttackArtifact,
    plan: MidDevFrozenPlanView,
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


def _validate_calibration_identity(
    mid_dev_corpus: MidDevAttackArtifact,
    calibration_corpus: MidDevCalibrationArtifact,
) -> None:
    attack_model_hashes = {sample.model.identity_hash for sample in mid_dev_corpus.manifest.samples}
    calibration_model_hashes = {
        sample.model.identity_hash for sample in calibration_corpus.manifest.samples
    }
    if attack_model_hashes != calibration_model_hashes or len(attack_model_hashes) != 1:
        raise ValueError("MidDev attack and calibration corpora must share one model/tokenizer identity")
    attack_watermark_hashes = {
        sample.watermark.condition_hash for sample in mid_dev_corpus.manifest.samples
    }
    calibration_watermark_hashes = {
        sample.watermark.condition_hash for sample in calibration_corpus.manifest.samples
    }
    if attack_watermark_hashes != calibration_watermark_hashes or len(attack_watermark_hashes) != 1:
        raise ValueError("MidDev attack and calibration corpora must share one watermark condition")


def _score_text(source: Any, text: str, tokenizer: Any, adapter: Any) -> float:
    tokens = encode_text(tokenizer, text)
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
    calibration_corpus: MidDevCalibrationArtifact,
    tokenizer: Any,
    plan: MidDevFrozenPlanView,
    traces: MidDevSelectionTraceArtifact,
    adapter: Any,
) -> MidDevScoringArtifact:
    validate_mid_dev_scoring_plan_trace_binding(plan, traces)
    sample_by_id = _validate_plan_against_corpus(mid_dev_corpus, plan)
    _validate_calibration_identity(mid_dev_corpus, calibration_corpus)
    if int(plan.ngram_len) != int(adapter.ngram_len):
        raise ValueError("MidDev plan ngram_len does not match scoring adapter")

    length_calibrations = build_mid_dev_length_calibrations(calibration_corpus, adapter)
    by_length = {value.target_length: value for value in length_calibrations}
    detector_hashes = {value.detector_identity_hash for value in length_calibrations}
    if len(detector_hashes) != 1:
        raise ValueError("MidDev length calibrations mixed detector identities")
    detector_identity_hash = next(iter(detector_hashes))
    length_calibration_registry_hash = sha256_json(
        tuple(
            (value.target_length, value.binding_hash)
            for value in sorted(length_calibrations, key=lambda item: item.target_length)
        )
    )
    pristine = {
        sample_id: float(text_only_weighted_evidence(source, adapter).raw_score)
        for sample_id, source in sample_by_id.items()
    }
    cache: dict[tuple[str, str], float] = {}
    scored_rows: list[MidDevScoredPlanRow] = []
    for plan_row in plan.rows:
        source = sample_by_id[plan_row.sample_id]
        binding = by_length[plan_row.target_length]
        cache_key = (plan_row.sample_id, plan_row.transformed_text_hash)
        transformed_score = cache.get(cache_key)
        if transformed_score is None:
            transformed_score = _score_text(source, plan_row.transformed_text, tokenizer, adapter)
            cache[cache_key] = transformed_score
        scored_rows.append(
            MidDevScoredPlanRow.create(
                plan_row=plan_row,
                detector_identity_hash=detector_identity_hash,
                threshold_hash=binding.threshold_hash,
                threshold_value=binding.threshold_value,
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
    pristine_watermarked_detected_count = sum(
        pristine[sample_id] >= by_length[sample_by_id[sample_id].target_length].threshold_value
        for sample_id in positive_ids
    )
    pristine_control_detected_count = sum(
        pristine[sample_id] >= by_length[sample_by_id[sample_id].target_length].threshold_value
        for sample_id in control_ids
    )
    payload = {
        "algorithm_version": MID_DEV_SCORING_ARTIFACT_VERSION,
        "mid_dev_corpus_artifact_hash": mid_dev_corpus.artifact_hash,
        "source_profile_hash": mid_dev_corpus.source_profile_hash,
        "analysis_split_hash": mid_dev_corpus.analysis_split_hash,
        "plan_hash": plan.plan_hash,
        "trace_artifact_hash": traces.artifact_hash,
        "calibration_corpus_artifact_hash": calibration_corpus.artifact_hash,
        "calibration_source_profile_hash": calibration_corpus.source_profile_hash,
        "detector_identity_hash": detector_identity_hash,
        "length_calibration_registry_hash": length_calibration_registry_hash,
        "length_calibration_binding_hashes": tuple(
            value.binding_hash
            for value in sorted(length_calibrations, key=lambda item: item.target_length)
        ),
        "independent_source_group_count": 36,
        "independent_watermarked_source_count": len(positive_ids),
        "independent_control_source_count": len(control_ids),
        "pristine_watermarked_detected_count": pristine_watermarked_detected_count,
        "pristine_control_detected_count": pristine_control_detected_count,
        "row_hashes": tuple(row.scored_row_hash for row in row_tuple),
    }
    return MidDevScoringArtifact(
        mid_dev_corpus.artifact_hash,
        mid_dev_corpus.source_profile_hash,
        mid_dev_corpus.analysis_split_hash,
        plan.plan_hash,
        traces.artifact_hash,
        calibration_corpus.artifact_hash,
        calibration_corpus.source_profile_hash,
        detector_identity_hash,
        length_calibrations,
        length_calibration_registry_hash,
        36,
        len(positive_ids),
        len(control_ids),
        pristine_watermarked_detected_count,
        pristine_control_detected_count,
        row_tuple,
        sha256_json(payload),
    )
