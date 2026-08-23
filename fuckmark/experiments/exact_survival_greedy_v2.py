from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..geometry import CounterfactualGeometryEngine, GeometryConfig
from ..hashing import sha256_json, sha256_text
from ..transforms.candidate_artifacts import CandidateEnumeration
from ..transforms.registry import TransformRegistry


EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION = "exact-survival-greedy-key-blind-v2"
EXACT_SURVIVAL_GREEDY_V2_POLICY_ID = "pairwise-completed-root-observation-survival-v1"


@dataclass(frozen=True, slots=True)
class ExactSurvivalGreedyV2Step:
    step_index: int
    candidate_id: str
    rule_id: str
    paired_with_candidate_id: str | None
    marginal_exact_destruction: int
    exact_destroyed_count: int
    exact_surviving_count: int
    transformed_text_hash: str
    step_hash: str

    def __post_init__(self) -> None:
        require_int("step_index", self.step_index)
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        require_sha256("candidate_id", self.candidate_id)
        if self.paired_with_candidate_id is not None:
            require_sha256("paired_with_candidate_id", self.paired_with_candidate_id)
            if self.paired_with_candidate_id == self.candidate_id:
                raise ValueError("a pair cannot contain the same candidate twice")
        require_clean_string("rule_id", self.rule_id)
        for name in ("marginal_exact_destruction", "exact_destroyed_count", "exact_surviving_count"):
            require_int(name, getattr(self, name))
        if self.marginal_exact_destruction < 0:
            raise ValueError("marginal exact destruction must be non-negative")
        if self.exact_destroyed_count < 0 or self.exact_surviving_count < 0:
            raise ValueError("exact observation counts must be non-negative")
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        require_sha256("step_hash", self.step_hash)
        if self.step_hash != sha256_json(self.payload()):
            raise ValueError("step_hash does not match exact-survival greedy v2 step")

    def payload(self) -> dict[str, object]:
        return {
            "step_index": self.step_index,
            "candidate_id": self.candidate_id,
            "rule_id": self.rule_id,
            "paired_with_candidate_id": self.paired_with_candidate_id,
            "marginal_exact_destruction": self.marginal_exact_destruction,
            "exact_destroyed_count": self.exact_destroyed_count,
            "exact_surviving_count": self.exact_surviving_count,
            "transformed_text_hash": self.transformed_text_hash,
        }


@dataclass(frozen=True, slots=True)
class ExactSurvivalGreedyV2Result:
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
    policy_saturated: bool
    pairwise_completion_used: bool
    root_observation_count: int
    exact_destroyed_observation_count: int
    exact_surviving_observation_count: int
    exact_destruction_ratio: float
    transformed_text_hash: str
    transform_trace_hash: str
    steps: tuple[ExactSurvivalGreedyV2Step, ...]
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION:
            raise ValueError("unsupported exact-survival greedy v2 algorithm version")
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
            "root_observation_count",
            "exact_destroyed_observation_count",
            "exact_surviving_observation_count",
        ):
            require_int(name, getattr(self, name))
        if self.ngram_len <= 0 or self.budget < 0 or self.candidate_count < 0:
            raise ValueError("ngram_len must be positive and budget/candidate_count non-negative")
        if self.budget_unit != "operation":
            raise ValueError("exact-survival greedy v2 supports operation budgets only")
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
                raise ValueError(f"{name} must not contain duplicates")
            for value in values:
                require_sha256(name, value)
        if set(self.selected_candidate_ids) & set(self.unselected_candidate_ids):
            raise ValueError("selected and unselected candidate IDs must be disjoint")
        if type(self.policy_saturated) is not bool or type(self.pairwise_completion_used) is not bool:
            raise TypeError("policy_saturated and pairwise_completion_used must be bool")
        if not isinstance(self.steps, tuple) or any(not isinstance(step, ExactSurvivalGreedyV2Step) for step in self.steps):
            raise TypeError("steps must contain ExactSurvivalGreedyV2Step values")
        if tuple(step.candidate_id for step in self.steps) != self.selection_order:
            raise ValueError("steps must follow selection_order")
        if self.root_observation_count < 0:
            raise ValueError("root_observation_count must be non-negative")
        if self.exact_destroyed_observation_count + self.exact_surviving_observation_count != self.root_observation_count:
            raise ValueError("exact counts must partition root observations")
        expected_ratio = (
            self.exact_destroyed_observation_count / self.root_observation_count if self.root_observation_count else 0.0
        )
        if self.exact_destruction_ratio != expected_ratio:
            raise ValueError("exact_destruction_ratio does not match exact counts")
        if self.steps:
            if self.steps[-1].exact_destroyed_count != self.exact_destroyed_observation_count:
                raise ValueError("final step does not match final exact destruction count")
        elif self.exact_destroyed_observation_count != 0:
            raise ValueError("empty selection must have zero exact destruction")
        if self.detector_access_observed is not False or self.secret_access_observed is not False:
            raise ValueError("exact-survival greedy v2 must remain detector-blind and key-blind")
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash does not match exact-survival greedy v2 result")

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
            "policy_saturated": self.policy_saturated,
            "pairwise_completion_used": self.pairwise_completion_used,
            "root_observation_count": self.root_observation_count,
            "exact_destroyed_observation_count": self.exact_destroyed_observation_count,
            "exact_surviving_observation_count": self.exact_surviving_observation_count,
            "exact_destruction_ratio": self.exact_destruction_ratio,
            "transformed_text_hash": self.transformed_text_hash,
            "transform_trace_hash": self.transform_trace_hash,
            "step_hashes": tuple(step.step_hash for step in self.steps),
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _conflict_map(enumeration: CandidateEnumeration) -> dict[str, set[str]]:
    output = {candidate.candidate_id: set() for candidate in enumeration.candidates}
    for conflict in enumeration.conflicts:
        output[conflict.first_candidate_id].add(conflict.second_candidate_id)
        output[conflict.second_candidate_id].add(conflict.first_candidate_id)
    return output


def _selection_hash(source_text_hash: str, selected_ids: tuple[str, ...]) -> str:
    return sha256_json(
        {
            "algorithm_version": EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION,
            "source_text_hash": source_text_hash,
            "selected_candidate_ids": selected_ids,
        }
    )


def _evaluate(
    engine: CounterfactualGeometryEngine,
    root: Any,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    trial_ids: tuple[str, ...],
):
    transformed = registry.apply(enumeration, trial_ids)
    exact = engine.evaluate_output(
        root=root,
        current_text=source_text,
        output_text=transformed.output_text,
        candidate_id=_selection_hash(enumeration.input_hash, trial_ids),
        rule_hash=registry.ruleset_hash,
        visible_cost_class=0,
        family="exact-survival-greedy-v2",
        tier=0,
    )
    return transformed, exact


def _record_step(
    steps: list[ExactSurvivalGreedyV2Step],
    step_index: int,
    candidate_id: str,
    rule_id: str,
    paired_with: str | None,
    marginal: int,
    exact: Any,
    transformed_text: str,
) -> None:
    payload = {
        "step_index": step_index,
        "candidate_id": candidate_id,
        "rule_id": rule_id,
        "paired_with_candidate_id": paired_with,
        "marginal_exact_destruction": marginal,
        "exact_destroyed_count": exact.destroyed_count,
        "exact_surviving_count": exact.surviving_count,
        "transformed_text_hash": sha256_text(transformed_text),
    }
    steps.append(ExactSurvivalGreedyV2Step(**payload, step_hash=sha256_json(payload)))


def _best_single(
    engine: CounterfactualGeometryEngine,
    root: Any,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    candidates_by_id: dict[str, Any],
    conflicts: dict[str, set[str]],
    remaining: set[str],
    selected_set: set[str],
    current_destroyed: int,
):
    feasible = tuple(sorted(candidate_id for candidate_id in remaining if not (conflicts[candidate_id] & selected_set)))
    best_id = None
    best_gain = 0
    best_state = None
    for candidate_id in feasible:
        trial_ids = tuple(sorted((*selected_set, candidate_id)))
        transformed, exact = _evaluate(engine, root, source_text, registry, enumeration, trial_ids)
        gain = exact.destroyed_count - current_destroyed
        if gain > best_gain or (gain == best_gain and gain > 0 and (best_id is None or candidate_id < best_id)):
            best_id = candidate_id
            best_gain = gain
            best_state = (transformed, exact)
    return best_id, best_gain, best_state


def _best_pair(
    engine: CounterfactualGeometryEngine,
    root: Any,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    candidates_by_id: dict[str, Any],
    conflicts: dict[str, set[str]],
    remaining: set[str],
    selected_set: set[str],
    current_destroyed: int,
    max_pair_candidates: int,
):
    feasible = tuple(sorted(candidate_id for candidate_id in remaining if not (conflicts[candidate_id] & selected_set)))
    if len(feasible) < 2:
        return None
    bounded = feasible[:max_pair_candidates]
    best_pair = None
    best_gain = 0
    best_state = None
    for i, first in enumerate(bounded):
        for second in bounded[i + 1 :]:
            if conflicts[first] & {second}:
                continue
            trial_ids = tuple(sorted((*selected_set, first, second)))
            transformed, exact = _evaluate(engine, root, source_text, registry, enumeration, trial_ids)
            gain = exact.destroyed_count - current_destroyed
            if gain > best_gain:
                best_pair = (first, second)
                best_gain = gain
                best_state = (transformed, exact)
    return (best_pair, best_gain, best_state) if best_pair is not None else None


def schedule_exact_survival_greedy_v2(
    *,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
    budget: int,
    max_pair_candidates: int = 24,
) -> ExactSurvivalGreedyV2Result:
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
    require_int("max_pair_candidates", max_pair_candidates)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if budget < 0 or max_pair_candidates < 2:
        raise ValueError("budget must be non-negative and max_pair_candidates at least 2")

    config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=EXACT_SURVIVAL_GREEDY_V2_POLICY_ID,
    )
    engine = CounterfactualGeometryEngine(tokenizer=tokenizer, config=config)
    root = engine.build_root(source_sample_id=source_sample_id, source_text=source_text)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    conflicts = _conflict_map(enumeration)
    remaining = set(candidates_by_id)
    selected_order: list[str] = []
    selected_set: set[str] = set()
    steps: list[ExactSurvivalGreedyV2Step] = []
    pairwise_used = False

    current_destroyed = 0
    final_transformed = registry.apply(enumeration, ())
    final_exact = engine.evaluate_output(
        root=root,
        current_text=source_text,
        output_text=source_text,
        candidate_id=_selection_hash(enumeration.input_hash, ()),
        rule_hash=registry.ruleset_hash,
        visible_cost_class=0,
        family="exact-survival-greedy-v2",
        tier=0,
    )
    policy_saturated = False

    while remaining and len(selected_order) < budget:
        best_id, best_gain, best_state = _best_single(
            engine, root, source_text, registry, enumeration, candidates_by_id, conflicts,
            remaining, selected_set, current_destroyed,
        )
        if best_id is None or best_gain <= 0:
            pair_outcome = _best_pair(
                engine, root, source_text, registry, enumeration, candidates_by_id, conflicts,
                remaining, selected_set, current_destroyed, max_pair_candidates,
            )
            if pair_outcome is None or pair_outcome[1] <= 0 or len(selected_order) + 2 > budget:
                policy_saturated = True
                break
            pairwise_used = True
            first_id, second_id = pair_outcome[0]
            pair_transformed, pair_exact = pair_outcome[2]
            _record_step(steps, len(selected_order), first_id, candidates_by_id[first_id].rule_id, second_id,
                         pair_exact.destroyed_count - current_destroyed, pair_exact, pair_transformed.output_text)
            selected_order.append(first_id)
            selected_set.add(first_id)
            remaining.remove(first_id)
            _record_step(steps, len(selected_order), second_id, candidates_by_id[second_id].rule_id, first_id,
                         0, pair_exact, pair_transformed.output_text)
            selected_order.append(second_id)
            selected_set.add(second_id)
            remaining.remove(second_id)
            current_destroyed = pair_exact.destroyed_count
            final_transformed = pair_transformed
            final_exact = pair_exact
            continue
        selected_order.append(best_id)
        selected_set.add(best_id)
        remaining.remove(best_id)
        current_destroyed = best_state[1].destroyed_count
        final_transformed, final_exact = best_state
        _record_step(steps, len(selected_order) - 1, best_id, candidates_by_id[best_id].rule_id, None,
                     best_gain, final_exact, final_transformed.output_text)

    selected_ids = tuple(sorted(selected_set))
    all_ids = set(candidates_by_id)
    unselected = tuple(sorted(all_ids - selected_set))
    conflict_excluded = tuple(candidate_id for candidate_id in unselected if conflicts[candidate_id] & selected_set)
    root_count = final_exact.root_observation_count
    exact_ratio = final_exact.destroyed_count / root_count if root_count else 0.0
    payload = {
        "algorithm_version": EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION,
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
        "policy_saturated": policy_saturated,
        "pairwise_completion_used": pairwise_used,
        "root_observation_count": root_count,
        "exact_destroyed_observation_count": final_exact.destroyed_count,
        "exact_surviving_observation_count": final_exact.surviving_count,
        "exact_destruction_ratio": exact_ratio,
        "transformed_text_hash": sha256_text(final_transformed.output_text),
        "transform_trace_hash": final_transformed.trace.trace_hash,
        "step_hashes": tuple(step.step_hash for step in steps),
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return ExactSurvivalGreedyV2Result(
        algorithm_version=EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION,
        source_sample_id=source_sample_id,
        source_text_hash=enumeration.input_hash,
        enumeration_hash=enumeration.enumeration_hash,
        ruleset_hash=registry.ruleset_hash,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        budget=budget,
        budget_unit="operation",
        candidate_count=len(enumeration.candidates),
        selection_order=tuple(selected_order),
        selected_candidate_ids=selected_ids,
        selected_candidate_count=len(selected_ids),
        unselected_candidate_ids=unselected,
        conflict_excluded_candidate_ids=conflict_excluded,
        policy_saturated=policy_saturated,
        pairwise_completion_used=pairwise_used,
        root_observation_count=root_count,
        exact_destroyed_observation_count=final_exact.destroyed_count,
        exact_surviving_observation_count=final_exact.surviving_count,
        exact_destruction_ratio=exact_ratio,
        transformed_text_hash=sha256_text(final_transformed.output_text),
        transform_trace_hash=final_transformed.trace.trace_hash,
        steps=tuple(steps),
        detector_access_observed=False,
        secret_access_observed=False,
        result_hash=sha256_json(payload),
    )
