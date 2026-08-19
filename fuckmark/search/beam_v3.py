from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..scheduling.state_search import SearchState, StateExpander


CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION = "context-survival-beam-v3"
BEAM_V3_METRICS_VERSION = "context-survival-beam-v3-metrics-v1"
BEAM_V3_RANKED_STATE_VERSION = "context-survival-beam-v3-ranked-state-v1"
BEAM_V3_RESULT_VERSION = "context-survival-beam-v3-result-v1"


@dataclass(frozen=True, slots=True)
class BeamV3StateMetrics:
    state_hash: str
    geometry_hash: str
    root_valid_observation_count: int
    final_valid_observation_count: int
    preserved_root_valid_observation_count: int
    repetition_mask_delta: int
    root_survival_fraction: float
    root_destruction_fraction: float
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    word_edit_rate: float
    character_edit_rate: float
    token_edit_distance: int
    length_ratio: float
    protected_span_violation_count: int
    hard_invariant_passed: bool
    eligible: bool
    reason_codes: tuple[str, ...]
    metrics_hash: str

    def __post_init__(self) -> None:
        require_sha256("state_hash", self.state_hash)
        require_sha256("geometry_hash", self.geometry_hash)
        for name in (
            "root_valid_observation_count",
            "final_valid_observation_count",
            "preserved_root_valid_observation_count",
            "token_edit_distance",
            "protected_span_violation_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        require_int("repetition_mask_delta", self.repetition_mask_delta)
        if self.preserved_root_valid_observation_count > self.root_valid_observation_count:
            raise ValueError("preserved observations exceed root valid observations")
        if self.preserved_root_valid_observation_count > self.final_valid_observation_count:
            raise ValueError("preserved observations exceed final valid observations")
        expected_rsf = self.preserved_root_valid_observation_count / max(1, self.root_valid_observation_count)
        expected_rif = self.preserved_root_valid_observation_count / max(1, self.final_valid_observation_count)
        expected_ncf = (
            self.final_valid_observation_count - self.preserved_root_valid_observation_count
        ) / max(1, self.final_valid_observation_count)
        expected_vdr = self.final_valid_observation_count / max(1, self.root_valid_observation_count)
        expected = {
            "root_survival_fraction": expected_rsf,
            "root_destruction_fraction": 1.0 - expected_rsf,
            "residual_inherited_fraction": expected_rif,
            "new_context_opportunity_fraction": expected_ncf,
            "valid_denominator_ratio": expected_vdr,
        }
        for name, wanted in expected.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if float(value) != wanted:
                raise ValueError(f"{name} does not match structural counts")
        for name in ("word_edit_rate", "character_edit_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if isinstance(self.length_ratio, bool) or not isinstance(self.length_ratio, (int, float)):
            raise TypeError("length_ratio must be a real number")
        if self.length_ratio < 0:
            raise ValueError("length_ratio must be non-negative")
        if type(self.hard_invariant_passed) is not bool or type(self.eligible) is not bool:
            raise TypeError("hard_invariant_passed and eligible must be booleans")
        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple")
        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("reason_codes must be unique and sorted")
        for value in self.reason_codes:
            require_clean_string("reason_code", value)
        if self.eligible != (not self.reason_codes):
            raise ValueError("eligible flag must match reason codes")
        require_sha256("metrics_hash", self.metrics_hash)
        if self.metrics_hash != sha256_json(self.payload()):
            raise ValueError("metrics_hash does not match BeamV3StateMetrics payload")

    @classmethod
    def create(
        cls,
        *,
        state_hash: str,
        geometry_hash: str,
        root_valid_observation_count: int,
        final_valid_observation_count: int,
        preserved_root_valid_observation_count: int,
        repetition_mask_delta: int,
        word_edit_rate: float,
        character_edit_rate: float,
        token_edit_distance: int,
        length_ratio: float,
        protected_span_violation_count: int,
        hard_invariant_passed: bool,
        reason_codes: Sequence[str] = (),
    ) -> BeamV3StateMetrics:
        reasons = tuple(sorted(set(reason_codes)))
        root_valid = int(root_valid_observation_count)
        final_valid = int(final_valid_observation_count)
        preserved = int(preserved_root_valid_observation_count)
        payload = {
            "algorithm_version": BEAM_V3_METRICS_VERSION,
            "state_hash": state_hash,
            "geometry_hash": geometry_hash,
            "root_valid_observation_count": root_valid,
            "final_valid_observation_count": final_valid,
            "preserved_root_valid_observation_count": preserved,
            "repetition_mask_delta": repetition_mask_delta,
            "root_survival_fraction": preserved / max(1, root_valid),
            "root_destruction_fraction": 1.0 - (preserved / max(1, root_valid)),
            "residual_inherited_fraction": preserved / max(1, final_valid),
            "new_context_opportunity_fraction": (final_valid - preserved) / max(1, final_valid),
            "valid_denominator_ratio": final_valid / max(1, root_valid),
            "word_edit_rate": float(word_edit_rate),
            "character_edit_rate": float(character_edit_rate),
            "token_edit_distance": token_edit_distance,
            "length_ratio": float(length_ratio),
            "protected_span_violation_count": protected_span_violation_count,
            "hard_invariant_passed": hard_invariant_passed,
            "eligible": not reasons,
            "reason_codes": reasons,
        }
        return cls(
            state_hash=state_hash,
            geometry_hash=geometry_hash,
            root_valid_observation_count=root_valid,
            final_valid_observation_count=final_valid,
            preserved_root_valid_observation_count=preserved,
            repetition_mask_delta=repetition_mask_delta,
            root_survival_fraction=payload["root_survival_fraction"],
            root_destruction_fraction=payload["root_destruction_fraction"],
            residual_inherited_fraction=payload["residual_inherited_fraction"],
            new_context_opportunity_fraction=payload["new_context_opportunity_fraction"],
            valid_denominator_ratio=payload["valid_denominator_ratio"],
            word_edit_rate=payload["word_edit_rate"],
            character_edit_rate=payload["character_edit_rate"],
            token_edit_distance=token_edit_distance,
            length_ratio=payload["length_ratio"],
            protected_span_violation_count=protected_span_violation_count,
            hard_invariant_passed=hard_invariant_passed,
            eligible=payload["eligible"],
            reason_codes=reasons,
            metrics_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": BEAM_V3_METRICS_VERSION,
            "state_hash": self.state_hash,
            "geometry_hash": self.geometry_hash,
            "root_valid_observation_count": self.root_valid_observation_count,
            "final_valid_observation_count": self.final_valid_observation_count,
            "preserved_root_valid_observation_count": self.preserved_root_valid_observation_count,
            "repetition_mask_delta": self.repetition_mask_delta,
            "root_survival_fraction": self.root_survival_fraction,
            "root_destruction_fraction": self.root_destruction_fraction,
            "residual_inherited_fraction": self.residual_inherited_fraction,
            "new_context_opportunity_fraction": self.new_context_opportunity_fraction,
            "valid_denominator_ratio": self.valid_denominator_ratio,
            "word_edit_rate": self.word_edit_rate,
            "character_edit_rate": self.character_edit_rate,
            "token_edit_distance": self.token_edit_distance,
            "length_ratio": self.length_ratio,
            "protected_span_violation_count": self.protected_span_violation_count,
            "hard_invariant_passed": self.hard_invariant_passed,
            "eligible": self.eligible,
            "reason_codes": self.reason_codes,
        }


class BeamV3MetricEvaluator(Protocol):
    @property
    def detector_access_observed(self) -> bool: ...

    @property
    def secret_access_observed(self) -> bool: ...

    def evaluate(self, state: SearchState) -> BeamV3StateMetrics: ...


@dataclass(frozen=True, slots=True)
class BeamV3RankedState:
    state: SearchState
    metrics: BeamV3StateMetrics
    ranked_state_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.state, SearchState):
            raise TypeError("state must be SearchState")
        if not isinstance(self.metrics, BeamV3StateMetrics):
            raise TypeError("metrics must be BeamV3StateMetrics")
        if self.metrics.state_hash != self.state.search_state_hash:
            raise ValueError("metrics do not bind the ranked SearchState")
        if not self.metrics.eligible:
            raise ValueError("ineligible metrics cannot enter the beam")
        require_sha256("ranked_state_hash", self.ranked_state_hash)
        if self.ranked_state_hash != sha256_json(self.payload()):
            raise ValueError("ranked_state_hash does not match payload")

    @classmethod
    def create(cls, state: SearchState, metrics: BeamV3StateMetrics) -> BeamV3RankedState:
        payload = {
            "algorithm_version": BEAM_V3_RANKED_STATE_VERSION,
            "state_hash": state.search_state_hash,
            "metrics_hash": metrics.metrics_hash,
        }
        return cls(state=state, metrics=metrics, ranked_state_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": BEAM_V3_RANKED_STATE_VERSION,
            "state_hash": self.state.search_state_hash,
            "metrics_hash": self.metrics.metrics_hash,
        }


@dataclass(frozen=True, slots=True)
class BeamV3Result:
    algorithm_version: str
    root_state_hash: str
    budget: int
    states: tuple[BeamV3RankedState, ...]
    frontier: tuple[BeamV3RankedState, ...]
    expanded_state_count: int
    pruned_state_count: int
    ineligible_state_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION:
            raise ValueError("unsupported beam-v3 algorithm version")
        require_sha256("root_state_hash", self.root_state_hash)
        for name in ("budget", "expanded_state_count", "pruned_state_count", "ineligible_state_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.states, tuple) or any(not isinstance(value, BeamV3RankedState) for value in self.states):
            raise TypeError("states must contain BeamV3RankedState values")
        if not isinstance(self.frontier, tuple) or any(not isinstance(value, BeamV3RankedState) for value in self.frontier):
            raise TypeError("frontier must contain BeamV3RankedState values")
        state_hashes = {value.state.text_hash for value in self.states}
        if len(state_hashes) != len(self.states):
            raise ValueError("states must be deduplicated by text hash")
        if any(value.state.text_hash not in state_hashes for value in self.frontier):
            raise ValueError("frontier must be a subset of states")
        if type(self.detector_access_observed) is not bool or type(self.secret_access_observed) is not bool:
            raise TypeError("access attestations must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("beam-v3 structural search is contaminated")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash does not match BeamV3Result payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "result_schema_version": BEAM_V3_RESULT_VERSION,
            "root_state_hash": self.root_state_hash,
            "budget": self.budget,
            "ranked_state_hashes": tuple(value.ranked_state_hash for value in self.states),
            "frontier_ranked_state_hashes": tuple(value.ranked_state_hash for value in self.frontier),
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "ineligible_state_count": self.ineligible_state_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _rif(value: BeamV3RankedState) -> Fraction:
    metrics = value.metrics
    return Fraction(
        metrics.preserved_root_valid_observation_count,
        max(1, metrics.final_valid_observation_count),
    )


def _vdr(value: BeamV3RankedState) -> Fraction:
    metrics = value.metrics
    return Fraction(
        metrics.final_valid_observation_count,
        max(1, metrics.root_valid_observation_count),
    )


def beam_v3_rank(value: BeamV3RankedState) -> tuple[object, ...]:
    state = value.state
    metrics = value.metrics
    return (
        _rif(value),
        -_vdr(value),
        metrics.word_edit_rate,
        metrics.character_edit_rate,
        metrics.token_edit_distance,
        state.visible_cost,
        state.highest_risk_tier,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _duplicate_rank(value: BeamV3RankedState) -> tuple[object, ...]:
    state = value.state
    metrics = value.metrics
    return (
        metrics.word_edit_rate,
        metrics.character_edit_rate,
        metrics.token_edit_distance,
        state.visible_cost,
        state.highest_risk_tier,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _deduplicate(values: Sequence[BeamV3RankedState]) -> tuple[BeamV3RankedState, ...]:
    by_text_hash: dict[str, BeamV3RankedState] = {}
    for value in values:
        if not isinstance(value, BeamV3RankedState):
            raise TypeError("values must contain BeamV3RankedState objects")
        existing = by_text_hash.get(value.state.text_hash)
        if existing is None or _duplicate_rank(value) < _duplicate_rank(existing):
            by_text_hash[value.state.text_hash] = value
    return tuple(sorted(by_text_hash.values(), key=beam_v3_rank))


def _dominates(left: BeamV3RankedState, right: BeamV3RankedState) -> bool:
    left_values = (
        _rif(left),
        -_vdr(left),
        left.metrics.word_edit_rate,
        left.metrics.character_edit_rate,
        left.metrics.token_edit_distance,
        left.state.visible_cost,
        left.state.highest_risk_tier,
        left.state.depth,
    )
    right_values = (
        _rif(right),
        -_vdr(right),
        right.metrics.word_edit_rate,
        right.metrics.character_edit_rate,
        right.metrics.token_edit_distance,
        right.state.visible_cost,
        right.state.highest_risk_tier,
        right.state.depth,
    )
    return all(a <= b for a, b in zip(left_values, right_values)) and any(
        a < b for a, b in zip(left_values, right_values)
    )


def beam_v3_frontier(values: Sequence[BeamV3RankedState]) -> tuple[BeamV3RankedState, ...]:
    materialized = _deduplicate(values)
    output = tuple(
        value
        for value in materialized
        if not any(
            other.ranked_state_hash != value.ranked_state_hash and _dominates(other, value)
            for other in materialized
        )
    )
    return tuple(sorted(output, key=beam_v3_rank))


def _assert_blind(expander: StateExpander, evaluator: BeamV3MetricEvaluator) -> None:
    if bool(getattr(expander, "detector_access_observed", False)):
        raise ValueError("detector access contaminates beam-v3 selection")
    if bool(getattr(expander, "secret_access_observed", False)):
        raise ValueError("secret access contaminates beam-v3 selection")
    if bool(getattr(evaluator, "detector_access_observed", False)):
        raise ValueError("detector access contaminates beam-v3 metrics")
    if bool(getattr(evaluator, "secret_access_observed", False)):
        raise ValueError("secret access contaminates beam-v3 metrics")


def _evaluate(
    evaluator: BeamV3MetricEvaluator,
    state: SearchState,
) -> BeamV3RankedState | None:
    metrics = evaluator.evaluate(state)
    if not isinstance(metrics, BeamV3StateMetrics):
        raise TypeError("beam-v3 evaluator must return BeamV3StateMetrics")
    if metrics.state_hash != state.search_state_hash:
        raise ValueError("beam-v3 evaluator returned metrics for a different state")
    if not metrics.eligible:
        return None
    return BeamV3RankedState.create(state, metrics)


def beam_search_v3(
    expander: StateExpander,
    evaluator: BeamV3MetricEvaluator,
    root: SearchState,
    budget: int,
    beam_width: int,
) -> BeamV3Result:
    require_int("budget", budget)
    require_int("beam_width", beam_width)
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    if not isinstance(root, SearchState):
        raise TypeError("root must be SearchState")
    _assert_blind(expander, evaluator)
    ranked_root = _evaluate(evaluator, root)
    if ranked_root is None:
        raise ValueError("beam-v3 root state must be eligible")
    beam = (ranked_root,)
    expanded = 0
    pruned = 0
    ineligible = 0
    for _ in range(budget):
        children: list[BeamV3RankedState] = []
        for ranked in beam:
            transitions = expander.expand(ranked.state)
            expanded += 1
            _assert_blind(expander, evaluator)
            for transition in transitions:
                candidate = _evaluate(evaluator, transition.child)
                _assert_blind(expander, evaluator)
                if candidate is None:
                    ineligible += 1
                else:
                    children.append(candidate)
        unique = _deduplicate(children)
        if not unique:
            beam = ()
            break
        ranked_children = tuple(sorted(unique, key=beam_v3_rank))
        pruned += max(0, len(ranked_children) - beam_width)
        beam = ranked_children[:beam_width]
    states = _deduplicate(beam)
    frontier = beam_v3_frontier(states)
    payload = {
        "algorithm_version": CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
        "result_schema_version": BEAM_V3_RESULT_VERSION,
        "root_state_hash": root.search_state_hash,
        "budget": budget,
        "ranked_state_hashes": tuple(value.ranked_state_hash for value in states),
        "frontier_ranked_state_hashes": tuple(value.ranked_state_hash for value in frontier),
        "expanded_state_count": expanded,
        "pruned_state_count": pruned,
        "ineligible_state_count": ineligible,
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return BeamV3Result(
        algorithm_version=CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
        root_state_hash=root.search_state_hash,
        budget=budget,
        states=states,
        frontier=frontier,
        expanded_state_count=expanded,
        pruned_state_count=pruned,
        ineligible_state_count=ineligible,
        detector_access_observed=False,
        secret_access_observed=False,
        result_hash=sha256_json(payload),
    )
