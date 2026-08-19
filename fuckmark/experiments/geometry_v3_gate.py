from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..search.beam_v3 import (
    CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
    BeamV3RankedState,
    BeamV3Result,
    BeamV3StateMetrics,
)
from ..scheduling.algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from ..scheduling.state_search import SearchState
from .mid_dev_quality import protected_span_violation_count
from .residual_signal_geometry import compute_residual_signal_geometry, strict_residual_signal_gate
from .structural_leverage import build_structural_leverage_sidecar


GEOMETRY_V3_GATE_ALGORITHM_VERSION = "middev-geometry-v3-gate-v1"
GEOMETRY_V3_ROW_VERSION = "middev-geometry-v3-row-v1"
MATCHED_COST_ENVELOPE_VERSION = "matched-visible-cost-envelope-v1"
GEOMETRY_V3_GATE_BUDGETS = (4, 6)
GEOMETRY_V3_REPETITION_MASK_GROWTH_CAP = 0
GEOMETRY_V3_STRICT_LENGTH_RATIO_MIN = 0.97
GEOMETRY_V3_STRICT_LENGTH_RATIO_MAX = 1.03
GEOMETRY_V3_PASS = "NS1_STRUCTURAL_LEVERAGE_PASS"
GEOMETRY_V3_K1 = "K1_RIF_ADDS_NO_STRUCTURAL_VALUE"
GEOMETRY_V3_K2 = "K2_V3_SEARCH_HAS_NO_MATCHED_COST_GAIN"
GEOMETRY_V3_INCOMPLETE = "GEOMETRY_V3_GATE_INCOMPLETE"
_GIT_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _require_git_object_id(name: str, value: str) -> None:
    require_clean_string(name, value)
    if _GIT_OBJECT_ID_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase 40- or 64-hex Git object ID")


@dataclass(frozen=True, slots=True)
class MatchedVisibleCostEnvelope:
    max_word_edit_rate: float
    max_character_edit_rate: float
    max_token_edit_distance: int
    max_visible_cost: int
    envelope_hash: str

    def __post_init__(self) -> None:
        for name in ("max_word_edit_rate", "max_character_edit_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        for name in ("max_token_edit_distance", "max_visible_cost"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        require_sha256("envelope_hash", self.envelope_hash)
        if self.envelope_hash != sha256_json(self.payload()):
            raise ValueError("envelope_hash does not match matched visible-cost envelope")

    @classmethod
    def create(
        cls,
        *,
        max_word_edit_rate: float,
        max_character_edit_rate: float,
        max_token_edit_distance: int,
        max_visible_cost: int,
    ) -> MatchedVisibleCostEnvelope:
        payload = {
            "algorithm_version": MATCHED_COST_ENVELOPE_VERSION,
            "max_word_edit_rate": float(max_word_edit_rate),
            "max_character_edit_rate": float(max_character_edit_rate),
            "max_token_edit_distance": max_token_edit_distance,
            "max_visible_cost": max_visible_cost,
        }
        return cls(
            max_word_edit_rate=payload["max_word_edit_rate"],
            max_character_edit_rate=payload["max_character_edit_rate"],
            max_token_edit_distance=max_token_edit_distance,
            max_visible_cost=max_visible_cost,
            envelope_hash=sha256_json(payload),
        )

    @classmethod
    def from_state(
        cls,
        state: SearchState,
        metrics: BeamV3StateMetrics,
    ) -> MatchedVisibleCostEnvelope:
        if metrics.state_hash != state.search_state_hash:
            raise ValueError("metrics do not bind state")
        return cls.create(
            max_word_edit_rate=metrics.word_edit_rate,
            max_character_edit_rate=metrics.character_edit_rate,
            max_token_edit_distance=metrics.token_edit_distance,
            max_visible_cost=state.visible_cost,
        )

    def allows(self, state: SearchState, metrics: BeamV3StateMetrics) -> bool:
        if metrics.state_hash != state.search_state_hash:
            raise ValueError("metrics do not bind state")
        return (
            metrics.word_edit_rate <= self.max_word_edit_rate
            and metrics.character_edit_rate <= self.max_character_edit_rate
            and metrics.token_edit_distance <= self.max_token_edit_distance
            and state.visible_cost <= self.max_visible_cost
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MATCHED_COST_ENVELOPE_VERSION,
            "max_word_edit_rate": self.max_word_edit_rate,
            "max_character_edit_rate": self.max_character_edit_rate,
            "max_token_edit_distance": self.max_token_edit_distance,
            "max_visible_cost": self.max_visible_cost,
        }


class PublicResidualStateEvaluator:
    def __init__(
        self,
        *,
        root_text: str,
        retokenize: Callable[[str], Sequence[int]],
        eos_token_id: int,
        ngram_len: int,
        context_history_size: int,
        hard_invariant_validator: Callable[[str], bool],
        repetition_mask_growth_cap: int = GEOMETRY_V3_REPETITION_MASK_GROWTH_CAP,
        cost_envelope: MatchedVisibleCostEnvelope | None = None,
    ) -> None:
        if not isinstance(root_text, str):
            raise TypeError("root_text must be a string")
        if not callable(retokenize):
            raise TypeError("retokenize must be callable")
        if not callable(hard_invariant_validator):
            raise TypeError("hard_invariant_validator must be callable")
        require_int("eos_token_id", eos_token_id)
        require_int("ngram_len", ngram_len)
        require_int("context_history_size", context_history_size)
        require_int("repetition_mask_growth_cap", repetition_mask_growth_cap)
        if eos_token_id < 0 or ngram_len < 2 or context_history_size <= 0:
            raise ValueError("invalid public residual geometry configuration")
        if repetition_mask_growth_cap < 0:
            raise ValueError("repetition_mask_growth_cap must be non-negative")
        if cost_envelope is not None and not isinstance(cost_envelope, MatchedVisibleCostEnvelope):
            raise TypeError("cost_envelope must be MatchedVisibleCostEnvelope or None")
        self._root_text = root_text
        self._root_hash = sha256_text(root_text)
        self._retokenize = retokenize
        self._root_tokens = self._tokens(root_text)
        self._eos_token_id = eos_token_id
        self._ngram_len = ngram_len
        self._context_history_size = context_history_size
        self._hard_invariant_validator = hard_invariant_validator
        self._repetition_mask_growth_cap = repetition_mask_growth_cap
        self._cost_envelope = cost_envelope
        self._cache: dict[str, BeamV3StateMetrics] = {}

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def secret_access_observed(self) -> bool:
        return False

    @property
    def cost_envelope(self) -> MatchedVisibleCostEnvelope | None:
        return self._cost_envelope

    def _tokens(self, text: str) -> tuple[int, ...]:
        values = tuple(self._retokenize(text))
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("retokenize must return non-negative integer token IDs")
        return values

    def evaluate(self, state: SearchState) -> BeamV3StateMetrics:
        if not isinstance(state, SearchState):
            raise TypeError("state must be SearchState")
        if state.root_source_hash != self._root_hash:
            raise ValueError("state belongs to a different root source")
        cached = self._cache.get(state.search_state_hash)
        if cached is not None:
            return cached
        final_tokens = self._tokens(state.text)
        geometry = compute_residual_signal_geometry(
            self._root_tokens,
            final_tokens,
            eos_token_id=self._eos_token_id,
            ngram_len=self._ngram_len,
            context_history_size=self._context_history_size,
        )
        sidecar = build_structural_leverage_sidecar(
            variant_hash=state.search_state_hash,
            source_text=self._root_text,
            transformed_text=state.text,
            operation_count=state.depth,
            geometry=geometry,
        )
        hard_passed = self._hard_invariant_validator(state.text)
        if type(hard_passed) is not bool:
            raise TypeError("hard_invariant_validator must return bool")
        protected_violations = protected_span_violation_count(self._root_text, state.text)
        length_ratio = len(state.text) / max(1, len(self._root_text))
        provisional = BeamV3StateMetrics.create(
            state_hash=state.search_state_hash,
            geometry_hash=geometry.geometry_hash,
            root_valid_observation_count=geometry.root_valid_observation_count,
            final_valid_observation_count=geometry.final_valid_observation_count,
            preserved_root_valid_observation_count=geometry.preserved_root_valid_observation_count,
            repetition_mask_delta=geometry.repetition_mask_delta,
            word_edit_rate=sidecar.visible_word_edit_rate,
            character_edit_rate=sidecar.visible_character_edit_rate,
            token_edit_distance=sidecar.token_edit_distance,
            length_ratio=length_ratio,
            protected_span_violation_count=protected_violations,
            hard_invariant_passed=hard_passed,
            reason_codes=(),
        )
        matched_cost = self._cost_envelope is None or self._cost_envelope.allows(state, provisional)
        strict_length = (
            GEOMETRY_V3_STRICT_LENGTH_RATIO_MIN
            <= length_ratio
            <= GEOMETRY_V3_STRICT_LENGTH_RATIO_MAX
        )
        gate = strict_residual_signal_gate(
            geometry,
            repetition_mask_growth_cap=self._repetition_mask_growth_cap,
            protected_span_violation_count=protected_violations,
            hard_invariant_passed=hard_passed,
            visible_fidelity_passed=matched_cost and strict_length,
        )
        metrics = BeamV3StateMetrics.create(
            state_hash=state.search_state_hash,
            geometry_hash=geometry.geometry_hash,
            root_valid_observation_count=geometry.root_valid_observation_count,
            final_valid_observation_count=geometry.final_valid_observation_count,
            preserved_root_valid_observation_count=geometry.preserved_root_valid_observation_count,
            repetition_mask_delta=geometry.repetition_mask_delta,
            word_edit_rate=sidecar.visible_word_edit_rate,
            character_edit_rate=sidecar.visible_character_edit_rate,
            token_edit_distance=sidecar.token_edit_distance,
            length_ratio=length_ratio,
            protected_span_violation_count=protected_violations,
            hard_invariant_passed=hard_passed,
            reason_codes=gate.reason_codes,
        )
        self._cache[state.search_state_hash] = metrics
        return metrics


@dataclass(frozen=True, slots=True)
class GeometryV3GateRow:
    source_sample_id: str
    budget: int
    v2_status: str
    v3_status: str
    v2_state_hash: str
    v3_state_hash: str | None
    v2_search_state_root_survivors: int
    v3_search_state_root_survivors: int | None
    v2_metrics_hash: str
    v3_metrics_hash: str | None
    v2_preserved_root_valid_count: int
    v2_final_valid_count: int
    v3_preserved_root_valid_count: int | None
    v3_final_valid_count: int | None
    v2_word_edit_rate: float
    v3_word_edit_rate: float | None
    v2_character_edit_rate: float
    v3_character_edit_rate: float | None
    v2_token_edit_distance: int
    v3_token_edit_distance: int | None
    v2_visible_cost: int
    v3_visible_cost: int | None
    v3_eligible: bool
    matched_cost_pass: bool
    residual_specific_win: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        require_clean_string("v2_status", self.v2_status)
        require_clean_string("v3_status", self.v3_status)
        require_int("budget", self.budget)
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        for name in ("v2_state_hash", "v2_metrics_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        for name in ("v3_state_hash", "v3_metrics_hash"):
            value = getattr(self, name)
            if value is not None:
                require_sha256(name, value)
        for name in (
            "v2_search_state_root_survivors",
            "v2_preserved_root_valid_count",
            "v2_final_valid_count",
            "v2_token_edit_distance",
            "v2_visible_cost",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in (
            "v3_search_state_root_survivors",
            "v3_preserved_root_valid_count",
            "v3_final_valid_count",
            "v3_token_edit_distance",
            "v3_visible_cost",
        ):
            value = getattr(self, name)
            if value is not None:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} must be non-negative")
        for name in ("v3_eligible", "matched_cost_pass", "residual_specific_win"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if self.v3_state_hash is None and (
            self.v3_metrics_hash is not None
            or self.v3_eligible
            or self.matched_cost_pass
            or self.residual_specific_win
        ):
            raise ValueError("missing v3 state cannot carry successful v3 fields")
        if self.residual_specific_win and not self.matched_cost_pass:
            raise ValueError("residual-specific win requires matched cost")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match GeometryV3GateRow payload")

    @classmethod
    def create(
        cls,
        *,
        source_sample_id: str,
        budget: int,
        v2_status: str,
        v3_status: str,
        v2_state: SearchState,
        v2_metrics: BeamV3StateMetrics,
        v3_state: SearchState | None,
        v3_metrics: BeamV3StateMetrics | None,
    ) -> GeometryV3GateRow:
        if v2_metrics.state_hash != v2_state.search_state_hash:
            raise ValueError("v2 metrics do not bind v2 state")
        if (v3_state is None) != (v3_metrics is None):
            raise ValueError("v3 state and metrics must both be present or absent")
        if (
            v3_state is not None
            and v3_metrics is not None
            and v3_metrics.state_hash != v3_state.search_state_hash
        ):
            raise ValueError("v3 metrics do not bind v3 state")
        matched = False
        residual_specific = False
        if v3_state is not None and v3_metrics is not None:
            matched = (
                v3_metrics.word_edit_rate <= v2_metrics.word_edit_rate
                and v3_metrics.character_edit_rate <= v2_metrics.character_edit_rate
                and v3_metrics.token_edit_distance <= v2_metrics.token_edit_distance
                and v3_state.visible_cost <= v2_state.visible_cost
            )
            if matched and v3_metrics.eligible:
                v2_rif = Fraction(
                    v2_metrics.preserved_root_valid_observation_count,
                    max(1, v2_metrics.final_valid_observation_count),
                )
                v3_rif = Fraction(
                    v3_metrics.preserved_root_valid_observation_count,
                    max(1, v3_metrics.final_valid_observation_count),
                )
                residual_specific = (
                    v3_rif < v2_rif
                    and v3_state.surviving_root_observations
                    >= v2_state.surviving_root_observations
                )
        payload = {
            "algorithm_version": GEOMETRY_V3_ROW_VERSION,
            "source_sample_id": source_sample_id,
            "budget": budget,
            "v2_status": v2_status,
            "v3_status": v3_status,
            "v2_state_hash": v2_state.search_state_hash,
            "v3_state_hash": v3_state.search_state_hash if v3_state is not None else None,
            "v2_search_state_root_survivors": v2_state.surviving_root_observations,
            "v3_search_state_root_survivors": (
                v3_state.surviving_root_observations if v3_state is not None else None
            ),
            "v2_metrics_hash": v2_metrics.metrics_hash,
            "v3_metrics_hash": v3_metrics.metrics_hash if v3_metrics is not None else None,
            "v2_preserved_root_valid_count": v2_metrics.preserved_root_valid_observation_count,
            "v2_final_valid_count": v2_metrics.final_valid_observation_count,
            "v3_preserved_root_valid_count": (
                v3_metrics.preserved_root_valid_observation_count
                if v3_metrics is not None
                else None
            ),
            "v3_final_valid_count": (
                v3_metrics.final_valid_observation_count if v3_metrics is not None else None
            ),
            "v2_word_edit_rate": v2_metrics.word_edit_rate,
            "v3_word_edit_rate": v3_metrics.word_edit_rate if v3_metrics is not None else None,
            "v2_character_edit_rate": v2_metrics.character_edit_rate,
            "v3_character_edit_rate": (
                v3_metrics.character_edit_rate if v3_metrics is not None else None
            ),
            "v2_token_edit_distance": v2_metrics.token_edit_distance,
            "v3_token_edit_distance": (
                v3_metrics.token_edit_distance if v3_metrics is not None else None
            ),
            "v2_visible_cost": v2_state.visible_cost,
            "v3_visible_cost": v3_state.visible_cost if v3_state is not None else None,
            "v3_eligible": bool(v3_metrics is not None and v3_metrics.eligible),
            "matched_cost_pass": matched,
            "residual_specific_win": residual_specific,
        }
        kwargs = {key: value for key, value in payload.items() if key != "algorithm_version"}
        return cls(**kwargs, row_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": GEOMETRY_V3_ROW_VERSION,
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name != "row_hash"
            },
        }

    @property
    def rif_improvement(self) -> Fraction | None:
        if self.v3_preserved_root_valid_count is None or self.v3_final_valid_count is None:
            return None
        return Fraction(
            self.v2_preserved_root_valid_count,
            max(1, self.v2_final_valid_count),
        ) - Fraction(
            self.v3_preserved_root_valid_count,
            max(1, self.v3_final_valid_count),
        )


def _median_fraction(values: Sequence[Fraction]) -> Fraction:
    if not values:
        raise ValueError("median requires values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def classify_geometry_v3_gate(
    rows: Sequence[GeometryV3GateRow],
    budgets: Sequence[int] = GEOMETRY_V3_GATE_BUDGETS,
) -> str:
    materialized = tuple(rows)
    budget_tuple = tuple(budgets)
    if budget_tuple != GEOMETRY_V3_GATE_BUDGETS:
        raise ValueError("geometry-v3 gate budgets must remain frozen at B4/B6")
    if not materialized:
        return GEOMETRY_V3_INCOMPLETE
    source_ids = tuple(sorted({row.source_sample_id for row in materialized}))
    seen = {(row.source_sample_id, row.budget) for row in materialized}
    expected = {(source_id, budget) for source_id in source_ids for budget in budget_tuple}
    if seen != expected or len(seen) != len(materialized):
        return GEOMETRY_V3_INCOMPLETE
    if any(
        row.v2_status != "SUCCESS"
        or row.v3_status != "SUCCESS"
        or row.v3_state_hash is None
        or not row.v3_eligible
        or not row.matched_cost_pass
        or row.rif_improvement is None
        for row in materialized
    ):
        return GEOMETRY_V3_K2
    improvements = tuple(row.rif_improvement for row in materialized)
    if any(value is None for value in improvements):
        return GEOMETRY_V3_K2
    exact = tuple(value for value in improvements if value is not None)
    if any(value < 0 for value in exact):
        return GEOMETRY_V3_K2
    for budget in budget_tuple:
        budget_gains = tuple(
            row.rif_improvement
            for row in materialized
            if row.budget == budget and row.rif_improvement is not None
        )
        if not budget_gains or _median_fraction(budget_gains) <= 0:
            return GEOMETRY_V3_K2
        if not any(
            row.residual_specific_win for row in materialized if row.budget == budget
        ):
            return GEOMETRY_V3_K1
    return GEOMETRY_V3_PASS


@dataclass(frozen=True, slots=True)
class GeometryV3GateArtifact:
    source_code_commit: str
    source_corpus_hash: str
    candidate_registry_hash: str
    model_identity_hash: str
    ngram_len: int
    context_history_size: int
    beam_width: int
    budgets: tuple[int, ...]
    v2_algorithm_version: str
    v3_algorithm_version: str
    repetition_mask_growth_cap: int
    rows: tuple[GeometryV3GateRow, ...]
    decision: str
    artifact_hash: str

    def __post_init__(self) -> None:
        _require_git_object_id("source_code_commit", self.source_code_commit)
        for name in ("source_corpus_hash", "candidate_registry_hash", "model_identity_hash"):
            require_sha256(name, getattr(self, name))
        for name in (
            "ngram_len",
            "context_history_size",
            "beam_width",
            "repetition_mask_growth_cap",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.ngram_len < 2 or self.context_history_size <= 0 or self.beam_width <= 0:
            raise ValueError("invalid geometry gate configuration")
        if self.budgets != GEOMETRY_V3_GATE_BUDGETS:
            raise ValueError("geometry gate budgets drifted")
        if self.v2_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
            raise ValueError("v2 algorithm version drifted")
        if self.v3_algorithm_version != CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION:
            raise ValueError("v3 algorithm version drifted")
        if self.repetition_mask_growth_cap != GEOMETRY_V3_REPETITION_MASK_GROWTH_CAP:
            raise ValueError("repetition-mask growth cap drifted")
        if not isinstance(self.rows, tuple) or any(
            not isinstance(row, GeometryV3GateRow) for row in self.rows
        ):
            raise TypeError("rows must contain GeometryV3GateRow values")
        if self.decision not in {
            GEOMETRY_V3_PASS,
            GEOMETRY_V3_K1,
            GEOMETRY_V3_K2,
            GEOMETRY_V3_INCOMPLETE,
        }:
            raise ValueError("unsupported geometry-v3 decision")
        if classify_geometry_v3_gate(self.rows, self.budgets) != self.decision:
            raise ValueError("decision does not reproduce from geometry-v3 rows")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match GeometryV3GateArtifact payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": GEOMETRY_V3_GATE_ALGORITHM_VERSION,
            "source_code_commit": self.source_code_commit,
            "source_corpus_hash": self.source_corpus_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "model_identity_hash": self.model_identity_hash,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "beam_width": self.beam_width,
            "budgets": self.budgets,
            "v2_algorithm_version": self.v2_algorithm_version,
            "v3_algorithm_version": self.v3_algorithm_version,
            "repetition_mask_growth_cap": self.repetition_mask_growth_cap,
            "row_hashes": tuple(row.row_hash for row in self.rows),
            "decision": self.decision,
        }


def build_geometry_v3_gate_artifact(
    *,
    source_code_commit: str,
    source_corpus_hash: str,
    candidate_registry_hash: str,
    model_identity_hash: str,
    ngram_len: int,
    context_history_size: int,
    beam_width: int,
    rows: Sequence[GeometryV3GateRow],
) -> GeometryV3GateArtifact:
    row_tuple = tuple(sorted(rows, key=lambda row: (row.source_sample_id, row.budget)))
    decision = classify_geometry_v3_gate(row_tuple)
    payload = {
        "algorithm_version": GEOMETRY_V3_GATE_ALGORITHM_VERSION,
        "source_code_commit": source_code_commit,
        "source_corpus_hash": source_corpus_hash,
        "candidate_registry_hash": candidate_registry_hash,
        "model_identity_hash": model_identity_hash,
        "ngram_len": ngram_len,
        "context_history_size": context_history_size,
        "beam_width": beam_width,
        "budgets": GEOMETRY_V3_GATE_BUDGETS,
        "v2_algorithm_version": CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        "v3_algorithm_version": CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
        "repetition_mask_growth_cap": GEOMETRY_V3_REPETITION_MASK_GROWTH_CAP,
        "row_hashes": tuple(row.row_hash for row in row_tuple),
        "decision": decision,
    }
    return GeometryV3GateArtifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=source_corpus_hash,
        candidate_registry_hash=candidate_registry_hash,
        model_identity_hash=model_identity_hash,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
        beam_width=beam_width,
        budgets=GEOMETRY_V3_GATE_BUDGETS,
        v2_algorithm_version=CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        v3_algorithm_version=CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
        repetition_mask_growth_cap=GEOMETRY_V3_REPETITION_MASK_GROWTH_CAP,
        rows=row_tuple,
        decision=decision,
        artifact_hash=sha256_json(payload),
    )


def select_v3_result_state(
    result: BeamV3Result,
    budget: int,
) -> BeamV3RankedState | None:
    require_int("budget", budget)
    full_depth = tuple(value for value in result.frontier if value.state.depth == budget)
    if full_depth:
        return full_depth[0]
    candidates = tuple(result.frontier or result.states)
    return candidates[0] if candidates else None
