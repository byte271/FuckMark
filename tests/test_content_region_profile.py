from __future__ import annotations

from types import SimpleNamespace

import pytest

from fuckmark.corpus import CorpusDomain, CorpusSplit, WatermarkLabel
from fuckmark.experiments.coverage_holes import classify_word
from fuckmark.experiments.effectiveness_plan import build_key_blind_high_coverage_plan
from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    CONTENT_REGION_COVERAGE_PROFILE_ID,
    CONTENT_REGION_COVERAGE_SEED_BASE,
    KEY_BLIND_HIGH_COVERAGE_PROFILE,
    content_region_coverage_profile,
    content_region_coverage_transform_registry,
    resolve_effectiveness_profile,
)
from fuckmark.transforms.rules import GeneralWordSpacingRule


class FakeTokenizer:
    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool = False,
    ) -> dict[str, object]:
        assert add_special_tokens is False
        ids = [index + 1 for index in range(len(text))]
        value: dict[str, object] = {"input_ids": ids}
        if return_offsets_mapping:
            value["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return value


def _sample(sample_id: str, label: WatermarkLabel, text: str, identity_hash: str):
    token_ids = tuple(index + 1 for index in range(len(text)))
    return SimpleNamespace(
        sample_id=sample_id,
        split=CorpusSplit.ATTACK_DEVELOPMENT,
        label=label,
        prompt_family_id=f"prompt-{sample_id}",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        text=text,
        text_sha256=sha256_text(text),
        text_only_tokens=SimpleNamespace(token_ids=token_ids),
        model=SimpleNamespace(identity_hash=identity_hash, eos_token_id=50256),
    )


def _corpus():
    identity_hash = sha256_text("fake-tokenizer")
    text = (
        "Careful researchers documented measurement uncertainty thoroughly. "
        "The auditor verified every reported number 42 before publishing results."
    )
    samples = (
        _sample("negative-1", WatermarkLabel.UNWATERMARKED, text, identity_hash),
        _sample("positive-1", WatermarkLabel.WATERMARKED, text, identity_hash),
    )
    return SimpleNamespace(
        artifact_hash=sha256_text("fake-corpus"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(samples=samples, manifest_hash=sha256_text("fake-manifest")),
    )


def test_general_word_spacing_rule_contract() -> None:
    rule = GeneralWordSpacingRule.create("surface-space-after-any-word")
    text = "Alpha beta gamma delta, epsilon zeta."
    matches = [text[m.start() : m.end()] for m in rule.pattern().finditer(text)]
    assert "Alpha" in matches
    assert "beta" in matches
    assert "gamma" in matches
    assert "delta" not in matches
    assert rule.replacement_for("beta") == "beta "
    assert rule.replacement_for("Beta") == "Beta "
    doubled = "beta  gamma"
    assert rule.pattern().search(doubled) is None
    with pytest.raises(ValueError):
        GeneralWordSpacingRule(
            rule_id="bad",
            version="general-word-space-after-v1",
            family=rule.family,
            tier=rule.tier,
            source="word",
            replacement="wrong ",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=rule.rule_hash,
        )


def test_general_rule_enumerates_content_words_with_exact_replacement() -> None:
    registry = content_region_coverage_transform_registry()
    text = "Measurement uncertainty remained stubbornly high throughout replication attempts."
    enumeration = registry.enumerate(text)
    general = [
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "surface-space-after-any-word"
    ]
    assert any(candidate.source_text == "Measurement" for candidate in general)
    assert all(candidate.replacement_text == candidate.source_text + " " for candidate in general)
    for candidate in general:
        transformed = text[: candidate.start] + candidate.replacement_text + text[candidate.end :]
        assert transformed.count(candidate.source_text + "  ") >= 1
        assert transformed.isascii()


def test_content_region_profile_resolves_and_builds_detector_blind_plans() -> None:
    profile = resolve_effectiveness_profile(CONTENT_REGION_COVERAGE_PROFILE_ID, (16,))
    assert profile.profile_id == CONTENT_REGION_COVERAGE_PROFILE_ID
    assert profile.schedule_seed_base == CONTENT_REGION_COVERAGE_SEED_BASE
    assert content_region_coverage_profile((16,)) == profile
    corpus = _corpus()
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=profile,
        source_code_commit="a" * 40,
    )
    assert plan["ruleset_hash"] == profile.ruleset_hash
    assert all(row["hard_invariant_status"] == "pass" for row in plan["variants"])
    assert all(row["detector_access_observed"] is False for row in plan["variants"])


def test_content_region_registry_protects_numbers_and_keeps_b16_frozen() -> None:
    registry = content_region_coverage_transform_registry()
    text = "The reported value 3.14159 stayed fixed across runs."
    enumeration = registry.enumerate(text)
    for candidate in enumeration.candidates:
        assert "3.14159" not in candidate.source_text
    assert KEY_BLIND_HIGH_COVERAGE_PROFILE.profile_hash == (
        "6ad142262bfb11a714565d7bd43daa859657fe817bdafa9c8dcf0f4884c07512"
    )


def test_classify_word_categories() -> None:
    assert classify_word("the") == "function_word"
    assert classify_word("measurement") == "lowercase_content"
    assert classify_word("Measurement") == "capitalized_content"
    assert classify_word("42") == "numeric"
    assert classify_word(",") == "punctuation_or_empty"


def test_resolve_rejects_invalid_content_region_requests() -> None:
    with pytest.raises(ValueError):
        resolve_effectiveness_profile(CONTENT_REGION_COVERAGE_PROFILE_ID)
    with pytest.raises(ValueError):
        content_region_coverage_profile((48, 16))
