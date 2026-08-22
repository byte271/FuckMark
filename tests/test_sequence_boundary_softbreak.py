from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from fuckmark.corpus import ModelTokenizerIdentity, PaddingSide
from fuckmark.experiments import (
    build_representation_differential_audit,
    capture_representation_pair,
    verify_representation_differential_audit,
    verify_representation_pair,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.sequence_boundary_opportunity_audit import (
    FROZEN_CORPUS_ARTIFACT_HASH,
    NEGATIVE_CONTROL_TOKENIZER,
    PRIMARY_TOKENIZERS,
    audit_sequence_boundary_opportunity,
)
from fuckmark.tiny_dev_context_survival_plan_hf import (
    HISTORICAL_CONTEXT_REGISTRY_PROFILE,
    SEQUENCE_BOUNDARY_REGISTRY_PROFILE,
    TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION,
    TINY_DEV_SEQUENCE_BOUNDARY_PLAN_VERSION,
    _sequence_boundary_registry,
)
from fuckmark.transforms import (
    InvariantStatus,
    SENTENCE_BOUNDARY_SOFTBREAK_RULESET_VERSION,
    TransformRegistry,
    TransformTier,
    development_sentence_boundary_softbreak_rules,
)


def _registry() -> TransformRegistry:
    return TransformRegistry(development_sentence_boundary_softbreak_rules())


def _apply_all(text: str):
    registry = _registry()
    enumeration = registry.enumerate(text)
    return registry.apply(
        enumeration,
        tuple(candidate.candidate_id for candidate in enumeration.candidates),
        seed=271,
    )


def _identity(index: int) -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id=f"boundary-model-{index}",
        model_revision=f"{index + 1:040x}",
        tokenizer_id=f"boundary-tokenizer-{index}",
        tokenizer_revision=f"{index + 11:040x}",
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text(f"boundary-tokens-{index}"),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=60000 + index,
        pad_token_id=60000 + index,
        add_bos_token=False,
        add_eos_token=False,
    )


def _bindings():
    return (
        (_identity(0), lambda text: tuple(text.encode("utf-8"))),
        (_identity(1), lambda text: tuple(ord(character) for character in text)),
    )


def test_sentence_boundary_softbreak_is_exact_deterministic_and_replayable() -> None:
    source = "First sentence. Second sentence! Third sentence? Fourth sentence."
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == (". ", "! ", "? ")
    selected = tuple(candidate.candidate_id for candidate in enumeration.candidates)
    first = registry.apply(enumeration, selected, seed=271)
    second = registry.apply(registry.enumerate(source), selected, seed=271)
    assert first == second
    assert first.output_text == "First sentence.\nSecond sentence!\nThird sentence?\nFourth sentence."
    assert first.trace.invariant_report.status is InvariantStatus.PASS
    assert all(operation.before_text.endswith(" ") for operation in first.trace.operations)
    assert all(operation.after_text.endswith("\n") for operation in first.trace.operations)


def test_sentence_boundary_softbreak_conservatively_excludes_false_boundaries() -> None:
    source = "Dr. Smith met Prof. Jones at version 3. Next step. Another step? Final step! Done."
    enumeration = _registry().enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == (". ", "? ", "! ")
    result = _registry().apply(
        enumeration,
        tuple(candidate.candidate_id for candidate in enumeration.candidates),
    )
    assert result.output_text == (
        "Dr. Smith met Prof. Jones at version 3. Next step.\nAnother step?\nFinal step!\nDone."
    )


def test_sentence_boundary_softbreak_preserves_protected_content() -> None:
    source = (
        'Keep "Quoted sentence. Inside quote." and `code. Block`. '
        "Outside sentence. Next sentence."
    )
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert tuple(candidate.source_text for candidate in enumeration.candidates) == (". ", ". ")
    assert len(enumeration.rejections) >= 2
    result = registry.apply(
        enumeration,
        tuple(candidate.candidate_id for candidate in enumeration.candidates),
    )
    assert '"Quoted sentence. Inside quote."' in result.output_text
    assert "`code. Block`" in result.output_text
    assert result.output_text.endswith("Outside sentence.\nNext sentence.")
    assert result.trace.invariant_report.status is InvariantStatus.PASS


def test_sentence_boundary_softbreak_is_nfc_and_word_identity_preserving() -> None:
    source = "Café remains stable. Another claim cannot change."
    result = _apply_all(source)
    assert unicodedata.normalize("NFC", result.output_text) == result.output_text
    assert source.split() == result.output_text.split()
    assert result.trace.operations[0].after_text == ".\n"
    assert all(rule.tier is TransformTier.FORMAT for rule in _registry().rules)


def test_sentence_boundary_softbreak_integrates_with_representation_audit() -> None:
    sources = (
        ("boundary-source-0", "family-0", "First stable sentence. Another stable sentence."),
        ("boundary-source-1", "family-1", "Is the result stable? The result remains stable."),
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
    verify_representation_differential_audit(audit, pairs)


def test_sequence_boundary_registry_profile_is_additive_and_versioned() -> None:
    registry = _sequence_boundary_registry()
    rule_ids = {rule.rule_id for rule in registry.rules}
    assert "sentence-boundary-softbreak-period" in rule_ids
    assert "surface-space-after-period" in rule_ids
    assert HISTORICAL_CONTEXT_REGISTRY_PROFILE == "historical-context-v3"
    assert SEQUENCE_BOUNDARY_REGISTRY_PROFILE == "sequence-boundary-softbreak-v1"
    assert TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION == "tiny-dev-context-survival-plan-v3"
    assert TINY_DEV_SEQUENCE_BOUNDARY_PLAN_VERSION == "tiny-dev-sequence-boundary-softbreak-plan-v1"
    assert SENTENCE_BOUNDARY_SOFTBREAK_RULESET_VERSION == "development-sentence-boundary-softbreak-v1"


def test_sequence_boundary_contract_is_falsifiable_and_detector_blind() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-sequence-boundary-softbreak-v1.contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    opportunity_path = path.with_name("fuckmark-sequence-boundary-softbreak-v1.opportunity.json")
    opportunity = json.loads(opportunity_path.read_text(encoding="utf-8"))
    opportunity_payload = {key: value for key, value in opportunity.items() if key != "artifact_hash"}
    assert contract["algorithm_version"] == TINY_DEV_SEQUENCE_BOUNDARY_PLAN_VERSION
    assert contract["selection_detector_query_count"] == 0
    assert contract["selection_secret_query_count"] == 0
    assert contract["release_authorized"] is False
    assert contract["opportunity_audit"]["budget_2_reachable_count"] > 250
    assert contract["opportunity_audit"]["universal_primary_tokenizer_change_count"] == 1774
    assert contract["opportunity_audit"]["negative_control_change_count"] == 0
    assert sha256_json(opportunity_payload) == opportunity["artifact_hash"]
    assert contract["opportunity_audit"]["audit_artifact_hash"] == opportunity["artifact_hash"]
    assert contract["hypothesis"]
    assert contract["mechanism"]
    assert contract["experiment"]
    assert len(contract["kill_criteria"]) >= 4


def test_context_plan_registry_override_rejects_wrong_type() -> None:
    from fuckmark.experiments.context_survival_plan import build_context_survival_plan

    with pytest.raises(TypeError, match="registry"):
        build_context_survival_plan(
            object(),
            object(),
            ngram_len=5,
            context_history_size=1024,
            registry=object(),
        )


def test_sequence_boundary_opportunity_audit_replays_without_detector_inputs() -> None:
    class _CharacterTokenizer:
        def encode(self, text, add_special_tokens=False):
            return tuple(ord(character) for character in text)

    class _WhitespaceTokenizer:
        def encode(self, text, add_special_tokens=False):
            return tuple(len(part) for part in text.split())

    sources = tuple(
        (f"source-{index}", "Stable opening sentence. Next stable sentence.")
        for index in range(500)
    )
    primary = {identity: _CharacterTokenizer() for identity in PRIMARY_TOKENIZERS}
    kwargs = {
        "source_corpus_artifact_hash": FROZEN_CORPUS_ARTIFACT_HASH,
        "sources": sources,
        "primary_tokenizers": primary,
        "negative_control": (NEGATIVE_CONTROL_TOKENIZER, _WhitespaceTokenizer()),
    }
    first = audit_sequence_boundary_opportunity(**kwargs)
    second = audit_sequence_boundary_opportunity(**kwargs)
    assert first == second
    assert first["source_count"] == 500
    assert first["protected_span_safe_candidate_count"] == 500
    assert first["universal_primary_tokenizer_change_count"] == 500
    assert first["negative_control"]["individual_change_count"] == 0
    assert first["detector_query_count"] == 0
    assert first["secret_query_count"] == 0
