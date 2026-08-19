from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import derive_seed, sha256_json
from ..scheduling.state_search import SearchState, SearchTransition
from .visible_cost_budget import (
    StateExpander,
    VisibleCostPolicy,
    VisibleCostTier,
    assess_visible_cost,
    policy_for_tier,
)


MATCHED_COST_ENVELOPE_VERSION = "normalized-matched-cost-envelope-v1"
MATCHED_COST_RANDOM_SAFE_VERSION = "normalized-matched-cost-random-safe-v1"
MATCHED_COST_RANDOM_SEED_BASE = 0x4D41544348454431
MATCHED_COST_SUCCESS = "MATCHED_COST_SUCCESS"
MATCHED_COST_INSUFFICIENT = "MATCHED_COST_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class MatchedVisibleCostEnvelope:
    tier: VisibleCostTier
    policy_hash: str
    reference_state_hash: str
    max_word_edit_rate: float
    max_character_edit_rate: float
    max_token_edit_distance: int
    max_visible_cost: int
    max_operation_count: int
    envelope_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        require_sha256("policy_hash", self.policy_hash)
        require_sha256("reference_state_hash", self.reference_state_hash)
        policy = policy_for_tier(self.tier)
        if self.policy_hash != policy.policy_hash:
            raise ValueError("matched-cost envelope policy hash drifted")
        for name in ("max_word_edit_rate", "max_character_edit_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name in ("max_token_edit_distance", "max_visible_cost", "max_operation_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        require_sha256("envelope_hash", self.envelope_hash)
        if self.envelope_hash != sha256_json(self.payload()):
            raise ValueError("matched-cost envelope hash mismatch")

    @classmethod
    def from_reference(
        cls,
        *,
        root_text: str,
        tier: VisibleCostTier,
        reference_state: SearchState,
    ) -> "MatchedVisibleCostEnvelope":
        policy = policy_for_tier(tier)
        assessment = assess_visible_cost(root_text, reference_state, policy)
        if not assessment.eligible:
            raise ValueError("reference state must satisfy the selected visible-cost tier")
        payload = {
            "algorithm_version": MATCHED_COST_ENVELOPE_VERSION,
            "tier": tier.value,
            "policy_hash": policy.policy_hash,
            "reference_state_hash": reference_state.search_state_hash,
            "max_word_edit_rate": assessment.word_edit_rate,
            "max_character_edit_rate": assessment.character_edit_rate,
            "max_token_edit_distance": reference_state.token_edit_distance,
            "max_visible_cost": reference_state.visible_cost,
            "max_operation_count": reference_state.depth,
        }
        return cls(
            tier=tier,
            policy_hash=policy.policy_hash,
            reference_state_hash=reference_state.search_state_hash,
            max_word_edit_rate=assessment.word_edit_rate,
            max_character_edit_rate=assessment.character_edit_rate,
            max_token_edit_distance=reference_state.token_edit_distance,
            max_visible_cost=reference_state.visible_cost,
            max_operation_count=reference_state.depth,
            envelope_hash=sha256_json(payload),
        )

    def allows(self, *, root_text: str, state: SearchState) -> bool:
        policy = policy_for_tier(self.tier)
        assessment = assess_visible_cost(root_text, state, policy)
        return (
            assessment.eligible
            and assessment.word_edit_rate <= self.max_word_edit_rate
            and assessment.character_edit_rate <= self.max_character_edit_rate
            and state.token_edit_distance <= self.max_token_edit_distance
            and state.visible_cost <= self.max_visible_cost
            and state.depth <= self.max_operation_count
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MATCHED_COST_ENVELOPE_VERSION,
            "tier": self.tier.value,
            "policy_hash": self.policy_hash,
            "reference_state_hash": self.reference_state_hash,
            "max_word_edit_rate": self.max_word_edit_rate,
            "max_character_edit_rate": self.max_character_edit_rate,
            "max_token_edit_distance": self.max_token_edit_distance,
            "max_visible_cost": self.max_visible_cost,
            "max_operation_count": self.max_operation_count,
        }


@dataclass(frozen=True, slots=True)
class MatchedCostRandomResult:
    tier: VisibleCostTier
    seed: int
    root_state_hash: str
    envelope_hash: str
    reference_state_hash: str
    final_state: SearchState
    transition_hashes: tuple[str, ...]
    candidate_hashes: tuple[str, ...]
    status: str
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        for name in ("root_state_hash", "envelope_hash", "reference_state_hash", "result_hash"):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.final_state, SearchState):
            raise TypeError("final_state must be SearchState")
        if self.final_state.root_source_hash == "":
            raise ValueError("final state must bind a root")
        if len(self.transition_hashes) != len(self.candidate_hashes):
            raise ValueError("transition/candidate trace lengths differ")
        if len(self.transition_hashes) != self.final_state.depth:
            raise ValueError("random-safe trace length must equal final state depth")
        for value in (*self.transition_hashes, *self.candidate_hashes):
            require_sha256("trace_hash", value)
        if self.status not in {MATCHED_COST_SUCCESS, MATCHED_COST_INSUFFICIENT}:
            raise ValueError("unsupported matched-cost random status")
        if type(self.detector_access_observed) is not bool or type(self.secret_access_observed) is not bool:
            raise TypeError("selection access flags must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("matched-cost random-safe search is contaminated")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("matched-cost random result hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MATCHED_COST_RANDOM_SAFE_VERSION,
            "tier": self.tier.value,
            "seed": self.seed,
            "root_state_hash": self.root_state_hash,
            "envelope_hash": self.envelope_hash,
            "reference_state_hash": self.reference_state_hash,
            "final_state_hash": self.final_state.search_state_hash,
            "transition_hashes": self.transition_hashes,
            "candidate_hashes": self.candidate_hashes,
            "status": self.status,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def derive_matched_cost_random_seed(sample_id: str, tier: VisibleCostTier, replicate: int) -> int:
    if not isinstance(sample_id, str) or not sample_id:
        raise ValueError("sample_id must be non-empty")
    require_int("replicate", replicate)
    if replicate < 0:
        raise ValueError("replicate must be non-negative")
    return derive_seed(
        MATCHED_COST_RANDOM_SEED_BASE,
        MATCHED_COST_RANDOM_SAFE_VERSION,
        sample_id,
        tier.value,
        str(replicate),
        bits=64,
    )


def matched_cost_random_safe_search(
    expander: StateExpander,
    root: SearchState,
    *,
    root_text: str,
    envelope: MatchedVisibleCostEnvelope,
    seed: int,
) -> MatchedCostRandomResult:
    if not isinstance(root, SearchState) or root.depth != 0:
        raise ValueError("matched-cost random-safe search requires a depth-zero SearchState root")
    require_int("seed", seed)
    if seed < 0 or seed >= 1 << 64:
        raise ValueError("seed must be between 0 and 2^64-1")
    state = root
    transition_hashes: list[str] = []
    candidate_hashes: list[str] = []
    for depth in range(envelope.max_operation_count):
        if bool(getattr(expander, "detector_access_observed", False)) or bool(getattr(expander, "secret_access_observed", False)):
            raise ValueError("matched-cost random-safe search observed prohibited selection access")
        eligible: list[SearchTransition] = []
        for transition in expander.expand(state):
            if envelope.allows(root_text=root_text, state=transition.child):
                eligible.append(transition)
        if not eligible:
            break
        ordered = tuple(sorted(eligible, key=lambda value: (value.candidate_hash, value.transition_hash)))
        choice = derive_seed(
            seed,
            MATCHED_COST_RANDOM_SAFE_VERSION,
            state.search_state_hash,
            str(depth),
            bits=64,
        ) % len(ordered)
        transition = ordered[choice]
        state = transition.child
        transition_hashes.append(transition.transition_hash)
        candidate_hashes.append(transition.candidate_hash)
    detector_access = bool(getattr(expander, "detector_access_observed", False))
    secret_access = bool(getattr(expander, "secret_access_observed", False))
    if detector_access or secret_access:
        raise ValueError("matched-cost random-safe search observed prohibited selection access")
    status = (
        MATCHED_COST_SUCCESS
        if state.depth == envelope.max_operation_count
        else MATCHED_COST_INSUFFICIENT
    )
    payload = {
        "algorithm_version": MATCHED_COST_RANDOM_SAFE_VERSION,
        "tier": envelope.tier.value,
        "seed": seed,
        "root_state_hash": root.search_state_hash,
        "envelope_hash": envelope.envelope_hash,
        "reference_state_hash": envelope.reference_state_hash,
        "final_state_hash": state.search_state_hash,
        "transition_hashes": tuple(transition_hashes),
        "candidate_hashes": tuple(candidate_hashes),
        "status": status,
        "detector_access_observed": detector_access,
        "secret_access_observed": secret_access,
    }
    return MatchedCostRandomResult(
        tier=envelope.tier,
        seed=seed,
        root_state_hash=root.search_state_hash,
        envelope_hash=envelope.envelope_hash,
        reference_state_hash=envelope.reference_state_hash,
        final_state=state,
        transition_hashes=tuple(transition_hashes),
        candidate_hashes=tuple(candidate_hashes),
        status=status,
        detector_access_observed=detector_access,
        secret_access_observed=secret_access,
        result_hash=sha256_json(payload),
    )
