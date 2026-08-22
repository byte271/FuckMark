from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from fuckmark.corpus import ModelTokenizerIdentity, PaddingSide
from fuckmark.experiments import (
    build_representation_differential_audit,
    capture_representation_pair,
    verify_representation_differential_audit,
    verify_representation_pair,
)
from fuckmark.hashing import sha256_text
from fuckmark.tiny_dev_context_survival_plan_hf import (
    HISTORICAL_CONTEXT_REGISTRY_PROFILE,
    TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION,
    TINY_DEV_VISIBLE_TYPOGRAPHY_PLAN_VERSION,
    VISIBLE_TYPOGRAPHY_REGISTRY_PROFILE,
    _visible_typography_registry,
)
from fuckmark.transforms import (
    HYPHEN,
    RIGHT_SINGLE_QUOTATION_MARK,
    InvariantStatus,
    TransformRegistry,
    development_visible_typography_rules,
)


def _registry() -> TransformRegistry:
    return TransformRegistry(development_visible_typography_rules())


def _identity(index: int) -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id=f"visible-model-{index}",
        model_revision=f"{index + 1:040x}",
        tokenizer_id=f"visible-tokenizer-{index}",
        tokenizer_revision=f"{index + 11:040x}",
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text(f"visible-tokens-{index}"),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=60000 + index,
        pad_token_id=60000 + index,
        add_bos_token=False,
        add_eos_token=False,
    )


def _byte_tokenizer(text: str) -> tuple[int, ...]:
    return tuple(text.encode("utf-8"))


def _codepoint_tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def _bindings():
    return (
        (_identity(0), _byte_tokenizer),
        (_identity(1), _codepoint_tokenizer),
    )


def _apply_all(text: str):
    registry = _registry()
    enumeration = registry.enumerate(text)
    return registry.apply(
        enumeration,
        tuple(candidate.candidate_id for candidate in enumeration.candidates),
        seed=271,
    )


def test_visible_typography_is_exact_deterministic_and_replayable() -> None:
    source = "A state-of-the-art system doesn't drift."
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == ("-", "-", "-", "'")
    selected = tuple(candidate.candidate_id for candidate in enumeration.candidates)
    first = registry.apply(enumeration, selected, seed=271)
    second = registry.apply(registry.enumerate(source), selected, seed=271)
    assert first == second
    assert first.output_text == "A state‐of‐the‐art system doesn’t drift."
    assert first.trace.invariant_report.status is InvariantStatus.PASS
    assert all(operation.before_text in ("-", "'") for operation in first.trace.operations)
    assert all(operation.after_text in (HYPHEN, RIGHT_SINGLE_QUOTATION_MARK) for operation in first.trace.operations)


def test_visible_typography_replacements_are_visible_nfc_punctuation() -> None:
    sensitive = {"Cf", "Cs", "Co", "Mn", "Me"}
    for replacement in (HYPHEN, RIGHT_SINGLE_QUOTATION_MARK):
        assert unicodedata.normalize("NFC", replacement) == replacement
        assert unicodedata.category(replacement) in {"Pd", "Pf"}
        assert unicodedata.category(replacement) not in sensitive
        assert unicodedata.name(replacement) in {"HYPHEN", "RIGHT SINGLE QUOTATION MARK"}


def test_visible_typography_preserves_protected_content() -> None:
    source = (
        "Keep https://state-of-art.example, state-of-art@example.com, /tmp/state-of-art, "
        "--state-of-art, and 'state-of-art'. Outside can't stay state-of-art."
    )
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == ("'", "-", "-")
    assert len(enumeration.rejections) >= 8
    result = registry.apply(
        enumeration,
        tuple(candidate.candidate_id for candidate in enumeration.candidates),
    )
    protected_prefix, outside = source.split(" Outside ")
    transformed_prefix, transformed_outside = result.output_text.split(" Outside ")
    assert transformed_prefix == protected_prefix
    assert transformed_outside == "can’t stay state‐of‐art."
    assert result.trace.invariant_report.status is InvariantStatus.PASS


def test_visible_typography_rejects_non_internal_or_numeric_punctuation() -> None:
    source = "Use 2026-08-21, A - B, '-' and --dry-run; don't alter x-ray."
    enumeration = _registry().enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == ("'", "-")
    assert tuple(source[candidate.start - 1:candidate.end + 1] for candidate in enumeration.candidates) == (
        "n't",
        "x-r",
    )


def test_visible_typography_integrates_with_representation_differential_audit() -> None:
    sources = (
        ("visible-source-0", "family-0", "A state-of-the-art method remains stable."),
        ("visible-source-1", "family-1", "The system doesn't change its claim."),
    )
    pairs = tuple(
        capture_representation_pair(source_id, family_id, source, _apply_all(source), _bindings())
        for source_id, family_id, source in sources
    )
    assert all(pair.universal_tokenization_change for pair in pairs)
    assert all(pair.detector_query_count == 0 and pair.secret_query_count == 0 for pair in pairs)
    for pair, (_, _, source) in zip(pairs, sources):
        verify_representation_pair(pair, source, _apply_all(source), _bindings())
    audit = build_representation_differential_audit(tuple(reversed(pairs)))
    assert audit.independent_source_count == 2
    assert audit.changed_cell_count == 4
    assert audit.universal_change_source_count == 2
    assert audit.detector_query_count == 0
    assert audit.secret_query_count == 0
    verify_representation_differential_audit(audit, pairs)


def test_visible_typography_registry_profile_is_additive_and_versioned() -> None:
    registry = _visible_typography_registry()
    rule_ids = {rule.rule_id for rule in registry.rules}
    assert "visible-typography-internal-apostrophe" in rule_ids
    assert "visible-typography-internal-hyphen" in rule_ids
    assert HISTORICAL_CONTEXT_REGISTRY_PROFILE == "historical-context-v3"
    assert VISIBLE_TYPOGRAPHY_REGISTRY_PROFILE == "visible-typography-v1"
    assert TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION == "tiny-dev-context-survival-plan-v3"
    assert TINY_DEV_VISIBLE_TYPOGRAPHY_PLAN_VERSION == "tiny-dev-visible-typography-plan-v1"


def test_visible_typography_contract_is_falsifiable_and_detector_blind() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-visible-typography-v1.contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    assert contract["algorithm_version"] == TINY_DEV_VISIBLE_TYPOGRAPHY_PLAN_VERSION
    assert contract["selection_detector_query_count"] == 0
    assert contract["selection_secret_query_count"] == 0
    assert contract["release_authorized"] is False
    assert contract["hypothesis"]
    assert contract["mechanism"]
    assert contract["experiment"]
    assert len(contract["kill_criteria"]) >= 3
