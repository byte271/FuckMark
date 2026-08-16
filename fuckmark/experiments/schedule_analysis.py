from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_int, require_sha256
from ..corpus import CorpusSplit, KeySplit, TinyDevCorpusArtifact, WatermarkLabel
from ..hashing import sha256_json, sha256_text
from ..transforms import SchedulePolicy
from .registry import DevelopmentExperimentId, default_development_experiment_registry
from .transform_analysis import DevelopmentTransformRow, TransformAnalysisInputError


E09_ALGORITHM_VERSION = "e09-random-baseline-v2"
E10_ALGORITHM_VERSION = "e10-spacing-comparison-v2"
E11_ALGORITHM_VERSION = "e11-key-blind-greedy-v2"


class E09BaselineStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class E10PairStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED_COST = "UNMATCHED_COST"


class E10Status(str, Enum):
    COMPLETE_MATCHED = "COMPLETE_MATCHED"
    WITHHELD_UNMATCHED_COST = "WITHHELD_UNMATCHED_COST"
    INCOMPLETE = "INCOMPLETE"


class E11Status(str, Enum):
    DESCRIPTIVE_DEV_ONLY = "DESCRIPTIVE_DEV_ONLY"
    INCOMPLETE_BASELINE = "INCOMPLETE_BASELINE"
    CONTAMINATED = "CONTAMINATED"


class HeldOutClaimStatus(str, Enum):
    WITHHELD_NO_HELD_OUT_KEYS = "WITHHELD_NO_HELD_OUT_KEYS"
    WITHHELD_CONTAMINATED = "WITHHELD_CONTAMINATED"


def _expected_attack_sources(artifact: TinyDevCorpusArtifact) -> dict[str, object]:
    return {
        sample.sample_id: sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
        and sample.label is WatermarkLabel.WATERMARKED
    }


def _validate_schedule_rows(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    *,
    allow_secret_access: bool = False,
) -> tuple[str, str, float]:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(rows, tuple):
        raise TypeError("rows must be a tuple")
    if any(not isinstance(row, DevelopmentTransformRow) for row in rows):
        raise TypeError("rows must contain DevelopmentTransformRow values")
    if len({row.row_hash for row in rows}) != len(rows):
        raise TransformAnalysisInputError("schedule analysis rows must not contain duplicate artifacts")
    if type(allow_secret_access) is not bool:
        raise TypeError("allow_secret_access must be a bool")
    if not allow_secret_access and any(row.secret_access_observed for row in rows):
        raise TransformAnalysisInputError("secret access contaminates key-blind schedule analysis")
    sample_by_id = _expected_attack_sources(artifact)
    for row in rows:
        sample = sample_by_id.get(row.source_sample_id)
        if sample is None:
            raise TransformAnalysisInputError("schedule row references a non-watermarked or non-attack source")
        if row.prompt_family_id != sample.prompt_family_id:
            raise TransformAnalysisInputError("schedule row prompt family does not match corpus source")
        if row.source_text_hash != sha256_text(sample.text):
            raise TransformAnalysisInputError("schedule row source text hash does not match corpus source")
        if row.key_split is not KeySplit.DEV:
            raise TransformAnalysisInputError("tiny-dev schedule rows must use DEV_KEYS")
    if not rows:
        raise TransformAnalysisInputError("schedule analysis requires at least one row")
    for source_sample_id in {row.source_sample_id for row in rows}:
        source_rows = tuple(row for row in rows if row.source_sample_id == source_sample_id)
        if len({row.pristine_score for row in source_rows}) != 1:
            raise TransformAnalysisInputError("variants from one source must share one pristine score")
    detector_ids = {row.detector_identity_hash for row in rows}
    threshold_hashes = {row.threshold_hash for row in rows}
    threshold_values = {row.threshold_value for row in rows}
    if len(detector_ids) != 1 or len(threshold_hashes) != 1 or len(threshold_values) != 1:
        raise TransformAnalysisInputError("schedule rows must use one frozen detector and threshold identity")
    return next(iter(detector_ids)), next(iter(threshold_hashes)), next(iter(threshold_values))


def _mean(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


@dataclass(frozen=True, slots=True)
class E09RandomBaselineResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    row_hashes: tuple[str, ...]
    expected_source_count: int
    observed_source_count: int
    missing_source_ids: tuple[str, ...]
    random_variant_count: int
    mean_replacement_per_edit: float | None
    mean_margin_drop: float | None
    status: E09BaselineStatus
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E09_ALGORITHM_VERSION:
            raise ValueError("unsupported E09 algorithm version")
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
        require_int("expected_source_count", self.expected_source_count)
        require_int("observed_source_count", self.observed_source_count)
        require_int("random_variant_count", self.random_variant_count)
        if self.expected_source_count != 4:
            raise ValueError("tiny-dev E09 expects four watermarked attack sources")
        if not 0 <= self.observed_source_count <= self.expected_source_count:
            raise ValueError("observed_source_count is outside expected range")
        if self.random_variant_count != len(self.row_hashes):
            raise ValueError("random_variant_count does not match row hashes")
        if self.missing_source_ids != tuple(sorted(set(self.missing_source_ids))):
            raise ValueError("missing_source_ids must be unique and canonically ordered")
        for value in self.missing_source_ids:
            if not isinstance(value, str) or not value:
                raise ValueError("missing source IDs must be non-empty strings")
        if len(self.missing_source_ids) != self.expected_source_count - self.observed_source_count:
            raise ValueError("missing source count does not match observed source count")
        for name, value in (
            ("mean_replacement_per_edit", self.mean_replacement_per_edit),
            ("mean_margin_drop", self.mean_margin_drop),
        ):
            if self.random_variant_count == 0:
                if value is not None:
                    raise ValueError("empty random baseline must use null mean metrics")
            else:
                if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} must be a real number for non-empty baseline")
                if not math.isfinite(float(value)):
                    raise ValueError(f"{name} must be finite")
                object.__setattr__(self, name, float(value))
        if not isinstance(self.status, E09BaselineStatus):
            raise TypeError("status must be an E09BaselineStatus")
        expected_status = E09BaselineStatus.COMPLETE if not self.missing_source_ids else E09BaselineStatus.INCOMPLETE
        if self.status is not expected_status:
            raise ValueError("E09 status does not match missing baseline sources")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E09 random baseline result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "row_hashes": self.row_hashes,
            "expected_source_count": self.expected_source_count,
            "observed_source_count": self.observed_source_count,
            "missing_source_ids": self.missing_source_ids,
            "random_variant_count": self.random_variant_count,
            "mean_replacement_per_edit": self.mean_replacement_per_edit,
            "mean_margin_drop": self.mean_margin_drop,
            "status": self.status.value,
        }


def run_e09_random_baseline(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> E09RandomBaselineResult:
    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows)
    if any(row.schedule_policy is not SchedulePolicy.RANDOM_VALID for row in rows):
        raise TransformAnalysisInputError("E09 accepts RANDOM_VALID rows only")
    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))
    observed_ids = tuple(sorted({row.source_sample_id for row in rows}))
    missing = tuple(sorted(set(expected_ids) - set(observed_ids)))
    replacement_values = tuple(
        sum(row.replacement_per_edit for row in rows if row.source_sample_id == source_id)
        / sum(row.source_sample_id == source_id for row in rows)
        for source_id in observed_ids
    )
    margin_values = tuple(
        sum(row.margin_drop for row in rows if row.source_sample_id == source_id)
        / sum(row.source_sample_id == source_id for row in rows)
        for source_id in observed_ids
    )
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E09)
    row_hashes = tuple(sorted(row.row_hash for row in rows))
    status = E09BaselineStatus.COMPLETE if not missing else E09BaselineStatus.INCOMPLETE
    payload = {
        "algorithm_version": E09_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "row_hashes": row_hashes,
        "expected_source_count": len(expected_ids),
        "observed_source_count": len(observed_ids),
        "missing_source_ids": missing,
        "random_variant_count": len(rows),
        "mean_replacement_per_edit": _mean(replacement_values),
        "mean_margin_drop": _mean(margin_values),
        "status": status.value,
    }
    return E09RandomBaselineResult(
        E09_ALGORITHM_VERSION,
        definition.definition_hash,
        artifact.artifact_hash,
        detector_identity_hash,
        threshold_hash,
        row_hashes,
        len(expected_ids),
        len(observed_ids),
        missing,
        len(rows),
        payload["mean_replacement_per_edit"],
        payload["mean_margin_drop"],
        status,
        sha256_json(payload),
    )


def _pair_key(row: DevelopmentTransformRow) -> tuple[object, ...]:
    return (
        row.source_sample_id,
        row.candidate_pool_hash,
        row.scheduler_input_hash,
        row.budget,
        row.budget_unit,
        row.schedule_seed,
        row.detector_identity_hash,
        row.threshold_hash,
        row.threshold_value,
    )


@dataclass(frozen=True, slots=True)
class E10SpacingPair:
    pair_key_hash: str
    source_sample_id: str
    clustered_row_hash: str
    even_row_hash: str
    clustered_cost: int
    even_cost: int
    status: E10PairStatus
    coverage_difference_even_minus_clustered: int | None
    observation_ratio_difference_even_minus_clustered: float | None
    margin_drop_difference_even_minus_clustered: float | None
    pair_hash: str

    def __post_init__(self) -> None:
        require_sha256("pair_key_hash", self.pair_key_hash)
        if not isinstance(self.source_sample_id, str) or not self.source_sample_id:
            raise ValueError("source_sample_id must be non-empty")
        require_sha256("clustered_row_hash", self.clustered_row_hash)
        require_sha256("even_row_hash", self.even_row_hash)
        require_int("clustered_cost", self.clustered_cost)
        require_int("even_cost", self.even_cost)
        if self.clustered_cost < 0 or self.even_cost < 0:
            raise ValueError("spacing pair costs must be non-negative")
        if not isinstance(self.status, E10PairStatus):
            raise TypeError("status must be an E10PairStatus")
        metrics = (
            self.coverage_difference_even_minus_clustered,
            self.observation_ratio_difference_even_minus_clustered,
            self.margin_drop_difference_even_minus_clustered,
        )
        if self.status is E10PairStatus.MATCHED:
            if self.clustered_cost != self.even_cost:
                raise ValueError("matched spacing pairs must have equal realized cost")
            if any(value is None for value in metrics):
                raise ValueError("matched spacing pairs require comparison metrics")
            if not isinstance(metrics[0], int) or isinstance(metrics[0], bool):
                raise TypeError("coverage difference must be an integer")
            for value in metrics[1:]:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise TypeError("spacing comparison metric must be a finite real number")
        else:
            if self.clustered_cost == self.even_cost:
                raise ValueError("unmatched-cost pair must have different realized costs")
            if any(value is not None for value in metrics):
                raise ValueError("unmatched-cost pairs must withhold comparison metrics")
        require_sha256("pair_hash", self.pair_hash)
        if self.pair_hash != sha256_json(self._payload()):
            raise ValueError("pair_hash does not match E10 spacing pair")

    def _payload(self) -> dict[str, object]:
        return {
            "pair_key_hash": self.pair_key_hash,
            "source_sample_id": self.source_sample_id,
            "clustered_row_hash": self.clustered_row_hash,
            "even_row_hash": self.even_row_hash,
            "clustered_cost": self.clustered_cost,
            "even_cost": self.even_cost,
            "status": self.status.value,
            "coverage_difference_even_minus_clustered": self.coverage_difference_even_minus_clustered,
            "observation_ratio_difference_even_minus_clustered": self.observation_ratio_difference_even_minus_clustered,
            "margin_drop_difference_even_minus_clustered": self.margin_drop_difference_even_minus_clustered,
        }


@dataclass(frozen=True, slots=True)
class E10SpacingComparisonResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    pair_hashes: tuple[str, ...]
    expected_source_count: int
    observed_source_count: int
    missing_source_ids: tuple[str, ...]
    matched_pair_count: int
    unmatched_cost_pair_count: int
    mean_coverage_difference_even_minus_clustered: float | None
    mean_observation_ratio_difference_even_minus_clustered: float | None
    mean_margin_drop_difference_even_minus_clustered: float | None
    comparison_withheld_for_unmatched_cost: bool
    status: E10Status
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E10_ALGORITHM_VERSION:
            raise ValueError("unsupported E10 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("threshold_hash", self.threshold_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if self.pair_hashes != tuple(sorted(set(self.pair_hashes))):
            raise ValueError("pair_hashes must be unique and canonically ordered")
        for value in self.pair_hashes:
            require_sha256("pair_hash", value)
        require_int("expected_source_count", self.expected_source_count)
        require_int("observed_source_count", self.observed_source_count)
        if self.expected_source_count != 4:
            raise ValueError("tiny-dev E10 expects four watermarked attack sources")
        if not 0 <= self.observed_source_count <= self.expected_source_count:
            raise ValueError("E10 observed_source_count is outside expected range")
        if self.missing_source_ids != tuple(sorted(set(self.missing_source_ids))):
            raise ValueError("E10 missing_source_ids must be unique and canonically ordered")
        if len(self.missing_source_ids) != self.expected_source_count - self.observed_source_count:
            raise ValueError("E10 missing source count does not match observed source count")
        require_int("matched_pair_count", self.matched_pair_count)
        require_int("unmatched_cost_pair_count", self.unmatched_cost_pair_count)
        if self.matched_pair_count < 0 or self.unmatched_cost_pair_count < 0:
            raise ValueError("E10 pair counts must be non-negative")
        metrics = (
            self.mean_coverage_difference_even_minus_clustered,
            self.mean_observation_ratio_difference_even_minus_clustered,
            self.mean_margin_drop_difference_even_minus_clustered,
        )
        if self.matched_pair_count == 0:
            if any(value is not None for value in metrics):
                raise ValueError("E10 with no matched pairs must use null mean metrics")
        else:
            for value in metrics:
                if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise TypeError("E10 matched comparison means must be finite real numbers")
        require_bool("comparison_withheld_for_unmatched_cost", self.comparison_withheld_for_unmatched_cost)
        if self.comparison_withheld_for_unmatched_cost != (self.unmatched_cost_pair_count > 0):
            raise ValueError("E10 unmatched-cost withholding flag does not match pair count")
        if not isinstance(self.status, E10Status):
            raise TypeError("status must be an E10Status")
        if self.missing_source_ids:
            expected_status = E10Status.INCOMPLETE
        elif self.unmatched_cost_pair_count:
            expected_status = E10Status.WITHHELD_UNMATCHED_COST
        else:
            expected_status = E10Status.COMPLETE_MATCHED
        if self.status is not expected_status:
            raise ValueError("E10 status does not match source completeness and cost matching")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E10 spacing comparison result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "pair_hashes": self.pair_hashes,
            "expected_source_count": self.expected_source_count,
            "observed_source_count": self.observed_source_count,
            "missing_source_ids": self.missing_source_ids,
            "matched_pair_count": self.matched_pair_count,
            "unmatched_cost_pair_count": self.unmatched_cost_pair_count,
            "mean_coverage_difference_even_minus_clustered": self.mean_coverage_difference_even_minus_clustered,
            "mean_observation_ratio_difference_even_minus_clustered": self.mean_observation_ratio_difference_even_minus_clustered,
            "mean_margin_drop_difference_even_minus_clustered": self.mean_margin_drop_difference_even_minus_clustered,
            "comparison_withheld_for_unmatched_cost": self.comparison_withheld_for_unmatched_cost,
            "status": self.status.value,
        }


def run_e10_spacing_comparison(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> E10SpacingComparisonResult:
    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows)
    allowed = {SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING}
    if any(row.schedule_policy not in allowed for row in rows):
        raise TransformAnalysisInputError("E10 accepts CLUSTERED and EVEN_SPACING rows only")
    groups: dict[tuple[object, ...], dict[SchedulePolicy, DevelopmentTransformRow]] = {}
    for row in rows:
        group = groups.setdefault(_pair_key(row), {})
        if row.schedule_policy in group:
            raise TransformAnalysisInputError("E10 pair key contains duplicate policy rows")
        group[row.schedule_policy] = row
    incomplete = tuple(key for key, group in groups.items() if set(group) != allowed)
    if incomplete:
        raise TransformAnalysisInputError("E10 requires both clustered and even rows for every pair key")
    pairs: list[E10SpacingPair] = []
    for key in sorted(groups, key=lambda value: sha256_json(value)):
        group = groups[key]
        clustered = group[SchedulePolicy.CLUSTERED]
        even = group[SchedulePolicy.EVEN_SPACING]
        pair_key_hash = sha256_json(key)
        if clustered.realized_edit_cost == even.realized_edit_cost:
            status = E10PairStatus.MATCHED
            coverage_difference = even.scheduler_covered_interval_size - clustered.scheduler_covered_interval_size
            observation_difference = even.observation_replacement_ratio - clustered.observation_replacement_ratio
            margin_difference = even.margin_drop - clustered.margin_drop
        else:
            status = E10PairStatus.UNMATCHED_COST
            coverage_difference = None
            observation_difference = None
            margin_difference = None
        payload = {
            "pair_key_hash": pair_key_hash,
            "source_sample_id": clustered.source_sample_id,
            "clustered_row_hash": clustered.row_hash,
            "even_row_hash": even.row_hash,
            "clustered_cost": clustered.realized_edit_cost,
            "even_cost": even.realized_edit_cost,
            "status": status.value,
            "coverage_difference_even_minus_clustered": coverage_difference,
            "observation_ratio_difference_even_minus_clustered": observation_difference,
            "margin_drop_difference_even_minus_clustered": margin_difference,
        }
        pairs.append(
            E10SpacingPair(
                pair_key_hash,
                clustered.source_sample_id,
                clustered.row_hash,
                even.row_hash,
                clustered.realized_edit_cost,
                even.realized_edit_cost,
                status,
                coverage_difference,
                observation_difference,
                margin_difference,
                sha256_json(payload),
            )
        )
    pair_tuple = tuple(pairs)
    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))
    observed_source_ids = tuple(sorted({value.source_sample_id for value in pair_tuple}))
    missing = tuple(sorted(set(expected_ids) - set(observed_source_ids)))
    matched = tuple(value for value in pair_tuple if value.status is E10PairStatus.MATCHED)
    unmatched_count = len(pair_tuple) - len(matched)
    coverage_values = tuple(float(value.coverage_difference_even_minus_clustered) for value in matched)
    observation_values = tuple(float(value.observation_ratio_difference_even_minus_clustered) for value in matched)
    margin_values = tuple(float(value.margin_drop_difference_even_minus_clustered) for value in matched)
    if missing:
        status = E10Status.INCOMPLETE
    elif unmatched_count:
        status = E10Status.WITHHELD_UNMATCHED_COST
    else:
        status = E10Status.COMPLETE_MATCHED
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E10)
    pair_hashes = tuple(sorted(value.pair_hash for value in pair_tuple))
    payload = {
        "algorithm_version": E10_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "pair_hashes": pair_hashes,
        "expected_source_count": len(expected_ids),
        "observed_source_count": len(observed_source_ids),
        "missing_source_ids": missing,
        "matched_pair_count": len(matched),
        "unmatched_cost_pair_count": unmatched_count,
        "mean_coverage_difference_even_minus_clustered": _mean(coverage_values),
        "mean_observation_ratio_difference_even_minus_clustered": _mean(observation_values),
        "mean_margin_drop_difference_even_minus_clustered": _mean(margin_values),
        "comparison_withheld_for_unmatched_cost": unmatched_count > 0,
        "status": status.value,
    }
    return E10SpacingComparisonResult(
        algorithm_version=E10_ALGORITHM_VERSION,
        experiment_definition_hash=definition.definition_hash,
        tiny_dev_artifact_hash=artifact.artifact_hash,
        detector_identity_hash=detector_identity_hash,
        threshold_hash=threshold_hash,
        pair_hashes=pair_hashes,
        expected_source_count=len(expected_ids),
        observed_source_count=len(observed_source_ids),
        missing_source_ids=missing,
        matched_pair_count=len(matched),
        unmatched_cost_pair_count=unmatched_count,
        mean_coverage_difference_even_minus_clustered=payload["mean_coverage_difference_even_minus_clustered"],
        mean_observation_ratio_difference_even_minus_clustered=payload["mean_observation_ratio_difference_even_minus_clustered"],
        mean_margin_drop_difference_even_minus_clustered=payload["mean_margin_drop_difference_even_minus_clustered"],
        comparison_withheld_for_unmatched_cost=unmatched_count > 0,
        status=status,
        result_hash=sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class E11GreedyPair:
    pair_key_hash: str
    source_sample_id: str
    random_row_hash: str
    greedy_row_hash: str
    random_replacement_per_edit: float
    greedy_replacement_per_edit: float
    improvement_greedy_minus_random: float
    secret_access_observed: bool
    pair_hash: str

    def __post_init__(self) -> None:
        require_sha256("pair_key_hash", self.pair_key_hash)
        if not isinstance(self.source_sample_id, str) or not self.source_sample_id:
            raise ValueError("source_sample_id must be non-empty")
        require_sha256("random_row_hash", self.random_row_hash)
        require_sha256("greedy_row_hash", self.greedy_row_hash)
        for name, value in (
            ("random_replacement_per_edit", self.random_replacement_per_edit),
            ("greedy_replacement_per_edit", self.greedy_replacement_per_edit),
            ("improvement_greedy_minus_random", self.improvement_greedy_minus_random),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be a finite real number")
            object.__setattr__(self, name, float(value))
        if self.improvement_greedy_minus_random != self.greedy_replacement_per_edit - self.random_replacement_per_edit:
            raise ValueError("greedy improvement does not match paired replacement-per-edit values")
        require_bool("secret_access_observed", self.secret_access_observed)
        require_sha256("pair_hash", self.pair_hash)
        if self.pair_hash != sha256_json(self._payload()):
            raise ValueError("pair_hash does not match E11 greedy pair")

    def _payload(self) -> dict[str, object]:
        return {
            "pair_key_hash": self.pair_key_hash,
            "source_sample_id": self.source_sample_id,
            "random_row_hash": self.random_row_hash,
            "greedy_row_hash": self.greedy_row_hash,
            "random_replacement_per_edit": self.random_replacement_per_edit,
            "greedy_replacement_per_edit": self.greedy_replacement_per_edit,
            "improvement_greedy_minus_random": self.improvement_greedy_minus_random,
            "secret_access_observed": self.secret_access_observed,
        }


@dataclass(frozen=True, slots=True)
class E11GreedyComparisonResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    pair_hashes: tuple[str, ...]
    expected_source_count: int
    paired_source_count: int
    missing_source_ids: tuple[str, ...]
    mean_improvement_greedy_minus_random: float | None
    contaminated_pair_count: int
    status: E11Status
    held_out_claim_status: HeldOutClaimStatus
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E11_ALGORITHM_VERSION:
            raise ValueError("unsupported E11 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("threshold_hash", self.threshold_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if self.pair_hashes != tuple(sorted(set(self.pair_hashes))):
            raise ValueError("pair_hashes must be unique and canonically ordered")
        for value in self.pair_hashes:
            require_sha256("pair_hash", value)
        require_int("expected_source_count", self.expected_source_count)
        require_int("paired_source_count", self.paired_source_count)
        require_int("contaminated_pair_count", self.contaminated_pair_count)
        if self.expected_source_count != 4:
            raise ValueError("tiny-dev E11 expects four watermarked attack sources")
        if not 0 <= self.paired_source_count <= self.expected_source_count:
            raise ValueError("paired_source_count is outside expected range")
        if not 0 <= self.contaminated_pair_count <= self.paired_source_count:
            raise ValueError("contaminated_pair_count is outside paired source range")
        if self.missing_source_ids != tuple(sorted(set(self.missing_source_ids))):
            raise ValueError("missing_source_ids must be unique and canonically ordered")
        if len(self.missing_source_ids) != self.expected_source_count - self.paired_source_count:
            raise ValueError("missing source count does not match paired source count")
        if self.paired_source_count == 0:
            if self.mean_improvement_greedy_minus_random is not None:
                raise ValueError("E11 with no pairs must use null mean improvement")
        else:
            if self.mean_improvement_greedy_minus_random is None or isinstance(self.mean_improvement_greedy_minus_random, bool) or not isinstance(self.mean_improvement_greedy_minus_random, (int, float)):
                raise TypeError("E11 mean improvement must be a real number when pairs exist")
            if not math.isfinite(float(self.mean_improvement_greedy_minus_random)):
                raise ValueError("E11 mean improvement must be finite")
            object.__setattr__(self, "mean_improvement_greedy_minus_random", float(self.mean_improvement_greedy_minus_random))
        if not isinstance(self.status, E11Status):
            raise TypeError("status must be an E11Status")
        if self.contaminated_pair_count:
            expected_status = E11Status.CONTAMINATED
            expected_claim = HeldOutClaimStatus.WITHHELD_CONTAMINATED
        elif self.missing_source_ids:
            expected_status = E11Status.INCOMPLETE_BASELINE
            expected_claim = HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS
        else:
            expected_status = E11Status.DESCRIPTIVE_DEV_ONLY
            expected_claim = HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS
        if self.status is not expected_status:
            raise ValueError("E11 status does not match contamination and baseline completeness")
        if self.held_out_claim_status is not expected_claim:
            raise ValueError("held_out_claim_status does not match E11 evidence boundary")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E11 greedy comparison result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "pair_hashes": self.pair_hashes,
            "expected_source_count": self.expected_source_count,
            "paired_source_count": self.paired_source_count,
            "missing_source_ids": self.missing_source_ids,
            "mean_improvement_greedy_minus_random": self.mean_improvement_greedy_minus_random,
            "contaminated_pair_count": self.contaminated_pair_count,
            "status": self.status.value,
            "held_out_claim_status": self.held_out_claim_status.value,
        }


def run_e11_greedy_comparison(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> E11GreedyComparisonResult:
    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows, allow_secret_access=True)
    allowed = {SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND}
    if any(row.schedule_policy not in allowed for row in rows):
        raise TransformAnalysisInputError("E11 accepts RANDOM_VALID and COVERAGE_GREEDY_KEY_BLIND rows only")
    groups: dict[tuple[object, ...], dict[SchedulePolicy, DevelopmentTransformRow]] = {}
    for row in rows:
        group = groups.setdefault(_pair_key(row), {})
        if row.schedule_policy in group:
            raise TransformAnalysisInputError("E11 pair key contains duplicate policy rows")
        group[row.schedule_policy] = row
    incomplete = tuple(key for key, group in groups.items() if set(group) != allowed)
    if incomplete:
        raise TransformAnalysisInputError("E11 requires both random and greedy rows for every pair key")
    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))
    paired_ids: set[str] = set()
    pairs: list[E11GreedyPair] = []
    for key in sorted(groups, key=lambda value: sha256_json(value)):
        group = groups[key]
        random_row = group[SchedulePolicy.RANDOM_VALID]
        greedy_row = group[SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND]
        paired_ids.add(random_row.source_sample_id)
        secret_access = random_row.secret_access_observed or greedy_row.secret_access_observed
        random_value = random_row.replacement_per_edit
        greedy_value = greedy_row.replacement_per_edit
        improvement = greedy_value - random_value
        pair_key_hash = sha256_json(key)
        payload = {
            "pair_key_hash": pair_key_hash,
            "source_sample_id": random_row.source_sample_id,
            "random_row_hash": random_row.row_hash,
            "greedy_row_hash": greedy_row.row_hash,
            "random_replacement_per_edit": random_value,
            "greedy_replacement_per_edit": greedy_value,
            "improvement_greedy_minus_random": improvement,
            "secret_access_observed": secret_access,
        }
        pairs.append(
            E11GreedyPair(
                pair_key_hash,
                random_row.source_sample_id,
                random_row.row_hash,
                greedy_row.row_hash,
                random_value,
                greedy_value,
                improvement,
                secret_access,
                sha256_json(payload),
            )
        )
    pair_tuple = tuple(pairs)
    missing = tuple(sorted(set(expected_ids) - paired_ids))
    contaminated_count = sum(value.secret_access_observed for value in pair_tuple)
    improvements = tuple(value.improvement_greedy_minus_random for value in pair_tuple)
    if contaminated_count:
        status = E11Status.CONTAMINATED
        claim_status = HeldOutClaimStatus.WITHHELD_CONTAMINATED
    elif missing:
        status = E11Status.INCOMPLETE_BASELINE
        claim_status = HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS
    else:
        status = E11Status.DESCRIPTIVE_DEV_ONLY
        claim_status = HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E11)
    pair_hashes = tuple(sorted(value.pair_hash for value in pair_tuple))
    payload = {
        "algorithm_version": E11_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "pair_hashes": pair_hashes,
        "expected_source_count": len(expected_ids),
        "paired_source_count": len(paired_ids),
        "missing_source_ids": missing,
        "mean_improvement_greedy_minus_random": _mean(improvements),
        "contaminated_pair_count": contaminated_count,
        "status": status.value,
        "held_out_claim_status": claim_status.value,
    }
    return E11GreedyComparisonResult(
        E11_ALGORITHM_VERSION,
        definition.definition_hash,
        artifact.artifact_hash,
        detector_identity_hash,
        threshold_hash,
        pair_hashes,
        len(expected_ids),
        len(paired_ids),
        missing,
        payload["mean_improvement_greedy_minus_random"],
        contaminated_count,
        status,
        claim_status,
        sha256_json(payload),
    )
