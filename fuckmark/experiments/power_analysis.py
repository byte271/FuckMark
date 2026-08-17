from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .m6_readiness import M6PowerAnalysisEvidence


POWER_ANALYSIS_ALGORITHM_VERSION = "validation-empirical-paired-bootstrap-power-v1"
POWER_ANALYSIS_BOOTSTRAP_METHOD = "paired-sample-percentile-bootstrap-v1"
POWER_ANALYSIS_SIMULATION_RNG = "python-random-mt19937-seeded-v1"


class PowerAnalysisDirection(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    TWO_SIDED = "TWO_SIDED"


class PowerAnalysisStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


def _probability(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0 or number >= 1.0:
        raise ValueError(f"{name} must be finite and strictly between 0 and 1")
    return number


def _finite_effects(values: tuple[float, ...]) -> tuple[float, ...]:
    if not isinstance(values, tuple) or len(values) < 2:
        raise ValueError("validation_effects must contain at least two paired sample effects")
    output = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("validation_effects must contain real numbers")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("validation_effects must contain finite values")
        output.append(number)
    return tuple(output)


def _quantile(sorted_values: tuple[float, ...], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def _bootstrap_interval(
    sample: tuple[float, ...],
    confidence_level: float,
    bootstrap_replicates: int,
    rng: random.Random,
) -> tuple[float, float]:
    means = []
    count = len(sample)
    for _ in range(bootstrap_replicates):
        total = math.fsum(sample[rng.randrange(count)] for _ in range(count))
        means.append(total / count)
    ordered = tuple(sorted(means))
    tail = (1.0 - confidence_level) / 2.0
    return _quantile(ordered, tail), _quantile(ordered, 1.0 - tail)


def _detected(interval: tuple[float, float], direction: PowerAnalysisDirection) -> bool:
    low, high = interval
    if direction is PowerAnalysisDirection.POSITIVE:
        return low > 0.0
    if direction is PowerAnalysisDirection.NEGATIVE:
        return high < 0.0
    return low > 0.0 or high < 0.0


@dataclass(frozen=True, slots=True)
class PowerAnalysisInput:
    metric_id: str
    stratum_id: str
    validation_effects: tuple[float, ...]
    candidate_sample_counts: tuple[int, ...]
    desired_power: float
    confidence_level: float
    direction: PowerAnalysisDirection
    simulation_replicates: int
    bootstrap_replicates: int
    seed: int
    input_hash: str

    def __post_init__(self) -> None:
        require_clean_string("metric_id", self.metric_id)
        require_clean_string("stratum_id", self.stratum_id)
        effects = _finite_effects(self.validation_effects)
        object.__setattr__(self, "validation_effects", effects)
        if not isinstance(self.candidate_sample_counts, tuple) or not self.candidate_sample_counts:
            raise ValueError("candidate_sample_counts must be a non-empty tuple")
        counts = []
        for value in self.candidate_sample_counts:
            require_int("candidate sample count", value)
            if value <= 1:
                raise ValueError("candidate sample counts must exceed one")
            counts.append(value)
        normalized_counts = tuple(counts)
        if normalized_counts != tuple(sorted(set(normalized_counts))):
            raise ValueError("candidate_sample_counts must be unique and increasing")
        object.__setattr__(self, "candidate_sample_counts", normalized_counts)
        object.__setattr__(self, "desired_power", _probability("desired_power", self.desired_power))
        object.__setattr__(self, "confidence_level", _probability("confidence_level", self.confidence_level))
        if not isinstance(self.direction, PowerAnalysisDirection):
            raise TypeError("direction must be a PowerAnalysisDirection")
        for name, value in (
            ("simulation_replicates", self.simulation_replicates),
            ("bootstrap_replicates", self.bootstrap_replicates),
        ):
            require_int(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        require_sha256("input_hash", self.input_hash)
        if self.input_hash != sha256_json(self._payload()):
            raise ValueError("input_hash does not match power analysis input")

    def _payload(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "stratum_id": self.stratum_id,
            "validation_effects": self.validation_effects,
            "candidate_sample_counts": self.candidate_sample_counts,
            "desired_power": self.desired_power,
            "confidence_level": self.confidence_level,
            "direction": self.direction.value,
            "simulation_replicates": self.simulation_replicates,
            "bootstrap_replicates": self.bootstrap_replicates,
            "seed": self.seed,
        }

    @classmethod
    def create(
        cls,
        *,
        metric_id: str,
        stratum_id: str,
        validation_effects: tuple[float, ...],
        candidate_sample_counts: tuple[int, ...],
        desired_power: float,
        confidence_level: float,
        direction: PowerAnalysisDirection,
        simulation_replicates: int,
        bootstrap_replicates: int,
        seed: int,
    ) -> PowerAnalysisInput:
        payload = {
            "metric_id": metric_id,
            "stratum_id": stratum_id,
            "validation_effects": tuple(float(value) for value in validation_effects),
            "candidate_sample_counts": candidate_sample_counts,
            "desired_power": float(desired_power),
            "confidence_level": float(confidence_level),
            "direction": direction.value,
            "simulation_replicates": simulation_replicates,
            "bootstrap_replicates": bootstrap_replicates,
            "seed": seed,
        }
        return cls(
            metric_id,
            stratum_id,
            tuple(float(value) for value in validation_effects),
            candidate_sample_counts,
            float(desired_power),
            float(confidence_level),
            direction,
            simulation_replicates,
            bootstrap_replicates,
            seed,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class PowerEstimate:
    sample_count: int
    detected_replicates: int
    simulation_replicates: int
    estimated_power: float
    estimate_hash: str

    def __post_init__(self) -> None:
        require_int("sample_count", self.sample_count)
        require_int("detected_replicates", self.detected_replicates)
        require_int("simulation_replicates", self.simulation_replicates)
        if self.sample_count <= 1 or self.simulation_replicates <= 0:
            raise ValueError("power estimate counts are outside their valid ranges")
        if self.detected_replicates < 0 or self.detected_replicates > self.simulation_replicates:
            raise ValueError("detected_replicates is outside the simulation range")
        expected_power = self.detected_replicates / self.simulation_replicates
        if self.estimated_power != expected_power:
            raise ValueError("estimated_power does not match simulation counts")
        require_sha256("estimate_hash", self.estimate_hash)
        if self.estimate_hash != sha256_json(self._payload()):
            raise ValueError("estimate_hash does not match power estimate")

    def _payload(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "detected_replicates": self.detected_replicates,
            "simulation_replicates": self.simulation_replicates,
            "estimated_power": self.estimated_power,
        }


@dataclass(frozen=True, slots=True)
class PowerAnalysisResult:
    algorithm_version: str
    bootstrap_method: str
    simulation_rng: str
    input_hash: str
    estimates: tuple[PowerEstimate, ...]
    status: PowerAnalysisStatus
    selected_sample_count: int | None
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != POWER_ANALYSIS_ALGORITHM_VERSION:
            raise ValueError("unsupported power analysis algorithm version")
        if self.bootstrap_method != POWER_ANALYSIS_BOOTSTRAP_METHOD:
            raise ValueError("unsupported power analysis bootstrap method")
        if self.simulation_rng != POWER_ANALYSIS_SIMULATION_RNG:
            raise ValueError("unsupported power analysis RNG")
        require_sha256("input_hash", self.input_hash)
        if not isinstance(self.estimates, tuple) or not self.estimates:
            raise ValueError("estimates must be a non-empty tuple")
        if any(not isinstance(value, PowerEstimate) for value in self.estimates):
            raise TypeError("estimates must contain PowerEstimate values")
        if tuple(value.sample_count for value in self.estimates) != tuple(
            sorted(set(value.sample_count for value in self.estimates))
        ):
            raise ValueError("power estimates must be unique and ordered by sample count")
        if not isinstance(self.status, PowerAnalysisStatus):
            raise TypeError("status must be a PowerAnalysisStatus")
        if self.status is PowerAnalysisStatus.RESOLVED:
            if self.selected_sample_count is None:
                raise ValueError("resolved power analysis requires selected_sample_count")
            require_int("selected_sample_count", self.selected_sample_count)
            if self.selected_sample_count not in tuple(value.sample_count for value in self.estimates):
                raise ValueError("selected_sample_count must be one of the evaluated candidates")
        elif self.selected_sample_count is not None:
            raise ValueError("unresolved power analysis cannot select a sample count")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match power analysis result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "bootstrap_method": self.bootstrap_method,
            "simulation_rng": self.simulation_rng,
            "input_hash": self.input_hash,
            "estimates": self.estimates,
            "status": self.status.value,
            "selected_sample_count": self.selected_sample_count,
        }


def run_power_analysis(value: PowerAnalysisInput) -> PowerAnalysisResult:
    if not isinstance(value, PowerAnalysisInput):
        raise TypeError("value must be a PowerAnalysisInput")
    rng = random.Random(value.seed)
    estimates = []
    source_count = len(value.validation_effects)
    selected = None
    for sample_count in value.candidate_sample_counts:
        detected = 0
        for _ in range(value.simulation_replicates):
            sample = tuple(
                value.validation_effects[rng.randrange(source_count)]
                for _ in range(sample_count)
            )
            interval = _bootstrap_interval(
                sample,
                value.confidence_level,
                value.bootstrap_replicates,
                rng,
            )
            if _detected(interval, value.direction):
                detected += 1
        power = detected / value.simulation_replicates
        estimate_payload = {
            "sample_count": sample_count,
            "detected_replicates": detected,
            "simulation_replicates": value.simulation_replicates,
            "estimated_power": power,
        }
        estimates.append(
            PowerEstimate(
                sample_count,
                detected,
                value.simulation_replicates,
                power,
                sha256_json(estimate_payload),
            )
        )
        if selected is None and power >= value.desired_power:
            selected = sample_count
    estimate_tuple = tuple(estimates)
    status = PowerAnalysisStatus.RESOLVED if selected is not None else PowerAnalysisStatus.UNRESOLVED
    payload = {
        "algorithm_version": POWER_ANALYSIS_ALGORITHM_VERSION,
        "bootstrap_method": POWER_ANALYSIS_BOOTSTRAP_METHOD,
        "simulation_rng": POWER_ANALYSIS_SIMULATION_RNG,
        "input_hash": value.input_hash,
        "estimates": estimate_tuple,
        "status": status.value,
        "selected_sample_count": selected,
    }
    return PowerAnalysisResult(
        POWER_ANALYSIS_ALGORITHM_VERSION,
        POWER_ANALYSIS_BOOTSTRAP_METHOD,
        POWER_ANALYSIS_SIMULATION_RNG,
        value.input_hash,
        estimate_tuple,
        status,
        selected,
        sha256_json(payload),
    )


def verify_power_analysis(result: PowerAnalysisResult, value: PowerAnalysisInput) -> None:
    if not isinstance(result, PowerAnalysisResult):
        raise TypeError("result must be a PowerAnalysisResult")
    expected = run_power_analysis(value)
    if result != expected:
        raise ValueError("power analysis result does not replay exactly from validation input")


def m6_power_evidence_from_result(result: PowerAnalysisResult) -> M6PowerAnalysisEvidence:
    if not isinstance(result, PowerAnalysisResult):
        raise TypeError("result must be a PowerAnalysisResult")
    if result.status is not PowerAnalysisStatus.RESOLVED or result.selected_sample_count is None:
        raise ValueError("M6 power evidence requires a resolved power analysis")
    return M6PowerAnalysisEvidence.create(
        POWER_ANALYSIS_ALGORITHM_VERSION,
        result.input_hash,
        result.result_hash,
        result.selected_sample_count,
    )
