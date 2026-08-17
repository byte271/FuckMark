from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusDomain, CorpusManifest
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e21_bundle import E21ResultBundle
from ._e21_human_audit_legacy import (
    E21HumanAuditCell,
    E21HumanAuditEvidenceError,
    E21HumanAuditSelection as _LegacyE21HumanAuditSelection,
    E21HumanAuditSelectionEntry,
    E21HumanAuditSelectionError,
    build_e21_human_audit_selection as _build_legacy_e21_human_audit_selection,
    verify_e21_human_audit_evidence as _verify_legacy_e21_human_audit_evidence,
)


E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION = "e21-human-audit-selection-v2"


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


@dataclass(frozen=True, slots=True)
class E21HumanAuditSelection:
    algorithm_version: str
    preregistration_hash: str
    human_audit_plan_hash: str
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
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("selection_hash", self.selection_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.cells, tuple) or not self.cells:
            raise TypeError("cells must be a non-empty tuple")
        if any(not isinstance(value, E21HumanAuditCell) for value in self.cells):
            raise TypeError("cells must contain E21HumanAuditCell values")
        if self.cells != tuple(sorted(self.cells, key=_cell_sort_key)):
            raise ValueError("E21 human-audit cells must be canonically ordered")
        if len({_cell_identity(value) for value in self.cells}) != len(self.cells):
            raise ValueError("E21 human-audit cells must be unique")
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple")
        if any(not isinstance(value, E21HumanAuditSelectionEntry) for value in self.entries):
            raise TypeError("entries must contain E21HumanAuditSelectionEntry values")
        if self.entries != tuple(sorted(self.entries, key=_entry_sort_key)):
            raise ValueError("E21 human-audit entries must be canonically ordered")
        if len({value.entry_hash for value in self.entries}) != len(self.entries):
            raise ValueError("E21 human-audit selection entries must be unique")
        cell_by_identity = {_cell_identity(value): value for value in self.cells}
        entry_counts: dict[tuple[str, int, str, CorpusDomain], list[int]] = defaultdict(
            lambda: [0, 0, 0, 0]
        )
        for entry in self.entries:
            identity = (entry.hypothesis_class, entry.budget, entry.budget_unit, entry.domain)
            if identity not in cell_by_identity:
                raise ValueError("E21 human-audit entry references an unknown cell")
            entry_counts[identity][entry.degradation_quartile - 1] += 1
        for identity, cell in cell_by_identity.items():
            if tuple(entry_counts[identity]) != cell.quartile_selected_counts:
                raise ValueError("E21 human-audit entry counts do not match cell counts")
        require_int("unique_selected_transform_count", self.unique_selected_transform_count)
        if self.unique_selected_transform_count != len(
            {value.review_sample_id for value in self.entries}
        ):
            raise ValueError("unique_selected_transform_count does not match E21 selected reviews")
        if self.selection_hash != sha256_json(self._payload()):
            raise ValueError("selection_hash does not match E21 human-audit selection")

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


def _from_legacy(selection: _LegacyE21HumanAuditSelection) -> E21HumanAuditSelection:
    payload = {
        "algorithm_version": E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        "preregistration_hash": selection.preregistration_hash,
        "human_audit_plan_hash": selection.human_audit_plan_hash,
        "corpus_manifest_hash": selection.corpus_manifest_hash,
        "condition_plan_hash": selection.condition_plan_hash,
        "cells": selection.cells,
        "entries": selection.entries,
        "unique_selected_transform_count": selection.unique_selected_transform_count,
    }
    return E21HumanAuditSelection(
        E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
        selection.preregistration_hash,
        selection.human_audit_plan_hash,
        selection.corpus_manifest_hash,
        selection.condition_plan_hash,
        selection.cells,
        selection.entries,
        selection.unique_selected_transform_count,
        sha256_json(payload),
    )


def build_e21_human_audit_selection(
    result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21HumanAuditSelection:
    legacy = _build_legacy_e21_human_audit_selection(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    return _from_legacy(legacy)


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
    legacy = _build_legacy_e21_human_audit_selection(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    _verify_legacy_e21_human_audit_evidence(
        legacy,
        audit,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
