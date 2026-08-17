from __future__ import annotations

from .e21_analysis import E21PrimaryAnalysis, build_e21_headline_evidence
from .e21_human_audit import E21HumanFidelitySummary
from .e21_inference import E21PrimaryInference
from .e21_replication import E21HeadlineEvidence


def build_fidelity_bound_e21_headline_evidence(
    analysis: E21PrimaryAnalysis,
    inference: E21PrimaryInference,
    fidelity_summary: E21HumanFidelitySummary,
) -> tuple[E21HeadlineEvidence, ...]:
    if not isinstance(fidelity_summary, E21HumanFidelitySummary):
        raise TypeError("fidelity_summary must be an E21HumanFidelitySummary")
    raw = build_e21_headline_evidence(analysis, inference)
    if fidelity_summary.gate_passed:
        return raw
    return tuple(
        E21HeadlineEvidence.create(
            value.condition_id,
            value.target_fpr,
            value.source_result_bundle_hash,
            tpr_change=value.tpr_change,
            tpr_change_ci_lower=value.tpr_change_ci_lower,
            tpr_change_ci_upper=value.tpr_change_ci_upper,
            transformed_tpr=value.transformed_tpr,
            standardized_margin_drop=value.standardized_margin_drop,
            coverage_efficiency=value.coverage_efficiency,
            decision_loss_rate=value.decision_loss_rate,
            holm_adjusted_p_value=value.holm_adjusted_p_value,
            headline_eligible=False,
        )
        for value in raw
    )
