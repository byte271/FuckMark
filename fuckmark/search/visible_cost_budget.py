from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..experiments.mid_dev_quality import protected_span_violation_count, word_edit_rate
from ..experiments.structural_leverage import character_edit_rate
from ..scheduling.state_search import SearchState, SearchTransition


VISIBLE_COST_POLICY_VERSION = "normalized-visible-cost-policy-v1"
VISIBLE_COST_ASSESSMENT_VERSION = "normalized-visible-cost-assessment-v1"
VISIBLE_COST_SEARCH_VERSION = "context-survival-visible-cost-beam-v1"
DEFAULT_VISIBLE_COST_BEAM_WIDTH = 32
DEFAULT_VISIBLE_COST_MAX_OPERATIONS = 64


class VisibleCostTier(str, Enum):
    STRICT = "STRICT"
    RELAXED = "RELAXED"


@dataclass(frozen=True, slots=True)
class VisibleCostPolicy:
    tier: VisibleCostTier
    word_edit_rate_max: float
    character_edit_rate_max: float
    length_ratio_min: float | None
    length_ratio_max: float | None
    protected_span_violations: int
    policy_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        for name in ("word_edit_rate_max", "character_edit_rate_max"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if (self.length_ratio_min is None) != (self.length_ratio_max is None):
            raise ValueError("length ratio bounds must both be set or both be None")
        if self.length_ratio_min is not None:
            if self.length_ratio_min <= 0.0 or self.length_ratio_max < self.length_ratio_min:
                raise ValueError("invalid length ratio bounds")
        require_int("protected_span_violations", self.protected_span_violations)
        if self.protected_span_violations != 0:
            raise ValueError("visible-cost policies require zero protected-span violations")
        require_sha256("policy_hash", self.policy_hash)
        if self.policy_hash != sha256_json(self.payload()):
            raise ValueError("policy_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        tier: VisibleCostTier,
        word_edit_rate_max: float,
        character_edit_rate_max: float,
        length_ratio_min: float | None,
        length_ratio_max: float | None,
    ) -> "VisibleCostPolicy":
        payload = {
            "algorithm_version": VISIBLE_COST_POLICY_VERSION,
            "tier": tier.value,
            "word_edit_rate_max": float(word_edit_rate_max),
            "character_edit_rate_max": float(character_edit_rate_max),
            "length_ratio_min": length_ratio_min,
            "length_ratio_max": length_ratio_max,
            "protected_span_violations": 0,
        }
        return cls(
            tier=tier,
            word_edit_rate_max=payload["word_edit_rate_max"],
            character_edit_rate_max=payload["character_edit_rate_max"],
            length_ratio_min=length_ratio_min,
            length_ratio_max=length_ratio_max,
            protected_span_violations=0,
            policy_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": VISIBLE_COST_POLICY_VERSION,
            "tier": self.tier.value,
            "word_edit_rate_max": self.word_edit_rate_max,
            "character_edit_rate_max": self.character_edit_rate_max,
            "length_ratio_min": self.length_ratio_min,
            "length_ratio_max": self.length_ratio_max,
            "protected_span_violations": self.protected_span_violations,
        }


STRICT_VISIBLE_COST_POLICY = VisibleCostPolicy.create(
    tier=VisibleCostTier.STRICT,
    word_edit_rate_max=0.03,
    character_edit_rate_max=0.015,
    length_ratio_min=0.97,
    length_ratio_max=1.03,
)
RELAXED_VISIBLE_COST_POLICY = VisibleCostPolicy.create(
    tier=VisibleCostTier.RELAXED,
    word_edit_rate_max=0.05,
    character_edit_rate_max=0.03,
    length_ratio_min=None,
    length_ratio_max=None,
)


def policy_for_tier(tier: VisibleCostTier) -> VisibleCostPolicy:
    if not isinstance(tier, VisibleCostTier):
        raise TypeError("tier must be VisibleCostTier")
    return STRICT_VISIBLE_COST_POLICY if tier is VisibleCostTier.STRICT else RELAXED_VISIBLE_COST_POLICY


@dataclass(frozen=True, slots=True)
class VisibleCostAssessment:
    state_hash: str
    policy_hash: str
    word_edit_rate: float
    character_edit_rate: float
    length_ratio: float
    protected_span_violation_count: int
    eligible: bool
    reason_codes: tuple[str, ...]
    assessment_hash: str

    def __post_init__(self) -> None:
        require_sha256("state_hash", self.state_hash)
        require_sha256("policy_hash", self.policy_hash)
        for name in ("word_edit_rate", "character_edit_rate", "length_ratio"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        require_int("protected_span_violation_count", self.protected_span_violation_count)
        if self.protected_span_violation_count < 0:
            raise ValueError("protected_span_violation_count must be non-negative")
        if type(self.eligible) is not bool:
            raise TypeError("eligible must be bool")
        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("reason_codes must be unique and sorted")
        for reason in self.reason_codes:
            require_clean_string("reason_code", reason)
        if self.eligible != (not self.reason_codes):
            raise ValueError("eligible does not match reason_codes")
        require_sha256("assessment_hash", self.assessment_hash)
        if self.assessment_hash != sha256_json(self.payload()):
            raise ValueError("assessment_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": VISIBLE_COST_ASSESSMENT_VERSION,
            "state_hash": self.state_hash,
            "policy_hash": self.policy_hash,
            "word_edit_rate": self.word_edit_rate,
            "character_edit_rate": self.character_edit_rate,
            "length_ratio": self.length_ratio,
            "protected_span_violation_count": self.protected_span_violation_count,
            "eligible": self.eligible,
            "reason_codes": self.reason_codes,
        }


def assess_visible_cost(root_text: str, state: SearchState, policy: VisibleCostPolicy) -> VisibleCostAssessment:
    if not isinstance(root_text, str) or not root_text:
        raise ValueError("root_text must be non-empty")
    if not isinstance(state, SearchState):
        raise TypeError("state must be SearchState")
    if not isinstance(policy, VisibleCostPolicy):
        raise TypeError("policy must be VisibleCostPolicy")
    word_rate = word_edit_rate(root_text, state.text)
    char_rate = character_edit_rate(root_text, state.text)
    length_ratio = len(state.text) / len(root_text)
    protected_violations = protected_span_violation_count(root_text, state.text)
    reasons: list[str] = []
    if word_rate > policy.word_edit_rate_max:
        reasons.append(f"{policy.tier.value}_WORD_EDIT_RATE_EXCEEDED")
    if char_rate > policy.character_edit_rate_max:
        reasons.append(f"{policy.tier.value}_CHARACTER_EDIT_RATE_EXCEEDED")
    if policy.length_ratio_min is not None and not policy.length_ratio_min <= length_ratio <= policy.length_ratio_max:
        reasons.append(f"{policy.tier.value}_LENGTH_RATIO_EXCEEDED")
    if protected_violations != policy.protected_span_violations:
        reasons.append(f"{policy.tier.value}_PROTECTED_SPAN_VIOLATION")
    normalized = tuple(sorted(set(reasons)))
    payload = {
        "algorithm_version": VISIBLE_COST_ASSESSMENT_VERSION,
        "state_hash": state.search_state_hash,
        "policy_hash": policy.policy_hash,
        "word_edit_rate": word_rate,
        "character_edit_rate": char_rate,
        "length_ratio": length_ratio,
        "protected_span_violation_count": protected_violations,
        "eligible": not normalized,
        "reason_codes": normalized,
    }
    return VisibleCostAssessment(
        **{key: value for key, value in payload.items() if key != "algorithm_version"},
        assessment_hash=sha256_json(payload),
    )


class StateExpander(Protocol):
    @property
    def detector_access_observed(self) -> bool: ...

    @property
    def secret_access_observed(self) -> bool: ...

    def expand(self, state: SearchState) -> Sequence[SearchTransition]: ...


class VisibleCostExpander:
    def __init__(self, base: StateExpander, root_text: str, policy: VisibleCostPolicy) -> None:
        if not isinstance(root_text, str) or not root_text:
            raise ValueError("root_text must be non-empty")
        if not isinstance(policy, VisibleCostPolicy):
            raise TypeError("policy must be VisibleCostPolicy")
        self._base = base
        self._root_text = root_text
        self._policy = policy
        self._cache: dict[str, tuple[SearchTransition, ...]] = {}
        self._assessments: dict[str, VisibleCostAssessment] = {}
        self.rejected_transition_count = 0

    @property
    def detector_access_observed(self) -> bool:
        return bool(getattr(self._base, "detector_access_observed", False))

    @property
    def secret_access_observed(self) -> bool:
        return bool(getattr(self._base, "secret_access_observed", False))

    @property
    def policy(self) -> VisibleCostPolicy:
        return self._policy

    def assessment_for(self, state: SearchState) -> VisibleCostAssessment:
        value = self._assessments.get(state.search_state_hash)
        if value is None:
            value = assess_visible_cost(self._root_text, state, self._policy)
            self._assessments[state.search_state_hash] = value
        return value

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        cached = self._cache.get(state.search_state_hash)
        if cached is not None:
            return cached
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("visible-cost controller observed prohibited selection access")
        output = []
        for transition in self._base.expand(state):
            if self.assessment_for(transition.child).eligible:
                output.append(transition)
            else:
                self.rejected_transition_count += 1
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("visible-cost controller observed prohibited selection access")
        result = tuple(output)
        self._cache[state.search_state_hash] = result
        return result


def _beam_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.surviving_root_observations,
        -state.newly_masked_count,
        state.highest_risk_tier,
        state.visible_cost,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _duplicate_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.highest_risk_tier,
        state.visible_cost,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _deduplicate(states: Sequence[SearchState]) -> tuple[SearchState, ...]:
    by_text_hash: dict[str, SearchState] = {}
    for state in states:
        if not isinstance(state, SearchState):
            raise TypeError("states must contain SearchState values")
        existing = by_text_hash.get(state.text_hash)
        if existing is None or _duplicate_rank(state) < _duplicate_rank(existing):
            by_text_hash[state.text_hash] = state
    return tuple(sorted(by_text_hash.values(), key=_beam_rank))


@dataclass(frozen=True, slots=True)
class VisibleCostSearchResult:
    tier: VisibleCostTier
    policy_hash: str
    root_state_hash: str
    beam_width: int
    maximum_search_operations: int
    reached_depth: int
    states: tuple[SearchState, ...]
    expanded_state_count: int
    pruned_state_count: int
    rejected_transition_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        require_sha256("policy_hash", self.policy_hash)
        require_sha256("root_state_hash", self.root_state_hash)
        for name in (
            "beam_width",
            "maximum_search_operations",
            "reached_depth",
            "expanded_state_count",
            "pruned_state_count",
            "rejected_transition_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.beam_width <= 0 or self.maximum_search_operations <= 0:
            raise ValueError("beam_width and maximum_search_operations must be positive")
        if self.reached_depth > self.maximum_search_operations:
            raise ValueError("reached_depth exceeds maximum_search_operations")
        if not isinstance(self.states, tuple) or any(not isinstance(state, SearchState) for state in self.states):
            raise TypeError("states must contain SearchState values")
        if not self.states:
            raise ValueError("visible-cost search must preserve at least the root state")
        if any(state.depth != self.reached_depth for state in self.states):
            raise ValueError("all terminal states must have reached_depth")
        if len({state.text_hash for state in self.states}) != len(self.states):
            raise ValueError("terminal states must be deduplicated by text hash")
        if type(self.detector_access_observed) is not bool or type(self.secret_access_observed) is not bool:
            raise TypeError("selection access flags must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("visible-cost search is contaminated")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": VISIBLE_COST_SEARCH_VERSION,
            "tier": self.tier.value,
            "policy_hash": self.policy_hash,
            "root_state_hash": self.root_state_hash,
            "beam_width": self.beam_width,
            "maximum_search_operations": self.maximum_search_operations,
            "reached_depth": self.reached_depth,
            "state_hashes": tuple(state.search_state_hash for state in self.states),
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "rejected_transition_count": self.rejected_transition_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def visible_cost_beam_search(
    expander: StateExpander,
    root: SearchState,
    *,
    root_text: str,
    tier: VisibleCostTier,
    beam_width: int = DEFAULT_VISIBLE_COST_BEAM_WIDTH,
    maximum_search_operations: int = DEFAULT_VISIBLE_COST_MAX_OPERATIONS,
) -> VisibleCostSearchResult:
    if not isinstance(root, SearchState):
        raise TypeError("root must be SearchState")
    if root.depth != 0:
        raise ValueError("visible-cost search requires a depth-zero root")
    require_int("beam_width", beam_width)
    require_int("maximum_search_operations", maximum_search_operations)
    if beam_width <= 0 or maximum_search_operations <= 0:
        raise ValueError("beam_width and maximum_search_operations must be positive")
    policy = policy_for_tier(tier)
    filtered = VisibleCostExpander(expander, root_text, policy)
    beam = (root,)
    reached_depth = root.depth
    expanded = 0
    pruned = 0
    for _ in range(maximum_search_operations):
        children = []
        for state in beam:
            transitions = filtered.expand(state)
            children.extend(transition.child for transition in transitions)
            expanded += 1
        unique = _deduplicate(children)
        if not unique:
            break
        ranked = tuple(sorted(unique, key=_beam_rank))
        pruned += max(0, len(ranked) - beam_width)
        beam = ranked[:beam_width]
        reached_depth = beam[0].depth
        if any(state.depth != reached_depth for state in beam):
            raise RuntimeError("visible-cost beam mixed search depths")
    if filtered.detector_access_observed or filtered.secret_access_observed:
        raise ValueError("visible-cost controller observed prohibited selection access")
    terminal = _deduplicate(beam)
    payload = {
        "algorithm_version": VISIBLE_COST_SEARCH_VERSION,
        "tier": tier.value,
        "policy_hash": policy.policy_hash,
        "root_state_hash": root.search_state_hash,
        "beam_width": beam_width,
        "maximum_search_operations": maximum_search_operations,
        "reached_depth": reached_depth,
        "state_hashes": tuple(state.search_state_hash for state in terminal),
        "expanded_state_count": expanded,
        "pruned_state_count": pruned,
        "rejected_transition_count": filtered.rejected_transition_count,
        "detector_access_observed": filtered.detector_access_observed,
        "secret_access_observed": filtered.secret_access_observed,
    }
    return VisibleCostSearchResult(
        tier=tier,
        policy_hash=policy.policy_hash,
        root_state_hash=root.search_state_hash,
        beam_width=beam_width,
        maximum_search_operations=maximum_search_operations,
        reached_depth=reached_depth,
        states=terminal,
        expanded_state_count=expanded,
        pruned_state_count=pruned,
        rejected_transition_count=filtered.rejected_transition_count,
        detector_access_observed=filtered.detector_access_observed,
        secret_access_observed=filtered.secret_access_observed,
        result_hash=sha256_json(payload),
    )
