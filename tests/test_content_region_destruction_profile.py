import pytest

from fuckmark.transforms import (
    content_region_coverage_transform_registry,
    content_region_destruction_profile,
    content_region_destruction_transform_registry,
    resolve_effectiveness_profile,
)
from fuckmark.transforms.effectiveness_profile import (
    CONTENT_REGION_COVERAGE_PROFILE_ID,
    CONTENT_REGION_DESTRUCTION_PROFILE_ID,
)


def test_cycle3_frozen_ruleset_hash_is_unchanged():
    registry = content_region_coverage_transform_registry()
    assert registry.ruleset_hash == "82011e6dd7048a97e07918d32f7f8670e7723c66eb1b5b0ac859adb4e9cde8ca"


def test_destruction_registry_is_strict_superset_of_cycle3_rules():
    cycle3 = {rule.rule_id for rule in content_region_coverage_transform_registry().rules}
    destruction = content_region_destruction_transform_registry()
    ids = {rule.rule_id for rule in destruction.rules}
    assert cycle3 <= ids
    assert "surface-space-before-sentence" in ids
    assert len(ids) > len(cycle3)


def test_destruction_profile_resolves_and_binds_registry():
    profile = content_region_destruction_profile((16,))
    assert profile.profile_id == CONTENT_REGION_DESTRUCTION_PROFILE_ID
    assert profile.ruleset_hash == content_region_destruction_transform_registry().ruleset_hash
    resolved = resolve_effectiveness_profile(CONTENT_REGION_DESTRUCTION_PROFILE_ID, (16,))
    assert resolved.profile_hash == profile.profile_hash


def test_destruction_profile_rejects_missing_budgets():
    with pytest.raises(ValueError):
        resolve_effectiveness_profile(CONTENT_REGION_DESTRUCTION_PROFILE_ID, ())


def test_destruction_pool_dominates_cycle3_pool_on_prose():
    text = (
        "The measurement problem matters because careful work reveals whether an idea "
        "survives. Many people think one result is enough. However evidence says otherwise, "
        "and replication remains important."
    )
    cycle3 = len(content_region_coverage_transform_registry().enumerate(text).candidates)
    destruction = len(content_region_destruction_transform_registry().enumerate(text).candidates)
    assert destruction >= cycle3
