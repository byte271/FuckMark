from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, CorpusManifest, WatermarkLabel
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit, FidelityLabel
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_rows import E20HumanFidelityStatus, E20OutcomeRow


E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION = "e20-human-audit-selection-v1"


class E20HumanAuditSelectionError(ValueError):
    pass


class E20HumanAuditEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E20HumanAuditCell:
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
            raise ValueError("invalid human-audit cell counts")
        for name, values in (
            ("quartile_candidate_counts", self.quartile_candidate_counts),
            ("quartile_selected_counts", self.quartile_selected_counts),
        ):
            if not isinstance(values, tuple) or len(values) != 4:
                raise TypeError(f"{name} must contain four integer counts")
            for value in values:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} counts must be non-negative")
        if sum(self.quartile_candidate_counts) != self.candidate_count:
            raise ValueError("quartile candidate counts do not close")
        if sum(self.quartile_selected_counts) != self.selected_count:
            raise ValueError("quartile selected counts do not close")
        if any(selected > candidate for selected, candidate in zip(self.quartile_selected_counts, self.quartile_candidate_counts)):
            raise ValueError("quartile selected count exceeds candidate count")
        require_sha256("cell_hash", self.cell_hash)
        if self.cell_hash != sha256_json(self._payload()):
            raise ValueError("cell_hash does not match human-audit cell")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
class E20HumanAuditSelectionEntry:
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
            raise ValueError("human-audit selection entries must represent changed text")
        require_bool("blind_original_first", self.blind_original_first)
        require_sha256("entry_hash", self.entry_hash)
        if self.entry_hash != sha256_json(self._payload()):
            raise ValueError("entry_hash does not match human-audit selection entry")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
class E20HumanAuditSelection:
    algorithm_version: str
    preregistration_hash: str
    human_audit_plan_hash: str
    corpus_manifest_hash: str
    condition_plan_hash: str
    cells: tuple[E20HumanAuditCell, ...]
    entries: tuple[E20HumanAuditSelectionEntry, ...]
    unique_selected_transform_count: int
    selection_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 human-audit selection algorithm version")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("human_audit_plan_hash", self.human_audit_plan_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("selection_hash", self.selection_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.cells, tuple) or not self.cells:
            raise TypeError("cells must be a non-empty tuple")
        if any(not isinstance(value, E20HumanAuditCell) for value in self.cells):
            raise TypeError("cells must contain E20HumanAuditCell values")
        expected_cells = tuple(sorted(self.cells, key=_cell_sort_key))
        if self.cells != expected_cells:
            raise ValueError("human-audit cells must be canonically ordered")
        if len({_cell_identity(value) for value in self.cells}) != len(self.cells):
            raise ValueError("human-audit cells must be unique")
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple")
        if any(not isinstance(value, E20HumanAuditSelectionEntry) for value in self.entries):
            raise TypeError("entries must contain E20HumanAuditSelectionEntry values")
        expected_entries = tuple(sorted(self.entries, key=_entry_sort_key))
        if self.entries != expected_entries:
            raise ValueError("human-audit entries must be canonically ordered")
        if len({value.entry_hash for value in self.entries}) != len(self.entries):
            raise ValueError("human-audit selection entries must be unique")
        cell_by_identity = {_cell_identity(value): value for value in self.cells}
        entry_counts: dict[tuple[str, int, str, CorpusDomain], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        for entry in self.entries:
            identity = (entry.hypothesis_class, entry.budget, entry.budget_unit, entry.domain)
            if identity not in cell_by_identity:
                raise ValueError("human-audit entry references an unknown cell")
            entry_counts[identity][entry.degradation_quartile - 1] += 1
        for identity, cell in cell_by_identity.items():
            actual = tuple(entry_counts[identity])
            if actual != cell.quartile_selected_counts:
                raise ValueError("human-audit entry counts do not match cell selection counts")
        require_int("unique_selected_transform_count", self.unique_selected_transform_count)
        if self.unique_selected_transform_count != len({value.review_sample_id for value in self.entries}):
            raise ValueError("unique_selected_transform_count does not match selected review identities")
        if self.selection_hash != sha256_json(self._payload()):
            raise ValueError("selection_hash does not match E20 human-audit selection")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "human_audit_plan_hash": self.human_audit_plan_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "condition_plan_hash": self.condition_plan_hash,
            "cells": self.cells,
            "entries": self.entries,
            "unique_selected_transform_count": self.unique_selected_transform_count,
        }


@dataclass(frozen=True, slots=True)
class _HumanAuditCandidate:
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


def _cell_identity(value: E20HumanAuditCell) -> tuple[str, int, str, CorpusDomain]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain


def _cell_sort_key(value: E20HumanAuditCell) -> tuple[str, int, str, str]:
    return value.hypothesis_class, value.budget, value.budget_unit, value.domain.value


def _entry_sort_key(value: E20HumanAuditSelectionEntry) -> tuple[object, ...]:
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
    return "e20-human-" + sha256_json(
        {
            "sample_id": sample_id,
            "transform_condition_id": transform_condition_id,
        }
    )


def _blind_original_first(seed: int, review_sample_id: str, source_hash: str, transformed_hash: str) -> bool:
    value = sha256_json(
        {
            "selection_algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
            "selection_algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
            raise E20HumanAuditSelectionError("human-audit quartile quota allocation could not satisfy target")
    return tuple(quotas)


def _candidate_groups(
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> tuple[tuple[tuple[str, int, str, CorpusDomain], ...], dict[tuple[str, int, str, CorpusDomain], list[_HumanAuditCandidate]]]:
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
    grouped_rows: dict[tuple[str, str], list[E20OutcomeRow]] = defaultdict(list)
    for row in result_bundle.outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        grouped_rows[(row.identity.sample_id, condition.transform_condition_id)].append(row)
    candidates: dict[tuple[str, int, str, CorpusDomain], list[_HumanAuditCandidate]] = defaultdict(list)
    for (sample_id, transform_condition_id), rows in sorted(grouped_rows.items()):
        sample = sample_by_id[sample_id]
        if sample.label is not WatermarkLabel.WATERMARKED:
            continue
        first = rows[0]
        if not first.transform.eligible or first.text.source_text_hash == first.text.transformed_text_hash:
            continue
        family_rows: dict[str, list[E20OutcomeRow]] = defaultdict(list)
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
            original_first = _blind_original_first(
                plan.sampling_seed,
                review_id,
                source_hash,
                transformed_hash,
            )
            payload = {
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
            candidate = _HumanAuditCandidate(
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
            candidates[(hypothesis_class, condition.budget, condition.budget_unit, sample.domain)].append(candidate)
    return expected_cells, candidates


def build_e20_human_audit_selection(
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E20HumanAuditSelection:
    if not isinstance(result_bundle, E20ResultBundle):
        raise TypeError("result_bundle must be an E20ResultBundle")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if result_bundle.corpus_manifest_hash != corpus_manifest.manifest_hash:
        raise E20HumanAuditSelectionError("result bundle corpus hash does not match human-audit corpus")
    if result_bundle.condition_plan_hash != condition_plan.plan_hash:
        raise E20HumanAuditSelectionError("result bundle condition plan does not match human-audit condition plan")
    if result_bundle.authorization_hash == preregistration.preregistration_hash:
        raise E20HumanAuditSelectionError("authorization hash cannot equal preregistration hash")
    expected_cells, candidates_by_cell = _candidate_groups(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    plan = preregistration.human_audit_plan
    cells: list[E20HumanAuditCell] = []
    entries: list[E20HumanAuditSelectionEntry] = []
    for identity in expected_cells:
        values = tuple(candidates_by_cell.get(identity, ()))
        ranked = tuple(sorted(values, key=lambda value: (value.degradation_score, value.candidate_hash)))
        quartiles: dict[int, list[_HumanAuditCandidate]] = {1: [], 2: [], 3: [], 4: []}
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
                    "algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
                    E20HumanAuditSelectionEntry(
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
            "algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
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
            E20HumanAuditCell(
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
    unique_count = len({value.review_sample_id for value in ordered_entries})
    payload = {
        "algorithm_version": E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "human_audit_plan_hash": plan.plan_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "cells": ordered_cells,
        "entries": ordered_entries,
        "unique_selected_transform_count": unique_count,
    }
    return E20HumanAuditSelection(
        E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        plan.plan_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        ordered_cells,
        ordered_entries,
        unique_count,
        sha256_json(payload),
    )


def verify_e20_human_audit_selection(
    selection: E20HumanAuditSelection,
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(selection, E20HumanAuditSelection):
        raise TypeError("selection must be an E20HumanAuditSelection")
    expected = build_e20_human_audit_selection(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if selection != expected:
        raise E20HumanAuditSelectionError("E20 human-audit selection does not replay exactly from sealed inputs")


def verify_e20_human_audit_evidence(
    selection: E20HumanAuditSelection,
    audit: BlindHumanFidelityAudit,
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    verify_e20_human_audit_selection(
        selection,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if not isinstance(audit, BlindHumanFidelityAudit):
        raise TypeError("audit must be a BlindHumanFidelityAudit")
    if not selection.entries:
        raise E20HumanAuditEvidenceError("confirmatory human audit has no selected changed outputs")
    if audit.rule_hash != preregistration.transform_ruleset_hash:
        raise E20HumanAuditEvidenceError("human-audit evidence ruleset does not match preregistration")
    if audit.review_policy_id != preregistration.human_audit_plan.review_policy_id:
        raise E20HumanAuditEvidenceError("human-audit evidence review policy does not match preregistration")
    entries_by_review: dict[str, E20HumanAuditSelectionEntry] = {}
    for entry in selection.entries:
        previous = entries_by_review.setdefault(entry.review_sample_id, entry)
        if (
            previous.sample_id != entry.sample_id
            or previous.transform_condition_id != entry.transform_condition_id
            or previous.source_text_hash != entry.source_text_hash
            or previous.transformed_text_hash != entry.transformed_text_hash
        ):
            raise E20HumanAuditEvidenceError("one review identity resolves to inconsistent selected transforms")
    if {value.sample_id for value in audit.review_samples} != set(entries_by_review):
        raise E20HumanAuditEvidenceError("human-audit review samples must exactly cover selected transforms")
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    review_by_id = {value.sample_id: value for value in audit.review_samples}
    for review_id, entry in entries_by_review.items():
        review = review_by_id[review_id]
        source = sample_by_id[entry.sample_id]
        if review.rule_hash != preregistration.transform_ruleset_hash:
            raise E20HumanAuditEvidenceError("review sample ruleset does not match preregistration")
        if review.source_text != source.text or review.source_text_hash != source.text_sha256:
            raise E20HumanAuditEvidenceError("review sample source text does not match sealed corpus text")
        if review.source_text_hash != entry.source_text_hash:
            raise E20HumanAuditEvidenceError("review sample source hash does not match selected transform")
        if review.transformed_text_hash != entry.transformed_text_hash:
            raise E20HumanAuditEvidenceError("review sample transformed text does not match selected transform")
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
            raise E20HumanAuditEvidenceError("selected transform maps to multiple review identities")
    for row in result_bundle.outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        key = (row.identity.sample_id, condition.transform_condition_id)
        review_id = selected_by_transform.get(key)
        if review_id is None:
            if row.fidelity.human_status is not E20HumanFidelityStatus.NOT_SELECTED:
                raise E20HumanAuditEvidenceError("nonselected transform contains a human fidelity judgment")
            if row.fidelity.human_adjudication_hash is not None:
                raise E20HumanAuditEvidenceError("nonselected transform contains a human adjudication hash")
            continue
        adjudication = adjudication_by_id[review_id]
        expected_status = label_map[adjudication.label]
        if row.fidelity.human_status is not expected_status:
            raise E20HumanAuditEvidenceError("selected transform human status does not match blind adjudication")
        if row.fidelity.human_adjudication_hash != adjudication.adjudication_hash:
            raise E20HumanAuditEvidenceError("selected transform adjudication hash does not match blind audit evidence")
