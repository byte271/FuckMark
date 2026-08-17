from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_bool, require_int, require_sha256
from ..corpus import CorpusManifest
from ..detectors.calibration_statistics import ExactBinomialInterval, exact_binomial_interval
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit, FidelityLabel
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e20_rows import ExperimentReasonCode
from .e21_bundle import E21ResultBundle
from .e21_human_audit import E21HumanAuditSelection, verify_e21_human_audit_evidence


E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION = "e21-human-fidelity-summary-v2"


@dataclass(frozen=True, slots=True)
class E21VerifiedFidelitySummary:
    selection_hash: str
    audit_hash: str
    reviewed_transform_count: int
    equivalent_or_minor_count: int
    material_change_count: int
    cannot_judge_count: int
    hard_invariant_failure_count: int
    equivalent_or_minor_rate: float
    equivalent_or_minor_interval: ExactBinomialInterval
    gate_passed: bool
    summary_hash: str

    def __post_init__(self) -> None:
        require_sha256("selection_hash", self.selection_hash)
        require_sha256("audit_hash", self.audit_hash)
        for name, value in (
            ("reviewed_transform_count", self.reviewed_transform_count),
            ("equivalent_or_minor_count", self.equivalent_or_minor_count),
            ("material_change_count", self.material_change_count),
            ("cannot_judge_count", self.cannot_judge_count),
            ("hard_invariant_failure_count", self.hard_invariant_failure_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.reviewed_transform_count <= 0:
            raise ValueError("E21 verified fidelity summary requires reviewed transforms")
        if self.reviewed_transform_count != (
            self.equivalent_or_minor_count
            + self.material_change_count
            + self.cannot_judge_count
        ):
            raise ValueError("E21 verified fidelity adjudication counts do not close")
        if isinstance(self.equivalent_or_minor_rate, bool) or not isinstance(
            self.equivalent_or_minor_rate, (int, float)
        ):
            raise TypeError("equivalent_or_minor_rate must be a real number")
        rate = float(self.equivalent_or_minor_rate)
        if not math.isfinite(rate) or rate < 0.0 or rate > 1.0:
            raise ValueError("equivalent_or_minor_rate must be between zero and one")
        object.__setattr__(self, "equivalent_or_minor_rate", rate)
        if not isinstance(self.equivalent_or_minor_interval, ExactBinomialInterval):
            raise TypeError("equivalent_or_minor_interval must be an ExactBinomialInterval")
        if not math.isclose(
            self.equivalent_or_minor_interval.confidence_level,
            0.95,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("E21 verified fidelity interval must use 95% confidence")
        if not (
            self.equivalent_or_minor_interval.lower
            <= rate
            <= self.equivalent_or_minor_interval.upper
        ):
            raise ValueError("E21 verified fidelity rate must lie inside its confidence interval")
        require_bool("gate_passed", self.gate_passed)
        if self.gate_passed and self.hard_invariant_failure_count != 0:
            raise ValueError("E21 fidelity gate cannot pass with a hard-invariant failure")
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match E21 verified fidelity summary")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION,
            "selection_hash": self.selection_hash,
            "audit_hash": self.audit_hash,
            "reviewed_transform_count": self.reviewed_transform_count,
            "equivalent_or_minor_count": self.equivalent_or_minor_count,
            "material_change_count": self.material_change_count,
            "cannot_judge_count": self.cannot_judge_count,
            "hard_invariant_failure_count": self.hard_invariant_failure_count,
            "equivalent_or_minor_rate": self.equivalent_or_minor_rate,
            "equivalent_or_minor_interval": self.equivalent_or_minor_interval,
            "gate_passed": self.gate_passed,
        }


def e21_hard_invariant_failure_count(result_bundle: E21ResultBundle) -> int:
    if not isinstance(result_bundle, E21ResultBundle):
        raise TypeError("result_bundle must be an E21ResultBundle")
    return sum(
        row.reason_code is ExperimentReasonCode.HARD_INVARIANT_FAILURE
        for row in result_bundle.failure_rows
    ) + sum(not row.fidelity.hard_pass for row in result_bundle.outcome_rows)


def build_verified_e21_fidelity_summary(
    selection: E21HumanAuditSelection,
    audit: BlindHumanFidelityAudit,
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21VerifiedFidelitySummary:
    verify_e21_human_audit_evidence(
        selection,
        audit,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    counts = {
        FidelityLabel.EQUIVALENT_OR_MINOR: 0,
        FidelityLabel.MATERIAL_CHANGE: 0,
        FidelityLabel.CANNOT_JUDGE: 0,
    }
    for adjudication in audit.adjudications:
        counts[adjudication.label] += 1
    reviewed = len(audit.adjudications)
    favorable = counts[FidelityLabel.EQUIVALENT_OR_MINOR]
    material = counts[FidelityLabel.MATERIAL_CHANGE]
    cannot = counts[FidelityLabel.CANNOT_JUDGE]
    hard_failures = e21_hard_invariant_failure_count(result_bundle)
    rate = favorable / reviewed
    interval = exact_binomial_interval(favorable, reviewed, 0.95)
    gate = preregistration.fidelity_gate
    gate_passed = (
        reviewed >= gate.minimum_audited_samples
        and rate >= gate.minimum_equivalent_or_minor_rate
        and hard_failures <= gate.maximum_hard_invariant_violations
    )
    payload = {
        "algorithm_version": E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION,
        "selection_hash": selection.selection_hash,
        "audit_hash": audit.audit_hash,
        "reviewed_transform_count": reviewed,
        "equivalent_or_minor_count": favorable,
        "material_change_count": material,
        "cannot_judge_count": cannot,
        "hard_invariant_failure_count": hard_failures,
        "equivalent_or_minor_rate": rate,
        "equivalent_or_minor_interval": interval,
        "gate_passed": gate_passed,
    }
    return E21VerifiedFidelitySummary(
        selection.selection_hash,
        audit.audit_hash,
        reviewed,
        favorable,
        material,
        cannot,
        hard_failures,
        rate,
        interval,
        gate_passed,
        sha256_json(payload),
    )
