from __future__ import annotations

import hashlib
import re

from fuckmark.geometry import CounterfactualGeometryEngine, GeometryConfig
from fuckmark.hashing import sha256_text
from fuckmark.scheduling.context_survival import ContextSurvivalExpander
from fuckmark.transforms.contractions import (
    context_survival_contraction_rules,
    contraction_inverse_semantic_resolver,
)
from fuckmark.transforms.protected_artifacts import UserProtectedRange
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import default_contraction_rules


class TinyTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        return [int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big") for value in pieces]


def _geometry() -> CounterfactualGeometryEngine:
    config = GeometryConfig.create(
        tokenizer_identity_hash=sha256_text("contraction-integration-tiny-tokenizer-v1"),
        ngram_len=2,
        repetition_mask_policy_id="all-eligible-v1",
    )
    return CounterfactualGeometryEngine(tokenizer=TinyTokenizer(), config=config)


def _expander(text: str, *, user_ranges=()) -> ContextSurvivalExpander:
    return ContextSurvivalExpander(
        registry=TransformRegistry(context_survival_contraction_rules()),
        geometry_engine=_geometry(),
        source_sample_id="contraction-integration",
        source_text=text,
        root_user_ranges=user_ranges,
        max_risk_tier=1,
        inverse_semantic_resolver=contraction_inverse_semantic_resolver,
    )


def test_forward_then_same_site_reverse_is_blocked() -> None:
    expander = _expander("We do not agree.")
    first = expander.expand(expander.root_state)
    assert len(first) == 1
    assert first[0].child.text == "We don't agree."
    assert expander.expand(first[0].child) == ()


def test_new_forward_then_same_site_reverse_is_blocked() -> None:
    expander = _expander("We are ready.")
    first = expander.expand(expander.root_state)
    matching = tuple(value for value in first if value.candidate.rule_id == "contract-we-are")
    assert len(matching) == 1
    assert matching[0].child.text == "We're ready."
    assert expander.expand(matching[0].child) == ()


def test_reverse_contraction_is_allowed_as_initial_action() -> None:
    expander = _expander("We don't agree.")
    first = expander.expand(expander.root_state)
    assert len(first) == 1
    assert first[0].child.text == "We do not agree."
    assert first[0].child.highest_risk_tier == 1


def test_reverse_contraction_remains_blocked_inside_user_protected_span() -> None:
    text = "We don't agree."
    start = text.index("don't")
    expander = _expander(
        text,
        user_ranges=(UserProtectedRange.create(start, start + len("don't"), "frozen-contraction"),),
    )
    assert expander.expand(expander.root_state) == ()


def test_e24_surface_fixture_candidate_set_expands() -> None:
    text = "We do not agree. They don't agree. I cannot stay, but you can't leave. We will not stop."
    forward = TransformRegistry(default_contraction_rules()).enumerate(text)
    reversible = TransformRegistry(context_survival_contraction_rules()).enumerate(text)
    assert len(forward.candidates) == 3
    assert len(reversible.candidates) == 6
    assert len(reversible.candidates) > len(forward.candidates)
    assert any(value.rule_id == "contract-we-will" for value in reversible.candidates)
    assert {value.tier.value for value in reversible.candidates} == {"tier_1_surface"}
    assert {value.family.value for value in reversible.candidates} == {"contraction"}
