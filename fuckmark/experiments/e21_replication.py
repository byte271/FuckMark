from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .e20_report import E20ConfirmatoryReport, E20ReportStatus
from .e21_execution import E21RunLedger, E21RunState, verify_e21_run_ledger
from .e21_rerun import E21ExecutionAuthorization, E21RerunSeal


E21_REPLICATION_ALGORITHM_VERSION = "e21-replication-comparison-v1"


class E21ReplicationStatus(str, Enum):
    BLOCKED_E20_REPORT = "BLOCKED_E20_REPORT"
    INCOMPLETE_E21 = "INCOMPLETE_E21"
    DESCRIPTIVE_COMPLETE = "DESCRIPTIVE_COMPLETE"


class E21ReplicationError(ValueError):
    pass


def _finite_optional(name: str, value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number or None")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class E21HeadlineEvidence:
    condition_id: str
    target_fpr: float
    source_result_bundle_hash: str
    tpr_change: float | None
    tpr_change_ci_lower: float | None
    tpr_change_ci_upper: float | None
    transformed_tpr: float | None
    standardized_margin_drop: float | None
    coverage_efficiency: float | None
    decision_loss_rate: float | None
    holm_adjusted_p_value: float | None
    headline_eligible: bool
    evidence_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        if isinstance(self.target_fpr, bool) or not isinstance(self.target_fpr, (int, float)):
            raise TypeError("target_fpr must be a real number")
        target_fpr = float(self.target_fpr)
        if not math.isfinite(target_fpr) or target_fpr <= 0.0 or target_fpr >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target_fpr)
        require_sha256("source_result_bundle_hash", self.source_result_bundle_hash)
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
            object.__setattr__(self, name, _finite_optional(name, getattr(self, name)))
        if self.tpr_change_ci_lower is not None and self.tpr_change_ci_upper is not None:
            if self.tpr_change_ci_lower > self.tpr_change_ci_upper:
                raise ValueError("E21 TPR-change confidence interval is reversed")
            if self.tpr_change is not None and not (
                self.tpr_change_ci_lower <= self.tpr_change <= self.tpr_change_ci_upper
            ):
                raise ValueError("E21 TPR change must lie inside its confidence interval")
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
                raise ValueError("headline-eligible E21 evidence requires every frozen primary field")
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match E21 headline evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E21_REPLICATION_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "target_fpr": self.target_fpr,
            "source_result_bundle_hash": self.source_result_bundle_hash,
            "tpr_change": self.tpr_change,
            "tpr_change_ci_lower": self.tpr_change_ci_lower,
            "tpr_change_ci_upper": self.tpr_change_ci_upper,
            "transformed_tpr": self.transformed_tpr,
            "standardized_margin_drop": self.standardized_margin_drop,
            "coverage_efficiency": self.coverage_efficiency,
            "decision_loss_rate": self.decision_loss_rate,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "headline_eligible": self.headline_eligible,
        }

    @classmethod
    def create(
        cls,
        condition_id: str,
        target_fpr: float,
        source_result_bundle_hash: str,
        *,
        tpr_change: float | None,
        tpr_change_ci_lower: float | None,
        tpr_change_ci_upper: float | None,
        transformed_tpr: float | None,
        standardized_margin_drop: float | None,
        coverage_efficiency: float | None,
        decision_loss_rate: float | None,
        holm_adjusted_p_value: float | None,
        headline_eligible: bool,
    ) -> E21HeadlineEvidence:
        payload = {
            "algorithm_version": E21_REPLICATION_ALGORITHM_VERSION,
            "condition_id": condition_id,
            "target_fpr": target_fpr,
            "source_result_bundle_hash": source_result_bundle_hash,
            "tpr_change": tpr_change,
            "tpr_change_ci_lower": tpr_change_ci_lower,
            "tpr_change_ci_upper": tpr_change_ci_upper,
            "transformed_tpr": transformed_tpr,
            "standardized_margin_drop": standardized_margin_drop,
            "coverage_efficiency": coverage_efficiency,
            "decision_loss_rate": decision_loss_rate,
            "holm_adjusted_p_value": holm_adjusted_p_value,
            "headline_eligible": headline_eligible,
        }
        return cls(
            condition_id,
            target_fpr,
            source_result_bundle_hash,
            tpr_change,
            tpr_change_ci_lower,
            tpr_change_ci_upper,
            transformed_tpr,
            standardized_margin_drop,
            coverage_efficiency,
            decision_loss_rate,
            holm_adjusted_p_value,
            headline_eligible,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E21ConditionComparison:
    condition_id: str
    e20_headline_hash: str
    e21_evidence_hash: str
    target_fpr: float
    tpr_change_e20: float | None
    tpr_change_e21: float | None
    tpr_change_delta: float | None
    transformed_tpr_e20: float | None
    transformed_tpr_e21: float | None
    transformed_tpr_delta: float | None
    standardized_margin_drop_e20: float | None
    standardized_margin_drop_e21: float | None
    standardized_margin_drop_delta: float | None
    coverage_efficiency_e20: float | None
    coverage_efficiency_e21: float | None
    coverage_efficiency_delta: float | None
    decision_loss_rate_e20: float | None
    decision_loss_rate_e21: float | None
    decision_loss_rate_delta: float | None
    both_headline_eligible: bool
    comparison_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_sha256("e20_headline_hash", self.e20_headline_hash)
        require_sha256("e21_evidence_hash", self.e21_evidence_hash)
        if isinstance(self.target_fpr, bool) or not isinstance(self.target_fpr, (int, float)):
            raise TypeError("target_fpr must be a real number")
        target_fpr = float(self.target_fpr)
        if not math.isfinite(target_fpr) or target_fpr <= 0.0 or target_fpr >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target_fpr)
        for name in (
            "tpr_change_e20",
            "tpr_change_e21",
            "tpr_change_delta",
            "transformed_tpr_e20",
            "transformed_tpr_e21",
            "transformed_tpr_delta",
            "standardized_margin_drop_e20",
            "standardized_margin_drop_e21",
            "standardized_margin_drop_delta",
            "coverage_efficiency_e20",
            "coverage_efficiency_e21",
            "coverage_efficiency_delta",
            "decision_loss_rate_e20",
            "decision_loss_rate_e21",
            "decision_loss_rate_delta",
        ):
            object.__setattr__(self, name, _finite_optional(name, getattr(self, name)))
        for prefix in (
            "tpr_change",
            "transformed_tpr",
            "standardized_margin_drop",
            "coverage_efficiency",
            "decision_loss_rate",
        ):
            left = getattr(self, f"{prefix}_e20")
            right = getattr(self, f"{prefix}_e21")
            delta = getattr(self, f"{prefix}_delta")
            expected = None if left is None or right is None else right - left
            if expected is None:
                if delta is not None:
                    raise ValueError(f"{prefix}_delta must be None when either run is unavailable")
            elif delta is None or not math.isclose(delta, expected, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError(f"{prefix}_delta does not equal E21 minus E20")
        require_bool("both_headline_eligible", self.both_headline_eligible)
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self._payload()):
            raise ValueError("comparison_hash does not match E21 condition comparison")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E21_REPLICATION_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "e20_headline_hash": self.e20_headline_hash,
            "e21_evidence_hash": self.e21_evidence_hash,
            "target_fpr": self.target_fpr,
            "tpr_change_e20": self.tpr_change_e20,
            "tpr_change_e21": self.tpr_change_e21,
            "tpr_change_delta": self.tpr_change_delta,
            "transformed_tpr_e20": self.transformed_tpr_e20,
            "transformed_tpr_e21": self.transformed_tpr_e21,
            "transformed_tpr_delta": self.transformed_tpr_delta,
            "standardized_margin_drop_e20": self.standardized_margin_drop_e20,
            "standardized_margin_drop_e21": self.standardized_margin_drop_e21,
            "standardized_margin_drop_delta": self.standardized_margin_drop_delta,
            "coverage_efficiency_e20": self.coverage_efficiency_e20,
            "coverage_efficiency_e21": self.coverage_efficiency_e21,
            "coverage_efficiency_delta": self.coverage_efficiency_delta,
            "decision_loss_rate_e20": self.decision_loss_rate_e20,
            "decision_loss_rate_e21": self.decision_loss_rate_e21,
            "decision_loss_rate_delta": self.decision_loss_rate_delta,
            "both_headline_eligible": self.both_headline_eligible,
        }


@dataclass(frozen=True, slots=True)
class E21ReplicationComparison:
    algorithm_version: str
    e20_report_hash: str
    e20_result_bundle_hash: str
    e21_execution_id: str
    e21_authorization_hash: str
    e21_rerun_seal_hash: str
    e21_result_bundle_hash: str
    conditions: tuple[E21ConditionComparison, ...]
    status: E21ReplicationStatus
    comparison_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_REPLICATION_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 replication comparison algorithm version")
        for name, value in (
            ("e20_report_hash", self.e20_report_hash),
            ("e20_result_bundle_hash", self.e20_result_bundle_hash),
            ("e21_execution_id", self.e21_execution_id),
            ("e21_authorization_hash", self.e21_authorization_hash),
            ("e21_rerun_seal_hash", self.e21_rerun_seal_hash),
            ("e21_result_bundle_hash", self.e21_result_bundle_hash),
            ("comparison_hash", self.comparison_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise TypeError("conditions must be a non-empty tuple")
        if any(not isinstance(value, E21ConditionComparison) for value in self.conditions):
            raise TypeError("conditions must contain E21ConditionComparison values")
        if self.conditions != tuple(sorted(self.conditions, key=lambda value: value.condition_id)):
            raise ValueError("E21 condition comparisons must be canonically ordered")
        if not isinstance(self.status, E21ReplicationStatus):
            raise TypeError("status must be an E21ReplicationStatus")
        if self.status is E21ReplicationStatus.DESCRIPTIVE_COMPLETE and not all(
            value.both_headline_eligible for value in self.conditions
        ):
            raise ValueError("descriptive-complete comparison requires eligible E20 and E21 headlines")
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self._payload()):
            raise ValueError("comparison_hash does not match E21 replication comparison")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "e20_report_hash": self.e20_report_hash,
            "e20_result_bundle_hash": self.e20_result_bundle_hash,
            "e21_execution_id": self.e21_execution_id,
            "e21_authorization_hash": self.e21_authorization_hash,
            "e21_rerun_seal_hash": self.e21_rerun_seal_hash,
            "e21_result_bundle_hash": self.e21_result_bundle_hash,
            "conditions": self.conditions,
            "status": self.status.value,
        }


def _delta(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else right - left


def _condition_comparison(e20, e21: E21HeadlineEvidence) -> E21ConditionComparison:
    payload = {
        "algorithm_version": E21_REPLICATION_ALGORITHM_VERSION,
        "condition_id": e20.condition_id,
        "e20_headline_hash": e20.headline_hash,
        "e21_evidence_hash": e21.evidence_hash,
        "target_fpr": e20.target_fpr,
        "tpr_change_e20": e20.tpr_change,
        "tpr_change_e21": e21.tpr_change,
        "tpr_change_delta": _delta(e20.tpr_change, e21.tpr_change),
        "transformed_tpr_e20": e20.transformed_tpr,
        "transformed_tpr_e21": e21.transformed_tpr,
        "transformed_tpr_delta": _delta(e20.transformed_tpr, e21.transformed_tpr),
        "standardized_margin_drop_e20": e20.standardized_margin_drop,
        "standardized_margin_drop_e21": e21.standardized_margin_drop,
        "standardized_margin_drop_delta": _delta(e20.standardized_margin_drop, e21.standardized_margin_drop),
        "coverage_efficiency_e20": e20.coverage_efficiency,
        "coverage_efficiency_e21": e21.coverage_efficiency,
        "coverage_efficiency_delta": _delta(e20.coverage_efficiency, e21.coverage_efficiency),
        "decision_loss_rate_e20": e20.decision_loss_rate,
        "decision_loss_rate_e21": e21.decision_loss_rate,
        "decision_loss_rate_delta": _delta(e20.decision_loss_rate, e21.decision_loss_rate),
        "both_headline_eligible": e20.headline_eligible and e21.headline_eligible,
    }
    return E21ConditionComparison(
        e20.condition_id,
        e20.headline_hash,
        e21.evidence_hash,
        e20.target_fpr,
        e20.tpr_change,
        e21.tpr_change,
        payload["tpr_change_delta"],
        e20.transformed_tpr,
        e21.transformed_tpr,
        payload["transformed_tpr_delta"],
        e20.standardized_margin_drop,
        e21.standardized_margin_drop,
        payload["standardized_margin_drop_delta"],
        e20.coverage_efficiency,
        e21.coverage_efficiency,
        payload["coverage_efficiency_delta"],
        e20.decision_loss_rate,
        e21.decision_loss_rate,
        payload["decision_loss_rate_delta"],
        payload["both_headline_eligible"],
        sha256_json(payload),
    )


def build_e21_replication_comparison(
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_ledger: E21RunLedger,
    e21_headlines: tuple[E21HeadlineEvidence, ...],
) -> E21ReplicationComparison:
    if not isinstance(e20_report, E20ConfirmatoryReport):
        raise TypeError("e20_report must be an E20ConfirmatoryReport")
    if not isinstance(e21_authorization, E21ExecutionAuthorization):
        raise TypeError("e21_authorization must be an E21ExecutionAuthorization")
    if not isinstance(e21_rerun_seal, E21RerunSeal):
        raise TypeError("e21_rerun_seal must be an E21RerunSeal")
    verify_e21_run_ledger(e21_ledger, e21_authorization)
    if e21_ledger.state is not E21RunState.COMPLETED:
        raise E21ReplicationError("E21 replication comparison requires a completed non-invalidated E21 run")
    result_bundle_hash = e21_ledger.events[-1].artifact_hash
    if result_bundle_hash is None:
        raise E21ReplicationError("completed E21 ledger is missing its result bundle hash")
    if e21_authorization.rerun_seal_hash != e21_rerun_seal.seal_hash:
        raise E21ReplicationError("E21 authorization does not bind the supplied rerun seal")
    if e20_report.execution_id != e21_rerun_seal.e20_execution_id:
        raise E21ReplicationError("E20 report execution does not match the E21 rerun seal")
    if e20_report.result_bundle_hash != e21_rerun_seal.e20_result_bundle_hash:
        raise E21ReplicationError("E20 report result bundle does not match the E21 rerun seal")
    if not isinstance(e21_headlines, tuple) or any(
        not isinstance(value, E21HeadlineEvidence) for value in e21_headlines
    ):
        raise TypeError("e21_headlines must be a tuple of E21HeadlineEvidence values")
    e21_by_id = {value.condition_id: value for value in e21_headlines}
    if len(e21_by_id) != len(e21_headlines):
        raise E21ReplicationError("E21 headline evidence contains duplicate condition IDs")
    expected_ids = {value.condition_id for value in e20_report.headlines}
    if set(e21_by_id) != expected_ids:
        raise E21ReplicationError("E21 headline evidence must exactly cover the frozen E20 headline conditions")
    comparisons = []
    for e20 in e20_report.headlines:
        e21 = e21_by_id[e20.condition_id]
        if e21.source_result_bundle_hash != result_bundle_hash:
            raise E21ReplicationError("E21 headline evidence is not bound to the completed E21 result bundle")
        if not math.isclose(e21.target_fpr, e20.target_fpr, rel_tol=0.0, abs_tol=1e-15):
            raise E21ReplicationError("E21 headline target FPR changed from E20")
        comparisons.append(_condition_comparison(e20, e21))
    conditions = tuple(sorted(comparisons, key=lambda value: value.condition_id))
    if e20_report.status is not E20ReportStatus.CONFIRMATORY_EVALUABLE:
        status = E21ReplicationStatus.BLOCKED_E20_REPORT
    elif all(value.both_headline_eligible for value in conditions):
        status = E21ReplicationStatus.DESCRIPTIVE_COMPLETE
    else:
        status = E21ReplicationStatus.INCOMPLETE_E21
    payload = {
        "algorithm_version": E21_REPLICATION_ALGORITHM_VERSION,
        "e20_report_hash": e20_report.report_hash,
        "e20_result_bundle_hash": e20_report.result_bundle_hash,
        "e21_execution_id": e21_authorization.execution_id,
        "e21_authorization_hash": e21_authorization.authorization_hash,
        "e21_rerun_seal_hash": e21_rerun_seal.seal_hash,
        "e21_result_bundle_hash": result_bundle_hash,
        "conditions": conditions,
        "status": status.value,
    }
    return E21ReplicationComparison(
        E21_REPLICATION_ALGORITHM_VERSION,
        e20_report.report_hash,
        e20_report.result_bundle_hash,
        e21_authorization.execution_id,
        e21_authorization.authorization_hash,
        e21_rerun_seal.seal_hash,
        result_bundle_hash,
        conditions,
        status,
        sha256_json(payload),
    )


def verify_e21_replication_comparison(
    comparison: E21ReplicationComparison,
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_ledger: E21RunLedger,
    e21_headlines: tuple[E21HeadlineEvidence, ...],
) -> None:
    if not isinstance(comparison, E21ReplicationComparison):
        raise TypeError("comparison must be an E21ReplicationComparison")
    expected = build_e21_replication_comparison(
        e20_report,
        e21_authorization,
        e21_rerun_seal,
        e21_ledger,
        e21_headlines,
    )
    if comparison != expected:
        raise E21ReplicationError("E21 replication comparison does not replay exactly from supplied artifacts")
