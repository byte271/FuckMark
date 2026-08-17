from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_aggregate import (
    E20_AGGREGATOR_ALGORITHM_VERSION,
    E20AnalysisPopulation,
    E20ConditionAggregate,
    E20MetricId,
    E20MetricStatus,
    _condition_aggregate,
)
from .e20_conditions import E20ConditionPlan
from .e21_bundle import E21ResultBundle, verify_e21_result_bundle
from .e21_execution import E21RunLedger
from .e21_rerun import E21ExecutionAuthorization


E21_PRIMARY_ANALYSIS_ALGORITHM_VERSION = "e21-primary-analysis-v1"


class E21PrimaryAnalysisError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E21PrimaryAnalysis:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    preregistration_hash: str
    bootstrap_plan_hash: str
    frozen_analysis_engine_version: str
    conditions: tuple[E20ConditionAggregate, ...]
    analysis_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_PRIMARY_ANALYSIS_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 primary analysis algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("result_bundle_hash", self.result_bundle_hash),
            ("preregistration_hash", self.preregistration_hash),
            ("bootstrap_plan_hash", self.bootstrap_plan_hash),
            ("analysis_hash", self.analysis_hash),
        ):
            require_sha256(name, value)
        require_clean_string("frozen_analysis_engine_version", self.frozen_analysis_engine_version)
        if self.frozen_analysis_engine_version != E20_AGGREGATOR_ALGORITHM_VERSION:
            raise ValueError("E21 must reuse the frozen E20 aggregate analysis engine")
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise TypeError("conditions must be a non-empty tuple")
        if any(not isinstance(value, E20ConditionAggregate) for value in self.conditions):
            raise TypeError("conditions must contain frozen E20 condition aggregate values")
        if self.conditions != tuple(sorted(self.conditions, key=lambda value: value.condition_id)):
            raise ValueError("E21 condition analyses must be canonically ordered")
        if len({value.condition_id for value in self.conditions}) != len(self.conditions):
            raise ValueError("E21 condition analysis IDs must be unique")
        if self.analysis_hash != sha256_json(self._payload()):
            raise ValueError("analysis_hash does not match E21 primary analysis")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "preregistration_hash": self.preregistration_hash,
            "bootstrap_plan_hash": self.bootstrap_plan_hash,
            "frozen_analysis_engine_version": self.frozen_analysis_engine_version,
            "conditions": self.conditions,
        }


def build_e21_primary_analysis(
    result_bundle: E21ResultBundle,
    authorization: E21ExecutionAuthorization,
    started_ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21PrimaryAnalysis:
    verify_e21_result_bundle(
        result_bundle,
        authorization,
        started_ledger,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    conditions = tuple(
        sorted(
            (
                _condition_aggregate(
                    condition,
                    result_bundle,
                    corpus_manifest,
                    preregistration,
                )
                for condition in condition_plan.conditions
            ),
            key=lambda value: value.condition_id,
        )
    )
    payload = {
        "algorithm_version": E21_PRIMARY_ANALYSIS_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "bootstrap_plan_hash": preregistration.bootstrap_plan.plan_hash,
        "frozen_analysis_engine_version": E20_AGGREGATOR_ALGORITHM_VERSION,
        "conditions": conditions,
    }
    return E21PrimaryAnalysis(
        E21_PRIMARY_ANALYSIS_ALGORITHM_VERSION,
        authorization.execution_id,
        result_bundle.bundle_hash,
        preregistration.preregistration_hash,
        preregistration.bootstrap_plan.plan_hash,
        E20_AGGREGATOR_ALGORITHM_VERSION,
        conditions,
        sha256_json(payload),
    )


def verify_e21_primary_analysis(
    analysis: E21PrimaryAnalysis,
    result_bundle: E21ResultBundle,
    authorization: E21ExecutionAuthorization,
    started_ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(analysis, E21PrimaryAnalysis):
        raise TypeError("analysis must be an E21PrimaryAnalysis")
    expected = build_e21_primary_analysis(
        result_bundle,
        authorization,
        started_ledger,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if analysis != expected:
        raise E21PrimaryAnalysisError("E21 primary analysis does not replay from the sealed result bundle")


def _metric(
    condition: E20ConditionAggregate,
    population: E20AnalysisPopulation,
    metric_id: E20MetricId,
):
    values = tuple(
        value
        for value in condition.metrics
        if value.population is population and value.metric_id is metric_id
    )
    if len(values) != 1:
        raise E21PrimaryAnalysisError(
            f"E21 condition {condition.condition_id} does not contain exactly one frozen {population.value}:{metric_id.value} metric"
        )
    return values[0]


def build_e21_headline_evidence(
    analysis: E21PrimaryAnalysis,
):
    from .e21_replication import E21HeadlineEvidence

    if not isinstance(analysis, E21PrimaryAnalysis):
        raise TypeError("analysis must be an E21PrimaryAnalysis")
    evidence = []
    for condition in analysis.conditions:
        tpr_change = _metric(
            condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.TPR_CHANGE,
        )
        transformed_tpr = _metric(
            condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.TRANSFORMED_TPR,
        )
        margin_drop = _metric(
            condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.STANDARDIZED_MARGIN_DROP,
        )
        coverage_efficiency = _metric(
            condition,
            E20AnalysisPopulation.POLICY_ALL,
            E20MetricId.COVERAGE_EFFICIENCY,
        )
        decision_loss = _metric(
            condition,
            E20AnalysisPopulation.PRISTINE_POSITIVE,
            E20MetricId.DECISION_LOSS_RATE,
        )
        primary = (
            tpr_change,
            transformed_tpr,
            margin_drop,
            coverage_efficiency,
            decision_loss,
        )
        headline_eligible = condition.headline_eligible and all(
            value.status is E20MetricStatus.COMPLETE and value.estimate is not None
            for value in primary
        )
        interval = tpr_change.confidence_interval
        evidence.append(
            E21HeadlineEvidence.create(
                condition.condition_id,
                condition.target_fpr,
                analysis.result_bundle_hash,
                tpr_change=tpr_change.estimate,
                tpr_change_ci_lower=None if interval is None else interval.lower,
                tpr_change_ci_upper=None if interval is None else interval.upper,
                transformed_tpr=transformed_tpr.estimate,
                standardized_margin_drop=margin_drop.estimate,
                coverage_efficiency=coverage_efficiency.estimate,
                decision_loss_rate=decision_loss.estimate,
                holm_adjusted_p_value=None,
                headline_eligible=headline_eligible,
            )
        )
    return tuple(evidence)
