from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int
from ..hashing import sha256_json, sha256_text
from .state_search import SearchState, SearchTransition


CONTEXT_SURVIVAL_EXPANDER_ALGORITHM_VERSION = "context-survival-expander-v1"


@dataclass(frozen=True, slots=True)
class InverseSemanticOperation:
    group_id: str
    site_id: str
    direction: str

    def __post_init__(self) -> None:
        require_clean_string("group_id", self.group_id)
        require_clean_string("site_id", self.site_id)
        require_clean_string("direction", self.direction)

    @property
    def history_entry(self) -> tuple[str, str, str]:
        return (self.group_id, self.site_id, self.direction)


class ContextSurvivalExpander:
    def __init__(
        self,
        *,
        registry: Any,
        geometry_engine: Any,
        source_sample_id: str,
        source_text: str,
        root_user_ranges: Sequence[Any] = (),
        max_risk_tier: int = 4,
        inverse_semantic_resolver: Callable[[SearchState, Any], InverseSemanticOperation | None] | None = None,
        visible_cost_resolver: Callable[[Any], int] | None = None,
        hard_invariant_validator: Callable[..., Any] | None = None,
        user_range_factory: Callable[[int, int, str], Any] | None = None,
    ) -> None:
        if registry is None:
            raise TypeError("registry is required")
        if geometry_engine is None:
            raise TypeError("geometry_engine is required")
        require_clean_string("source_sample_id", source_sample_id)
        if not isinstance(source_text, str):
            raise TypeError("source_text must be a string")
        require_int("max_risk_tier", max_risk_tier)
        if not 0 <= max_risk_tier <= 4:
            raise ValueError("max_risk_tier must be between 0 and 4")
        if inverse_semantic_resolver is not None and not callable(inverse_semantic_resolver):
            raise TypeError("inverse_semantic_resolver must be callable")
        if visible_cost_resolver is not None and not callable(visible_cost_resolver):
            raise TypeError("visible_cost_resolver must be callable")
        if hard_invariant_validator is None:
            from ..transforms.hard_invariants import validate_hard_invariants

            hard_invariant_validator = validate_hard_invariants
        if user_range_factory is None:
            from ..transforms.protected_artifacts import UserProtectedRange

            user_range_factory = UserProtectedRange.create
        self._registry = registry
        self._geometry_engine = geometry_engine
        self._source_sample_id = source_sample_id
        self._source_text = source_text
        self._root_user_ranges = tuple(root_user_ranges)
        self._max_risk_tier = max_risk_tier
        self._inverse_semantic_resolver = inverse_semantic_resolver
        self._visible_cost_resolver = visible_cost_resolver
        self._hard_invariant_validator = hard_invariant_validator
        self._user_range_factory = user_range_factory
        self._root_user_entities = self._capture_root_user_entities()
        self._root = geometry_engine.build_root(source_sample_id=source_sample_id, source_text=source_text)
        self._root_state = self._build_root_state()

    @property
    def root_state(self) -> SearchState:
        return self._root_state

    @property
    def detector_access_observed(self) -> bool:
        return bool(getattr(self._geometry_engine, "detector_access_observed", False))

    @property
    def secret_access_observed(self) -> bool:
        return False

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        if not isinstance(state, SearchState):
            raise TypeError("state must be a SearchState")
        if state.root_source_hash != self._root.source_text_hash:
            raise ValueError("state belongs to a different root source")
        enumeration = self._enumerate_text(state.text)
        if enumeration.enumeration_hash != state.enumeration_hash:
            raise ValueError("state enumeration does not replay exactly")
        transitions: list[SearchTransition] = []
        for candidate in enumeration.candidates:
            risk_tier = self._risk_tier(candidate)
            if risk_tier > self._max_risk_tier:
                continue
            try:
                applied = self._registry.apply(enumeration, (candidate.candidate_id,))
            except (KeyError, ValueError):
                continue
            output_text = applied.output_text
            output_hash = sha256_text(output_text)
            if output_hash in (*state.ancestor_text_hashes, state.text_hash):
                continue
            inverse_operation = self._resolve_inverse(state, candidate)
            if inverse_operation is not None and self._is_direct_inverse(state, inverse_operation):
                continue
            root_hard_report = self._validate_root_hard_invariants(output_text)
            if not self._is_pass(root_hard_report):
                continue
            visible_cost_delta = self._visible_cost(candidate)
            counterfactual = self._geometry_engine.evaluate_output(
                root=self._root,
                current_text=state.text,
                output_text=output_text,
                candidate_id=candidate.candidate_id,
                rule_hash=candidate.rule_hash,
                visible_cost_class=visible_cost_delta,
                family=candidate.family.value,
                tier=risk_tier,
                hard_invariant_status="PASS",
            )
            child_enumeration = self._enumerate_text(output_text)
            operations = tuple(applied.trace.operations)
            if len(operations) != 1:
                raise ValueError("stateful search requires exactly one operation per transition")
            operation_hash = operations[0].operation_hash
            inverse_history = state.inverse_semantic_history
            if inverse_operation is not None:
                inverse_history = (*inverse_history, inverse_operation.history_entry)
            child = SearchState.create(
                root_source_hash=self._root.source_text_hash,
                text=output_text,
                depth=state.depth + 1,
                operation_hashes=(*state.operation_hashes, operation_hash),
                ancestor_text_hashes=(*state.ancestor_text_hashes, state.text_hash),
                inverse_semantic_history=inverse_history,
                root_tokenization_hash=sha256_json(self._root.root_tokens),
                current_tokenization_hash=counterfactual.output_token_hash,
                survival_report_hash=counterfactual.survival_report.report_hash,
                enumeration_hash=child_enumeration.enumeration_hash,
                hard_invariant_report_hash=root_hard_report.report_hash,
                surviving_root_observations=counterfactual.surviving_count,
                newly_masked_count=counterfactual.newly_masked_count,
                highest_risk_tier=max(state.highest_risk_tier, risk_tier),
                visible_cost=state.visible_cost + visible_cost_delta,
                token_edit_distance=counterfactual.token_edit_distance,
            )
            transitions.append(
                SearchTransition.create(
                    parent=state,
                    candidate_hash=candidate.candidate_id,
                    operation_hash=operation_hash,
                    visible_cost_delta=visible_cost_delta,
                    child=child,
                )
            )
        return tuple(sorted(transitions, key=lambda value: value.candidate_hash))

    def _build_root_state(self) -> SearchState:
        enumeration = self._enumerate_text(self._source_text)
        hard_report = self._validate_root_hard_invariants(self._source_text)
        if not self._is_pass(hard_report):
            raise ValueError("root source fails hard invariants against itself")
        identity = self._geometry_engine.evaluate_output(
            root=self._root,
            current_text=self._source_text,
            output_text=self._source_text,
            candidate_id=sha256_text("context-survival-root-identity"),
            rule_hash=sha256_text("context-survival-root-identity-rule"),
            visible_cost_class=0,
            family="identity",
            tier=0,
            hard_invariant_status="PASS",
        )
        return SearchState.create(
            root_source_hash=self._root.source_text_hash,
            text=self._source_text,
            depth=0,
            operation_hashes=(),
            ancestor_text_hashes=(),
            inverse_semantic_history=(),
            root_tokenization_hash=sha256_json(self._root.root_tokens),
            current_tokenization_hash=identity.output_token_hash,
            survival_report_hash=identity.survival_report.report_hash,
            enumeration_hash=enumeration.enumeration_hash,
            hard_invariant_report_hash=hard_report.report_hash,
            surviving_root_observations=identity.surviving_count,
            newly_masked_count=identity.newly_masked_count,
            highest_risk_tier=0,
            visible_cost=0,
            token_edit_distance=0,
        )

    def _capture_root_user_entities(self) -> tuple[tuple[str, str], ...]:
        output: list[tuple[str, str]] = []
        for value in self._root_user_ranges:
            start = getattr(value, "start", None)
            end = getattr(value, "end", None)
            label = getattr(value, "label", None)
            require_int("user range start", start)
            require_int("user range end", end)
            require_clean_string("user range label", label)
            if start < 0 or end <= start or end > len(self._source_text):
                raise ValueError("root user range is outside source text")
            output.append((self._source_text[start:end], label))
        return tuple(output)

    def _dynamic_user_ranges(self, text: str) -> tuple[Any, ...]:
        by_geometry: dict[tuple[int, int], set[str]] = {}
        for exact_text, label in self._root_user_entities:
            start = 0
            while True:
                index = text.find(exact_text, start)
                if index < 0:
                    break
                geometry = (index, index + len(exact_text))
                by_geometry.setdefault(geometry, set()).add(label)
                start = index + 1
        return tuple(
            self._user_range_factory(start, end, "|".join(sorted(labels)))
            for (start, end), labels in sorted(by_geometry.items())
        )

    def _enumerate_text(self, text: str) -> Any:
        return self._registry.enumerate(text, self._dynamic_user_ranges(text))

    def _validate_root_hard_invariants(self, output_text: str) -> Any:
        return self._hard_invariant_validator(
            self._source_text,
            output_text,
            getattr(self._registry, "identifiers", ()),
            self._root_user_ranges,
        )

    def _resolve_inverse(self, state: SearchState, candidate: Any) -> InverseSemanticOperation | None:
        if self._inverse_semantic_resolver is None:
            return None
        value = self._inverse_semantic_resolver(state, candidate)
        if value is not None and not isinstance(value, InverseSemanticOperation):
            raise TypeError("inverse_semantic_resolver must return InverseSemanticOperation or None")
        return value

    def _is_direct_inverse(self, state: SearchState, value: InverseSemanticOperation) -> bool:
        return any(
            group_id == value.group_id and site_id == value.site_id and direction != value.direction
            for group_id, site_id, direction in state.inverse_semantic_history
        )

    def _visible_cost(self, candidate: Any) -> int:
        if self._visible_cost_resolver is not None:
            value = self._visible_cost_resolver(candidate)
            require_int("visible cost", value)
            if value <= 0:
                raise ValueError("visible cost must be positive")
            return value
        mapping = {
            "tier_0_format": 1,
            "tier_1_surface": 1,
            "tier_2_lexical": 3,
            "tier_3_syntax": 4,
            "tier_4_experimental": 5,
        }
        value = mapping.get(candidate.tier.value)
        if value is None:
            raise ValueError("unsupported transform tier for visible cost")
        return value

    def _risk_tier(self, candidate: Any) -> int:
        mapping = {
            "tier_0_format": 0,
            "tier_1_surface": 1,
            "tier_2_lexical": 2,
            "tier_3_syntax": 3,
            "tier_4_experimental": 4,
        }
        value = mapping.get(candidate.tier.value)
        if value is None:
            raise ValueError("unsupported transform tier")
        return value

    @staticmethod
    def _is_pass(report: Any) -> bool:
        status = getattr(report, "status", None)
        value = getattr(status, "value", status)
        return value in ("PASS", "pass")
