from dataclasses import replace

import pytest

from fuckmark.transforms import (
    KEY_BLIND_HIGH_COVERAGE_BUDGETS,
    KEY_BLIND_HIGH_COVERAGE_PROFILE,
    KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    KEY_BLIND_HIGH_COVERAGE_SEED_BASE,
    development_transform_registry,
    key_blind_high_coverage_transform_registry,
    release_transform_registry,
    validate_effectiveness_profile_registry,
)


def test_key_blind_high_coverage_profile_is_frozen_and_hash_bound() -> None:
    profile = KEY_BLIND_HIGH_COVERAGE_PROFILE
    registry = key_blind_high_coverage_transform_registry()
    assert profile.profile_id == KEY_BLIND_HIGH_COVERAGE_PROFILE_ID
    assert profile.budgets == KEY_BLIND_HIGH_COVERAGE_BUDGETS == (16,)
    assert profile.schedule_policy_id == "COVERAGE_GREEDY_KEY_BLIND"
    assert profile.schedule_seed_base == KEY_BLIND_HIGH_COVERAGE_SEED_BASE == 1_120_000
    assert profile.replicate_count == 1
    assert profile.ngram_len == 5
    assert profile.ruleset_hash == registry.ruleset_hash
    validate_effectiveness_profile_registry(profile, registry)
    with pytest.raises(ValueError, match="profile_hash"):
        replace(profile, profile_id="tampered-profile")


def test_effectiveness_registry_is_isolated_from_development_and_release() -> None:
    effectiveness_ids = {
        rule.rule_id for rule in key_blind_high_coverage_transform_registry().rules
    }
    development_ids = {rule.rule_id for rule in development_transform_registry().rules}
    release_ids = {rule.rule_id for rule in release_transform_registry().rules}
    added_ids = {
        "contract-you-are",
        "contract-we-are",
        "contract-they-are",
        "contract-must-not",
    }
    assert added_ids <= effectiveness_ids
    assert added_ids.isdisjoint(development_ids)
    assert added_ids.isdisjoint(release_ids)
    assert release_ids == {
        "contract-cannot",
        "contract-did-not",
        "contract-do-not",
        "contract-does-not",
        "contract-should-not",
        "contract-will-not",
    }


def test_effectiveness_registry_applies_copula_contraction_without_losing_negation() -> None:
    registry = key_blind_high_coverage_transform_registry()
    enumeration = registry.enumerate("You are not ready.")
    candidate = next(
        value for value in enumeration.candidates if value.rule_id == "contract-you-are"
    )
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == "You're not ready."
    assert result.trace.invariant_report.status.value == "pass"
