import json
import unicodedata
from pathlib import Path

from fuckmark.hashing import sha256_json
from fuckmark.transforms.registry import (
    default_transform_registry,
    development_transform_registry,
    release_transform_registry,
)
from fuckmark.transforms.visible_projection_registry import visible_projection_experimental_registry
from fuckmark.transforms.visible_projection_rules import (
    VISIBLE_PROJECTION_EXPERIMENTAL_RULE_ID,
    visible_projection_experimental_rules,
)


def test_visible_projection_rules_are_experimental_space_insertions() -> None:
    rules = visible_projection_experimental_rules()
    assert len(rules) == 1
    assert rules[0].rule_id == VISIBLE_PROJECTION_EXPERIMENTAL_RULE_ID
    assert rules[0].source == " "
    assert rules[0].replacement == " \u200c"
    assert rules[0].tier.value == "tier_4_experimental"


def test_visible_projection_registry_only_allows_ascii_word_boundaries() -> None:
    registry = visible_projection_experimental_registry()
    text = "alpha beta 42 gamma a_b delta"
    enumeration = registry.enumerate(text)
    positions = {candidate.start for candidate in enumeration.candidates}
    assert positions == {text.index(" ")}
    assert len(enumeration.candidates) == 1


def test_visible_projection_registry_replays_hard_invariants() -> None:
    registry = visible_projection_experimental_registry()
    enumeration = registry.enumerate("alpha beta")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text.startswith("alpha ")
    assert result.trace.invariant_report.status.value == "pass"


def test_visible_projection_rules_do_not_enter_default_development_or_release_registries() -> None:
    experimental_ids = {rule.rule_id for rule in visible_projection_experimental_rules()}
    default_ids = {rule.rule_id for rule in default_transform_registry().rules}
    development_ids = {rule.rule_id for rule in development_transform_registry().rules}
    release_ids = {rule.rule_id for rule in release_transform_registry().rules}
    assert not experimental_ids & default_ids
    assert not experimental_ids & development_ids
    assert not experimental_ids & release_ids


def test_visible_projection_contract_is_self_validating_and_fail_closed() -> None:
    path = Path(__file__).parents[1] / "specs" / "fuckmark-quarantined-visible-projection-u200c-v1.contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in contract.items() if key != "contract_hash"}
    assert contract["contract_hash"] == sha256_json(payload)
    assert contract["status"] == "quarantined_experimental_only"
    assert contract["registry_boundary"]["release_registry"] == "forbidden"
    assert contract["known_failure_boundary"]["release_safe"] is False
    assert "release readiness" in contract["prohibited_claims"]


def test_visible_projection_is_removed_by_format_control_stripping() -> None:
    registry = visible_projection_experimental_registry()
    source = "alpha beta"
    enumeration = registry.enumerate(source)
    transformed = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,)).output_text
    stripped = "".join(character for character in transformed if unicodedata.category(character) != "Cf")
    assert stripped == source
