from dataclasses import replace

import pytest

from fuckmark.coverage import Interval
from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    LiteralTransformRule,
    ScheduleGeometryMode,
    SchedulePolicy,
    TokenizerGeometryError,
    TransformFamily,
    TransformRegistry,
    TransformTier,
    build_candidate_tokenizer_geometry,
)


_TOKENIZER_HASH = sha256_text("fixture-public-tokenizer")


def _registry() -> TransformRegistry:
    return TransformRegistry(
        (
            LiteralTransformRule.create(
                rule_id="fixture-contract-do-not",
                version="v1",
                family=TransformFamily.CONTRACTION,
                tier=TransformTier.SURFACE,
                source="do not",
                replacement="don't",
            ),
            LiteralTransformRule.create(
                rule_id="fixture-contract-will-not",
                version="v1",
                family=TransformFamily.CONTRACTION,
                tier=TransformTier.SURFACE,
                source="will not",
                replacement="won't",
            ),
        )
    )


def _geometry():
    text = "You do not stop and you will not wait."
    enumeration = _registry().enumerate(text)
    token_ids = (10, 11, 12, 13, 14, 15, 16, 17, 18, 19)
    offsets = (
        (0, 3),
        (3, 6),
        (6, 10),
        (10, 15),
        (15, 19),
        (19, 23),
        (23, 28),
        (28, 32),
        (32, 37),
        (37, 38),
    )
    return text, enumeration, build_candidate_tokenizer_geometry(
        text,
        enumeration,
        token_ids,
        offsets,
        tokenizer_identity_hash=_TOKENIZER_HASH,
        ngram_len=5,
    )


def test_candidate_tokenizer_geometry_maps_character_spans_to_ngram_coverage() -> None:
    _, enumeration, geometry = _geometry()
    assert geometry.input_hash == enumeration.input_hash
    assert geometry.enumeration_hash == enumeration.enumeration_hash
    assert geometry.tokenizer_identity_hash == _TOKENIZER_HASH
    assert geometry.token_count == 10
    assert geometry.ngram_len == 5
    mapping = geometry.coverage_mapping()
    assert set(mapping) == {candidate.candidate_id for candidate in enumeration.candidates}
    by_rule = {candidate.rule_id: candidate for candidate in enumeration.candidates}
    assert mapping[by_rule["fixture-contract-do-not"].candidate_id] == (Interval(0, 3),)
    assert mapping[by_rule["fixture-contract-will-not"].candidate_id] == (Interval(2, 6),)


def test_public_tokenizer_geometry_feeds_key_blind_coverage_scheduler() -> None:
    _, enumeration, geometry = _geometry()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=geometry.coverage_mapping(),
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        budget=1,
        seed=123,
    )
    by_rule = {candidate.rule_id: candidate for candidate in enumeration.candidates}
    assert result.selected_candidate_ids == (by_rule["fixture-contract-will-not"].candidate_id,)
    assert result.covered_interval_size == 4


def test_candidate_tokenizer_geometry_rejects_special_token_zero_width_offsets() -> None:
    text = "You do not stop."
    enumeration = _registry().enumerate(text)
    with pytest.raises(TokenizerGeometryError, match="zero-width"):
        build_candidate_tokenizer_geometry(
            text,
            enumeration,
            (10, 11, 12, 13),
            ((0, 0), (0, 3), (3, 10), (10, 15)),
            tokenizer_identity_hash=_TOKENIZER_HASH,
            ngram_len=5,
        )


def test_candidate_tokenizer_geometry_rejects_enumeration_text_mismatch() -> None:
    _, enumeration, _ = _geometry()
    with pytest.raises(TokenizerGeometryError, match="does not bind"):
        build_candidate_tokenizer_geometry(
            "different text",
            enumeration,
            (1,),
            ((0, 1),),
            tokenizer_identity_hash=_TOKENIZER_HASH,
            ngram_len=5,
        )


def test_candidate_tokenizer_geometry_hash_is_tamper_evident() -> None:
    _, _, geometry = _geometry()
    with pytest.raises(ValueError, match="geometry_hash"):
        replace(geometry, geometry_hash="0" * 64)
