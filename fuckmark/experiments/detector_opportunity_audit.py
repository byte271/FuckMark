from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_int, require_sha256
from ..corpus.sample import CorpusSample
from ..hashing import sha256_json
from ..public_eligibility import PUBLIC_ELIGIBILITY_ALGORITHM_VERSION, build_huggingface_public_eligibility


DETECTOR_OPPORTUNITY_AUDIT_VERSION = "mid-dev-detector-opportunity-audit-v1"
CALIBRATION_REGIME_DECISION_VERSION = "mid-dev-calibration-regime-decision-v1"
OPPORTUNITY_CV_LIMIT = 0.05
ELIGIBLE_IQR_OVERLAP_LIMIT = 0.10
MID_DEV_OPPORTUNITY_TARGET_LENGTHS = (128, 256)


class DetectorOpportunityAuditError(ValueError):
    pass


class CalibrationRegimeMode(str, Enum):
    NOMINAL_TARGET_LENGTH = "NOMINAL_TARGET_LENGTH"
    ELIGIBLE_OBSERVATION_BINS = "ELIGIBLE_OBSERVATION_BINS"


@dataclass(frozen=True, slots=True)
class CountDistribution:
    count: int
    minimum: int
    q25: float
    median: float
    q75: float
    maximum: int
    mean: float
    coefficient_of_variation: float

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class DetectorOpportunityAuditRow:
    sample_id: str
    prompt_id: str
    label: str
    requested_generation_length: int
    generation_continuation_token_count: int
    decoded_utf8_length: int
    decoded_codepoint_count: int
    text_only_token_count: int
    root_candidate_observation_count: int
    root_valid_eligible_observation_count: int
    repeated_context_masked_count: int
    eos_masked_count: int
    tokenizer_round_trip_ok: bool
    model_tokenizer_identity_hash: str
    model_revision: str
    tokenizer_revision: str
    watermark_config_hash: str
    watermark_condition_hash: str
    public_eligibility_algorithm_version: str
    public_eligibility_mask_hash: str
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        require_sha256("watermark_condition_hash", self.watermark_condition_hash)
        require_sha256("public_eligibility_mask_hash", self.public_eligibility_mask_hash)
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"}


@dataclass(frozen=True, slots=True)
class OpportunityLengthSummary:
    nominal_target_length: int
    text_only_tokens: CountDistribution
    candidate_observations: CountDistribution
    eligible_observations: CountDistribution
    repeated_context_masked: CountDistribution
    eos_masked: CountDistribution
    decoded_utf8_length: CountDistribution
    tokenizer_round_trip_failures: int
    summary_hash: str

    def __post_init__(self) -> None:
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("summary hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "nominal_target_length": self.nominal_target_length,
            "text_only_tokens": self.text_only_tokens.payload(),
            "candidate_observations": self.candidate_observations.payload(),
            "eligible_observations": self.eligible_observations.payload(),
            "repeated_context_masked": self.repeated_context_masked.payload(),
            "eos_masked": self.eos_masked.payload(),
            "decoded_utf8_length": self.decoded_utf8_length.payload(),
            "tokenizer_round_trip_failures": self.tokenizer_round_trip_failures,
        }


@dataclass(frozen=True, slots=True)
class DetectorOpportunityAuditArtifact:
    algorithm_version: str
    ngram_len: int
    context_history_size: int
    rows: tuple[DetectorOpportunityAuditRow, ...]
    summaries: tuple[OpportunityLengthSummary, ...]
    model_tokenizer_identity_hash: str
    watermark_config_hash: str
    watermark_condition_hash: str
    artifact_hash: str

    @property
    def tokenizer_round_trip_all_ok(self) -> bool:
        return all(row.tokenizer_round_trip_ok for row in self.rows)

    def __post_init__(self) -> None:
        if self.algorithm_version != DETECTOR_OPPORTUNITY_AUDIT_VERSION:
            raise ValueError("unsupported opportunity audit version")
        require_int("ngram_len", self.ngram_len)
        require_int("context_history_size", self.context_history_size)
        if tuple(summary.nominal_target_length for summary in self.summaries) != MID_DEV_OPPORTUNITY_TARGET_LENGTHS:
            raise DetectorOpportunityAuditError("opportunity audit requires 128 and 256 strata")
        for name in ("model_tokenizer_identity_hash", "watermark_config_hash", "watermark_condition_hash", "artifact_hash"):
            require_sha256(name, getattr(self, name))
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("opportunity audit hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in self.rows),
            "summaries": tuple(summary.payload() | {"summary_hash": summary.summary_hash} for summary in self.summaries),
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "watermark_config_hash": self.watermark_config_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
        }


@dataclass(frozen=True, slots=True)
class CalibrationRegimeDecision:
    algorithm_version: str
    opportunity_audit_hash: str
    mode: CalibrationRegimeMode
    coefficient_of_variation_limit: float
    eligible_iqr_overlap_limit: float
    observed_eligible_iqr_overlap: float
    nominal_strata_pass: bool
    eligible_bin_upper_bounds: tuple[int, ...]
    decision_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CALIBRATION_REGIME_DECISION_VERSION:
            raise ValueError("unsupported regime decision version")
        require_sha256("opportunity_audit_hash", self.opportunity_audit_hash)
        require_sha256("decision_hash", self.decision_hash)
        if tuple(sorted(set(self.eligible_bin_upper_bounds))) != self.eligible_bin_upper_bounds:
            raise ValueError("eligible bin bounds must be unique and sorted")
        if self.decision_hash != sha256_json(self.payload()):
            raise ValueError("regime decision hash mismatch")

    def regime_id_for(self, target_length: int, eligible_observation_count: int) -> str:
        require_int("target_length", target_length)
        require_int("eligible_observation_count", eligible_observation_count)
        if self.mode is CalibrationRegimeMode.NOMINAL_TARGET_LENGTH:
            if target_length not in MID_DEV_OPPORTUNITY_TARGET_LENGTHS:
                raise DetectorOpportunityAuditError("unsupported nominal calibration target")
            return f"nominal-{target_length}"
        return f"eligible-{bisect_left(self.eligible_bin_upper_bounds, eligible_observation_count):02d}"

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "opportunity_audit_hash": self.opportunity_audit_hash,
            "mode": self.mode.value,
            "coefficient_of_variation_limit": self.coefficient_of_variation_limit,
            "eligible_iqr_overlap_limit": self.eligible_iqr_overlap_limit,
            "observed_eligible_iqr_overlap": self.observed_eligible_iqr_overlap,
            "nominal_strata_pass": self.nominal_strata_pass,
            "eligible_bin_upper_bounds": self.eligible_bin_upper_bounds,
        }


def _quantile(values: Sequence[int], probability: float) -> float:
    ordered = tuple(sorted(values))
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    fraction = position - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * fraction)


def _distribution(values: Sequence[int]) -> CountDistribution:
    if not values:
        raise DetectorOpportunityAuditError("empty opportunity distribution")
    values = tuple(int(value) for value in values)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    cv = 0.0 if mean == 0.0 else math.sqrt(variance) / mean
    return CountDistribution(len(values), min(values), _quantile(values, .25), _quantile(values, .5), _quantile(values, .75), max(values), mean, cv)


def _summary(target_length: int, rows: Sequence[DetectorOpportunityAuditRow]) -> OpportunityLengthSummary:
    selected = tuple(row for row in rows if row.requested_generation_length == target_length)
    if not selected:
        raise DetectorOpportunityAuditError(f"missing nominal target {target_length}")
    payload = {
        "nominal_target_length": target_length,
        "text_only_tokens": _distribution(tuple(row.text_only_token_count for row in selected)).payload(),
        "candidate_observations": _distribution(tuple(row.root_candidate_observation_count for row in selected)).payload(),
        "eligible_observations": _distribution(tuple(row.root_valid_eligible_observation_count for row in selected)).payload(),
        "repeated_context_masked": _distribution(tuple(row.repeated_context_masked_count for row in selected)).payload(),
        "eos_masked": _distribution(tuple(row.eos_masked_count for row in selected)).payload(),
        "decoded_utf8_length": _distribution(tuple(row.decoded_utf8_length for row in selected)).payload(),
        "tokenizer_round_trip_failures": sum(not row.tokenizer_round_trip_ok for row in selected),
    }
    return OpportunityLengthSummary(
        target_length,
        _distribution(tuple(row.text_only_token_count for row in selected)),
        _distribution(tuple(row.root_candidate_observation_count for row in selected)),
        _distribution(tuple(row.root_valid_eligible_observation_count for row in selected)),
        _distribution(tuple(row.repeated_context_masked_count for row in selected)),
        _distribution(tuple(row.eos_masked_count for row in selected)),
        _distribution(tuple(row.decoded_utf8_length for row in selected)),
        payload["tokenizer_round_trip_failures"],
        sha256_json(payload),
    )


def build_detector_opportunity_audit_row(
    sample: CorpusSample, *, ngram_len: int, context_history_size: int,
    retokenize: Callable[[str], Sequence[int]],
) -> DetectorOpportunityAuditRow:
    if not isinstance(sample, CorpusSample):
        raise TypeError("sample must be CorpusSample")
    recorded = tuple(sample.text_only_tokens.token_ids)
    replayed = tuple(int(value) for value in retokenize(sample.text))
    mask = build_huggingface_public_eligibility(recorded, sample.model.eos_token_id, ngram_len, context_history_size)
    payload = {
        "sample_id": sample.sample_id,
        "prompt_id": sample.prompt_id,
        "label": sample.label.value,
        "requested_generation_length": sample.target_length,
        "generation_continuation_token_count": len(sample.generation_tokens.continuation_token_ids),
        "decoded_utf8_length": len(sample.text.encode("utf-8")),
        "decoded_codepoint_count": len(sample.text),
        "text_only_token_count": len(recorded),
        "root_candidate_observation_count": mask.observation_count,
        "root_valid_eligible_observation_count": mask.valid_count,
        "repeated_context_masked_count": mask.repeated_count,
        "eos_masked_count": mask.post_eos_count,
        "tokenizer_round_trip_ok": replayed == recorded,
        "model_tokenizer_identity_hash": sample.model.identity_hash,
        "model_revision": sample.model.model_revision,
        "tokenizer_revision": sample.model.tokenizer_revision,
        "watermark_config_hash": sample.watermark.watermark_config_hash,
        "watermark_condition_hash": sample.watermark.condition_hash,
        "public_eligibility_algorithm_version": PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        "public_eligibility_mask_hash": mask.mask_hash,
    }
    return DetectorOpportunityAuditRow(**payload, row_hash=sha256_json(payload))


def build_detector_opportunity_audit_artifact(
    samples: Sequence[CorpusSample], *, ngram_len: int, context_history_size: int,
    retokenize: Callable[[str], Sequence[int]],
) -> DetectorOpportunityAuditArtifact:
    rows = tuple(sorted((build_detector_opportunity_audit_row(sample, ngram_len=ngram_len, context_history_size=context_history_size, retokenize=retokenize) for sample in samples), key=lambda row: row.sample_id))
    if not rows:
        raise DetectorOpportunityAuditError("opportunity audit requires samples")
    if {row.requested_generation_length for row in rows} != set(MID_DEV_OPPORTUNITY_TARGET_LENGTHS):
        raise DetectorOpportunityAuditError("opportunity audit requires both 128 and 256 nominal strata")
    identities = {row.model_tokenizer_identity_hash for row in rows}
    configs = {row.watermark_config_hash for row in rows}
    conditions = {row.watermark_condition_hash for row in rows}
    if len(identities) != 1 or len(configs) != 1 or len(conditions) != 1:
        raise DetectorOpportunityAuditError("opportunity audit requires one immutable model/tokenizer/watermark identity")
    summaries = tuple(_summary(target, rows) for target in MID_DEV_OPPORTUNITY_TARGET_LENGTHS)
    payload = {
        "algorithm_version": DETECTOR_OPPORTUNITY_AUDIT_VERSION,
        "ngram_len": ngram_len,
        "context_history_size": context_history_size,
        "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in rows),
        "summaries": tuple(summary.payload() | {"summary_hash": summary.summary_hash} for summary in summaries),
        "model_tokenizer_identity_hash": next(iter(identities)),
        "watermark_config_hash": next(iter(configs)),
        "watermark_condition_hash": next(iter(conditions)),
    }
    return DetectorOpportunityAuditArtifact(
        DETECTOR_OPPORTUNITY_AUDIT_VERSION, ngram_len, context_history_size, rows, summaries,
        payload["model_tokenizer_identity_hash"], payload["watermark_config_hash"], payload["watermark_condition_hash"],
        sha256_json(payload),
    )


def _iqr_overlap_ratio(left: CountDistribution, right: CountDistribution) -> float:
    overlap = max(0.0, min(left.q75, right.q75) - max(left.q25, right.q25))
    width = min(left.q75 - left.q25, right.q75 - right.q25)
    if width > 0.0:
        return min(1.0, overlap / width)
    if left.q25 == left.q75 and right.q25 <= left.q25 <= right.q75:
        return 1.0
    if right.q25 == right.q75 and left.q25 <= right.q25 <= left.q75:
        return 1.0
    return 0.0


def _minimal_eligible_bin_bounds(rows: Sequence[DetectorOpportunityAuditRow]) -> tuple[int, ...]:
    by_value: dict[int, list[DetectorOpportunityAuditRow]] = {}
    for row in rows:
        by_value.setdefault(row.root_valid_eligible_observation_count, []).append(row)
    values = tuple(sorted(by_value))
    groups = tuple(tuple(by_value[value]) for value in values)
    size = len(values)
    feasible = [[False] * size for _ in range(size)]
    for start in range(size):
        current: list[DetectorOpportunityAuditRow] = []
        for end in range(start, size):
            current.extend(groups[end])
            text_cv = _distribution(tuple(row.text_only_token_count for row in current)).coefficient_of_variation
            eligible_cv = _distribution(tuple(row.root_valid_eligible_observation_count for row in current)).coefficient_of_variation
            feasible[start][end] = text_cv <= OPPORTUNITY_CV_LIMIT and eligible_cv <= OPPORTUNITY_CV_LIMIT
    best: list[tuple[int, tuple[int, ...]] | None] = [None] * (size + 1)
    best[0] = (0, ())
    for end in range(1, size + 1):
        candidates = [
            (best[start][0] + 1, best[start][1] + (end,))
            for start in range(end) if best[start] is not None and feasible[start][end - 1]
        ]
        best[end] = min(candidates) if candidates else None
    if best[size] is None:
        raise DetectorOpportunityAuditError("no deterministic opportunity partition satisfies frozen CV limit")
    return tuple((values[end - 1] + values[end]) // 2 for end in best[size][1][:-1])


def freeze_calibration_regime_decision(audit: DetectorOpportunityAuditArtifact) -> CalibrationRegimeDecision:
    if not audit.tokenizer_round_trip_all_ok:
        raise DetectorOpportunityAuditError("cannot freeze regimes with tokenizer round-trip failures")
    left, right = audit.summaries
    overlap = _iqr_overlap_ratio(left.eligible_observations, right.eligible_observations)
    concentrated = all(
        summary.text_only_tokens.coefficient_of_variation <= OPPORTUNITY_CV_LIMIT
        and summary.eligible_observations.coefficient_of_variation <= OPPORTUNITY_CV_LIMIT
        for summary in audit.summaries
    )
    nominal = concentrated and overlap <= ELIGIBLE_IQR_OVERLAP_LIMIT
    mode = CalibrationRegimeMode.NOMINAL_TARGET_LENGTH if nominal else CalibrationRegimeMode.ELIGIBLE_OBSERVATION_BINS
    bounds = () if nominal else _minimal_eligible_bin_bounds(audit.rows)
    payload = {
        "algorithm_version": CALIBRATION_REGIME_DECISION_VERSION,
        "opportunity_audit_hash": audit.artifact_hash,
        "mode": mode.value,
        "coefficient_of_variation_limit": OPPORTUNITY_CV_LIMIT,
        "eligible_iqr_overlap_limit": ELIGIBLE_IQR_OVERLAP_LIMIT,
        "observed_eligible_iqr_overlap": overlap,
        "nominal_strata_pass": nominal,
        "eligible_bin_upper_bounds": bounds,
    }
    return CalibrationRegimeDecision(
        CALIBRATION_REGIME_DECISION_VERSION, audit.artifact_hash, mode, OPPORTUNITY_CV_LIMIT,
        ELIGIBLE_IQR_OVERLAP_LIMIT, overlap, nominal, bounds, sha256_json(payload),
    )
