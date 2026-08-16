from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_bool, require_int, require_sha256
from ..corpus import TinyDevCorpusArtifact
from ..hashing import sha256_json
from .registry import DevelopmentExperimentId, default_development_experiment_registry
from .transform_analysis import (
    DevelopmentClaimStatus,
    DevelopmentTransformRow,
    TransformAnalysisInputError,
    _validate_tiny_attack_rows,
)


E08_ALGORITHM_VERSION = "e08-dose-response-v1"
E08_BIN_EDGES = (0.0, 0.10, 0.25, 0.50, 0.75, 1.0)
E08_BOOTSTRAP_REPLICATES = 1000


@dataclass(frozen=True, slots=True)
class E08DoseBin:
    lower: float
    upper: float
    includes_upper: bool
    row_count: int
    source_count: int
    mean_margin_drop: float | None
    bootstrap_lower: float | None
    bootstrap_upper: float | None
    bin_hash: str

    def __post_init__(self) -> None:
        for name, value in (("lower", self.lower), ("upper", self.upper)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, float(value))
        if not 0.0 <= self.lower < self.upper <= 1.0:
            raise ValueError("dose bin bounds must satisfy 0 <= lower < upper <= 1")
        require_bool("includes_upper", self.includes_upper)
        require_int("row_count", self.row_count)
        require_int("source_count", self.source_count)
        if self.row_count < 0 or self.source_count < 0 or self.source_count > self.row_count:
            raise ValueError("dose bin counts are invalid")
        values = (self.mean_margin_drop, self.bootstrap_lower, self.bootstrap_upper)
        if self.row_count == 0:
            if self.source_count != 0 or any(value is not None for value in values):
                raise ValueError("empty dose bins must preserve explicit null summary fields")
        else:
            if self.source_count == 0 or any(value is None for value in values):
                raise ValueError("non-empty dose bins require source count, mean, and uncertainty interval")
            normalized = tuple(float(value) for value in values if value is not None)
            if any(not math.isfinite(value) for value in normalized):
                raise ValueError("dose bin summary values must be finite")
            object.__setattr__(self, "mean_margin_drop", normalized[0])
            object.__setattr__(self, "bootstrap_lower", normalized[1])
            object.__setattr__(self, "bootstrap_upper", normalized[2])
            if normalized[1] > normalized[2]:
                raise ValueError("bootstrap interval lower bound exceeds upper bound")
        require_sha256("bin_hash", self.bin_hash)
        if self.bin_hash != sha256_json(self._payload()):
            raise ValueError("bin_hash does not match E08 dose bin")

    def _payload(self) -> dict[str, object]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "includes_upper": self.includes_upper,
            "row_count": self.row_count,
            "source_count": self.source_count,
            "mean_margin_drop": self.mean_margin_drop,
            "bootstrap_lower": self.bootstrap_lower,
            "bootstrap_upper": self.bootstrap_upper,
        }


@dataclass(frozen=True, slots=True)
class E08DoseResponseResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    row_hashes: tuple[str, ...]
    bins: tuple[E08DoseBin, ...]
    nonempty_bin_count: int
    monotonic_violation_count: int
    monotonic_non_decreasing: bool
    bootstrap_replicates: int
    claim_status: DevelopmentClaimStatus
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E08_ALGORITHM_VERSION:
            raise ValueError("unsupported E08 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("threshold_hash", self.threshold_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if self.row_hashes != tuple(sorted(set(self.row_hashes))):
            raise ValueError("row_hashes must be unique and canonically ordered")
        for value in self.row_hashes:
            require_sha256("row_hash", value)
        if not isinstance(self.bins, tuple) or len(self.bins) != len(E08_BIN_EDGES) - 1:
            raise ValueError("E08 bins must match the frozen dose bin profile")
        if any(not isinstance(value, E08DoseBin) for value in self.bins):
            raise TypeError("bins must contain E08DoseBin values")
        for index, dose_bin in enumerate(self.bins):
            if dose_bin.lower != E08_BIN_EDGES[index] or dose_bin.upper != E08_BIN_EDGES[index + 1]:
                raise ValueError("E08 dose bin edges do not match frozen profile")
            if dose_bin.includes_upper != (index == len(self.bins) - 1):
                raise ValueError("only the final E08 dose bin may include its upper bound")
        require_int("nonempty_bin_count", self.nonempty_bin_count)
        if self.nonempty_bin_count != sum(value.row_count > 0 for value in self.bins):
            raise ValueError("nonempty_bin_count does not match bins")
        require_int("monotonic_violation_count", self.monotonic_violation_count)
        means = tuple(value.mean_margin_drop for value in self.bins if value.mean_margin_drop is not None)
        expected_violations = sum(current < previous for previous, current in zip(means, means[1:]))
        if self.monotonic_violation_count != expected_violations:
            raise ValueError("monotonic_violation_count does not match non-empty bin means")
        require_bool("monotonic_non_decreasing", self.monotonic_non_decreasing)
        if self.monotonic_non_decreasing != (expected_violations == 0):
            raise ValueError("monotonic_non_decreasing does not match violation count")
        require_int("bootstrap_replicates", self.bootstrap_replicates)
        if self.bootstrap_replicates != E08_BOOTSTRAP_REPLICATES:
            raise ValueError("bootstrap_replicates does not match frozen E08 policy")
        if self.claim_status is not DevelopmentClaimStatus.WITHHELD_DEV_ONLY:
            raise ValueError("E08 development result must withhold confirmatory claims")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E08 dose-response result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "row_hashes": self.row_hashes,
            "bins": self.bins,
            "nonempty_bin_count": self.nonempty_bin_count,
            "monotonic_violation_count": self.monotonic_violation_count,
            "monotonic_non_decreasing": self.monotonic_non_decreasing,
            "bootstrap_replicates": self.bootstrap_replicates,
            "claim_status": self.claim_status.value,
        }


def _bin_index(value: float) -> int:
    for index, (lower, upper) in enumerate(zip(E08_BIN_EDGES, E08_BIN_EDGES[1:])):
        if value >= lower and (value < upper or (index == len(E08_BIN_EDGES) - 2 and value <= upper)):
            return index
    raise ValueError("observation replacement ratio is outside frozen E08 bins")


def _bootstrap_interval(rows: tuple[DevelopmentTransformRow, ...], bin_index: int) -> tuple[float, float]:
    source_ids = tuple(sorted({row.source_sample_id for row in rows}))
    if len(source_ids) == 1:
        mean = sum(row.margin_drop for row in rows) / len(rows)
        return mean, mean
    by_source = {
        source_id: tuple(row for row in rows if row.source_sample_id == source_id)
        for source_id in source_ids
    }
    means: list[float] = []
    for replicate in range(E08_BOOTSTRAP_REPLICATES):
        sampled_rows: list[DevelopmentTransformRow] = []
        for draw in range(len(source_ids)):
            digest = sha256_json(
                {
                    "algorithm_version": E08_ALGORITHM_VERSION,
                    "bin_index": bin_index,
                    "replicate": replicate,
                    "draw": draw,
                    "source_ids": source_ids,
                }
            )
            source_id = source_ids[int(digest, 16) % len(source_ids)]
            sampled_rows.extend(by_source[source_id])
        means.append(sum(row.margin_drop for row in sampled_rows) / len(sampled_rows))
    means.sort()
    lower_index = int(math.floor(0.025 * (len(means) - 1)))
    upper_index = int(math.ceil(0.975 * (len(means) - 1)))
    return means[lower_index], means[upper_index]


def run_e08_dose_response(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> E08DoseResponseResult:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(rows, tuple) or not rows:
        raise TypeError("rows must be a non-empty tuple")
    if any(not isinstance(row, DevelopmentTransformRow) for row in rows):
        raise TypeError("rows must contain DevelopmentTransformRow values")
    if len({row.row_hash for row in rows}) != len(rows):
        raise TransformAnalysisInputError("E08 rows must not contain duplicate artifacts")
    detector_identity_hash, threshold_hash, _ = _validate_tiny_attack_rows(artifact, rows)
    grouped: list[list[DevelopmentTransformRow]] = [[] for _ in range(len(E08_BIN_EDGES) - 1)]
    for row in rows:
        grouped[_bin_index(row.observation_replacement_ratio)].append(row)
    bins: list[E08DoseBin] = []
    for index, values in enumerate(grouped):
        lower = E08_BIN_EDGES[index]
        upper = E08_BIN_EDGES[index + 1]
        includes_upper = index == len(grouped) - 1
        materialized = tuple(values)
        if not materialized:
            payload = {
                "lower": lower,
                "upper": upper,
                "includes_upper": includes_upper,
                "row_count": 0,
                "source_count": 0,
                "mean_margin_drop": None,
                "bootstrap_lower": None,
                "bootstrap_upper": None,
            }
            bins.append(E08DoseBin(lower, upper, includes_upper, 0, 0, None, None, None, sha256_json(payload)))
            continue
        mean = sum(row.margin_drop for row in materialized) / len(materialized)
        bootstrap_lower, bootstrap_upper = _bootstrap_interval(materialized, index)
        source_count = len({row.source_sample_id for row in materialized})
        payload = {
            "lower": lower,
            "upper": upper,
            "includes_upper": includes_upper,
            "row_count": len(materialized),
            "source_count": source_count,
            "mean_margin_drop": mean,
            "bootstrap_lower": bootstrap_lower,
            "bootstrap_upper": bootstrap_upper,
        }
        bins.append(
            E08DoseBin(
                lower,
                upper,
                includes_upper,
                len(materialized),
                source_count,
                mean,
                bootstrap_lower,
                bootstrap_upper,
                sha256_json(payload),
            )
        )
    bin_tuple = tuple(bins)
    means = tuple(value.mean_margin_drop for value in bin_tuple if value.mean_margin_drop is not None)
    violations = sum(current < previous for previous, current in zip(means, means[1:]))
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E08)
    row_hashes = tuple(sorted(row.row_hash for row in rows))
    payload = {
        "algorithm_version": E08_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "row_hashes": row_hashes,
        "bins": bin_tuple,
        "nonempty_bin_count": sum(value.row_count > 0 for value in bin_tuple),
        "monotonic_violation_count": violations,
        "monotonic_non_decreasing": violations == 0,
        "bootstrap_replicates": E08_BOOTSTRAP_REPLICATES,
        "claim_status": DevelopmentClaimStatus.WITHHELD_DEV_ONLY.value,
    }
    return E08DoseResponseResult(
        E08_ALGORITHM_VERSION,
        definition.definition_hash,
        artifact.artifact_hash,
        detector_identity_hash,
        threshold_hash,
        row_hashes,
        bin_tuple,
        payload["nonempty_bin_count"],
        violations,
        violations == 0,
        E08_BOOTSTRAP_REPLICATES,
        DevelopmentClaimStatus.WITHHELD_DEV_ONLY,
        sha256_json(payload),
    )
