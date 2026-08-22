from dataclasses import replace
import json
from pathlib import Path

import pytest

from fuckmark.corpus import ModelTokenizerIdentity, PaddingSide
from fuckmark.experiments import (
    REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION,
    REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS,
    RepresentationDifferentialInputError,
    build_representation_differential_audit,
    capture_representation_pair,
    verify_representation_differential_audit,
    verify_representation_pair,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import TransformFamily, TransformRegistry, TransformTier, default_transform_registry
from fuckmark.transforms.rules import LiteralTransformRule


def _identity(index: int) -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id=f"model-{index}",
        model_revision=f"{index + 1:040x}",
        tokenizer_id=f"tokenizer-{index}",
        tokenizer_revision=f"{index + 11:040x}",
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text(f"tokens-{index}"),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=50256 + index,
        pad_token_id=50256 + index,
        add_bos_token=False,
        add_eos_token=False,
    )


def _character_tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def _word_tokenizer(text: str) -> tuple[int, ...]:
    return tuple(sum(ord(character) for character in word) for word in text.split())


def _bindings():
    return (
        (_identity(0), _character_tokenizer),
        (_identity(1), _word_tokenizer),
    )


def _result(text: str):
    registry = default_transform_registry()
    enumeration = registry.enumerate(text)
    return registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))


def _pair(index: int, text: str):
    return capture_representation_pair(
        f"source-{index}",
        f"prompt-family-{index}",
        text,
        _result(text),
        _bindings(),
    )


def test_representation_pair_captures_two_pinned_tokenizers_and_replays() -> None:
    source = "You do not need to wait."
    result = _result(source)
    pair = capture_representation_pair("source-0", "prompt-family-0", source, result, tuple(reversed(_bindings())))
    assert pair.algorithm_version == REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION
    assert pair.changed_tokenizer_count == 2
    assert pair.universal_tokenization_change
    assert pair.metric_disagreement
    assert pair.detector_query_count == 0
    assert pair.secret_query_count == 0
    assert pair.model_tokenizer_identities == tuple(sorted(pair.model_tokenizer_identities, key=lambda value: value.identity_hash))
    verify_representation_pair(pair, source, result, _bindings())


def test_representation_pair_rejects_duplicate_tokenizer_identity() -> None:
    source = "You do not need to wait."
    identity = _identity(0)
    with pytest.raises(RepresentationDifferentialInputError, match="unique"):
        capture_representation_pair(
            "source-0",
            "prompt-family-0",
            source,
            _result(source),
            ((identity, _character_tokenizer), (identity, _word_tokenizer)),
        )


def test_representation_pair_rejects_single_tokenizer() -> None:
    source = "You do not need to wait."
    with pytest.raises(RepresentationDifferentialInputError, match="at least two"):
        capture_representation_pair(
            "source-0",
            "prompt-family-0",
            source,
            _result(source),
            ((_identity(0), _character_tokenizer),),
        )


def test_representation_pair_rejects_non_nfc_text() -> None:
    source = "Cafe\u0301 does not close."
    with pytest.raises(RepresentationDifferentialInputError, match="Unicode NFC"):
        capture_representation_pair("source-0", "prompt-family-0", source, _result(source), _bindings())


def test_representation_pair_rejects_invisible_unicode_injection() -> None:
    rule = LiteralTransformRule.create(
        "inject-zero-width",
        "v1",
        TransformFamily.ORTHOGRAPHY,
        TransformTier.EXPERIMENTAL,
        "alpha",
        "alpha\u200b",
    )
    registry = TransformRegistry((rule,))
    source = "alpha stays here."
    enumeration = registry.enumerate(source)
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    with pytest.raises(RepresentationDifferentialInputError, match="representation-sensitive"):
        capture_representation_pair("source-0", "prompt-family-0", source, result, _bindings())


def test_representation_pair_replay_rejects_tokenizer_drift() -> None:
    source = "You do not need to wait."
    result = _result(source)
    pair = capture_representation_pair("source-0", "prompt-family-0", source, result, _bindings())

    def changed_tokenizer(text: str) -> tuple[int, ...]:
        return (*_word_tokenizer(text), 999)

    drifted = ((_identity(0), _character_tokenizer), (_identity(1), changed_tokenizer))
    with pytest.raises(RepresentationDifferentialInputError, match="does not replay exactly"):
        verify_representation_pair(pair, source, result, drifted)


def test_representation_pair_rejects_wrong_source_binding() -> None:
    source = "You do not need to wait."
    with pytest.raises(RepresentationDifferentialInputError, match="does not bind"):
        capture_representation_pair(
            "source-0",
            "prompt-family-0",
            "You will not need to wait.",
            _result(source),
            _bindings(),
        )


def test_representation_row_rejects_self_hash_tampering() -> None:
    pair = _pair(0, "You do not need to wait.")
    with pytest.raises(ValueError, match="row_hash"):
        replace(pair.rows[0], row_hash="0" * 64)


def test_representation_audit_counts_independent_sources_and_replays() -> None:
    first = _pair(0, "You do not need to wait.")
    second = _pair(1, "They will not leave now.")
    audit = build_representation_differential_audit((second, first))
    assert audit.independent_source_count == 2
    assert audit.representation_cell_count == 4
    assert audit.changed_cell_count == sum(value.changed_tokenizer_count for value in audit.pairs)
    assert audit.claim_status == REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS
    assert audit.detector_query_count == 0
    assert audit.secret_query_count == 0
    verify_representation_differential_audit(audit, (first, second))


def test_representation_audit_rejects_dependent_variants_as_independent_sources() -> None:
    source = "Do not wait and do not retry."
    registry = default_transform_registry()
    enumeration = registry.enumerate(source)
    first_result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    second_result = registry.apply(enumeration, (enumeration.candidates[1].candidate_id,))
    first = capture_representation_pair("source-0", "prompt-family-0", source, first_result, _bindings())
    second = capture_representation_pair("source-0", "prompt-family-0", source, second_result, _bindings())
    with pytest.raises(ValueError, match="one transformed pair"):
        build_representation_differential_audit((first, second))


def test_representation_audit_rejects_duplicate_source_text_with_valid_pair_hash() -> None:
    source = "You do not need to wait."
    first = _pair(0, source)
    second = capture_representation_pair("source-1", "prompt-family-1", source, _result(source), _bindings())
    with pytest.raises(ValueError, match="duplicate source text"):
        build_representation_differential_audit((first, second))


def test_representation_audit_rejects_mixed_tokenizer_sets() -> None:
    first = _pair(0, "You do not need to wait.")
    source = "They will not leave now."
    other_bindings = ((_identity(0), _character_tokenizer), (_identity(2), _word_tokenizer))
    second = capture_representation_pair("source-1", "prompt-family-1", source, _result(source), other_bindings)
    with pytest.raises(ValueError, match="same tokenizer"):
        build_representation_differential_audit((first, second))


def test_representation_audit_requires_two_independent_sources() -> None:
    with pytest.raises(RepresentationDifferentialInputError, match="at least two"):
        build_representation_differential_audit((_pair(0, "You do not need to wait."),))


def test_representation_contract_matches_public_constants() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-representation-differential-audit-v1.contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    assert contract["algorithm_version"] == REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION
    assert contract["minimum_tokenizer_families"] == 2
    assert contract["selection_detector_query_count"] == 0
    assert contract["selection_secret_query_count"] == 0
    assert contract["claim_status"] == REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS
