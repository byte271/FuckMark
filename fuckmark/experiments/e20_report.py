from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_int, require_sha256
from ..corpus import CorpusManifest
from ..detectors import ExactBinomialInterval, exact_binomial_interval
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_detector_readiness import (
    ConfirmatoryDetectorReadinessReport,
    verify_confirmatory_detector_readiness,
)
from .e20_aggregate import (
    E20AggregateBundle,
    E20AnalysisPopulation,
    E20MetricId,
    E20MetricStatus,
)
from .e20_aggregate_verification import verify_e20_aggregate_bundle
from .e20_bundle import E20ReasonCount, E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization
from .e20_inference import E20InferenceBundle, E20InferenceStatus, verify_e20_inference_bundle
from .e20_key_analysis import E20KeyAnalysisBundle, verify_e20_key_analysis_bundle
from .e20_rows import E20HumanFidelityStatus, ExperimentReasonCode


E20_REPORT_ALGORITHM_VERSION = "e20-report-v4"


class E20ReportStatus(str, Enum):
    BLOCKED_DETECTOR_READINESS = "BLOCKED_DETECTOR_READINESS"
    BLOCKED_FIDELITY_AUDIT = "BLOCKED_FIDELITY_AUDIT"
    INCOMPLETE_FAILURE_ROWS = "INCOMPLETE_FAILURE_ROWS"
    INCOMPLETE_INFERENCE = "INCOMPLETE_INFERENCE"
    INCOMPLETE_PRIMARY_METRICS = "INCOMPLETE_PRIMARY_METRICS"
    CONFIRMATORY_EVALUABLE = "CONFIRMATORY_EVALUABLE"


@dataclass(frozen=True, slots=True)
class E20HumanFidelitySummary:
    unique_transform_count: int
    reviewed_transform_count: int
    equivalent_or_minor_count: int
    material_change_count: int
    cannot_judge_count: int
    hard_invariant_failure_count: int
    equivalent_or_minor_rate: float | None
    equivalent_or_minor_interval: ExactBinomialInterval | None
    gate_passed: bool
    summary_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("unique_transform_count", self.unique_transform_count),
            ("reviewed_transform_count", self.reviewed_transform_count),
            ("equivalent_or_minor_count", self.equivalent_or_minor_count),
            ("material_change_count", self.material_change_count),
            ("cannot_judge_count", self.cannot_judge_count),
            ("hard_invariant_failure_count", self.hard_invariant_failure_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.reviewed_transform_count != (
            self.equivalent_or_minor_count
            + self.material_change_count
            + self.cannot_judge_count
        ):
            raise ValueError("human fidelity reviewed counts do not close")
        if self.reviewed_transform_count > self.unique_transform_count:
            raise ValueError("human fidelity reviewed transform count cannot exceed unique transform count")
        if self.reviewed_transform_count == 0:
            if self.equivalent_or_minor_rate is not None or self.equivalent_or_minor_interval is not None:
                raise ValueError("unreviewed fidelity summary cannot contain rate or interval")
        else:
            if self.equivalent_or_minor_rate is None:
                raise ValueError("reviewed transforms require equivalent-or-minor rate")
            if isinstance(self.equivalent_or_minor_rate, bool) or not isinstance(
                self.equivalent_or_minor_rate, (int, float)
            ):
                raise TypeError("equivalent_or_minor_rate must be a real number or None")
            rate = float(self.equivalent_or_minor_rate)
            if not math.isfinite(rate) or rate < 0.0 or rate > 1.0:
                raise ValueError("equivalent_or_minor_rate must be in [0, 1]")
            object.__setattr__(self, "equivalent_or_minor_rate", rate)
            if not isinstance(self.equivalent_or_minor_interval, ExactBinomialInterval):
                raise TypeError("reviewed transforms require an exact binomial confidence interval")
            if not math.isclose(
                self.equivalent_or_minor_interval.confidence_level,
                0.95,
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                raise ValueError("human fidelity confidence interval must use 95% confidence")
            if not (
                self.equivalent_or_minor_interval.lower
                <= rate
                <= self.equivalent_or_minor_interval.upper
            ):
                raise ValueError("human fidelity rate must lie inside its exact confidence interval")
        require_bool("gate_passed", self.gate_passed)
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match E20 human fidelity summary")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
            "unique_transform_count": self.unique_transform_count,
            "reviewed_transform_count": self.reviewed_transform_count,
            "equivalent_or_minor_count": self.equivalent_or_minor_count,
            "material_change_count": self.material_change_count,
            "cannot_judge_count": self.cannot_judge_count,
            "hard_invariant_failure_count": self.hard_invariant_failure_count,
            "equivalent_or_minor_rate": self.equivalent_or_minor_rate,
            "equivalent_or_minor_interval": self.equivalent_or_minor_interval,
            "gate_passed": self.gate_passed,
        }


@dataclass(frozen=True, slots=True)
class E20HeadlineCondition:
    condition_id: str
    calibration_bundle_hash: str
    target_fpr: float
    expected_row_count: int
    failure_row_count: int
    tpr_change: float | None
    tpr_change_ci_lower: float | None
    tpr_change_ci_upper: float | None
    transformed_tpr: float | None
    standardized_margin_drop: float | None
    coverage_efficiency: float | None
    decision_loss_rate: float | None
    holm_adjusted_p_value: float | None
    key_summary_hash: str
    headline_eligible: bool
    headline_hash: str

    def __post_init__(self) -> None:
        require_sha256("calibration_bundle_hash", self.calibration_bundle_hash)
        require_int("expected_row_count", self.expected_row_count)
        require_int("failure_row_count", self.failure_row_count)
        if (
            self.expected_row_count <= 0
            or self.failure_row_count < 0
            or self.failure_row_count > self.expected_row_count
        ):
            raise ValueError("invalid E20 headline row counts")
        if isinstance(self.target_fpr, bool) or not isinstance(self.target_fpr, (int, float)):
            raise TypeError("target_fpr must be a real number")
        target = float(self.target_fpr)
        if not math.isfinite(target) or target <= 0.0 or target >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        for name in (
            "tpr_change",
            "tpr_change_ci_lower",
            "tpr_change_ci_upper",
            "transformed_tpr",
            "standardized_margin_drop",
            "coverage_efficiency",
            "decision_loss_rate",
            "holm_adjusted_p_value",
        ):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} must be a real number or None")
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"{name} must be finite")
                object.__setattr__(self, name, number)
        require_sha256("key_summary_hash", self.key_summary_hash)
        require_bool("headline_eligible", self.headline_eligible)
        if self.headline_eligible:
            required = (
                self.tpr_change,
                self.tpr_change_ci_lower,
                self.tpr_change_ci_upper,
                self.transformed_tpr,
                self.standardized_margin_drop,
                self.coverage_efficiency,
                self.decision_loss_rate,
                self.holm_adjusted_p_value,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "headline-eligible condition requires complete primary effects, interval, and inference fields"
                )
            if self.failure_row_count != 0:
                raise ValueError("headline-eligible condition cannot contain failure rows")
        require_sha256("headline_hash", self.headline_hash)
        if self.headline_hash != sha256_json(self._payload()):
            raise ValueError("headline_hash does not match E20 headline condition")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "target_fpr": self.target_fpr,
            "expected_row_count": self.expected_row_count,
            "failure_row_count": self.failure_row_count,
            "tpr_change": self.tpr_change,
            "tpr_change_ci_lower": self.tpr_change_ci_lower,
            "tpr_change_ci_upper": self.tpr_change_ci_upper,
            "transformed_tpr": self.transformed_tpr,
            "standardized_margin_drop": self.standardized_margin_drop,
            "coverage_efficiency": self.coverage_efficiency,
            "decision_loss_rate": self.decision_loss_rate,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "key_summary_hash": self.key_summary_hash,
            "headline_eligible": self.headline_eligible,
        }


@dataclass(frozen=True, slots=True)
class E20ConfirmatoryReport:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    aggregate_hash: str
    key_analysis_hash: str
    inference_hash: str
    detector_readiness_hash: str
    human_fidelity: E20HumanFidelitySummary
    reason_counts: tuple[E20ReasonCount, ...]
    headlines: tuple[E20HeadlineCondition, ...]
    status: E20ReportStatus
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_REPORT_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 report algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("result_bundle_hash", self.result_bundle_hash),
            ("aggregate_hash", self.aggregate_hash),
            ("key_analysis_hash", self.key_analysis_hash),
            ("inference_hash", self.inference_hash),
            ("detector_readiness_hash", self.detector_readiness_hash),
            ("report_hash", self.report_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.human_fidelity, E20HumanFidelitySummary):
            raise TypeError("human_fidelity must be an E20HumanFidelitySummary")
        if tuple(value.reason_code for value in self.reason_counts) != tuple(ExperimentReasonCode):
            raise ValueError("report reason counts must contain every frozen reason code")
        if not isinstance(self.headlines, tuple) or not self.headlines:
            raise TypeError("headlines must be a non-empty tuple")
        if any(not isinstance(value, E20HeadlineCondition) for value in self.headlines):
            raise TypeError("headlines must contain E20HeadlineCondition values")
        expected = tuple(sorted(self.headlines, key=lambda value: value.condition_id))
        if self.headlines != expected:
            raise ValueError("headline conditions must be canonically ordered")
        if not isinstance(self.status, E20ReportStatus):
            raise TypeError("status must be an E20ReportStatus")
        if self.status is E20ReportStatus.CONFIRMATORY_EVALUABLE and not all(
            value.headline_eligible for value in self.headlines
        ):
            raise ValueError("confirmatory-evaluable report requires every headline condition to be eligible")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match E20 confirmatory report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "aggregate_hash": self.aggregate_hash,
            "key_analysis_hash": self.key_analysis_hash,
            "inference_hash": self.inference_hash,
            "detector_readiness_hash": self.detector_readiness_hash,
            "human_fidelity": self.human_fidelity,
            "reason_counts": self.reason_counts,
            "headlines": self.headlines,
            "status": self.status.value,
        }


def _metric(condition, population, metric_id):
    values = tuple(
        value
        for value in condition.metrics
        if value.population is population and value.metric_id is metric_id
    )
    if len(values) != 1:
        raise ValueError("E20 report requires exactly one matching aggregate metric")
    return values[0]


def _human_fidelity_summary(
    result_bundle: E20ResultBundle,
    condition_plan: E20ConditionPlan,
    preregistration: ConfirmatoryPreregistration,
) -> E20HumanFidelitySummary:
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    unique: dict[tuple[str, str], E20HumanFidelityStatus] = {}
    for row in result_bundle.outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        key = (row.identity.sample_id, condition.transform_condition_id)
        previous = unique.setdefault(key, row.fidelity.human_status)
        if previous is not row.fidelity.human_status:
            raise ValueError(
                "human fidelity status changed across detector evaluations of the same transform"
            )
    counts: Counter[E20HumanFidelityStatus] = Counter(unique.values())
    favorable = counts[E20HumanFidelityStatus.EQUIVALENT_OR_MINOR]
    material = counts[E20HumanFidelityStatus.MATERIAL_CHANGE]
    cannot_judge = counts[E20HumanFidelityStatus.CANNOT_JUDGE]
    reviewed = favorable + material + cannot_judge
    hard_failures = sum(
        row.reason_code is ExperimentReasonCode.HARD_INVARIANT_FAILURE
        for row in result_bundle.failure_rows
    )
    rate = None if reviewed == 0 else favorable / reviewed
    interval = None if reviewed == 0 else exact_binomial_interval(favorable, reviewed, 0.95)
    gate_passed = (
        reviewed >= preregistration.fidelity_gate.minimum_audited_samples
        and hard_failures <= preregistration.fidelity_gate.maximum_hard_invariant_violations
        and rate is not None
        and rate >= preregistration.fidelity_gate.minimum_equivalent_or_minor_rate
    )
    payload = {
        "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
        "unique_transform_count": len(unique),
        "reviewed_transform_count": reviewed,
        "equivalent_or_minor_count": favorable,
        "material_change_count": material,
        "cannot_judge_count": cannot_judge,
        "hard_invariant_failure_count": hard_failures,
        "equivalent_or_minor_rate": rate,
        "equivalent_or_minor_interval": interval,
        "gate_passed": gate_passed,
    }
    return E20HumanFidelitySummary(
        len(unique),
        reviewed,
        favorable,
        material,
        cannot_judge,
        hard_failures,
        rate,
        interval,
        gate_passed,
        sha256_json(payload),
    )


def build_e20_confirmatory_report(
    result_bundle: E20ResultBundle,
    aggregate: E20AggregateBundle,
    key_analysis: E20KeyAnalysisBundle,
    inference: E20InferenceBundle,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> E20ConfirmatoryReport:
    verify_confirmatory_detector_readiness(detector_readiness, preregistration)
    verify_e20_aggregate_bundle(
        aggregate,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    verify_e20_key_analysis_bundle(
        key_analysis,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    verify_e20_inference_bundle(
        inference,
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    human = _human_fidelity_summary(result_bundle, condition_plan, preregistration)
    aggregate_by_id = {value.condition_id: value for value in aggregate.conditions}
    key_by_id = {value.condition_id: value for value in key_analysis.summaries}
    inference_by_id = {value.condition_id: value for value in inference.inferences}
    headlines: list[E20HeadlineCondition] = []
    for condition in condition_plan.conditions:
        aggregate_condition = aggregate_by_id[condition.condition_id]
        key_summary = key_by_id[condition.condition_id]
        inference_cell = inference_by_id[condition.condition_id]
        tpr_change = _metric(
            aggregate_condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.TPR_CHANGE,
        )
        transformed_tpr = _metric(
            aggregate_condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.TRANSFORMED_TPR,
        )
        margin_drop = _metric(
            aggregate_condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.STANDARDIZED_MARGIN_DROP,
        )
        coverage_efficiency = _metric(
            aggregate_condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.COVERAGE_EFFICIENCY,
        )
        decision_loss = _metric(
            aggregate_condition,
            E20AnalysisPopulation.PRISTINE_POSITIVE,
            E20MetricId.DECISION_LOSS_RATE,
        )
        eligible = (
            aggregate_condition.headline_eligible
            and human.gate_passed
            and detector_readiness.ready_for_e20
            and inference_cell.status is E20InferenceStatus.COMPLETE
            and tpr_change.status is E20MetricStatus.COMPLETE
            and transformed_tpr.status is E20MetricStatus.COMPLETE
            and margin_drop.status is E20MetricStatus.COMPLETE
            and coverage_efficiency.status is E20MetricStatus.COMPLETE
            and decision_loss.status is E20MetricStatus.COMPLETE
        )
        interval = tpr_change.confidence_interval
        headline_payload = {
            "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
            "condition_id": condition.condition_id,
            "calibration_bundle_hash": condition.calibration_bundle_hash,
            "target_fpr": condition.target_fpr,
            "expected_row_count": aggregate_condition.expected_row_count,
            "failure_row_count": aggregate_condition.failure_row_count,
            "tpr_change": tpr_change.estimate,
            "tpr_change_ci_lower": None if interval is None else interval.lower,
            "tpr_change_ci_upper": None if interval is None else interval.upper,
            "transformed_tpr": transformed_tpr.estimate,
            "standardized_margin_drop": margin_drop.estimate,
            "coverage_efficiency": coverage_efficiency.estimate,
            "decision_loss_rate": decision_loss.estimate,
            "holm_adjusted_p_value": inference_cell.holm_adjusted_p_value,
            "key_summary_hash": key_summary.summary_hash,
            "headline_eligible": eligible,
        }
        headlines.append(
            E20HeadlineCondition(
                condition.condition_id,
                condition.calibration_bundle_hash,
                condition.target_fpr,
                aggregate_condition.expected_row_count,
                aggregate_condition.failure_row_count,
                tpr_change.estimate,
                None if interval is None else interval.lower,
                None if interval is None else interval.upper,
                transformed_tpr.estimate,
                margin_drop.estimate,
                coverage_efficiency.estimate,
                decision_loss.estimate,
                inference_cell.holm_adjusted_p_value,
                key_summary.summary_hash,
                eligible,
                sha256_json(headline_payload),
            )
        )
    ordered_headlines = tuple(sorted(headlines, key=lambda value: value.condition_id))
    if not detector_readiness.ready_for_e20:
        status = E20ReportStatus.BLOCKED_DETECTOR_READINESS
    elif not human.gate_passed:
        status = E20ReportStatus.BLOCKED_FIDELITY_AUDIT
    elif result_bundle.failure_row_count:
        status = E20ReportStatus.INCOMPLETE_FAILURE_ROWS
    elif any(value.status is not E20InferenceStatus.COMPLETE for value in inference.inferences):
        status = E20ReportStatus.INCOMPLETE_INFERENCE
    elif not all(value.headline_eligible for value in ordered_headlines):
        status = E20ReportStatus.INCOMPLETE_PRIMARY_METRICS
    else:
        status = E20ReportStatus.CONFIRMATORY_EVALUABLE
    payload = {
        "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "aggregate_hash": aggregate.aggregate_hash,
        "key_analysis_hash": key_analysis.bundle_hash,
        "inference_hash": inference.bundle_hash,
        "detector_readiness_hash": detector_readiness.report_hash,
        "human_fidelity": human,
        "reason_counts": result_bundle.reason_counts,
        "headlines": ordered_headlines,
        "status": status.value,
    }
    return E20ConfirmatoryReport(
        E20_REPORT_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        aggregate.aggregate_hash,
        key_analysis.bundle_hash,
        inference.bundle_hash,
        detector_readiness.report_hash,
        human,
        result_bundle.reason_counts,
        ordered_headlines,
        status,
        sha256_json(payload),
    )


def verify_e20_confirmatory_report(
    report: E20ConfirmatoryReport,
    result_bundle: E20ResultBundle,
    aggregate: E20AggregateBundle,
    key_analysis: E20KeyAnalysisBundle,
    inference: E20InferenceBundle,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> None:
    if not isinstance(report, E20ConfirmatoryReport):
        raise TypeError("report must be an E20ConfirmatoryReport")
    expected = build_e20_confirmatory_report(
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        detector_readiness,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    if report != expected:
        raise ValueError(
            "E20 confirmatory report does not replay exactly from sealed analysis artifacts"
        )
