from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.context_survival import ContextSurvivalExpander, InverseSemanticOperation
from fuckmark.scheduling.state_search import exact_b2


@dataclass(frozen=True)
class Value:
    value: str


@dataclass(frozen=True)
class FakeRange:
    start: int
    end: int
    label: str


@dataclass(frozen=True)
class FakeCandidate:
    candidate_id: str
    rule_id: str
    rule_hash: str
    source_text: str
    replacement_text: str
    family: Value
    tier: Value

    @classmethod
    def create(
        cls,
        rule_id: str,
        source_text: str,
        replacement_text: str,
        *,
        tier: str = "tier_1_surface",
    ) -> FakeCandidate:
        return cls(
            candidate_id=sha256_text(f"candidate:{rule_id}:{source_text}:{replacement_text}"),
            rule_id=rule_id,
            rule_hash=sha256_text("rule:" + rule_id),
            source_text=source_text,
            replacement_text=replacement_text,
            family=Value("orthography"),
            tier=Value(tier),
        )


@dataclass(frozen=True)
class FakeEnumeration:
    input_text: str
    candidates: tuple[FakeCandidate, ...]
    enumeration_hash: str


class FakeRegistry:
    def __init__(self, rules: dict[str, tuple[FakeCandidate, ...]]) -> None:
        self.rules = rules
        self.identifiers: tuple[str, ...] = ()
        self.enumeration_calls: list[tuple[str, tuple[FakeRange, ...]]] = []

    def enumerate(self, text: str, user_ranges=()) -> FakeEnumeration:
        ranges = tuple(user_ranges)
        self.enumeration_calls.append((text, ranges))
        candidates = tuple(self.rules.get(text, ()))
        return FakeEnumeration(text, candidates, sha256_json((text, tuple(value.candidate_id for value in candidates), ranges)))

    def apply(self, enumeration: FakeEnumeration, candidate_ids: tuple[str, ...]):
        candidate = next(value for value in enumeration.candidates if value.candidate_id == candidate_ids[0])
        index = enumeration.input_text.index(candidate.source_text)
        output = (
            enumeration.input_text[:index]
            + candidate.replacement_text
            + enumeration.input_text[index + len(candidate.source_text) :]
        )
        operation = SimpleNamespace(operation_hash=sha256_text("operation:" + candidate.candidate_id + ":" + enumeration.input_text))
        return SimpleNamespace(output_text=output, trace=SimpleNamespace(operations=(operation,)))


class FakeGeometry:
    def __init__(self, surviving: dict[str, int], masked: dict[str, int] | None = None) -> None:
        self.surviving = surviving
        self.masked = masked or {}
        self.detector_access_observed = False

    def build_root(self, *, source_sample_id: str, source_text: str):
        tokens = tuple(range(max(1, len(source_text.split()))))
        return SimpleNamespace(
            source_sample_id=source_sample_id,
            source_text=source_text,
            source_text_hash=sha256_text(source_text),
            root_tokens=tokens,
        )

    def evaluate_output(self, *, root, current_text: str, output_text: str, **kwargs):
        surviving = self.surviving[output_text]
        masked = self.masked.get(output_text, 0)
        report = SimpleNamespace(report_hash=sha256_text(f"report:{output_text}:{surviving}:{masked}"))
        return SimpleNamespace(
            output_token_hash=sha256_text("tokens:" + output_text),
            survival_report=report,
            surviving_count=surviving,
            newly_masked_count=masked,
            token_edit_distance=0 if output_text == root.source_text else 1,
        )


def _hard_validator(original: str, transformed: str, identifiers=(), user_ranges=()):
    status = Value("pass" if "BAD" not in transformed else "fail")
    return SimpleNamespace(status=status, report_hash=sha256_text("hard:" + original + ":" + transformed))


def _range_factory(start: int, end: int, label: str) -> FakeRange:
    return FakeRange(start, end, label)


def test_exact_b2_uses_reenumerated_second_step_candidates() -> None:
    first = FakeCandidate.create("first", "A", "B")
    second = FakeCandidate.create("second", "X", "Y")
    registry = FakeRegistry({"A X": (first,), "B X": (second,)})
    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"A X": 5, "B X": 3, "B Y": 1}),
        source_sample_id="source",
        source_text="A X",
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    result = exact_b2(expander, expander.root_state)
    assert tuple(state.text for state in result.states) == ("B Y",)
    assert result.states[0].surviving_root_observations == 1
    assert any(text == "B X" for text, _ in registry.enumeration_calls)
    assert expander.detector_access_observed is False
    assert expander.secret_access_observed is False


def test_ancestor_hash_cycle_is_rejected() -> None:
    forward = FakeCandidate.create("forward", "A", "B")
    backward = FakeCandidate.create("backward", "B", "A")
    registry = FakeRegistry({"A": (forward,), "B": (backward,)})
    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"A": 3, "B": 2}),
        source_sample_id="source",
        source_text="A",
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    first = expander.expand(expander.root_state)
    assert len(first) == 1
    assert expander.expand(first[0].child) == ()


def test_direct_inverse_same_semantic_site_is_rejected_after_unrelated_edit() -> None:
    forward = FakeCandidate.create("forward", "A", "B")
    unrelated = FakeCandidate.create("unrelated", "X", "Y")
    backward = FakeCandidate.create("backward", "B", "A")
    registry = FakeRegistry({"A X": (forward,), "B X": (unrelated,), "B Y": (backward,)})

    def inverse_resolver(state, candidate):
        if candidate.rule_id == "forward":
            return InverseSemanticOperation("contraction", "site-a", "forward")
        if candidate.rule_id == "backward":
            return InverseSemanticOperation("contraction", "site-a", "backward")
        return None

    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"A X": 6, "B X": 4, "B Y": 3, "A Y": 2}),
        source_sample_id="source",
        source_text="A X",
        inverse_semantic_resolver=inverse_resolver,
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    s1 = expander.expand(expander.root_state)[0].child
    s2 = expander.expand(s1)[0].child
    assert s2.text == "B Y"
    assert expander.expand(s2) == ()


def test_root_relative_hard_invariant_failure_blocks_transition() -> None:
    candidate = FakeCandidate.create("unsafe", "A", "BAD")
    registry = FakeRegistry({"A": (candidate,)})
    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"A": 3, "BAD": 0}),
        source_sample_id="source",
        source_text="A",
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    assert expander.expand(expander.root_state) == ()


def test_user_marked_entity_is_relocated_before_reenumeration() -> None:
    first = FakeCandidate.create("shrink", "AA", "A")
    registry = FakeRegistry({"AA ID": (first,), "A ID": ()})
    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"AA ID": 4, "A ID": 2}),
        source_sample_id="source",
        source_text="AA ID",
        root_user_ranges=(FakeRange(3, 5, "entity"),),
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    child = expander.expand(expander.root_state)[0].child
    assert child.text == "A ID"
    matching = [ranges for text, ranges in registry.enumeration_calls if text == "A ID"]
    assert matching
    assert matching[-1] == (FakeRange(2, 4, "entity"),)


def test_risk_ceiling_filters_higher_tier_candidates() -> None:
    safe = FakeCandidate.create("safe", "A", "B", tier="tier_1_surface")
    risky = FakeCandidate.create("risky", "A", "C", tier="tier_2_lexical")
    registry = FakeRegistry({"A": (safe, risky)})
    expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=FakeGeometry({"A": 4, "B": 3, "C": 1}),
        source_sample_id="source",
        source_text="A",
        max_risk_tier=1,
        hard_invariant_validator=_hard_validator,
        user_range_factory=_range_factory,
    )
    assert tuple(value.child.text for value in expander.expand(expander.root_state)) == ("B",)
