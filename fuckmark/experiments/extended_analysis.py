from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, KeySplit, TARGET_LENGTHS
from ..detectors import DetectorFamily
from ..hashing import sha256_json
from .registry import DevelopmentExperimentId, default_development_experiment_registry
from .transform_analysis import DevelopmentClaimStatus, DevelopmentTransformRow


EXTENDED_ANALYSIS_ROW_VERSION = "extended-analysis-row-v1"
EXTENDED_ANALYSIS_ALGORITHM_VERSION = "extended-development-analysis-v1"
_REQUIRED_DETECTOR_FAMILIES = frozenset(
    {DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN, DetectorFamily.BAYESIAN}
)


class ExtendedAnalysisInputError(ValueError):
    pass


def _ratio(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


def _finite(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _depth_values(name: str, values: tuple[float, ...]) -> tuple[float, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{name} must be a non-empty tuple")
    return tuple(_ratio(f"{name} value", value) for value in values)


@dataclass(frozen=True, slots=True)
class ExtendedAnalysisRow:
    algorithm_version: str
    base_row_hash: str
    source_sample_id: str
    source_text_hash: str
    transformed_text_hash: str
    key_split: KeySplit
    key_id: str
    model_tokenizer_hash: str
    domain: CorpusDomain
    target_length: int
    rule_family: str
    rule_id: str
    schedule_policy: str
    budget: int
    budget_unit: str
    realized_density: float
    detector_family: DetectorFamily
    detector_identity_hash: str
    standardized_margin_drop: float
    token_edit_count: int
    source_token_count: int
    observation_replacement_ratio: float
    fidelity_passed: bool
    hard_invariant_passed: bool
    pristine_depth_means: tuple[float, ...]
    transformed_depth_means: tuple[float, ...]
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != EXTENDED_ANALYSIS_ROW_VERSION:
            raise ValueError("unsupported extended analysis row version")
        for name, value in (
            ("base_row_hash", self.base_row_hash),
            ("source_text_hash", self.source_text_hash),
            ("transformed_text_hash", self.transformed_text_hash),
            ("model_tokenizer_hash", self.model_tokenizer_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("row_hash", self.row_hash),
        ):
            require_sha256(name, value)
        for name, value in (
            ("source_sample_id", self.source_sample_id),
            ("key_id", self.key_id),
            ("rule_family", self.rule_family),
            ("rule_id", self.rule_id),
            ("schedule_policy", self.schedule_policy),
            ("budget_unit", self.budget_unit),
        ):
            require_clean_string(name, value)
        if not isinstance(self.key_split, KeySplit):
            raise TypeError("key_split must be a KeySplit")
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("target_length", self.target_length)
        if self.target_length not in TARGET_LENGTHS:
            raise ValueError("target_length must be one of the frozen target lengths")
        require_int("budget", self.budget)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        object.__setattr__(self, "realized_density", _ratio("realized_density", self.realized_density))
        if not isinstance(self.detector_family, DetectorFamily):
            raise TypeError("detector_family must be a DetectorFamily")
        object.__setattr__(
            self,
            "standardized_margin_drop",
            _finite("standardized_margin_drop", self.standardized_margin_drop),
        )
        require_int("token_edit_count", self.token_edit_count)
        require_int("source_token_count", self.source_token_count)
        if self.token_edit_count < 0 or self.source_token_count <= 0:
            raise ValueError("token edit geometry requires non-negative edits and a positive denominator")
        if self.token_edit_count > self.source_token_count:
            raise ValueError("token_edit_count cannot exceed source_token_count")
        object.__setattr__(
            self,
            "observation_replacement_ratio",
            _ratio("observation_replacement_ratio", self.observation_replacement_ratio),
        )
        require_bool("fidelity_passed", self.fidelity_passed)
        require_bool("hard_invariant_passed", self.hard_invariant_passed)
        pristine = _depth_values("pristine_depth_means", self.pristine_depth_means)
        transformed = _depth_values("transformed_depth_means", self.transformed_depth_means)
        if len(pristine) != len(transformed):
            raise ValueError("pristine and transformed depth vectors must have the same length")
        object.__setattr__(self, "pristine_depth_means", pristine)
        object.__setattr__(self, "transformed_depth_means", transformed)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match extended analysis row")

    @property
    def token_edit_ratio(self) -> float:
        return self.token_edit_count / self.source_token_count

    @property
    def depth_drift(self) -> tuple[float, ...]:
        return tuple(before - after for before, after in zip(self.pristine_depth_means, self.transformed_depth_means))

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "base_row_hash": self.base_row_hash,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "key_split": self.key_split.value,
            "key_id": self.key_id,
            "model_tokenizer_hash": self.model_tokenizer_hash,
            "domain": self.domain.value,
            "target_length": self.target_length,
            "rule_family": self.rule_family,
            "rule_id": self.rule_id,
            "schedule_policy": self.schedule_policy,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "realized_density": self.realized_density,
            "detector_family": self.detector_family.value,
            "detector_identity_hash": self.detector_identity_hash,
            "standardized_margin_drop": self.standardized_margin_drop,
            "token_edit_count": self.token_edit_count,
            "source_token_count": self.source_token_count,
            "observation_replacement_ratio": self.observation_replacement_ratio,
            "fidelity_passed": self.fidelity_passed,
            "hard_invariant_passed": self.hard_invariant_passed,
            "pristine_depth_means": self.pristine_depth_means,
            "transformed_depth_means": self.transformed_depth_means,
        }

    @classmethod
    def create(
        cls,
        base_row: DevelopmentTransformRow,
        *,
        key_id: str,
        model_tokenizer_hash: str,
        domain: CorpusDomain,
        target_length: int,
        rule_family: str,
        rule_id: str,
        realized_density: float,
        detector_family: DetectorFamily,
        standardized_margin_drop: float,
        token_edit_count: int,
        source_token_count: int,
        fidelity_passed: bool,
        hard_invariant_passed: bool,
        pristine_depth_means: tuple[float, ...],
        transformed_depth_means: tuple[float, ...],
    ) -> ExtendedAnalysisRow:
        if not isinstance(base_row, DevelopmentTransformRow):
            raise TypeError("base_row must be a DevelopmentTransformRow")
        payload = {
            "algorithm_version": EXTENDED_ANALYSIS_ROW_VERSION,
            "base_row_hash": base_row.row_hash,
            "source_sample_id": base_row.source_sample_id,
            "source_text_hash": base_row.source_text_hash,
            "transformed_text_hash": base_row.transformed_text_hash,
            "key_split": base_row.key_split.value,
            "key_id": key_id,
            "model_tokenizer_hash": model_tokenizer_hash,
            "domain": domain.value,
            "target_length": target_length,
            "rule_family": rule_family,
            "rule_id": rule_id,
            "schedule_policy": base_row.schedule_policy.value,
            "budget": base_row.budget,
            "budget_unit": base_row.budget_unit,
            "realized_density": float(realized_density),
            "detector_family": detector_family.value,
            "detector_identity_hash": base_row.detector_identity_hash,
            "standardized_margin_drop": float(standardized_margin_drop),
            "token_edit_count": token_edit_count,
            "source_token_count": source_token_count,
            "observation_replacement_ratio": base_row.observation_replacement_ratio,
            "fidelity_passed": fidelity_passed,
            "hard_invariant_passed": hard_invariant_passed,
            "pristine_depth_means": tuple(float(value) for value in pristine_depth_means),
            "transformed_depth_means": tuple(float(value) for value in transformed_depth_means),
        }
        return cls(
            EXTENDED_ANALYSIS_ROW_VERSION,
            base_row.row_hash,
            base_row.source_sample_id,
            base_row.source_text_hash,
            base_row.transformed_text_hash,
            base_row.key_split,
            key_id,
            model_tokenizer_hash,
            domain,
            target_length,
            rule_family,
            rule_id,
            base_row.schedule_policy.value,
            base_row.budget,
            base_row.budget_unit,
            float(realized_density),
            detector_family,
            base_row.detector_identity_hash,
            float(standardized_margin_drop),
            token_edit_count,
            source_token_count,
            base_row.observation_replacement_ratio,
            fidelity_passed,
            hard_invariant_passed,
            tuple(float(value) for value in pristine_depth_means),
            tuple(float(value) for value in transformed_depth_means),
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class ExtendedStratumSummary:
    stratum_key: tuple[str, ...]
    sample_count: int
    mean_token_edit_ratio: float
    mean_observation_replacement_ratio: float
    mean_standardized_margin_drop: float
    fidelity_pass_rate: float
    mean_depth_drift: tuple[float, ...]
    depth_covariance: tuple[tuple[float, ...], ...]
    summary_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.stratum_key, tuple) or not self.stratum_key:
            raise ValueError("stratum_key must be a non-empty tuple")
        for value in self.stratum_key:
            require_clean_string("stratum key value", value)
        require_int("sample_count", self.sample_count)
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        object.__setattr__(self, "mean_token_edit_ratio", _ratio("mean_token_edit_ratio", self.mean_token_edit_ratio))
        object.__setattr__(
            self,
            "mean_observation_replacement_ratio",
            _ratio("mean_observation_replacement_ratio", self.mean_observation_replacement_ratio),
        )
        object.__setattr__(
            self,
            "mean_standardized_margin_drop",
            _finite("mean_standardized_margin_drop", self.mean_standardized_margin_drop),
        )
        object.__setattr__(self, "fidelity_pass_rate", _ratio("fidelity_pass_rate", self.fidelity_pass_rate))
        if not isinstance(self.mean_depth_drift, tuple) or not self.mean_depth_drift:
            raise ValueError("mean_depth_drift must be a non-empty tuple")
        drift = tuple(_finite("mean_depth_drift value", value) for value in self.mean_depth_drift)
        object.__setattr__(self, "mean_depth_drift", drift)
        if not isinstance(self.depth_covariance, tuple) or len(self.depth_covariance) != len(drift):
            raise ValueError("depth_covariance shape must match depth")
        covariance = []
        for row in self.depth_covariance:
            if not isinstance(row, tuple) or len(row) != len(drift):
                raise ValueError("depth_covariance must be square")
            covariance.append(tuple(_finite("depth_covariance value", value) for value in row))
        object.__setattr__(self, "depth_covariance", tuple(covariance))
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match extended stratum summary")

    def _payload(self) -> dict[str, object]:
        return {
            "stratum_key": self.stratum_key,
            "sample_count": self.sample_count,
            "mean_token_edit_ratio": self.mean_token_edit_ratio,
            "mean_observation_replacement_ratio": self.mean_observation_replacement_ratio,
            "mean_standardized_margin_drop": self.mean_standardized_margin_drop,
            "fidelity_pass_rate": self.fidelity_pass_rate,
            "mean_depth_drift": self.mean_depth_drift,
            "depth_covariance": self.depth_covariance,
        }


@dataclass(frozen=True, slots=True)
class ExtendedAnalysisResult:
    algorithm_version: str
    experiment_id: DevelopmentExperimentId
    experiment_definition_hash: str
    row_hashes: tuple[str, ...]
    strata: tuple[ExtendedStratumSummary, ...]
    claim_status: DevelopmentClaimStatus
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != EXTENDED_ANALYSIS_ALGORITHM_VERSION:
            raise ValueError("unsupported extended analysis algorithm version")
        if self.experiment_id not in tuple(DevelopmentExperimentId)[10:]:
            raise ValueError("extended analysis result must target E12 through E19")
        require_sha256("experiment_definition_hash", self.experiment_definition_hash)
        if self.row_hashes != tuple(sorted(set(self.row_hashes))):
            raise ValueError("row_hashes must be unique and canonically ordered")
        for value in self.row_hashes:
            require_sha256("row_hash", value)
        if not self.row_hashes:
            raise ValueError("extended analysis result requires rows")
        if not isinstance(self.strata, tuple) or not self.strata:
            raise ValueError("strata must be a non-empty tuple")
        if any(not isinstance(value, ExtendedStratumSummary) for value in self.strata):
            raise TypeError("strata must contain ExtendedStratumSummary values")
        if self.strata != tuple(sorted(self.strata, key=lambda value: value.stratum_key)):
            raise ValueError("strata must be canonically ordered")
        if self.claim_status is not DevelopmentClaimStatus.WITHHELD_DEV_ONLY:
            raise ValueError("extended development analyses must withhold confirmatory claims")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match extended analysis result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_id": self.experiment_id.value,
            "experiment_definition_hash": self.experiment_definition_hash,
            "row_hashes": self.row_hashes,
            "strata": self.strata,
            "claim_status": self.claim_status.value,
        }


def _covariance(vectors: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    depth = len(vectors[0])
    if any(len(value) != depth for value in vectors):
        raise ExtendedAnalysisInputError("all per-depth vectors must have the same depth")
    means = tuple(sum(vector[index] for vector in vectors) / len(vectors) for index in range(depth))
    denominator = max(1, len(vectors) - 1)
    return tuple(
        tuple(
            sum((vector[i] - means[i]) * (vector[j] - means[j]) for vector in vectors) / denominator
            for j in range(depth)
        )
        for i in range(depth)
    )


def _summary(key: tuple[str, ...], rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedStratumSummary:
    vectors = tuple(row.depth_drift for row in rows)
    depth = len(vectors[0])
    if any(len(value) != depth for value in vectors):
        raise ExtendedAnalysisInputError("all rows in a stratum must have the same g-value depth")
    mean_drift = tuple(sum(vector[index] for vector in vectors) / len(vectors) for index in range(depth))
    payload = {
        "stratum_key": key,
        "sample_count": len(rows),
        "mean_token_edit_ratio": sum(row.token_edit_ratio for row in rows) / len(rows),
        "mean_observation_replacement_ratio": sum(row.observation_replacement_ratio for row in rows) / len(rows),
        "mean_standardized_margin_drop": sum(row.standardized_margin_drop for row in rows) / len(rows),
        "fidelity_pass_rate": sum(row.fidelity_passed for row in rows) / len(rows),
        "mean_depth_drift": mean_drift,
        "depth_covariance": _covariance(vectors),
    }
    return ExtendedStratumSummary(
        key,
        len(rows),
        payload["mean_token_edit_ratio"],
        payload["mean_observation_replacement_ratio"],
        payload["mean_standardized_margin_drop"],
        payload["fidelity_pass_rate"],
        mean_drift,
        payload["depth_covariance"],
        sha256_json(payload),
    )


def _result(
    experiment_id: DevelopmentExperimentId,
    rows: tuple[ExtendedAnalysisRow, ...],
    key_function,
) -> ExtendedAnalysisResult:
    if not isinstance(rows, tuple) or not rows:
        raise ExtendedAnalysisInputError("extended analysis requires a non-empty row tuple")
    if any(not isinstance(row, ExtendedAnalysisRow) for row in rows):
        raise TypeError("rows must contain ExtendedAnalysisRow values")
    if len({row.row_hash for row in rows}) != len(rows):
        raise ExtendedAnalysisInputError("extended analysis rows must be unique")
    groups: dict[tuple[str, ...], list[ExtendedAnalysisRow]] = {}
    for row in rows:
        key = key_function(row)
        groups.setdefault(key, []).append(row)
    strata = tuple(
        _summary(key, tuple(groups[key]))
        for key in sorted(groups)
    )
    definition = default_development_experiment_registry().get(experiment_id)
    row_hashes = tuple(sorted(row.row_hash for row in rows))
    payload = {
        "algorithm_version": EXTENDED_ANALYSIS_ALGORITHM_VERSION,
        "experiment_id": experiment_id.value,
        "experiment_definition_hash": definition.definition_hash,
        "row_hashes": row_hashes,
        "strata": strata,
        "claim_status": DevelopmentClaimStatus.WITHHELD_DEV_ONLY.value,
    }
    return ExtendedAnalysisResult(
        EXTENDED_ANALYSIS_ALGORITHM_VERSION,
        experiment_id,
        definition.definition_hash,
        row_hashes,
        strata,
        DevelopmentClaimStatus.WITHHELD_DEV_ONLY,
        sha256_json(payload),
    )


def run_e12_surface_battery(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    if any(row.rule_family != "surface" for row in rows):
        raise ExtendedAnalysisInputError("E12 accepts only surface-rule rows")
    if any(not row.hard_invariant_passed for row in rows):
        raise ExtendedAnalysisInputError("E12 rejects rows with hard-invariant failure")
    return _result(
        DevelopmentExperimentId.E12,
        rows,
        lambda row: (row.model_tokenizer_hash, row.domain.value, row.rule_id),
    )


def run_e13_contraction_battery(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    if any(row.rule_family != "contraction" for row in rows):
        raise ExtendedAnalysisInputError("E13 accepts only contraction-rule rows")
    if any(not row.hard_invariant_passed for row in rows):
        raise ExtendedAnalysisInputError("E13 rejects rows with hard-invariant failure")
    return _result(
        DevelopmentExperimentId.E13,
        rows,
        lambda row: (row.rule_id, f"{row.realized_density:.12g}", row.domain.value),
    )


def run_e14_length_scaling(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    if {row.target_length for row in rows} != set(TARGET_LENGTHS):
        raise ExtendedAnalysisInputError("E14 requires all frozen 64 through 1024 token length strata")
    return _result(
        DevelopmentExperimentId.E14,
        rows,
        lambda row: (str(row.target_length), row.model_tokenizer_hash, row.domain.value, row.detector_family.value),
    )


def run_e15_domain_transfer(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    if {row.domain for row in rows} != set(CorpusDomain):
        raise ExtendedAnalysisInputError("E15 requires all four frozen domains")
    return _result(
        DevelopmentExperimentId.E15,
        rows,
        lambda row: (row.domain.value, row.schedule_policy, str(row.budget), row.budget_unit),
    )


def run_e16_validation_key_transfer(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    if any(row.key_split is not KeySplit.VALIDATION for row in rows):
        raise ExtendedAnalysisInputError("M6 E16 may use VALIDATION_KEYS only; TEST_KEYS remain sealed for E20")
    if len({row.key_id for row in rows}) < 2:
        raise ExtendedAnalysisInputError("E16 requires at least two held-out validation keys")
    return _result(
        DevelopmentExperimentId.E16,
        rows,
        lambda row: (row.key_id, row.model_tokenizer_hash, row.domain.value, str(row.target_length)),
    )


def run_e17_tokenizer_transfer(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    pairs: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        pairs.setdefault((row.source_text_hash, row.transformed_text_hash), set()).add(row.model_tokenizer_hash)
    if not pairs or any(len(models) < 2 for models in pairs.values()):
        raise ExtendedAnalysisInputError("E17 requires every text perturbation to be observed under at least two tokenizer/model families")
    return _result(
        DevelopmentExperimentId.E17,
        rows,
        lambda row: (row.source_text_hash, row.transformed_text_hash, row.model_tokenizer_hash),
    )


def run_e18_detector_disagreement(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    pairs: dict[tuple[str, str], set[DetectorFamily]] = {}
    for row in rows:
        pairs.setdefault((row.source_text_hash, row.transformed_text_hash), set()).add(row.detector_family)
    if not pairs or any(families != _REQUIRED_DETECTOR_FAMILIES for families in pairs.values()):
        raise ExtendedAnalysisInputError("E18 requires paired Mean, Weighted Mean, and Bayesian rows for every text perturbation")
    return _result(
        DevelopmentExperimentId.E18,
        rows,
        lambda row: (row.source_text_hash, row.transformed_text_hash, row.detector_family.value),
    )


def run_e19_per_depth_drift(rows: tuple[ExtendedAnalysisRow, ...]) -> ExtendedAnalysisResult:
    depths = {len(row.depth_drift) for row in rows}
    if len(depths) != 1:
        raise ExtendedAnalysisInputError("E19 requires a consistent watermark depth within one analysis artifact")
    return _result(
        DevelopmentExperimentId.E19,
        rows,
        lambda row: (row.rule_family, row.schedule_policy, str(row.budget), row.budget_unit),
    )


def verify_extended_analysis_result(
    result: ExtendedAnalysisResult,
    rows: tuple[ExtendedAnalysisRow, ...],
) -> None:
    if not isinstance(result, ExtendedAnalysisResult):
        raise TypeError("result must be an ExtendedAnalysisResult")
    runners = {
        DevelopmentExperimentId.E12: run_e12_surface_battery,
        DevelopmentExperimentId.E13: run_e13_contraction_battery,
        DevelopmentExperimentId.E14: run_e14_length_scaling,
        DevelopmentExperimentId.E15: run_e15_domain_transfer,
        DevelopmentExperimentId.E16: run_e16_validation_key_transfer,
        DevelopmentExperimentId.E17: run_e17_tokenizer_transfer,
        DevelopmentExperimentId.E18: run_e18_detector_disagreement,
        DevelopmentExperimentId.E19: run_e19_per_depth_drift,
    }
    expected = runners[result.experiment_id](rows)
    if result != expected:
        raise ValueError("extended analysis result does not replay exactly from rows")
