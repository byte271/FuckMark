from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..public_eligibility import PUBLIC_ELIGIBILITY_ALGORITHM_VERSION, build_huggingface_public_eligibility
from .tiny_dev_residual_replay import (
    FROZEN_BASELINE_SHA,
    FROZEN_TINY_DEV_CORPUS_HASH,
    FROZEN_TINY_DEV_EVIDENCE_HASH,
)


TINY_DEV_CALIBRATION_OPPORTUNITY_AUDIT_VERSION = "tiny-dev-calibration-opportunity-audit-v1"
SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM = 1000
PREFERRED_DEVELOPMENT_CALIBRATION_COUNT = 2000
OPPORTUNITY_CV_LIMIT = 0.05


@dataclass(frozen=True, slots=True)
class OpportunityDistribution:
    count: int
    minimum: int
    q25: float
    median: float
    q75: float
    maximum: int
    mean: float
    population_sd: float
    coefficient_of_variation: float

    def __post_init__(self) -> None:
        for name in ("count", "minimum", "maximum"):
            require_int(name, getattr(self, name))
        if self.count <= 0 or self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("invalid opportunity distribution counts")
        for name in ("q25", "median", "q75", "mean", "population_sd", "coefficient_of_variation"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if not self.minimum <= self.q25 <= self.median <= self.q75 <= self.maximum:
            raise ValueError("invalid opportunity distribution quantiles")
        if self.population_sd < 0.0 or self.coefficient_of_variation < 0.0:
            raise ValueError("invalid opportunity distribution spread")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class TinyDevCalibrationOpportunityRow:
    sample_id: str
    text_only_token_count: int
    candidate_observation_count: int
    valid_observation_count: int
    repeated_context_masked_count: int
    eos_masked_count: int
    public_eligibility_mask_hash: str
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        for name in (
            "text_only_token_count",
            "candidate_observation_count",
            "valid_observation_count",
            "repeated_context_masked_count",
            "eos_masked_count",
        ):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError("opportunity row counts must be non-negative")
        if self.valid_observation_count > self.candidate_observation_count:
            raise ValueError("valid observations exceed candidates")
        require_sha256("public_eligibility_mask_hash", self.public_eligibility_mask_hash)
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match TinyDev calibration opportunity row")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"}


@dataclass(frozen=True, slots=True)
class TinyDevCalibrationOpportunityAudit:
    algorithm_version: str
    source_code_commit: str
    tiny_dev_corpus_hash: str
    tiny_dev_evidence_hash: str
    public_eligibility_algorithm_version: str
    target_fpr: float
    calibration_negative_count: int
    observed_calibration_false_positive_count: int
    selected_threshold: float
    exact_interval_lower: float
    exact_interval_upper: float
    serious_development_minimum: int
    preferred_development_count: int
    opportunity_cv_limit: float
    token_counts: OpportunityDistribution
    candidate_observations: OpportunityDistribution
    valid_observations: OpportunityDistribution
    repeated_context_masked: OpportunityDistribution
    eos_masked: OpportunityDistribution
    nominal_length_proxy_pass: bool
    calibration_resolution_pass: bool
    rows: tuple[TinyDevCalibrationOpportunityRow, ...]
    audit_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TINY_DEV_CALIBRATION_OPPORTUNITY_AUDIT_VERSION:
            raise ValueError("unsupported TinyDev calibration opportunity audit version")
        if self.source_code_commit != FROZEN_BASELINE_SHA:
            raise ValueError("calibration opportunity audit must bind frozen #47 baseline")
        if self.tiny_dev_corpus_hash != FROZEN_TINY_DEV_CORPUS_HASH:
            raise ValueError("TinyDev corpus hash drifted")
        if self.tiny_dev_evidence_hash != FROZEN_TINY_DEV_EVIDENCE_HASH:
            raise ValueError("TinyDev evidence hash drifted")
        if self.public_eligibility_algorithm_version != PUBLIC_ELIGIBILITY_ALGORITHM_VERSION:
            raise ValueError("public eligibility algorithm version drifted")
        require_int("calibration_negative_count", self.calibration_negative_count)
        require_int("observed_calibration_false_positive_count", self.observed_calibration_false_positive_count)
        require_int("serious_development_minimum", self.serious_development_minimum)
        require_int("preferred_development_count", self.preferred_development_count)
        if self.calibration_negative_count != 100 or self.observed_calibration_false_positive_count != 1:
            raise ValueError("frozen TinyDev calibration must remain 1/100")
        if self.serious_development_minimum != SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM:
            raise ValueError("serious calibration minimum drifted")
        if self.preferred_development_count != PREFERRED_DEVELOPMENT_CALIBRATION_COUNT:
            raise ValueError("preferred calibration count drifted")
        if self.opportunity_cv_limit != OPPORTUNITY_CV_LIMIT:
            raise ValueError("opportunity CV limit drifted")
        for name in ("target_fpr", "selected_threshold", "exact_interval_lower", "exact_interval_upper"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if self.target_fpr != 0.01:
            raise ValueError("TinyDev target FPR drifted")
        if not 0.0 <= self.exact_interval_lower <= self.target_fpr <= self.exact_interval_upper <= 1.0:
            raise ValueError("invalid exact calibration interval")
        if type(self.nominal_length_proxy_pass) is not bool or type(self.calibration_resolution_pass) is not bool:
            raise TypeError("audit pass flags must be bool")
        if self.nominal_length_proxy_pass != (self.valid_observations.coefficient_of_variation <= OPPORTUNITY_CV_LIMIT):
            raise ValueError("nominal length proxy flag does not match valid-opportunity CV")
        if self.calibration_resolution_pass != (self.calibration_negative_count >= SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM):
            raise ValueError("calibration resolution flag does not match frozen minimum")
        if len(self.rows) != self.calibration_negative_count:
            raise ValueError("calibration opportunity rows do not match calibration N")
        if tuple(sorted(self.rows, key=lambda row: row.sample_id)) != self.rows:
            raise ValueError("calibration opportunity rows must be canonically ordered")
        if len({row.sample_id for row in self.rows}) != len(self.rows):
            raise ValueError("calibration opportunity sample IDs must be unique")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self.payload()):
            raise ValueError("audit_hash does not match TinyDev calibration opportunity audit")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_code_commit": self.source_code_commit,
            "tiny_dev_corpus_hash": self.tiny_dev_corpus_hash,
            "tiny_dev_evidence_hash": self.tiny_dev_evidence_hash,
            "public_eligibility_algorithm_version": self.public_eligibility_algorithm_version,
            "target_fpr": self.target_fpr,
            "calibration_negative_count": self.calibration_negative_count,
            "observed_calibration_false_positive_count": self.observed_calibration_false_positive_count,
            "selected_threshold": self.selected_threshold,
            "exact_interval_lower": self.exact_interval_lower,
            "exact_interval_upper": self.exact_interval_upper,
            "serious_development_minimum": self.serious_development_minimum,
            "preferred_development_count": self.preferred_development_count,
            "opportunity_cv_limit": self.opportunity_cv_limit,
            "token_counts": self.token_counts.payload(),
            "candidate_observations": self.candidate_observations.payload(),
            "valid_observations": self.valid_observations.payload(),
            "repeated_context_masked": self.repeated_context_masked.payload(),
            "eos_masked": self.eos_masked.payload(),
            "nominal_length_proxy_pass": self.nominal_length_proxy_pass,
            "calibration_resolution_pass": self.calibration_resolution_pass,
            "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in self.rows),
        }


def _quantile(values: Sequence[int], probability: float) -> float:
    ordered = tuple(sorted(values))
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _distribution(values: Sequence[int]) -> OpportunityDistribution:
    if not values:
        raise ValueError("opportunity distribution cannot be empty")
    materialized = tuple(int(value) for value in values)
    mean = sum(materialized) / len(materialized)
    variance = sum((value - mean) ** 2 for value in materialized) / len(materialized)
    sd = math.sqrt(variance)
    return OpportunityDistribution(
        len(materialized),
        min(materialized),
        _quantile(materialized, 0.25),
        _quantile(materialized, 0.50),
        _quantile(materialized, 0.75),
        max(materialized),
        mean,
        sd,
        0.0 if mean == 0.0 else sd / mean,
    )


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _sequence(name: str, value: object) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence")
    return value


def audit_frozen_tiny_dev_calibration_opportunity(
    corpus: Mapping[str, object],
    evidence: Mapping[str, object],
    *,
    ngram_len: int = 5,
    context_history_size: int = 1024,
) -> TinyDevCalibrationOpportunityAudit:
    corpus = _mapping("corpus", corpus)
    evidence = _mapping("evidence", evidence)
    if corpus.get("artifact_hash") != FROZEN_TINY_DEV_CORPUS_HASH:
        raise ValueError("TinyDev corpus hash does not match frozen artifact")
    if evidence.get("artifact_hash") != FROZEN_TINY_DEV_EVIDENCE_HASH:
        raise ValueError("TinyDev evidence hash does not match frozen artifact")
    require_int("ngram_len", ngram_len)
    require_int("context_history_size", context_history_size)
    manifest = _mapping("corpus.manifest", corpus.get("manifest"))
    samples = _sequence("corpus.manifest.samples", manifest.get("samples"))
    rows: list[TinyDevCalibrationOpportunityRow] = []
    for value in samples:
        sample = _mapping("sample", value)
        if sample.get("split") != "threshold_calibration" or sample.get("label") != "unwatermarked":
            continue
        sample_id = sample.get("sample_id")
        if not isinstance(sample_id, str):
            raise TypeError("calibration sample_id must be a string")
        text_track = _mapping("sample.text_only_tokens", sample.get("text_only_tokens"))
        token_ids = tuple(int(token) for token in _sequence("sample token ids", text_track.get("token_ids")))
        model = _mapping("sample.model", sample.get("model"))
        eos_token_id = model.get("eos_token_id")
        require_int("eos_token_id", eos_token_id)
        mask = build_huggingface_public_eligibility(
            token_ids,
            eos_token_id,
            ngram_len,
            context_history_size,
        )
        payload = {
            "sample_id": sample_id,
            "text_only_token_count": len(token_ids),
            "candidate_observation_count": mask.observation_count,
            "valid_observation_count": mask.valid_count,
            "repeated_context_masked_count": mask.repeated_count,
            "eos_masked_count": mask.post_eos_count,
            "public_eligibility_mask_hash": mask.mask_hash,
        }
        rows.append(TinyDevCalibrationOpportunityRow(**payload, row_hash=sha256_json(payload)))
    canonical_rows = tuple(sorted(rows, key=lambda row: row.sample_id))
    if len(canonical_rows) != 100:
        raise ValueError("frozen TinyDev calibration opportunity audit requires 100 negatives")
    interval = _mapping("calibration_fpr_interval", evidence.get("calibration_fpr_interval"))
    target_fpr = float(evidence.get("primary_target_fpr"))
    calibration_n = int(evidence.get("calibration_negative_count"))
    achieved = float(evidence.get("achieved_calibration_fpr"))
    false_positives_float = calibration_n * achieved
    false_positives = int(round(false_positives_float))
    if abs(false_positives_float - false_positives) > 1e-12:
        raise ValueError("calibration achieved FPR does not correspond to an integer false-positive count")
    token_counts = _distribution(tuple(row.text_only_token_count for row in canonical_rows))
    candidates = _distribution(tuple(row.candidate_observation_count for row in canonical_rows))
    valid = _distribution(tuple(row.valid_observation_count for row in canonical_rows))
    repeated = _distribution(tuple(row.repeated_context_masked_count for row in canonical_rows))
    eos = _distribution(tuple(row.eos_masked_count for row in canonical_rows))
    payload = {
        "algorithm_version": TINY_DEV_CALIBRATION_OPPORTUNITY_AUDIT_VERSION,
        "source_code_commit": FROZEN_BASELINE_SHA,
        "tiny_dev_corpus_hash": FROZEN_TINY_DEV_CORPUS_HASH,
        "tiny_dev_evidence_hash": FROZEN_TINY_DEV_EVIDENCE_HASH,
        "public_eligibility_algorithm_version": PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        "target_fpr": target_fpr,
        "calibration_negative_count": calibration_n,
        "observed_calibration_false_positive_count": false_positives,
        "selected_threshold": float(evidence.get("primary_threshold_value")),
        "exact_interval_lower": float(interval.get("lower")),
        "exact_interval_upper": float(interval.get("upper")),
        "serious_development_minimum": SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM,
        "preferred_development_count": PREFERRED_DEVELOPMENT_CALIBRATION_COUNT,
        "opportunity_cv_limit": OPPORTUNITY_CV_LIMIT,
        "token_counts": token_counts.payload(),
        "candidate_observations": candidates.payload(),
        "valid_observations": valid.payload(),
        "repeated_context_masked": repeated.payload(),
        "eos_masked": eos.payload(),
        "nominal_length_proxy_pass": valid.coefficient_of_variation <= OPPORTUNITY_CV_LIMIT,
        "calibration_resolution_pass": calibration_n >= SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM,
        "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in canonical_rows),
    }
    return TinyDevCalibrationOpportunityAudit(
        TINY_DEV_CALIBRATION_OPPORTUNITY_AUDIT_VERSION,
        FROZEN_BASELINE_SHA,
        FROZEN_TINY_DEV_CORPUS_HASH,
        FROZEN_TINY_DEV_EVIDENCE_HASH,
        PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        target_fpr,
        calibration_n,
        false_positives,
        float(evidence.get("primary_threshold_value")),
        float(interval.get("lower")),
        float(interval.get("upper")),
        SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM,
        PREFERRED_DEVELOPMENT_CALIBRATION_COUNT,
        OPPORTUNITY_CV_LIMIT,
        token_counts,
        candidates,
        valid,
        repeated,
        eos,
        valid.coefficient_of_variation <= OPPORTUNITY_CV_LIMIT,
        calibration_n >= SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM,
        canonical_rows,
        sha256_json(payload),
    )
