from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, CorpusManifest, WatermarkLabel
from ..detectors.calibration_statistics import ExactBinomialInterval, exact_binomial_interval
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit, FidelityLabel
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e20_rows import E20HumanFidelityStatus
from .e21_bundle import E21ResultBundle
from .e21_rows import E21OutcomeRow


E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION = "e21-human-audit-selection-v1"
E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION = "e21-human-fidelity-summary-v1"


class E21HumanAuditSelectionError(ValueError):
    pass


class E21HumanAuditEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E21HumanAuditCell:
    hypothesis_class: str
    budget: int
    budget_unit: str
    domain: CorpusDomain
    candidate_count: int
    selected_count: int
    quartile_candidate_counts: tuple[int, int, int, int]
    quartile_selected_counts: tuple[int, int, int, int]
    cell_hash: str

    def __post_init__(self) -> None:
        require_clean_string("hypothesis_class", self.hypothesis_class)
        require_int("budget", self.budget)
        require_clean_string("budget_unit", self.budget_unit)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("candidate_count", self.candidate_count)
        require_int("selected_count", self.selected_count)
        if self.candidate_count < 0 or self.selected_count < 0 or self.selected_count > self.candidate_count:
            raise ValueError("invalid E21 human-audit cell counts")
        for name, values in (
            ("quartile_candidate_counts", self.quartile_candidate_counts),
            ("quartile_selected_counts", self.quartile_selected_counts),
        ):
            if not isinstance(values, tuple) or len(values) != 4:
                raise TypeError(f"{name} must contain four counts")
            for value in values:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} counts must be non-negative")
        if sum(self.quartile_candidate_counts) != self.candidate_count:
            raise ValueError("E21 quartile candidate counts do not close")
        if sum(self.quartile_selected_counts) != self.selected_count:
            raise ValueError("E21 quartile selected counts do not close")
        if any(selected > candidate for selected, candidate in zip(self.quartile_selected_counts, self.quartile_candidate_counts)):
            raise ValueError("E21 quartile selected count exceeds candidate count")
        require_sha256("cell_hash", self.cell_hash)
        if self.cell_hash != sha256_json(self._payload()):
            raise ValueError("cell_hash does not match E21 human-audit cell")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "hypothesis_class": self.hypothesis_class,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "domain": self.domain.value,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "quartile_candidate_counts": self.quartile_candidate_counts,
            "quartile_selected_counts": self.quartile_selected_counts,
        }


@dataclass(frozen=True, slots=True)
class E21HumanAuditSelectionEntry:
    sample_id: str
    transform_condition_id: str
    hypothesis_class: str
    budget: int
    budget_unit: str
    domain: CorpusDomain
    degradation_quartile: int
    degradation_score: float
    source_text_hash: str
    transformed_text_hash: str
    blind_original_first: bool
    review_sample_id: str
    entry_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("sample_id", self.sample_id),
            ("transform_condition_id", self.transform_condition_id),
            ("hypothesis_class", self.hypothesis_class),
            ("budget_unit", self.budget_unit),
            ("review_sample_id", self.review_sample_id),
        ):
            require_clean_string(name, value)
        require_int("budget", self.budget)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("degradation_quartile", self.degradation_quartile)
        if self.degradation_quartile < 1 or self.degradation_quartile > 4:
            raise ValueError("degradation_quartile must be between one and four")
        if isinstance(self.degradation_score, bool) or not isinstance(self.degradation_score, (int, float)):
            raise TypeError("degradation_score must be a real number")
        score = float(self.degradation_score)
        if not math.isfinite(score):
            raise ValueError("degradation_score must be finite")
        object.__setattr__(self, "degradation_score", score)
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.source_text_hash == self.transformed_text_hash:
            raise ValueError("E21 audit selection entries must represent changed text")
        require_bool("blind_original_first", self.blind_original_first)
        require_sha256("entry_hash", self.entry_hash)
        if self.entry_hash != sha256_json(self._payload()):
            raise ValueError("entry_hash does not match E21 human-audit selection entry")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "sample_id": self.sample_id,
            "transform_condition_id": self.transform_condition_id,
            "hypothesis_class": self.hypothesis_class,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "domain": self.domain.value,
            "degradation_quartile": self.degradation_quartile,
            "degradation_score": self.degradation_score,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "blind_original_first": self.blind_original_first,
            "review_sample_id": self.review_sample_id,
        }


@dataclass(frozen=True, slots=True)
class E21HumanAuditSelection:
    algorithm_version: str
    preregistration_hash: str
    human_audit_plan_hash: str
    result_bundle_hash: str
    corpus_manifest_hash: str
    condition_plan_hash: str
    cells: tuple[E21HumanAuditCell, ...]
    entries: tuple[E21HumanAuditSelectionEntry, ...]
    unique_selected_transform_count: int
    selection_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 human-audit selection algorithm version")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("human_audit_plan_hash", self.human_audit_plan_hash),
            ("result_bundle_hash", self.result_bundle_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("selection_hash", self.selection_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.cells, tuple) or not self.cells:
            raise TypeError("cells must be a non-empty tuple")
        if any(not isinstance(value, E21HumanAuditCell) for value in self.cells):
            raise TypeError("cells must contain E21HumanAuditCell values")
        expected_cells = tuple(sorted(self.cells, key=_cell_sort_key))
        if self.cells != expected_cells:
            raise ValueError("E21 human-audit cells must be canonically ordered")
        if len({_cell_identity(value) for value in self.cells}) != len(self.cells):
            raise ValueError("E21 human-audit cells must be unique")
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple")
        if any(not isinstance(value, E21HumanAuditSelectionEntry) for value in self.entries):
            raise TypeError("entries must contain E21HumanAuditSelectionEntry values")
        expected_entries = tuple(sorted(self.entries, key=_entry_sort_key))
        if self.entries != expected_entries:
            raise ValueError("E21 human-audit entries must be canonically ordered")
        if len({value.entry_hash for value in self.entries}) != len(self.entries):
            raise ValueError("E21 human-audit selection entries must be unique")
        cell_by_identity = {_cell_identity(value): value for value in self.cells}
        entry_counts: dict[tuple[str, int, str, CorpusDomain], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        for entry in self.entries:
            identity = (entry.hypothesis_class, entry.budget, entry.budget_unit, entry.domain)
            if identity not in cell_by_identity:
                raise ValueError("E21 human-audit entry references an unknown cell")
            entry_counts[identity][entry.degradation_quartile - 1] += 1
        for identity, cell in cell_by_identity.items():
            if tuple(entry_counts[identity]) != cell.quartile_selected_counts:
                raise ValueError("E21 human-audit entry counts do not match cell counts")
        require_int("unique_selected_transform_count", self.unique_selected_transform_count)
        if self.unique_selected_transform_count != len({value.review_sample_id for value in self.entries}):
            raise ValueError("unique_selected_transform_count does not match E21 selected reviews")
        if self.selection_hash != sha256_json(self._payload()):
            raise ValueError("selection_hash does not match E21 human-audit selection")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "human_audit_plan_hash": self.human_audit_plan_hash,
            "result_bundle_hash": self.result_bundle_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "condition_plan_hash": self.condition_plan_hash,
            "cells": self.cells,
            "entries": self.entries,
            "unique_selected_transform_count": self.unique_selected_transform_count,
        }


@dataclass(frozen=True, slots=True)
class E21HumanFidelitySummary:
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
            raise ValueError("E21 human fidelity summary requires reviewed transforms")
        if self.reviewed_transform_count != self.equivalent_or_minor_count + self.material_change_count + self.cannot_judge_count:
            raise ValueError("E21 human fidelity adjudication counts do not close")
        if isinstance(self.equivalent_or_minor_rate, bool) or not isinstance(self.equivalent_or_minor_rate, (int, float)):
            raise TypeError("equivalent_or_minor_rate must be a real number")
        rate = float(self.equivalent_or_minor_rate)
        if not math.isfinite(rate) or rate < 0.0 or rate > 1.0:
            raise ValueError("equivalent_or_minor_rate must be between zero and one")
        object.__setattr__(self, "equivalent_or_minor_rate", rate)
        if not isinstance(self.equivalent_or_minor_interval, ExactBinomialInterval):
            raise TypeError("equivalent_or_minor_interval must be an ExactBinomialInterval")
        require_bool("gate_passed", self.gate_passed)
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match E21 human fidelity summary")

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


@dataclass(frozen=True, slots=True)
class _Candidate:
    sample_id: str
    transform_condition_id: str
    hypothesis_class: str
    budget: int
    budget_unit: str
    domain: CorpusDomain
    degradation_score: float
    source_text_hash: str
    transformed_text_hash: str
    blind_original_first: bool
    review_sample_id: str
    candidate_hash: str


def _cell_identity(value: E21HumanAuditCell) -> tuple[str, int, str, CorpusDomain]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain


def _cell_sort_key(value: E21HumanAuditCell) -> tuple[str, int, str, str]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain.value


def _entry_sort_key(value: E21HumanAuditSelectionEntry) -> tuple[object, ...]:
    return (
        value.hypothesis_class,
        value.budget,
        value.budget_unit,
        value.domain.value,
        value.degradation_quartile,
        value.review_sample_id,
        value.entry_hash,
    )


def _review_sample_id(sample_id: str, transform_condition_id: str) -> str:
    return "e21-human-" + sha256_json(
        {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "sample_id": sample_id,
            "transform_condition_id": transform_condition_id,
        }
    )


def _blind_original_first(seed: int, review_sample_id: str, source_hash: str, transformed_hash: str) -> bool:
    value = sha256_json(
        {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "seed": seed,
            "review_sample_id": review_sample_id,
            "source_text_hash": source_hash,
            "transformed_text_hash": transformed_hash,
        }
    )
    return int(value[-1], 16) % 2 == 0


def _selection_rank(seed: int, candidate_hash: str, quartile: int) -> str:
    return sha256_json(
        {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "seed": seed,
            "candidate_hash": candidate_hash,
            "quartile": quartile,
        }
    )


def _allocate_quota(capacities: tuple[int, int, int, int], target: int) -> tuple[int, int, int, int]:
    if target >= sum(capacities):
        return capacities
    base = target // 4
    quotas = [min(base, value) for value in capacities]
    remaining = target - sum(quotas)
    while remaining:
        progressed = False
        for index in range(4):
            if quotas[index] < capacities[index]:
                quotas[index] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            raise E21HumanAuditSelectionError("E21 quartile quota allocation could not satisfy target")
    return tuple(quotas)


def _candidate_groups(
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
):
    plan = preregistration.human_audit_plan
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    headline_semantics = tuple(
        sorted(
            {
                (value.hypothesis_class, value.budget, value.budget_unit)
                for value in condition_plan.conditions
                if math.isclose(value.target_fpr, plan.degradation_target_fpr, rel_tol=0.0, abs_tol=1e-15)
            }
        )
    )
    expected_cells = tuple(
        sorted(
            (
                (hypothesis_class, budget, budget_unit, domain)
                for hypothesis_class, budget, budget_unit in headline_semantics
                for domain in preregistration.domains
            ),
            key=lambda value: (value[0], value[1], value[2], value[3].value),
        )
    )
    grouped_rows: dict[tuple[str, str], list[E21OutcomeRow]] = defaultdict(list)
    for row in result_bundle.outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        grouped_rows[(row.identity.sample_id, condition.transform_condition_id)].append(row)
    candidates: dict[tuple[str, int, str, CorpusDomain], list[_Candidate]] = defaultdict(list)
    for (sample_id, transform_condition_id), rows in sorted(grouped_rows.items()):
        sample = sample_by_id[sample_id]
        if sample.label is not WatermarkLabel.WATERMARKED:
            continue
        first = rows[0]
        if not first.transform.eligible or first.text.source_text_hash == first.text.transformed_text_hash:
            continue
        family_rows: dict[str, list[E21OutcomeRow]] = defaultdict(list)
        for row in rows:
            condition = condition_by_id[row.identity.condition_id]
            if math.isclose(condition.target_fpr, plan.degradation_target_fpr, rel_tol=0.0, abs_tol=1e-15):
                family_rows[condition.hypothesis_class].append(row)
        for hypothesis_class, relevant_rows in sorted(family_rows.items()):
            condition = condition_by_id[relevant_rows[0].identity.condition_id]
            score = math.fsum(
                row.detector.pristine_standardized_margin - row.detector.transformed_standardized_margin
                for row in relevant_rows
            ) / len(relevant_rows)
            review_id = _review_sample_id(sample_id, transform_condition_id)
            source_hash = first.text.source_text_hash
            transformed_hash = first.text.transformed_text_hash
            original_first = _blind_original_first(plan.sampling_seed, review_id, source_hash, transformed_hash)
            payload = {
                "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
                "sample_id": sample_id,
                "transform_condition_id": transform_condition_id,
                "hypothesis_class": hypothesis_class,
                "budget": condition.budget,
                "budget_unit": condition.budget_unit,
                "domain": sample.domain.value,
                "degradation_score": score,
                "source_text_hash": source_hash,
                "transformed_text_hash": transformed_hash,
                "blind_original_first": original_first,
                "review_sample_id": review_id,
            }
            candidates[(hypothesis_class, condition.budget, condition.budget_unit, sample.domain)].append(
                _Candidate(
                    sample_id,
                    transform_condition_id,
                    hypothesis_class,
                    condition.budget,
                    condition.budget_unit,
                    sample.domain,
                    score,
                    source_hash,
                    transformed_hash,
                    original_first,
                    review_id,
                    sha256_json(payload),
                )
            )
    return expected_cells, candidates


def build_e21_human_audit_selection(
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21HumanAuditSelection:
    if not isinstance(result_bundle, E21ResultBundle):
        raise TypeError("result_bundle must be an E21ResultBundle")
    if result_bundle.corpus_manifest_hash != corpus_manifest.manifest_hash:
        raise E21HumanAuditSelectionError("E21 result bundle corpus hash does not match audit corpus")
    if result_bundle.condition_plan_hash != condition_plan.plan_hash:
        raise E21HumanAuditSelectionError("E21 result bundle condition plan does not match audit condition plan")
    expected_cells, candidates_by_cell = _candidate_groups(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    plan = preregistration.human_audit_plan
    cells: list[E21HumanAuditCell] = []
    entries: list[E21HumanAuditSelectionEntry] = []
    for identity in expected_cells:
        values = tuple(candidates_by_cell.get(identity, ()))
        ranked = tuple(sorted(values, key=lambda value: (value.degradation_score, value.candidate_hash)))
        quartiles: dict[int, list[_Candidate]] = {1: [], 2: [], 3: [], 4: []}
        for index, candidate in enumerate(ranked):
            quartile = min(4, index * 4 // len(ranked) + 1) if ranked else 1
            quartiles[quartile].append(candidate)
        capacities = tuple(len(quartiles[index]) for index in range(1, 5))
        target = min(plan.target_sample_count, len(ranked))
        quotas = _allocate_quota(capacities, target)
        selected_counts = [0, 0, 0, 0]
        for quartile in range(1, 5):
            ordered = tuple(
                sorted(
                    quartiles[quartile],
                    key=lambda value: (_selection_rank(plan.sampling_seed, value.candidate_hash, quartile), value.candidate_hash),
                )
            )
            selected = ordered[: quotas[quartile - 1]]
            selected_counts[quartile - 1] = len(selected)
            for candidate in selected:
                payload = {
                    "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
                    "sample_id": candidate.sample_id,
                    "transform_condition_id": candidate.transform_condition_id,
                    "hypothesis_class": candidate.hypothesis_class,
                    "budget": candidate.budget,
                    "budget_unit": candidate.budget_unit,
                    "domain": candidate.domain.value,
                    "degradation_quartile": quartile,
                    "degradation_score": candidate.degradation_score,
                    "source_text_hash": candidate.source_text_hash,
                    "transformed_text_hash": candidate.transformed_text_hash,
                    "blind_original_first": candidate.blind_original_first,
                    "review_sample_id": candidate.review_sample_id,
                }
                entries.append(
                    E21HumanAuditSelectionEntry(
                        candidate.sample_id,
                        candidate.transform_condition_id,
                        candidate.hypothesis_class,
                        candidate.budget,
                        candidate.budget_unit,
                        candidate.domain,
                        quartile,
                        candidate.degradation_score,
                        candidate.source_text_hash,
                        candidate.transformed_text_hash,
                        candidate.blind_original_first,
                        candidate.review_sample_id,
                        sha256_json(payload),
                    )
                )
        hypothesis_class, budget, budget_unit, domain = identity
        cell_payload = {
            "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "hypothesis_class": hypothesis_class,
            "budget": budget,
            "budget_unit": budget_unit,
            "domain": domain.value,
            "candidate_count": len(ranked),
            "selected_count": target,
            "quartile_candidate_counts": capacities,
            "quartile_selected_counts": tuple(selected_counts),
        }
        cells.append(
            E21HumanAuditCell(
                hypothesis_class,
                budget,
                budget_unit,
                domain,
                len(ranked),
                target,
                capacities,
                tuple(selected_counts),
                sha256_json(cell_payload),
            )
        )
    ordered_cells = tuple(sorted(cells, key=_cell_sort_key))
    ordered_entries = tuple(sorted(entries, key=_entry_sort_key))
    payload = {
        "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "human_audit_plan_hash": plan.plan_hash,
        "result_bundle_hash": result_bundle.bundle_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "cells": ordered_cells,
        "entries": ordered_entries,
        "unique_selected_transform_count": len({value.review_sample_id for value in ordered_entries}),
    }
    return E21HumanAuditSelection(
        E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        plan.plan_hash,
        result_bundle.bundle_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        ordered_cells,
        ordered_entries,
        payload["unique_selected_transform_count"],
        sha256_json(payload),
    )


def verify_e21_human_audit_selection(
    selection: E21HumanAuditSelection,
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(selection, E21HumanAuditSelection):
        raise TypeError("selection must be an E21HumanAuditSelection")
    expected = build_e21_human_audit_selection(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if selection != expected:
        raise E21HumanAuditSelectionError("E21 human-audit selection does not replay exactly")


def verify_e21_human_audit_evidence(
    selection: E21HumanAuditSelection,
    audit: BlindHumanFidelityAudit,
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    verify_e21_human_audit_selection(
        selection,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if not isinstance(audit, BlindHumanFidelityAudit):
        raise TypeError("audit must be a BlindHumanFidelityAudit")
    if not selection.entries:
        raise E21HumanAuditEvidenceError("E21 confirmatory human audit has no selected changed outputs")
    if audit.rule_hash != preregistration.transform_ruleset_hash:
        raise E21HumanAuditEvidenceError("E21 audit ruleset does not match preregistration")
    if audit.review_policy_id != preregistration.human_audit_plan.review_policy_id:
        raise E21HumanAuditEvidenceError("E21 audit review policy does not match preregistration")
    entries_by_review: dict[str, E21HumanAuditSelectionEntry] = {}
    for entry in selection.entries:
        previous = entries_by_review.setdefault(entry.review_sample_id, entry)
        if (
            previous.sample_id != entry.sample_id
            or previous.transform_condition_id != entry.transform_condition_id
            or previous.source_text_hash != entry.source_text_hash
            or previous.transformed_text_hash != entry.transformed_text_hash
        ):
            raise E21HumanAuditEvidenceError("one E21 review identity resolves to inconsistent transforms")
    if {value.sample_id for value in audit.review_samples} != set(entries_by_review):
        raise E21HumanAuditEvidenceError("E21 review samples must exactly cover selected transforms")
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    review_by_id = {value.sample_id: value for value in audit.review_samples}
    for review_id, entry in entries_by_review.items():
        review = review_by_id[review_id]
        source = sample_by_id[entry.sample_id]
        if review.rule_hash != preregistration.transform_ruleset_hash:
            raise E21HumanAuditEvidenceError("E21 review sample ruleset does not match preregistration")
        if review.source_text != source.text or review.source_text_hash != source.text_sha256:
            raise E21HumanAuditEvidenceError("E21 review source text does not match sealed rerun corpus")
        if review.source_text_hash != entry.source_text_hash:
            raise E21HumanAuditEvidenceError("E21 review source hash does not match selection")
        if review.transformed_text_hash != entry.transformed_text_hash:
            raise E21HumanAuditEvidenceError("E21 review transformed hash does not match selection")
    adjudication_by_id = {value.sample_id: value for value in audit.adjudications}
    label_map = {
        FidelityLabel.EQUIVALENT_OR_MINOR: E20HumanFidelityStatus.EQUIVALENT_OR_MINOR,
        FidelityLabel.MATERIAL_CHANGE: E20HumanFidelityStatus.MATERIAL_CHANGE,
        FidelityLabel.CANNOT_JUDGE: E20HumanFidelityStatus.CANNOT_JUDGE,
    }
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    selected_by_transform: dict[tuple[str, str], str] = {}
    for review_id, entry in entries_by_review.items():
        key = (entry.sample_id, entry.transform_condition_id)
        previous = selected_by_transform.setdefault(key, review_id)
        if previous != review_id:
            raise E21HumanAuditEvidenceError("selected E21 transform maps to multiple review identities")
    for row in result_bundle.outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        key = (row.identity.sample_id, condition.transform_condition_id)
        review_id = selected_by_transform.get(key)
        if review_id is None:
            if row.fidelity.human_status is not E20HumanFidelityStatus.NOT_SELECTED:
                raise E21HumanAuditEvidenceError("nonselected E21 transform contains a human fidelity judgment")
            if row.fidelity.human_adjudication_hash is not None:
                raise E21HumanAuditEvidenceError("nonselected E21 transform contains an adjudication hash")
            continue
        adjudication = adjudication_by_id[review_id]
        if row.fidelity.human_status is not label_map[adjudication.label]:
            raise E21HumanAuditEvidenceError("E21 selected transform status does not match blind adjudication")
        if row.fidelity.human_adjudication_hash != adjudication.adjudication_hash:
            raise E21HumanAuditEvidenceError("E21 adjudication hash does not match blind audit evidence")


def build_e21_human_fidelity_summary(
    selection: E21HumanAuditSelection,
    audit: BlindHumanFidelityAudit,
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21HumanFidelitySummary:
    verify_e21_human_audit_evidence(
        selection,
        audit,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    label_counts = {
        FidelityLabel.EQUIVALENT_OR_MINOR: 0,
        FidelityLabel.MATERIAL_CHANGE: 0,
        FidelityLabel.CANNOT_JUDGE: 0,
    }
    for adjudication in audit.adjudications:
        label_counts[adjudication.label] += 1
    reviewed = len(audit.adjudications)
    favorable = label_counts[FidelityLabel.EQUIVALENT_OR_MINOR]
    material = label_counts[FidelityLabel.MATERIAL_CHANGE]
    cannot = label_counts[FidelityLabel.CANNOT_JUDGE]
    hard_failures = sum(not row.fidelity.hard_pass for row in result_bundle.outcome_rows)
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
    return E21HumanFidelitySummary(
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
