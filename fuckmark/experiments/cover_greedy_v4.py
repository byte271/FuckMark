from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
from ..geometry.repetition import PublicRepetitionGeometry
from ..geometry.tuple_closure import TupleClosureReport, compute_tuple_closure
from ..hashing import sha256_json, sha256_text
from ..transforms.candidate_artifacts import CandidateEnumeration
from ..transforms.registry import TransformRegistry
from .cover_greedy_v3 import (
    _conflict_map,
    _root_eligible_windows,
    _token_index_ranges,
)


COVER_GREEDY_V4_ALGORITHM_VERSION = "cover-greedy-key-blind-v4"
COVER_GREEDY_V4_POLICY_ID = "closure-free-root-evidence-v1"


@dataclass(frozen=True, slots=True)
class CoverGreedyV4Result:
    algorithm_version: str
    source_sample_id: str
    source_text_hash: str
    enumeration_hash: str
    ruleset_hash: str
    tokenizer_identity_hash: str
    ngram_len: int
    budget: int
    budget_unit: str
    candidate_count: int
    selection_order: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    selected_candidate_count: int
    unselected_candidate_ids: tuple[str, ...]
    conflict_excluded_candidate_ids: tuple[str, ...]
    budget_exhausted: bool
    static_phase_selections: int
    repair_phase_selections: int
    root_window_count: int
    intact_window_count: int
    tuple_leak_window_count: int
    closure_free: bool
    achieved_zero: bool
    transformed_text_hash: str
    transform_trace_hash: str
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != COVER_GREEDY_V4_ALGORITHM_VERSION:
            raise ValueError("unsupported cover-greedy v4 algorithm version")
        require_clean_string("source_sample_id", self.source_sample_id)
        for name in (
            "source_text_hash",
            "enumeration_hash",
            "ruleset_hash",
            "tokenizer_identity_hash",
            "transformed_text_hash",
            "transform_trace_hash",
            "result_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "ngram_len",
            "budget",
            "candidate_count",
            "selected_candidate_count",
            "root_window_count",
            "intact_window_count",
            "tuple_leak_window_count",
            "static_phase_selections",
            "repair_phase_selections",
        ):
            require_int(name, getattr(self, name))
        if self.ngram_len <= 0 or self.budget < 0 or self.candidate_count < 0:
            raise ValueError("ngram_len must be positive and budget/candidate_count non-negative")
        if self.budget_unit != "operation":
            raise ValueError("cover-greedy v4 supports operation budgets only")
        if self.selected_candidate_count != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_count does not match selected_candidate_ids")
        if self.selected_candidate_count > self.budget:
            raise ValueError("selected candidates exceed budget")
        if tuple(sorted(self.selected_candidate_ids)) != self.selected_candidate_ids:
            raise ValueError("selected_candidate_ids must use canonical candidate-id ordering")
        if len(set(self.selection_order)) != len(self.selection_order):
            raise ValueError("selection_order must not contain duplicates")
        if set(self.selection_order) != set(self.selected_candidate_ids):
            raise ValueError("selection_order and selected_candidate_ids must identify the same set")
        for name, values in (
            ("selection_order", self.selection_order),
            ("selected_candidate_ids", self.selected_candidate_ids),
            ("unselected_candidate_ids", self.unselected_candidate_ids),
            ("conflict_excluded_candidate_ids", self.conflict_excluded_candidate_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(set(values)) != len(values):
                raise TypeError(f"{name} must not contain duplicates")
            for value in values:
                require_sha256(name, value)
        if set(self.selected_candidate_ids) & set(self.unselected_candidate_ids):
            raise ValueError("selected and unselected candidate IDs must be disjoint")
        for name in ("root_window_count", "intact_window_count", "tuple_leak_window_count"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.intact_window_count > self.root_window_count:
            raise ValueError("intact windows cannot exceed root windows")
        expected_closure_free = self.root_window_count > 0 and self.tuple_leak_window_count == 0
        if self.closure_free != expected_closure_free:
            raise ValueError("closure_free does not match window counts")
        if self.achieved_zero != (
            self.root_window_count > 0
            and self.intact_window_count == 0
            and self.tuple_leak_window_count == 0
        ):
            raise ValueError("achieved_zero does not match window counts")
        if self.static_phase_selections < 0 or self.repair_phase_selections < 0:
            raise ValueError("phase counts must be non-negative")
        if self.static_phase_selections + self.repair_phase_selections != self.selected_candidate_count:
            raise ValueError("phase selections must partition selected candidates")
        if self.detector_access_observed is not False or self.secret_access_observed is not False:
            raise ValueError("cover-greedy v4 must remain detector-blind and key-blind")
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash does not match cover-greedy v4 result")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "enumeration_hash": self.enumeration_hash,
            "ruleset_hash": self.ruleset_hash,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "ngram_len": self.ngram_len,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "candidate_count": self.candidate_count,
            "selection_order": self.selection_order,
            "selected_candidate_ids": self.selected_candidate_ids,
            "selected_candidate_count": self.selected_candidate_count,
            "unselected_candidate_ids": self.unselected_candidate_ids,
            "conflict_excluded_candidate_ids": self.conflict_excluded_candidate_ids,
            "budget_exhausted": self.budget_exhausted,
            "static_phase_selections": self.static_phase_selections,
            "repair_phase_selections": self.repair_phase_selections,
            "root_window_count": self.root_window_count,
            "intact_window_count": self.intact_window_count,
            "tuple_leak_window_count": self.tuple_leak_window_count,
            "closure_free": self.closure_free,
            "achieved_zero": self.achieved_zero,
            "transformed_text_hash": self.transformed_text_hash,
            "transform_trace_hash": self.transform_trace_hash,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _selection_hash(source_text_hash: str, selected_ids: tuple[str, ...]) -> str:
    return sha256_json(
        {
            "algorithm_version": COVER_GREEDY_V4_ALGORITHM_VERSION,
            "source_text_hash": source_text_hash,
            "selected_candidate_ids": selected_ids,
        }
    )


def schedule_cover_greedy_v4(
    *,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
    budget: int,
    boundary_margin: int = 1,
) -> CoverGreedyV4Result:
    require_clean_string("source_sample_id", source_sample_id)
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    if not isinstance(enumeration, CandidateEnumeration):
        raise TypeError("enumeration must be a CandidateEnumeration")
    if enumeration.input_text != source_text or enumeration.input_hash != sha256_text(source_text):
        raise ValueError("enumeration does not bind source_text")
    if enumeration.ruleset_hash != registry.ruleset_hash:
        raise ValueError("enumeration ruleset does not match registry")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    require_int("ngram_len", ngram_len)
    require_int("budget", budget)
    require_int("boundary_margin", boundary_margin)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if budget < 0 or boundary_margin < 0:
        raise ValueError("budget and boundary_margin must be non-negative")

    repetition = PublicRepetitionGeometry.create(ngram_len=ngram_len, context_history_size=1024)
    config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=repetition.policy_id,
    )
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=config,
        eligibility_policy=repetition.eligibility_policy,
    )
    root = engine.build_root(source_sample_id=source_sample_id, source_text=source_text)

    encoded = tokenizer(source_text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tuple((int(s), int(e)) for s, e in encoded["offset_mapping"])
    elig_flags = _root_eligible_windows(root.root_tokens, repetition)
    root_window_indices = tuple(index for index, flag in enumerate(elig_flags) if flag)

    def windows_touched_by_token_indices(token_indices: set[int]) -> set[int]:
        first_index = min(token_indices)
        last_index = max(token_indices)
        lowest_start = max(0, last_index - ngram_len + 1)
        highest_start = min(first_index, len(root.root_tokens) - ngram_len)
        return {
            index
            for index in root_window_indices
            if lowest_start <= index <= highest_start
            and any(offset in token_indices for offset in range(index, index + ngram_len))
        }

    static_cover: dict[str, set[int]] = {}
    for candidate in enumeration.candidates:
        touched = _token_index_ranges(offsets, candidate.start, candidate.end, boundary_margin)
        static_cover[candidate.candidate_id] = windows_touched_by_token_indices(touched)

    candidates_by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    conflicts = _conflict_map(enumeration)
    selected_order: list[str] = []
    selected_set: set[str] = set()
    uncovered = set(root_window_indices)
    static_selections = 0

    def feasible() -> tuple[str, ...]:
        return tuple(
            sorted(cid for cid in candidates_by_id if not (conflicts[cid] & selected_set))
        )

    remaining_budget = budget

    while remaining_budget > 0:
        options = [
            cid
            for cid in feasible()
            if cid not in selected_set and static_cover[cid] & uncovered
        ]
        if not options:
            break
        best_id = None
        best_gain = 0
        for cid in options:
            gain = len(static_cover[cid] & uncovered)
            if gain > best_gain or (gain == best_gain and (best_id is None or cid < best_id)):
                best_id = cid
                best_gain = gain
        if best_id is None or best_gain <= 0:
            break
        selected_order.append(best_id)
        selected_set.add(best_id)
        uncovered -= static_cover[best_id]
        static_selections += 1
        remaining_budget -= 1

    def measure(trial_ids: tuple[str, ...]) -> tuple[Any, int, int]:
        transformed = registry.apply(enumeration, trial_ids)
        exact = engine.evaluate_output(
            root=root,
            current_text=source_text,
            output_text=transformed.output_text,
            candidate_id=_selection_hash(enumeration.input_hash, trial_ids),
            rule_hash=registry.ruleset_hash,
            visible_cost_class=0,
            family="cover-greedy-v4",
            tier=0,
        )
        encoded_output = tokenizer(transformed.output_text, add_special_tokens=False)
        closure = compute_tuple_closure(
            root=root.observations,
            transformed_tokens=tuple(encoded_output["input_ids"]),
            expected_output_token_hash=exact.output_token_hash,
        )
        return transformed, exact.surviving_count, closure.leaked_window_count

    selected_ids_tuple = tuple(sorted(selected_set))
    if selected_ids_tuple:
        transformed, intact, leak = measure(selected_ids_tuple)
    else:
        transformed = registry.apply(enumeration, selected_ids_tuple)
        intact = len(root_window_indices)
        encoded_source = tokenizer(source_text, add_special_tokens=False)
        closure = compute_tuple_closure(
            root=root.observations,
            transformed_tokens=tuple(encoded_source["input_ids"]),
            expected_output_token_hash=sha256_json(root.root_tokens),
        )
        leak = closure.leaked_window_count
    repair_selections = 0

    while (intact > 0 or leak > 0) and remaining_budget > 0:
        best_id = None
        best_state: None | tuple[Any, int, int] = None
        best_gain = 0
        for cid in feasible():
            if cid in selected_set:
                continue
            trial_ids = tuple(sorted((*selected_set, cid)))
            try:
                trial_transformed, trial_intact, trial_leak = measure(trial_ids)
            except (KeyError, ValueError):
                continue
            gain = (intact - trial_intact) + (leak - trial_leak)
            if gain > best_gain or (gain == best_gain and gain > 0 and (best_id is None or cid < best_id)):
                best_id = cid
                best_gain = gain
                best_state = (trial_transformed, trial_intact, trial_leak)
        if best_id is None or best_gain <= 0 or best_state is None:
            break
        selected_order.append(best_id)
        selected_set.add(best_id)
        transformed, intact, leak = best_state
        repair_selections += 1
        remaining_budget -= 1

    selected_ids = tuple(sorted(selected_set))
    all_ids = set(candidates_by_id)
    unselected = tuple(sorted(all_ids - selected_set))
    conflict_excluded = tuple(cid for cid in unselected if conflicts[cid] & selected_set)
    root_count = len(root_window_indices)
    closure_free = root_count > 0 and leak == 0
    achieved_zero = root_count > 0 and intact == 0 and leak == 0
    payload = {
        "algorithm_version": COVER_GREEDY_V4_ALGORITHM_VERSION,
        "source_sample_id": source_sample_id,
        "source_text_hash": enumeration.input_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "ruleset_hash": registry.ruleset_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "budget": budget,
        "budget_unit": "operation",
        "candidate_count": len(enumeration.candidates),
        "selection_order": tuple(selected_order),
        "selected_candidate_ids": selected_ids,
        "selected_candidate_count": len(selected_ids),
        "unselected_candidate_ids": unselected,
        "conflict_excluded_candidate_ids": conflict_excluded,
        "budget_exhausted": remaining_budget == 0 and not achieved_zero,
        "static_phase_selections": static_selections,
        "repair_phase_selections": repair_selections,
        "root_window_count": root_count,
        "intact_window_count": intact,
        "tuple_leak_window_count": leak,
        "closure_free": closure_free,
        "achieved_zero": achieved_zero,
        "transformed_text_hash": sha256_text(transformed.output_text),
        "transform_trace_hash": transformed.trace.trace_hash,
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return CoverGreedyV4Result(**payload, result_hash=sha256_json(dict(payload)))
