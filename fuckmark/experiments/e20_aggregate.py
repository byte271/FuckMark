from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, CorpusSample, WatermarkLabel
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ReasonCount, E20ResultBundle, verify_e20_result_bundle
from .e20_conditions import E20Condition, E20ConditionPlan
from .e20_rows import E20FailureRow, E20OutcomeRow, ExperimentReasonCode


E20_AGGREGATOR_ALGORITHM_VERSION = "e20-aggregator-v2"
E20_BOOTSTRAP_RNG_ALGORITHM_VERSION = "splitmix64-rejection-v1"
E20_BOOTSTRAP_QUANTILE_ALGORITHM_VERSION = "linear-type7-v1"
_MASK64 = (1 << 64) - 1


class E20AnalysisPopulation(str, Enum):
    POLICY_ALL = "POLICY_ALL"
    ELIGIBLE_ONLY = "ELIGIBLE_ONLY"
    PRISTINE_POSITIVE = "PRISTINE_POSITIVE"
    NEGATIVE_CONTROL_ALL = "NEGATIVE_CONTROL_ALL"
    COMBINED_CLASSIFICATION = "COMBINED_CLASSIFICATION"


class E20MetricStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE_FAILURE_ROWS = "INCOMPLETE_FAILURE_ROWS"
    NO_ANALYSABLE_ROWS = "NO_ANALYSABLE_ROWS"
    NO_PRISTINE_POSITIVES = "NO_PRISTINE_POSITIVES"
    SINGLE_CLASS_ONLY = "SINGLE_CLASS_ONLY"
    ZERO_TOKEN_EDIT_DENOMINATOR = "ZERO_TOKEN_EDIT_DENOMINATOR"


class E20MetricId(str, Enum):
    PRISTINE_TPR = "pristine_tpr"
    TRANSFORMED_TPR = "transformed_tpr"
    TPR_CHANGE = "transformed_minus_pristine_tpr"
    STANDARDIZED_MARGIN_DROP = "standardized_margin_drop"
    DECISION_LOSS_RATE = "conditional_pristine_positive_decision_loss"
    OBSERVATION_REPLACEMENT_RATIO = "observation_replacement_ratio"
    NORMALIZED_TOKEN_EDIT_RATE = "normalized_token_edit_rate"
    COVERAGE_EFFICIENCY = "observation_replacement_per_normalized_token_edit"
    ELIGIBILITY_RATE = "eligibility_rate"
    PRISTINE_FPR = "pristine_fpr"
    TRANSFORMED_FPR = "transformed_fpr"
    FPR_CHANGE = "transformed_minus_pristine_fpr"
    PRISTINE_ROC_AUC = "pristine_roc_auc"
    TRANSFORMED_ROC_AUC = "transformed_roc_auc"


@dataclass(frozen=True, slots=True)
class E20ConfidenceInterval:
    confidence_level: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        for name, value in (
            ("confidence_level", self.confidence_level),
            ("lower", self.lower),
            ("upper", self.upper),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.confidence_level <= 0.0 or self.confidence_level >= 1.0:
            raise ValueError("confidence_level must be strictly between 0 and 1")
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound cannot exceed upper bound")


@dataclass(frozen=True, slots=True)
class E20MetricEstimate:
    metric_id: E20MetricId
    population: E20AnalysisPopulation
    status: E20MetricStatus
    estimate: float | None
    confidence_interval: E20ConfidenceInterval | None
    expected_sample_count: int
    analysed_sample_count: int
    failure_sample_count: int
    estimate_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.metric_id, E20MetricId):
            raise TypeError("metric_id must be an E20MetricId")
        if not isinstance(self.population, E20AnalysisPopulation):
            raise TypeError("population must be an E20AnalysisPopulation")
        if not isinstance(self.status, E20MetricStatus):
            raise TypeError("status must be an E20MetricStatus")
        for name, value in (
            ("expected_sample_count", self.expected_sample_count),
            ("analysed_sample_count", self.analysed_sample_count),
            ("failure_sample_count", self.failure_sample_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.analysed_sample_count + self.failure_sample_count > self.expected_sample_count:
            raise ValueError("analysed and failure sample counts cannot exceed expected population")
        if self.estimate is None:
            if self.confidence_interval is not None:
                raise ValueError("missing estimate cannot have a confidence interval")
            if self.status not in (
                E20MetricStatus.NO_ANALYSABLE_ROWS,
                E20MetricStatus.NO_PRISTINE_POSITIVES,
                E20MetricStatus.SINGLE_CLASS_ONLY,
                E20MetricStatus.ZERO_TOKEN_EDIT_DENOMINATOR,
            ):
                raise ValueError("missing estimate requires a machine-readable no-estimate status")
        else:
            if isinstance(self.estimate, bool) or not isinstance(self.estimate, (int, float)):
                raise TypeError("estimate must be a real number or None")
            estimate = float(self.estimate)
            if not math.isfinite(estimate):
                raise ValueError("estimate must be finite")
            object.__setattr__(self, "estimate", estimate)
            if self.confidence_interval is None:
                raise ValueError("available estimate requires a confidence interval")
            if self.status not in (
                E20MetricStatus.COMPLETE,
                E20MetricStatus.INCOMPLETE_FAILURE_ROWS,
            ):
                raise ValueError("available estimate must be complete or explicitly incomplete due to failures")
        require_sha256("estimate_hash", self.estimate_hash)
        if self.estimate_hash != sha256_json(self._payload()):
            raise ValueError("estimate_hash does not match E20 metric estimate")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
            "metric_id": self.metric_id.value,
            "population": self.population.value,
            "status": self.status.value,
            "estimate": self.estimate,
            "confidence_interval": self.confidence_interval,
            "expected_sample_count": self.expected_sample_count,
            "analysed_sample_count": self.analysed_sample_count,
            "failure_sample_count": self.failure_sample_count,
        }


@dataclass(frozen=True, slots=True)
class E20ConditionAggregate:
    condition_id: str
    transform_condition_id: str
    calibration_bundle_hash: str
    target_fpr: float
    hypothesis_class: str
    expected_row_count: int
    outcome_row_count: int
    failure_row_count: int
    reason_counts: tuple[E20ReasonCount, ...]
    headline_eligible: bool
    metrics: tuple[E20MetricEstimate, ...]
    aggregate_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("transform_condition_id", self.transform_condition_id)
        require_sha256("calibration_bundle_hash", self.calibration_bundle_hash)
        if isinstance(self.target_fpr, bool) or not isinstance(self.target_fpr, (int, float)):
            raise TypeError("target_fpr must be a real number")
        target = float(self.target_fpr)
        if not math.isfinite(target) or target <= 0.0 or target >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        require_clean_string("hypothesis_class", self.hypothesis_class)
        for name, value in (
            ("expected_row_count", self.expected_row_count),
            ("outcome_row_count", self.outcome_row_count),
            ("failure_row_count", self.failure_row_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.outcome_row_count + self.failure_row_count != self.expected_row_count:
            raise ValueError("condition aggregate row counts do not close")
        if tuple(value.reason_code for value in self.reason_counts) != tuple(ExperimentReasonCode):
            raise ValueError("condition reason counts must contain every frozen reason code")
        if sum(value.count for value in self.reason_counts) != self.expected_row_count:
            raise ValueError("condition reason counts do not sum to expected rows")
        require_bool("headline_eligible", self.headline_eligible)
        if self.headline_eligible != (self.failure_row_count == 0):
            raise ValueError("headline eligibility must fail closed when any failure row exists")
        if not isinstance(self.metrics, tuple) or not self.metrics:
            raise TypeError("metrics must be a non-empty tuple")
        expected_metrics = tuple(sorted(self.metrics, key=lambda value: (value.population.value, value.metric_id.value)))
        if self.metrics != expected_metrics:
            raise ValueError("condition metrics must be canonically ordered")
        keys = tuple((value.population, value.metric_id) for value in self.metrics)
        if len(set(keys)) != len(keys):
            raise ValueError("condition metrics must be unique by population and metric")
        require_sha256("aggregate_hash", self.aggregate_hash)
        if self.aggregate_hash != sha256_json(self._payload()):
            raise ValueError("aggregate_hash does not match E20 condition aggregate")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "transform_condition_id": self.transform_condition_id,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "target_fpr": self.target_fpr,
            "hypothesis_class": self.hypothesis_class,
            "expected_row_count": self.expected_row_count,
            "outcome_row_count": self.outcome_row_count,
            "failure_row_count": self.failure_row_count,
            "reason_counts": self.reason_counts,
            "headline_eligible": self.headline_eligible,
            "metrics": self.metrics,
        }


@dataclass(frozen=True, slots=True)
class E20AggregateBundle:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    preregistration_hash: str
    bootstrap_plan_hash: str
    bootstrap_rng_version: str
    bootstrap_quantile_version: str
    conditions: tuple[E20ConditionAggregate, ...]
    aggregate_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_AGGREGATOR_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 aggregator algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("result_bundle_hash", self.result_bundle_hash),
            ("preregistration_hash", self.preregistration_hash),
            ("bootstrap_plan_hash", self.bootstrap_plan_hash),
            ("aggregate_hash", self.aggregate_hash),
        ):
            require_sha256(name, value)
        if self.bootstrap_rng_version != E20_BOOTSTRAP_RNG_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 bootstrap RNG version")
        if self.bootstrap_quantile_version != E20_BOOTSTRAP_QUANTILE_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 bootstrap quantile version")
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise TypeError("conditions must be a non-empty tuple")
        if any(not isinstance(value, E20ConditionAggregate) for value in self.conditions):
            raise TypeError("conditions must contain E20ConditionAggregate values")
        expected = tuple(sorted(self.conditions, key=lambda value: value.condition_id))
        if self.conditions != expected:
            raise ValueError("condition aggregates must be canonically ordered")
        if len({value.condition_id for value in self.conditions}) != len(self.conditions):
            raise ValueError("condition aggregate IDs must be unique")
        require_sha256("aggregate_hash", self.aggregate_hash)
        if self.aggregate_hash != sha256_json(self._payload()):
            raise ValueError("aggregate_hash does not match E20 aggregate bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "preregistration_hash": self.preregistration_hash,
            "bootstrap_plan_hash": self.bootstrap_plan_hash,
            "bootstrap_rng_version": self.bootstrap_rng_version,
            "bootstrap_quantile_version": self.bootstrap_quantile_version,
            "conditions": self.conditions,
        }


class _SplitMix64:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK64
        return (value ^ (value >> 31)) & _MASK64

    def randbelow(self, upper: int) -> int:
        require_int("upper", upper)
        if upper <= 0:
            raise ValueError("upper must be positive")
        limit = (1 << 64) - ((1 << 64) % upper)
        while True:
            value = self.next_u64()
            if value < limit:
                return value % upper


def _bootstrap_seed(execution_id: str, condition_id: str, metric_key: str, replicate: int) -> int:
    return int(
        sha256_json(
            {
                "rng_version": E20_BOOTSTRAP_RNG_ALGORITHM_VERSION,
                "execution_id": execution_id,
                "condition_id": condition_id,
                "metric_key": metric_key,
                "replicate": replicate,
            }
        )[:16],
        16,
    )


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile values must not be empty")
    if probability < 0.0 or probability > 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _stratum_key(sample: CorpusSample, fields: tuple[str, ...]) -> tuple[object, ...]:
    values: list[object] = []
    for field in fields:
        if field == "domain":
            values.append(sample.domain.value)
        elif field == "length":
            values.append(sample.target_length)
        elif field == "model":
            values.append((sample.model.model_id, sample.model.model_revision))
        elif field == "tokenizer":
            values.append((sample.model.tokenizer_id, sample.model.tokenizer_revision))
        else:
            raise ValueError(f"unsupported confirmatory bootstrap stratum field {field}")
    return tuple(values)


def _bootstrap_mean_ci(
    execution_id: str,
    condition_id: str,
    metric_key: str,
    values: tuple[tuple[CorpusSample, float], ...],
    preregistration: ConfirmatoryPreregistration,
) -> E20ConfidenceInterval:
    strata: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for sample, value in values:
        strata[_stratum_key(sample, preregistration.bootstrap_plan.stratify_by)].append(value)
    ordered_strata = tuple(sorted(strata.items(), key=lambda item: sha256_json(item[0])))
    replicates: list[float] = []
    total_count = len(values)
    for replicate in range(preregistration.bootstrap_plan.replicates):
        rng = _SplitMix64(_bootstrap_seed(execution_id, condition_id, metric_key, replicate))
        total = 0.0
        for _, stratum_values in ordered_strata:
            size = len(stratum_values)
            for _ in range(size):
                total += stratum_values[rng.randbelow(size)]
        replicates.append(total / total_count)
    alpha = 1.0 - preregistration.bootstrap_plan.confidence_level
    return E20ConfidenceInterval(
        preregistration.bootstrap_plan.confidence_level,
        _quantile(replicates, alpha / 2.0),
        _quantile(replicates, 1.0 - alpha / 2.0),
    )


def _roc_auc(positive_scores: tuple[float, ...], negative_scores: tuple[float, ...]) -> float:
    if not positive_scores or not negative_scores:
        raise ValueError("ROC-AUC requires both positive and negative scores")
    wins = 0.0
    for positive in positive_scores:
        for negative in negative_scores:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positive_scores) * len(negative_scores))


def _bootstrap_auc_ci(
    execution_id: str,
    condition_id: str,
    metric_key: str,
    positives: tuple[tuple[CorpusSample, float], ...],
    negatives: tuple[tuple[CorpusSample, float], ...],
    preregistration: ConfirmatoryPreregistration,
) -> E20ConfidenceInterval:
    grouped: dict[tuple[str, tuple[object, ...]], list[float]] = defaultdict(list)
    for sample, value in positives:
        grouped[("positive", _stratum_key(sample, preregistration.bootstrap_plan.stratify_by))].append(value)
    for sample, value in negatives:
        grouped[("negative", _stratum_key(sample, preregistration.bootstrap_plan.stratify_by))].append(value)
    ordered = tuple(sorted(grouped.items(), key=lambda item: sha256_json(item[0])))
    replicates: list[float] = []
    for replicate in range(preregistration.bootstrap_plan.replicates):
        rng = _SplitMix64(_bootstrap_seed(execution_id, condition_id, metric_key, replicate))
        sampled_positive: list[float] = []
        sampled_negative: list[float] = []
        for (label, _), scores in ordered:
            destination = sampled_positive if label == "positive" else sampled_negative
            size = len(scores)
            for _ in range(size):
                destination.append(scores[rng.randbelow(size)])
        replicates.append(_roc_auc(tuple(sampled_positive), tuple(sampled_negative)))
    alpha = 1.0 - preregistration.bootstrap_plan.confidence_level
    return E20ConfidenceInterval(
        preregistration.bootstrap_plan.confidence_level,
        _quantile(replicates, alpha / 2.0),
        _quantile(replicates, 1.0 - alpha / 2.0),
    )


def _metric_estimate(
    execution_id: str,
    condition_id: str,
    metric_id: E20MetricId,
    population: E20AnalysisPopulation,
    values: tuple[tuple[CorpusSample, float], ...],
    expected_count: int,
    failure_count: int,
    preregistration: ConfirmatoryPreregistration,
    empty_status: E20MetricStatus = E20MetricStatus.NO_ANALYSABLE_ROWS,
) -> E20MetricEstimate:
    if not values:
        payload = {
            "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
            "metric_id": metric_id.value,
            "population": population.value,
            "status": empty_status.value,
            "estimate": None,
            "confidence_interval": None,
            "expected_sample_count": expected_count,
            "analysed_sample_count": 0,
            "failure_sample_count": failure_count,
        }
        return E20MetricEstimate(
            metric_id,
            population,
            empty_status,
            None,
            None,
            expected_count,
            0,
            failure_count,
            sha256_json(payload),
        )
    estimate = math.fsum(value for _, value in values) / len(values)
    status = E20MetricStatus.COMPLETE if failure_count == 0 else E20MetricStatus.INCOMPLETE_FAILURE_ROWS
    interval = _bootstrap_mean_ci(
        execution_id,
        condition_id,
        f"{population.value}:{metric_id.value}",
        values,
        preregistration,
    )
    payload = {
        "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
        "metric_id": metric_id.value,
        "population": population.value,
        "status": status.value,
        "estimate": estimate,
        "confidence_interval": interval,
        "expected_sample_count": expected_count,
        "analysed_sample_count": len(values),
        "failure_sample_count": failure_count,
    }
    return E20MetricEstimate(
        metric_id,
        population,
        status,
        estimate,
        interval,
        expected_count,
        len(values),
        failure_count,
        sha256_json(payload),
    )


def _coverage_efficiency_estimate(
    execution_id: str,
    condition_id: str,
    population: E20AnalysisPopulation,
    rows: tuple[E20OutcomeRow, ...],
    sample_by_id: dict[str, CorpusSample],
    expected_count: int,
    failure_count: int,
    preregistration: ConfirmatoryPreregistration,
) -> E20MetricEstimate:
    if not rows:
        return _metric_estimate(
            execution_id,
            condition_id,
            E20MetricId.COVERAGE_EFFICIENCY,
            population,
            (),
            expected_count,
            failure_count,
            preregistration,
        )
    if any(row.fidelity.token_edit_distance == 0 for row in rows):
        return _metric_estimate(
            execution_id,
            condition_id,
            E20MetricId.COVERAGE_EFFICIENCY,
            population,
            (),
            expected_count,
            failure_count,
            preregistration,
            E20MetricStatus.ZERO_TOKEN_EDIT_DENOMINATOR,
        )
    values = tuple(
        (
            sample_by_id[row.identity.sample_id],
            (row.observation.replaced_count / row.observation.original_valid_count)
            / (row.fidelity.token_edit_distance / row.text.source_token_count),
        )
        for row in rows
    )
    return _metric_estimate(
        execution_id,
        condition_id,
        E20MetricId.COVERAGE_EFFICIENCY,
        population,
        values,
        expected_count,
        failure_count,
        preregistration,
    )


def _auc_estimate(
    execution_id: str,
    condition_id: str,
    metric_id: E20MetricId,
    positives: tuple[tuple[CorpusSample, float], ...],
    negatives: tuple[tuple[CorpusSample, float], ...],
    expected_count: int,
    failure_count: int,
    preregistration: ConfirmatoryPreregistration,
) -> E20MetricEstimate:
    if not positives or not negatives:
        payload = {
            "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
            "metric_id": metric_id.value,
            "population": E20AnalysisPopulation.COMBINED_CLASSIFICATION.value,
            "status": E20MetricStatus.SINGLE_CLASS_ONLY.value,
            "estimate": None,
            "confidence_interval": None,
            "expected_sample_count": expected_count,
            "analysed_sample_count": len(positives) + len(negatives),
            "failure_sample_count": failure_count,
        }
        return E20MetricEstimate(
            metric_id,
            E20AnalysisPopulation.COMBINED_CLASSIFICATION,
            E20MetricStatus.SINGLE_CLASS_ONLY,
            None,
            None,
            expected_count,
            len(positives) + len(negatives),
            failure_count,
            sha256_json(payload),
        )
    estimate = _roc_auc(
        tuple(value for _, value in positives),
        tuple(value for _, value in negatives),
    )
    status = E20MetricStatus.COMPLETE if failure_count == 0 else E20MetricStatus.INCOMPLETE_FAILURE_ROWS
    interval = _bootstrap_auc_ci(
        execution_id,
        condition_id,
        metric_id.value,
        positives,
        negatives,
        preregistration,
    )
    payload = {
        "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
        "metric_id": metric_id.value,
        "population": E20AnalysisPopulation.COMBINED_CLASSIFICATION.value,
        "status": status.value,
        "estimate": estimate,
        "confidence_interval": interval,
        "expected_sample_count": expected_count,
        "analysed_sample_count": len(positives) + len(negatives),
        "failure_sample_count": failure_count,
    }
    return E20MetricEstimate(
        metric_id,
        E20AnalysisPopulation.COMBINED_CLASSIFICATION,
        status,
        estimate,
        interval,
        expected_count,
        len(positives) + len(negatives),
        failure_count,
        sha256_json(payload),
    )


def _condition_aggregate(
    condition: E20Condition,
    result_bundle: E20ResultBundle,
    corpus_manifest: CorpusManifest,
    preregistration: ConfirmatoryPreregistration,
) -> E20ConditionAggregate:
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    outcomes = tuple(
        value for value in result_bundle.outcome_rows if value.identity.condition_id == condition.condition_id
    )
    failures = tuple(
        value for value in result_bundle.failure_rows if value.identity.condition_id == condition.condition_id
    )
    watermarked_outcomes = tuple(
        value for value in outcomes if sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
    )
    negative_outcomes = tuple(
        value for value in outcomes if sample_by_id[value.identity.sample_id].label is WatermarkLabel.UNWATERMARKED
    )
    watermarked_failures = tuple(
        value for value in failures if sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
    )
    negative_failures = tuple(
        value for value in failures if sample_by_id[value.identity.sample_id].label is WatermarkLabel.UNWATERMARKED
    )
    watermarked_expected = len(watermarked_outcomes) + len(watermarked_failures)
    negative_expected = len(negative_outcomes) + len(negative_failures)
    metrics: list[E20MetricEstimate] = []

    def paired_values(rows: tuple[E20OutcomeRow, ...], function):
        return tuple((sample_by_id[row.identity.sample_id], float(function(row))) for row in rows)

    policy_population = E20AnalysisPopulation.POLICY_ALL
    metrics.extend(
        (
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.PRISTINE_TPR, policy_population, paired_values(watermarked_outcomes, lambda row: row.detector.pristine_decision), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.TRANSFORMED_TPR, policy_population, paired_values(watermarked_outcomes, lambda row: row.detector.transformed_decision), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.TPR_CHANGE, policy_population, paired_values(watermarked_outcomes, lambda row: int(row.detector.transformed_decision) - int(row.detector.pristine_decision)), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.STANDARDIZED_MARGIN_DROP, policy_population, paired_values(watermarked_outcomes, lambda row: row.detector.pristine_standardized_margin - row.detector.transformed_standardized_margin), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.OBSERVATION_REPLACEMENT_RATIO, policy_population, paired_values(watermarked_outcomes, lambda row: row.observation.replaced_count / row.observation.original_valid_count), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.NORMALIZED_TOKEN_EDIT_RATE, policy_population, paired_values(watermarked_outcomes, lambda row: row.fidelity.token_edit_distance / row.text.source_token_count), watermarked_expected, len(watermarked_failures), preregistration),
            _coverage_efficiency_estimate(result_bundle.execution_id, condition.condition_id, policy_population, watermarked_outcomes, sample_by_id, watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.ELIGIBILITY_RATE, policy_population, paired_values(watermarked_outcomes, lambda row: row.transform.eligible), watermarked_expected, len(watermarked_failures), preregistration),
        )
    )
    eligible = tuple(row for row in watermarked_outcomes if row.transform.eligible)
    eligible_population = E20AnalysisPopulation.ELIGIBLE_ONLY
    metrics.extend(
        (
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.TPR_CHANGE, eligible_population, paired_values(eligible, lambda row: int(row.detector.transformed_decision) - int(row.detector.pristine_decision)), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.STANDARDIZED_MARGIN_DROP, eligible_population, paired_values(eligible, lambda row: row.detector.pristine_standardized_margin - row.detector.transformed_standardized_margin), watermarked_expected, len(watermarked_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.OBSERVATION_REPLACEMENT_RATIO, eligible_population, paired_values(eligible, lambda row: row.observation.replaced_count / row.observation.original_valid_count), watermarked_expected, len(watermarked_failures), preregistration),
            _coverage_efficiency_estimate(result_bundle.execution_id, condition.condition_id, eligible_population, eligible, sample_by_id, watermarked_expected, len(watermarked_failures), preregistration),
        )
    )
    pristine_positive = tuple(row for row in watermarked_outcomes if row.detector.pristine_decision)
    metrics.append(
        _metric_estimate(
            result_bundle.execution_id,
            condition.condition_id,
            E20MetricId.DECISION_LOSS_RATE,
            E20AnalysisPopulation.PRISTINE_POSITIVE,
            paired_values(pristine_positive, lambda row: not row.detector.transformed_decision),
            watermarked_expected,
            len(watermarked_failures),
            preregistration,
            E20MetricStatus.NO_PRISTINE_POSITIVES,
        )
    )
    negative_population = E20AnalysisPopulation.NEGATIVE_CONTROL_ALL
    metrics.extend(
        (
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.PRISTINE_FPR, negative_population, paired_values(negative_outcomes, lambda row: row.detector.pristine_decision), negative_expected, len(negative_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.TRANSFORMED_FPR, negative_population, paired_values(negative_outcomes, lambda row: row.detector.transformed_decision), negative_expected, len(negative_failures), preregistration),
            _metric_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.FPR_CHANGE, negative_population, paired_values(negative_outcomes, lambda row: int(row.detector.transformed_decision) - int(row.detector.pristine_decision)), negative_expected, len(negative_failures), preregistration),
        )
    )
    combined_expected = watermarked_expected + negative_expected
    combined_failures = len(watermarked_failures) + len(negative_failures)
    metrics.extend(
        (
            _auc_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.PRISTINE_ROC_AUC, paired_values(watermarked_outcomes, lambda row: row.detector.pristine_raw_score), paired_values(negative_outcomes, lambda row: row.detector.pristine_raw_score), combined_expected, combined_failures, preregistration),
            _auc_estimate(result_bundle.execution_id, condition.condition_id, E20MetricId.TRANSFORMED_ROC_AUC, paired_values(watermarked_outcomes, lambda row: row.detector.transformed_raw_score), paired_values(negative_outcomes, lambda row: row.detector.transformed_raw_score), combined_expected, combined_failures, preregistration),
        )
    )
    counts: Counter[ExperimentReasonCode] = Counter()
    for row in outcomes:
        counts[row.fidelity.reason_codes[0]] += 1
    for row in failures:
        counts[row.reason_code] += 1
    reason_counts = tuple(E20ReasonCount(reason, counts[reason]) for reason in ExperimentReasonCode)
    ordered_metrics = tuple(sorted(metrics, key=lambda value: (value.population.value, value.metric_id.value)))
    payload = {
        "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
        "condition_id": condition.condition_id,
        "transform_condition_id": condition.transform_condition_id,
        "calibration_bundle_hash": condition.calibration_bundle_hash,
        "target_fpr": condition.target_fpr,
        "hypothesis_class": condition.hypothesis_class,
        "expected_row_count": len(outcomes) + len(failures),
        "outcome_row_count": len(outcomes),
        "failure_row_count": len(failures),
        "reason_counts": reason_counts,
        "headline_eligible": len(failures) == 0,
        "metrics": ordered_metrics,
    }
    return E20ConditionAggregate(
        condition.condition_id,
        condition.transform_condition_id,
        condition.calibration_bundle_hash,
        condition.target_fpr,
        condition.hypothesis_class,
        len(outcomes) + len(failures),
        len(outcomes),
        len(failures),
        reason_counts,
        len(failures) == 0,
        ordered_metrics,
        sha256_json(payload),
    )


def build_e20_aggregate_bundle(
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization,
) -> E20AggregateBundle:
    verify_e20_result_bundle(
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    conditions = tuple(
        _condition_aggregate(condition, result_bundle, corpus_manifest, preregistration)
        for condition in condition_plan.conditions
    )
    ordered = tuple(sorted(conditions, key=lambda value: value.condition_id))
    payload = {
        "algorithm_version": E20_AGGREGATOR_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "bootstrap_plan_hash": preregistration.bootstrap_plan.plan_hash,
        "bootstrap_rng_version": E20_BOOTSTRAP_RNG_ALGORITHM_VERSION,
        "bootstrap_quantile_version": E20_BOOTSTRAP_QUANTILE_ALGORITHM_VERSION,
        "conditions": ordered,
    }
    return E20AggregateBundle(
        E20_AGGREGATOR_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        preregistration.preregistration_hash,
        preregistration.bootstrap_plan.plan_hash,
        E20_BOOTSTRAP_RNG_ALGORITHM_VERSION,
        E20_BOOTSTRAP_QUANTILE_ALGORITHM_VERSION,
        ordered,
        sha256_json(payload),
    )
