from __future__ import annotations

from types import SimpleNamespace

import pytest

from fuckmark.corpus import CorpusDomain, CorpusSplit, WatermarkLabel
from fuckmark.experiments.effectiveness_plan import build_key_blind_high_coverage_plan
from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
    KEY_BLIND_COVERAGE_COMPLETION_SEED_BASE,
    KEY_BLIND_HIGH_COVERAGE_PROFILE,
    key_blind_coverage_completion_profile,
    key_blind_coverage_completion_transform_registry,
    key_blind_high_coverage_transform_registry,
    resolve_effectiveness_profile,
)
from fuckmark.transforms.surface_rules import (
    coverage_completion_extension_words,
    coverage_completion_surface_rules,
    development_surface_rules,
)


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
    text = "He said they were not sure, because more work was needed before one can decide."
    samples = (
        _sample("negative-1", WatermarkLabel.UNWATERMARKED, text, identity_hash),
        _sample("positive-1", WatermarkLabel.WATERMARKED, text, identity_hash),
    )
    return SimpleNamespace(
        artifact_hash=sha256_text("fake-corpus"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(samples=samples, manifest_hash=sha256_text("fake-manifest")),
    )


def test_extension_words_obey_the_frozen_surface_contract() -> None:
    words = coverage_completion_extension_words()
    assert len(words) == 65
    assert len(set(words)) == len(words)
    base_words = {rule.source for rule in development_surface_rules() if rule.source.isalpha()}
    assert not (set(words) & base_words)
    assert all(word.isalpha() and word == word.lower() and len(word) >= 2 for word in words)
    rules = coverage_completion_surface_rules()
    base = development_surface_rules()
    assert len(rules) == len(base) + 65
    assert set(rule.rule_id for rule in base) < set(rule.rule_id for rule in rules)


def test_extension_rules_do_not_split_words_mid_token() -> None:
    registry = key_blind_coverage_completion_transform_registry()
    text = "The weather, whether he measured then, was often more random than before."
    enumeration = registry.enumerate(text)
    replaced_words = set()
    for candidate in enumeration.candidates:
        replaced_words.add(text[candidate.start : candidate.end].strip())
    assert "he" in replaced_words or "then" in replaced_words
    joined = "".join(
        candidate.replacement_text
        for candidate in enumeration.candidates[:1]
    )
    assert "random" not in joined or joined == "random"
    transformed_spans = [text[c.start : c.end] for c in enumeration.candidates]
    assert all(span.strip().isalpha() or span in (". ", ", ", "; ", ": ", "? ", "! ") for span in transformed_spans)


def test_coverage_completion_registry_extends_and_rebinds_ruleset() -> None:
    base_registry = key_blind_high_coverage_transform_registry()
    registry = key_blind_coverage_completion_transform_registry()
    assert registry.ruleset_hash != base_registry.ruleset_hash
    base_ids = {rule.rule_id for rule in base_registry.rules}
    extended_ids = {rule.rule_id for rule in registry.rules}
    assert base_ids < extended_ids


def test_frozen_b16_profile_hash_is_unchanged() -> None:
    assert (
        KEY_BLIND_HIGH_COVERAGE_PROFILE.profile_hash
        == "6ad142262bfb11a714565d7bd43daa859657fe817bdafa9c8dcf0f4884c07512"
    )


def test_coverage_completion_profile_resolves_and_builds_plans() -> None:
    profile = resolve_effectiveness_profile(KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID, (16,))
    assert profile.profile_id == KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID
    assert profile.schedule_seed_base == KEY_BLIND_COVERAGE_COMPLETION_SEED_BASE
    assert key_blind_coverage_completion_profile((16,)) == profile
    corpus = _corpus()
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=profile,
        source_code_commit="a" * 40,
    )
    assert plan["ruleset_hash"] == profile.ruleset_hash
    assert len(plan["variants"]) == 2
    assert all(row["hard_invariant_status"] == "pass" for row in plan["variants"])
    assert all(row["detector_access_observed"] is False for row in plan["variants"])


def test_resolve_rejects_invalid_coverage_completion_requests() -> None:
    with pytest.raises(ValueError):
        resolve_effectiveness_profile(KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID)
    with pytest.raises(ValueError):
        key_blind_coverage_completion_profile((48, 16))
