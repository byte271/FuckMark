from __future__ import annotations

import unicodedata

from fuckmark.transforms import (
    CandidateRejectionReason,
    quote_safe_zrd_transform_registry,
    zrd_destruction_transform_registry,
)
from fuckmark.transforms.quote_policy import QUOTE_SAFE_SURFACE_POLICY_ID
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import SurfaceSpacingRule


def _general_candidates(enumeration):
    return tuple(
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "surface-space-after-any-word"
    )


def test_blanket_policy_still_blocks_every_candidate_inside_a_quote() -> None:
    enumeration = zrd_destruction_transform_registry().enumerate(
        '"Being a bike enthusiast is rewarding."'
    )
    assert not enumeration.candidates
    assert enumeration.rejections
    assert {
        rejection.reason for rejection in enumeration.rejections
    } == {CandidateRejectionReason.PROTECTED_OVERLAP}


def test_quote_safe_policy_admits_only_surface_spacing_inside_closed_quote() -> None:
    registry = quote_safe_zrd_transform_registry()
    enumeration = registry.enumerate(
        '"For example, do not change the quoted words."'
    )
    assert _general_candidates(enumeration)
    blocked = tuple(
        rejection
        for rejection in enumeration.rejections
        if rejection.reason is CandidateRejectionReason.QUOTE_POLICY_BLOCKED
    )
    assert any(rejection.rule_id == "contract-do-not" for rejection in blocked)
    assert any(
        rejection.rule_id == "lexical-for-example-for-instance"
        for rejection in blocked
    )


def test_quote_safe_policy_rejects_unrecognized_surface_rule_identity_during_enumeration() -> None:
    registry = TransformRegistry(
        (
            SurfaceSpacingRule.create(
                rule_id="custom-spacing",
                version="v1",
                source="hello",
                replacement="hello ",
            ),
        ),
        quote_policy_id=QUOTE_SAFE_SURFACE_POLICY_ID,
    )
    enumeration = registry.enumerate('"hello world"')
    assert not enumeration.candidates
    assert any(
        rejection.rule_id == "custom-spacing"
        and rejection.reason is CandidateRejectionReason.QUOTE_POLICY_BLOCKED
        for rejection in enumeration.rejections
    )


def test_quote_safe_policy_admits_surface_spacing_in_truncated_quote() -> None:
    registry = quote_safe_zrd_transform_registry()
    enumeration = registry.enumerate('He said, "This quote ends at the sample boundary')
    candidates = _general_candidates(enumeration)
    candidate = next(candidate for candidate in candidates if candidate.source_text == "This")
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text.startswith('He said, "')
    assert result.trace.selection_policy_id.endswith(
        ":quote-container-surface-spacing-v1"
    )


def test_quote_safe_surface_edit_preserves_words_numbers_and_attribution() -> None:
    registry = quote_safe_zrd_transform_registry(("Lacey",))
    source = '"Lacey said the value 12 is exact and do not alter it."'
    enumeration = registry.enumerate(source)
    selected = tuple(candidate.candidate_id for candidate in _general_candidates(enumeration))
    result = registry.apply(enumeration, selected)
    assert "Lacey" in result.output_text
    assert "12" in result.output_text
    assert "do not" in result.output_text.replace("  ", " ")
    assert result.output_text.replace("  ", " ") == source


def test_quote_safe_surface_output_is_nfkc_and_cf_durable() -> None:
    registry = quote_safe_zrd_transform_registry()
    source = '"This is ordinary quoted text."'
    enumeration = registry.enumerate(source)
    candidate = _general_candidates(enumeration)[0]
    output = registry.apply(enumeration, (candidate.candidate_id,)).output_text
    assert unicodedata.normalize("NFKC", output) == output
    assert all(not unicodedata.category(character).startswith("Cf") for character in output)


def test_quote_safe_policy_does_not_admit_surface_edit_inside_code() -> None:
    registry = quote_safe_zrd_transform_registry()
    enumeration = registry.enumerate('"Run `the exact command` now."')
    assert all(
        not (candidate.start < 24 and candidate.end > 5)
        for candidate in enumeration.candidates
        if "command" in candidate.source_text
    )
    assert any(
        rejection.reason is CandidateRejectionReason.PROTECTED_OVERLAP
        and rejection.source_text == "the"
        for rejection in enumeration.rejections
    )
