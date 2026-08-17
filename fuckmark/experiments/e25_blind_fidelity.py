from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, CorpusManifest
from ..detectors import ExactBinomialInterval, exact_binomial_interval
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit, FidelityLabel
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ResultBundle, verify_e20_result_bundle
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import E20ExecutionAuthorization
from .e20_human_audit import E20HumanAuditSelection, verify_e20_human_audit_evidence
from .e20_rows import ExperimentReasonCode
from .e21_bundle import E21ResultBundle, verify_e21_result_bundle
from .e21_execution import E21RunLedger
from .e21_human_audit_v2 import E21HumanAuditSelection, verify_e21_human_audit_evidence
from .e21_rerun import E21ExecutionAuthorization


E25_BLIND_FIDELITY_ALGORITHM_VERSION = "e25-blind-fidelity-consolidation-v1"


@dataclass(frozen=True, slots=True)
class E25FidelityCell:
    experiment_id: str
    hypothesis_class: str
    budget: int
    budget_unit: str
    domain: CorpusDomain
    candidate_count: int
    selected_count: int
    quartile_candidate_counts: tuple[int, int, int, int]
    quartile_selected_counts: tuple[int, int, int, int]
    reviewed_count: int
    equivalent_or_minor_count: int
    material_change_count: int
    cannot_judge_count: int
    equivalent_or_minor_rate: float | None
    equivalent_or_minor_interval: ExactBinomialInterval | None
    cell_hash: str

    def __post_init__(self) -> None:
        if self.experiment_id not in ("E20", "E21"):
            raise ValueError("experiment_id must be E20 or E21")
        require_clean_string("hypothesis_class", self.hypothesis_class)
        require_int("budget", self.budget)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        require_clean_string("budget_unit", self.budget_unit)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        for name, value in (("candidate_count", self.candidate_count), ("selected_count", self.selected_count), ("reviewed_count", self.reviewed_count), ("equivalent_or_minor_count", self.equivalent_or_minor_count), ("material_change_count", self.material_change_count), ("cannot_judge_count", self.cannot_judge_count)):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.selected_count > self.candidate_count:
            raise ValueError("selected_count cannot exceed candidate_count")
        if self.reviewed_count != self.selected_count:
            raise ValueError("every selected E25 cell entry must have one adjudication")
        if self.reviewed_count != self.equivalent_or_minor_count + self.material_change_count + self.cannot_judge_count:
            raise ValueError("E25 cell adjudication counts do not close")
        for name, values in (("quartile_candidate_counts", self.quartile_candidate_counts), ("quartile_selected_counts", self.quartile_selected_counts)):
            if not isinstance(values, tuple) or len(values) != 4:
                raise TypeError(f"{name} must contain four integer counts")
            for value in values:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} counts must be non-negative")
        if sum(self.quartile_candidate_counts) != self.candidate_count or sum(self.quartile_selected_counts) != self.selected_count:
            raise ValueError("E25 quartile counts do not close")
        if any(selected > candidate for selected, candidate in zip(self.quartile_selected_counts, self.quartile_candidate_counts)):
            raise ValueError("quartile selected count exceeds candidate count")
        if self.reviewed_count == 0:
            if self.equivalent_or_minor_rate is not None or self.equivalent_or_minor_interval is not None:
                raise ValueError("empty E25 cells cannot carry fidelity estimates")
        else:
            if self.equivalent_or_minor_rate is None:
                raise ValueError("reviewed E25 cells require an equivalent-or-minor rate")
            rate = float(self.equivalent_or_minor_rate)
            if not math.isfinite(rate) or not 0.0 <= rate <= 1.0:
                raise ValueError("equivalent_or_minor_rate must be in [0, 1]")
            if not math.isclose(rate, self.equivalent_or_minor_count / self.reviewed_count, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("E25 cell rate does not match adjudication counts")
            object.__setattr__(self, "equivalent_or_minor_rate", rate)
            if self.equivalent_or_minor_interval != exact_binomial_interval(self.equivalent_or_minor_count, self.reviewed_count, 0.95):
                raise ValueError("E25 cell interval must be the exact 95% binomial interval")
        require_sha256("cell_hash", self.cell_hash)
        if self.cell_hash != sha256_json(self._payload()):
            raise ValueError("cell_hash does not match E25 fidelity cell")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": E25_BLIND_FIDELITY_ALGORITHM_VERSION, "experiment_id": self.experiment_id, "hypothesis_class": self.hypothesis_class, "budget": self.budget, "budget_unit": self.budget_unit, "domain": self.domain.value, "candidate_count": self.candidate_count, "selected_count": self.selected_count, "quartile_candidate_counts": self.quartile_candidate_counts, "quartile_selected_counts": self.quartile_selected_counts, "reviewed_count": self.reviewed_count, "equivalent_or_minor_count": self.equivalent_or_minor_count, "material_change_count": self.material_change_count, "cannot_judge_count": self.cannot_judge_count, "equivalent_or_minor_rate": self.equivalent_or_minor_rate, "equivalent_or_minor_interval": self.equivalent_or_minor_interval}


@dataclass(frozen=True, slots=True)
class E25RunFidelitySummary:
    experiment_id: str
    execution_id: str
    authorization_hash: str
    corpus_manifest_hash: str
    result_bundle_hash: str
    selection_hash: str
    audit_hash: str
    cells: tuple[E25FidelityCell, ...]
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
        if self.experiment_id not in ("E20", "E21"):
            raise ValueError("experiment_id must be E20 or E21")
        for name, value in (("execution_id", self.execution_id), ("authorization_hash", self.authorization_hash), ("corpus_manifest_hash", self.corpus_manifest_hash), ("result_bundle_hash", self.result_bundle_hash), ("selection_hash", self.selection_hash), ("audit_hash", self.audit_hash), ("summary_hash", self.summary_hash)):
            require_sha256(name, value)
        if not isinstance(self.cells, tuple) or not self.cells or any(not isinstance(value, E25FidelityCell) for value in self.cells):
            raise TypeError("cells must be a non-empty tuple of E25FidelityCell values")
        if any(value.experiment_id != self.experiment_id for value in self.cells):
            raise ValueError("E25 run cells must match the run experiment_id")
        if self.cells != tuple(sorted(self.cells, key=_cell_sort_key)):
            raise ValueError("E25 run cells must use canonical ordering")
        for name, value in (("reviewed_transform_count", self.reviewed_transform_count), ("equivalent_or_minor_count", self.equivalent_or_minor_count), ("material_change_count", self.material_change_count), ("cannot_judge_count", self.cannot_judge_count), ("hard_invariant_failure_count", self.hard_invariant_failure_count)):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.reviewed_transform_count <= 0:
            raise ValueError("E25 run summary requires reviewed transforms")
        if self.reviewed_transform_count != self.equivalent_or_minor_count + self.material_change_count + self.cannot_judge_count:
            raise ValueError("E25 run adjudication counts do not close")
        rate = float(self.equivalent_or_minor_rate)
        if not math.isfinite(rate) or not math.isclose(rate, self.equivalent_or_minor_count / self.reviewed_transform_count, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("E25 run rate does not match adjudication counts")
        object.__setattr__(self, "equivalent_or_minor_rate", rate)
        if self.equivalent_or_minor_interval != exact_binomial_interval(self.equivalent_or_minor_count, self.reviewed_transform_count, 0.95):
            raise ValueError("E25 run interval must be the exact 95% binomial interval")
        require_bool("gate_passed", self.gate_passed)
        if self.gate_passed and self.hard_invariant_failure_count != 0:
            raise ValueError("E25 run gate cannot pass with a hard-invariant failure")
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match E25 run fidelity summary")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": E25_BLIND_FIDELITY_ALGORITHM_VERSION, "experiment_id": self.experiment_id, "execution_id": self.execution_id, "authorization_hash": self.authorization_hash, "corpus_manifest_hash": self.corpus_manifest_hash, "result_bundle_hash": self.result_bundle_hash, "selection_hash": self.selection_hash, "audit_hash": self.audit_hash, "cells": self.cells, "reviewed_transform_count": self.reviewed_transform_count, "equivalent_or_minor_count": self.equivalent_or_minor_count, "material_change_count": self.material_change_count, "cannot_judge_count": self.cannot_judge_count, "hard_invariant_failure_count": self.hard_invariant_failure_count, "equivalent_or_minor_rate": self.equivalent_or_minor_rate, "equivalent_or_minor_interval": self.equivalent_or_minor_interval, "gate_passed": self.gate_passed}


@dataclass(frozen=True, slots=True)
class E25BlindFidelityReport:
    algorithm_version: str
    preregistration_hash: str
    condition_plan_hash: str
    e20: E25RunFidelitySummary
    e21: E25RunFidelitySummary
    combined_reviewed_transform_count: int
    combined_equivalent_or_minor_count: int
    combined_material_change_count: int
    combined_cannot_judge_count: int
    combined_equivalent_or_minor_rate: float
    combined_equivalent_or_minor_interval: ExactBinomialInterval
    overall_gate_passed: bool
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E25_BLIND_FIDELITY_ALGORITHM_VERSION:
            raise ValueError("unsupported E25 blind fidelity algorithm version")
        require_sha256("preregistration_hash", self.preregistration_hash)
        require_sha256("condition_plan_hash", self.condition_plan_hash)
        if not isinstance(self.e20, E25RunFidelitySummary) or self.e20.experiment_id != "E20":
            raise TypeError("e20 must be an E20 E25RunFidelitySummary")
        if not isinstance(self.e21, E25RunFidelitySummary) or self.e21.experiment_id != "E21":
            raise TypeError("e21 must be an E21 E25RunFidelitySummary")
        for name, value in (("combined_reviewed_transform_count", self.combined_reviewed_transform_count), ("combined_equivalent_or_minor_count", self.combined_equivalent_or_minor_count), ("combined_material_change_count", self.combined_material_change_count), ("combined_cannot_judge_count", self.combined_cannot_judge_count)):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.combined_reviewed_transform_count != self.e20.reviewed_transform_count + self.e21.reviewed_transform_count:
            raise ValueError("combined reviewed count does not close")
        if self.combined_equivalent_or_minor_count != self.e20.equivalent_or_minor_count + self.e21.equivalent_or_minor_count or self.combined_material_change_count != self.e20.material_change_count + self.e21.material_change_count or self.combined_cannot_judge_count != self.e20.cannot_judge_count + self.e21.cannot_judge_count:
            raise ValueError("combined adjudication counts do not close")
        rate = float(self.combined_equivalent_or_minor_rate)
        if not math.isfinite(rate) or not math.isclose(rate, self.combined_equivalent_or_minor_count / self.combined_reviewed_transform_count, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("combined equivalent-or-minor rate does not match counts")
        object.__setattr__(self, "combined_equivalent_or_minor_rate", rate)
        if self.combined_equivalent_or_minor_interval != exact_binomial_interval(self.combined_equivalent_or_minor_count, self.combined_reviewed_transform_count, 0.95):
            raise ValueError("combined interval must be the exact 95% binomial interval")
        require_bool("overall_gate_passed", self.overall_gate_passed)
        if self.overall_gate_passed != (self.e20.gate_passed and self.e21.gate_passed):
            raise ValueError("E25 overall gate must require both independently verified run gates")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match E25 blind fidelity report")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": self.algorithm_version, "preregistration_hash": self.preregistration_hash, "condition_plan_hash": self.condition_plan_hash, "e20": self.e20, "e21": self.e21, "combined_reviewed_transform_count": self.combined_reviewed_transform_count, "combined_equivalent_or_minor_count": self.combined_equivalent_or_minor_count, "combined_material_change_count": self.combined_material_change_count, "combined_cannot_judge_count": self.combined_cannot_judge_count, "combined_equivalent_or_minor_rate": self.combined_equivalent_or_minor_rate, "combined_equivalent_or_minor_interval": self.combined_equivalent_or_minor_interval, "overall_gate_passed": self.overall_gate_passed}


def _cell_sort_key(value: E25FidelityCell) -> tuple[str, int, str, str, str]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain.value, value.experiment_id


def _cell_identity(value) -> tuple[str, int, str, CorpusDomain]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain


def _cells(experiment_id: str, selection, audit: BlindHumanFidelityAudit) -> tuple[E25FidelityCell, ...]:
    adjudications = {value.sample_id: value for value in audit.adjudications}
    entries_by_cell: dict[tuple[str, int, str, CorpusDomain], list[object]] = {}
    for entry in selection.entries:
        entries_by_cell.setdefault(_cell_identity(entry), []).append(entry)
    result = []
    for cell in selection.cells:
        entries = tuple(entries_by_cell.get(_cell_identity(cell), ()))
        review_ids = tuple(sorted({value.review_sample_id for value in entries}))
        if len(review_ids) != cell.selected_count:
            raise ValueError("E25 cell selected count does not match unique review identities")
        labels = tuple(adjudications[value].label for value in review_ids)
        favorable = sum(value is FidelityLabel.EQUIVALENT_OR_MINOR for value in labels)
        material = sum(value is FidelityLabel.MATERIAL_CHANGE for value in labels)
        cannot = sum(value is FidelityLabel.CANNOT_JUDGE for value in labels)
        reviewed = len(labels)
        rate = None if reviewed == 0 else favorable / reviewed
        interval = None if reviewed == 0 else exact_binomial_interval(favorable, reviewed, 0.95)
        payload = {"algorithm_version": E25_BLIND_FIDELITY_ALGORITHM_VERSION, "experiment_id": experiment_id, "hypothesis_class": cell.hypothesis_class, "budget": cell.budget, "budget_unit": cell.budget_unit, "domain": cell.domain.value, "candidate_count": cell.candidate_count, "selected_count": cell.selected_count, "quartile_candidate_counts": cell.quartile_candidate_counts, "quartile_selected_counts": cell.quartile_selected_counts, "reviewed_count": reviewed, "equivalent_or_minor_count": favorable, "material_change_count": material, "cannot_judge_count": cannot, "equivalent_or_minor_rate": rate, "equivalent_or_minor_interval": interval}
        result.append(E25FidelityCell(experiment_id, cell.hypothesis_class, cell.budget, cell.budget_unit, cell.domain, cell.candidate_count, cell.selected_count, cell.quartile_candidate_counts, cell.quartile_selected_counts, reviewed, favorable, material, cannot, rate, interval, sha256_json(payload)))
    return tuple(sorted(result, key=_cell_sort_key))


def _run_summary(experiment_id: str, execution_id: str, authorization_hash: str, corpus_manifest_hash: str, result_bundle_hash: str, selection, audit: BlindHumanFidelityAudit, failure_rows, outcome_rows, preregistration: ConfirmatoryPreregistration) -> E25RunFidelitySummary:
    cells = _cells(experiment_id, selection, audit)
    counts = {FidelityLabel.EQUIVALENT_OR_MINOR: 0, FidelityLabel.MATERIAL_CHANGE: 0, FidelityLabel.CANNOT_JUDGE: 0}
    for adjudication in audit.adjudications:
        counts[adjudication.label] += 1
    reviewed = len(audit.adjudications)
    if reviewed <= 0:
        raise ValueError("E25 requires reviewed blind fidelity evidence for each run")
    favorable = counts[FidelityLabel.EQUIVALENT_OR_MINOR]
    material = counts[FidelityLabel.MATERIAL_CHANGE]
    cannot = counts[FidelityLabel.CANNOT_JUDGE]
    hard_failures = sum(value.reason_code is ExperimentReasonCode.HARD_INVARIANT_FAILURE for value in failure_rows) + sum(not value.fidelity.hard_pass for value in outcome_rows)
    rate = favorable / reviewed
    interval = exact_binomial_interval(favorable, reviewed, 0.95)
    gate = preregistration.fidelity_gate
    gate_passed = reviewed >= gate.minimum_audited_samples and rate >= gate.minimum_equivalent_or_minor_rate and hard_failures <= gate.maximum_hard_invariant_violations
    payload = {"algorithm_version": E25_BLIND_FIDELITY_ALGORITHM_VERSION, "experiment_id": experiment_id, "execution_id": execution_id, "authorization_hash": authorization_hash, "corpus_manifest_hash": corpus_manifest_hash, "result_bundle_hash": result_bundle_hash, "selection_hash": selection.selection_hash, "audit_hash": audit.audit_hash, "cells": cells, "reviewed_transform_count": reviewed, "equivalent_or_minor_count": favorable, "material_change_count": material, "cannot_judge_count": cannot, "hard_invariant_failure_count": hard_failures, "equivalent_or_minor_rate": rate, "equivalent_or_minor_interval": interval, "gate_passed": gate_passed}
    return E25RunFidelitySummary(experiment_id, execution_id, authorization_hash, corpus_manifest_hash, result_bundle_hash, selection.selection_hash, audit.audit_hash, cells, reviewed, favorable, material, cannot, hard_failures, rate, interval, gate_passed, sha256_json(payload))


def build_e25_blind_fidelity_report(preregistration: ConfirmatoryPreregistration, condition_plan: E20ConditionPlan, e20_result_bundle: E20ResultBundle, e20_authorization: E20ExecutionAuthorization, e20_corpus_manifest: CorpusManifest, e20_selection: E20HumanAuditSelection, e20_audit: BlindHumanFidelityAudit, e21_result_bundle: E21ResultBundle, e21_authorization: E21ExecutionAuthorization, e21_started_ledger: E21RunLedger, e21_corpus_manifest: CorpusManifest, e21_selection: E21HumanAuditSelection, e21_audit: BlindHumanFidelityAudit) -> E25BlindFidelityReport:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    verify_e20_condition_plan(condition_plan, preregistration)
    verify_e20_result_bundle(e20_result_bundle, e20_authorization, preregistration, e20_corpus_manifest, condition_plan)
    verify_e21_result_bundle(e21_result_bundle, e21_authorization, e21_started_ledger, preregistration, e21_corpus_manifest, condition_plan)
    verify_e20_human_audit_evidence(e20_selection, e20_audit, e20_result_bundle, preregistration, e20_corpus_manifest, condition_plan)
    verify_e21_human_audit_evidence(e21_selection, e21_audit, e21_result_bundle, preregistration, e21_corpus_manifest, condition_plan)
    e20 = _run_summary("E20", e20_result_bundle.execution_id, e20_authorization.authorization_hash, e20_corpus_manifest.manifest_hash, e20_result_bundle.bundle_hash, e20_selection, e20_audit, e20_result_bundle.failure_rows, e20_result_bundle.outcome_rows, preregistration)
    e21 = _run_summary("E21", e21_result_bundle.execution_id, e21_authorization.authorization_hash, e21_corpus_manifest.manifest_hash, e21_result_bundle.bundle_hash, e21_selection, e21_audit, e21_result_bundle.failure_rows, e21_result_bundle.outcome_rows, preregistration)
    reviewed = e20.reviewed_transform_count + e21.reviewed_transform_count
    favorable = e20.equivalent_or_minor_count + e21.equivalent_or_minor_count
    material = e20.material_change_count + e21.material_change_count
    cannot = e20.cannot_judge_count + e21.cannot_judge_count
    rate = favorable / reviewed
    interval = exact_binomial_interval(favorable, reviewed, 0.95)
    overall = e20.gate_passed and e21.gate_passed
    payload = {"algorithm_version": E25_BLIND_FIDELITY_ALGORITHM_VERSION, "preregistration_hash": preregistration.preregistration_hash, "condition_plan_hash": condition_plan.plan_hash, "e20": e20, "e21": e21, "combined_reviewed_transform_count": reviewed, "combined_equivalent_or_minor_count": favorable, "combined_material_change_count": material, "combined_cannot_judge_count": cannot, "combined_equivalent_or_minor_rate": rate, "combined_equivalent_or_minor_interval": interval, "overall_gate_passed": overall}
    return E25BlindFidelityReport(E25_BLIND_FIDELITY_ALGORITHM_VERSION, preregistration.preregistration_hash, condition_plan.plan_hash, e20, e21, reviewed, favorable, material, cannot, rate, interval, overall, sha256_json(payload))


def verify_e25_blind_fidelity_report(report: E25BlindFidelityReport, *args, **kwargs) -> None:
    if not isinstance(report, E25BlindFidelityReport):
        raise TypeError("report must be an E25BlindFidelityReport")
    expected = build_e25_blind_fidelity_report(*args, **kwargs)
    if report != expected:
        raise ValueError("E25 blind fidelity report does not replay exactly from verified E20 and E21 evidence")
