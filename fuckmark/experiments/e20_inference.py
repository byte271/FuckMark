from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, WatermarkLabel
from ..hashing import sha256_json
from .confirmatory import (
    ConfirmatoryPreregistration,
    ConfirmatoryPrimaryOutcome,
    MultipleTestingMethod,
)
from .e20_aggregate import (
    E20AggregateBundle,
    E20AnalysisPopulation,
    E20MetricId,
    E20MetricStatus,
)
from .e20_aggregate_verification import verify_e20_aggregate_bundle
from .e20_bundle import E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization


E20_INFERENCE_ALGORITHM_VERSION = "e20-inference-v2"
E20_DECISION_TEST_ALGORITHM_VERSION = "paired-exact-mcnemar-binomial-logcomb-v2"
E20_CONTINUOUS_TEST_ALGORITHM_VERSION = "paired-sign-flip-splitmix64-v1"
E20_SIGN_FLIP_REPLICATES = 10_000
_MASK64 = (1 << 64) - 1
_LOG_TWO = math.log(2.0)
_MIN_POSITIVE_FLOAT = math.nextafter(0.0, 1.0)
_LOG_MIN_POSITIVE_FLOAT = math.log(_MIN_POSITIVE_FLOAT)


class E20InferenceStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE_FAILURE_ROWS = "INCOMPLETE_FAILURE_ROWS"
    UNSUPPORTED_PRIMARY_OUTCOME = "UNSUPPORTED_PRIMARY_OUTCOME"


@dataclass(frozen=True, slots=True)
class E20HypothesisInference:
    condition_id: str
    hypothesis_id: str
    primary_outcome: ConfirmatoryPrimaryOutcome
    status: E20InferenceStatus
    effect_estimate: float | None
    test_algorithm_version: str | None
    raw_p_value: float | None
    holm_adjusted_p_value: float | None
    family_size: int
    inference_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("hypothesis_id", self.hypothesis_id)
        if not isinstance(self.primary_outcome, ConfirmatoryPrimaryOutcome):
            raise TypeError("primary_outcome must be a ConfirmatoryPrimaryOutcome")
        if not isinstance(self.status, E20InferenceStatus):
            raise TypeError("status must be an E20InferenceStatus")
        require_int("family_size", self.family_size)
        if self.family_size <= 0:
            raise ValueError("family_size must be positive")
        values = (self.effect_estimate, self.raw_p_value, self.holm_adjusted_p_value)
        if self.status is E20InferenceStatus.COMPLETE:
            if self.test_algorithm_version is None:
                raise ValueError("complete inference requires a test algorithm version")
            require_clean_string("test_algorithm_version", self.test_algorithm_version)
            if any(value is None for value in values):
                raise ValueError("complete inference requires effect and p-values")
            effect = float(self.effect_estimate)
            raw = float(self.raw_p_value)
            adjusted = float(self.holm_adjusted_p_value)
            if not math.isfinite(effect):
                raise ValueError("effect_estimate must be finite")
            if not (0.0 <= raw <= 1.0 and 0.0 <= adjusted <= 1.0):
                raise ValueError("p-values must be in [0, 1]")
            if adjusted + 1e-15 < raw:
                raise ValueError("Holm adjusted p-value cannot be smaller than raw p-value")
        else:
            if self.test_algorithm_version is not None or any(value is not None for value in values):
                raise ValueError("incomplete or unsupported inference cannot contain effect/test p-values")
        require_sha256("inference_hash", self.inference_hash)
        if self.inference_hash != sha256_json(self._payload()):
            raise ValueError("inference_hash does not match E20 hypothesis inference")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_INFERENCE_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "hypothesis_id": self.hypothesis_id,
            "primary_outcome": self.primary_outcome.value,
            "status": self.status.value,
            "effect_estimate": self.effect_estimate,
            "test_algorithm_version": self.test_algorithm_version,
            "raw_p_value": self.raw_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "family_size": self.family_size,
        }


@dataclass(frozen=True, slots=True)
class E20InferenceBundle:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    aggregate_hash: str
    preregistration_hash: str
    multiple_testing_method: MultipleTestingMethod
    family_size: int
    inferences: tuple[E20HypothesisInference, ...]
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_INFERENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 inference algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("result_bundle_hash", self.result_bundle_hash),
            ("aggregate_hash", self.aggregate_hash),
            ("preregistration_hash", self.preregistration_hash),
            ("bundle_hash", self.bundle_hash),
        ):
            require_sha256(name, value)
        if self.multiple_testing_method is not MultipleTestingMethod.HOLM_BONFERRONI:
            raise ValueError("E20 inference v2 requires the preregistered Holm-Bonferroni method")
        require_int("family_size", self.family_size)
        if self.family_size <= 0:
            raise ValueError("family_size must be positive")
        if not isinstance(self.inferences, tuple) or not self.inferences:
            raise TypeError("inferences must be a non-empty tuple")
        if any(not isinstance(value, E20HypothesisInference) for value in self.inferences):
            raise TypeError("inferences must contain E20HypothesisInference values")
        expected = tuple(sorted(self.inferences, key=lambda value: (value.condition_id, value.hypothesis_id)))
        if self.inferences != expected:
            raise ValueError("E20 inferences must be canonically ordered")
        keys = tuple((value.condition_id, value.hypothesis_id) for value in self.inferences)
        if len(set(keys)) != len(keys):
            raise ValueError("E20 inference cells must be unique")
        if len(self.inferences) != self.family_size:
            raise ValueError("E20 inference family size must equal the preregistered condition-hypothesis cell count")
        if any(value.family_size != self.family_size for value in self.inferences):
            raise ValueError("all inference cells must carry the same frozen family size")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E20 inference bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "aggregate_hash": self.aggregate_hash,
            "preregistration_hash": self.preregistration_hash,
            "multiple_testing_method": self.multiple_testing_method.value,
            "family_size": self.family_size,
            "inferences": self.inferences,
        }


def _exact_binomial_two_sided(successes: int, trials: int) -> float:
    require_int("successes", successes)
    require_int("trials", trials)
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("invalid exact binomial count")
    if trials == 0 or successes * 2 >= trials:
        return 1.0
    log_probability_at_successes = math.log(math.comb(trials, successes)) - trials * _LOG_TWO
    scaled_tail = 1.0
    scaled_term = 1.0
    for index in range(successes, 0, -1):
        scaled_term *= index / (trials - index + 1)
        scaled_tail += scaled_term
    log_two_sided = log_probability_at_successes + math.log(scaled_tail) + _LOG_TWO
    if log_two_sided >= 0.0:
        return 1.0
    if log_two_sided <= _LOG_MIN_POSITIVE_FLOAT:
        return _MIN_POSITIVE_FLOAT
    return math.exp(log_two_sided)


def _mcnemar_p_value(rows) -> float:
    losses = sum(row.detector.pristine_decision and not row.detector.transformed_decision for row in rows)
    gains = sum((not row.detector.pristine_decision) and row.detector.transformed_decision for row in rows)
    return _exact_binomial_two_sided(min(losses, gains), losses + gains)


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


def _sign_flip_p_value(
    execution_id: str,
    condition_id: str,
    hypothesis_id: str,
    differences: tuple[float, ...],
) -> float:
    if not differences:
        return 1.0
    observed = abs(math.fsum(differences) / len(differences))
    extreme = 0
    for replicate in range(E20_SIGN_FLIP_REPLICATES):
        seed = int(
            sha256_json(
                {
                    "algorithm_version": E20_CONTINUOUS_TEST_ALGORITHM_VERSION,
                    "execution_id": execution_id,
                    "condition_id": condition_id,
                    "hypothesis_id": hypothesis_id,
                    "replicate": replicate,
                }
            )[:16],
            16,
        )
        rng = _SplitMix64(seed)
        flipped = math.fsum(
            value if (rng.next_u64() & 1) else -value for value in differences
        ) / len(differences)
        if abs(flipped) + 1e-15 >= observed:
            extreme += 1
    return (extreme + 1) / (E20_SIGN_FLIP_REPLICATES + 1)


def _metric_effect(aggregate_condition, metric_id: E20MetricId) -> float | None:
    candidates = tuple(
        value
        for value in aggregate_condition.metrics
        if value.population is E20AnalysisPopulation.POLICY_ALL and value.metric_id is metric_id
    )
    if len(candidates) != 1:
        raise ValueError("confirmatory aggregate is missing the required primary metric")
    metric = candidates[0]
    return metric.estimate if metric.status is E20MetricStatus.COMPLETE else None


def _raw_inference(condition, hypothesis, aggregate_condition, rows, execution_id: str):
    if not aggregate_condition.headline_eligible:
        return (E20InferenceStatus.INCOMPLETE_FAILURE_ROWS, None, None, None)
    if hypothesis.primary_outcome is ConfirmatoryPrimaryOutcome.TPR_CHANGE_AT_ONE_PERCENT_FPR:
        effect = _metric_effect(aggregate_condition, E20MetricId.TPR_CHANGE)
        if effect is None:
            return (E20InferenceStatus.INCOMPLETE_FAILURE_ROWS, None, None, None)
        return (
            E20InferenceStatus.COMPLETE,
            effect,
            E20_DECISION_TEST_ALGORITHM_VERSION,
            _mcnemar_p_value(rows),
        )
    if hypothesis.primary_outcome is ConfirmatoryPrimaryOutcome.STANDARDIZED_MARGIN_DROP:
        effect = _metric_effect(aggregate_condition, E20MetricId.STANDARDIZED_MARGIN_DROP)
        if effect is None:
            return (E20InferenceStatus.INCOMPLETE_FAILURE_ROWS, None, None, None)
        differences = tuple(
            row.detector.pristine_standardized_margin - row.detector.transformed_standardized_margin
            for row in rows
        )
        return (
            E20InferenceStatus.COMPLETE,
            effect,
            E20_CONTINUOUS_TEST_ALGORITHM_VERSION,
            _sign_flip_p_value(
                execution_id,
                condition.condition_id,
                hypothesis.hypothesis_id,
                differences,
            ),
        )
    return (E20InferenceStatus.UNSUPPORTED_PRIMARY_OUTCOME, None, None, None)


def _holm_adjust(raw_cells, family_size: int) -> dict[int, float]:
    complete = sorted(
        (
            (index, value[3])
            for index, value in enumerate(raw_cells)
            if value[0] is E20InferenceStatus.COMPLETE
        ),
        key=lambda item: (item[1], item[0]),
    )
    adjusted: dict[int, float] = {}
    running = 0.0
    for rank, (index, p_value) in enumerate(complete, start=1):
        candidate = min(1.0, (family_size - rank + 1) * p_value)
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def build_e20_inference_bundle(
    result_bundle: E20ResultBundle,
    aggregate: E20AggregateBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> E20InferenceBundle:
    verify_e20_aggregate_bundle(
        aggregate,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    if preregistration.multiple_testing_method is not MultipleTestingMethod.HOLM_BONFERRONI:
        raise ValueError("E20 inference requires preregistered Holm-Bonferroni correction")
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    aggregate_by_condition = {value.condition_id: value for value in aggregate.conditions}
    hypotheses = {value.hypothesis_id: value for value in preregistration.hypotheses}
    cells = []
    for condition in condition_plan.conditions:
        hypothesis = hypotheses[condition.hypothesis_class]
        rows = tuple(
            value
            for value in result_bundle.outcome_rows
            if value.identity.condition_id == condition.condition_id
            and sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
        )
        cells.append((condition, hypothesis, aggregate_by_condition[condition.condition_id], rows))
    family_size = len(cells)
    raw = tuple(
        _raw_inference(
            condition,
            hypothesis,
            aggregate_condition,
            rows,
            result_bundle.execution_id,
        )
        for condition, hypothesis, aggregate_condition, rows in cells
    )
    adjusted = _holm_adjust(raw, family_size)
    inferences: list[E20HypothesisInference] = []
    for index, ((condition, hypothesis, _, _), values) in enumerate(zip(cells, raw)):
        status, effect, test_version, p_value = values
        adjusted_p = adjusted.get(index)
        payload = {
            "algorithm_version": E20_INFERENCE_ALGORITHM_VERSION,
            "condition_id": condition.condition_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "primary_outcome": hypothesis.primary_outcome.value,
            "status": status.value,
            "effect_estimate": effect,
            "test_algorithm_version": test_version,
            "raw_p_value": p_value,
            "holm_adjusted_p_value": adjusted_p,
            "family_size": family_size,
        }
        inferences.append(
            E20HypothesisInference(
                condition.condition_id,
                hypothesis.hypothesis_id,
                hypothesis.primary_outcome,
                status,
                effect,
                test_version,
                p_value,
                adjusted_p,
                family_size,
                sha256_json(payload),
            )
        )
    ordered = tuple(sorted(inferences, key=lambda value: (value.condition_id, value.hypothesis_id)))
    payload = {
        "algorithm_version": E20_INFERENCE_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "aggregate_hash": aggregate.aggregate_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "multiple_testing_method": preregistration.multiple_testing_method.value,
        "family_size": family_size,
        "inferences": ordered,
    }
    return E20InferenceBundle(
        E20_INFERENCE_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        aggregate.aggregate_hash,
        preregistration.preregistration_hash,
        preregistration.multiple_testing_method,
        family_size,
        ordered,
        sha256_json(payload),
    )


def verify_e20_inference_bundle(
    inference: E20InferenceBundle,
    result_bundle: E20ResultBundle,
    aggregate: E20AggregateBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> None:
    if not isinstance(inference, E20InferenceBundle):
        raise TypeError("inference must be an E20InferenceBundle")
    expected = build_e20_inference_bundle(
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    if inference != expected:
        raise ValueError(
            "E20 inference bundle does not replay exactly from sealed results and preregistered analysis"
        )
