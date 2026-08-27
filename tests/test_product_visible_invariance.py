import json
from pathlib import Path

import pytest

from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from fuckmark.hashing import sha256_json
from fuckmark.product.carriers import rule_preserves_visible_projection, space_carrier_rule
from fuckmark.product.contract import (
    FROZEN_PRODUCT_CONTRACT_HASH,
    load_product_contract,
    product_contract_hash,
    product_contract_payload,
)
from fuckmark.product.domain import is_supported_product_domain_v1
from fuckmark.product.invariants import UserVisibleInvariantReason, validate_user_visible_invariants
from fuckmark.product.registry import ProductTransformRegistry, product_transform_registry
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters
from fuckmark.transforms.registry import historical_visible_edit_transform_registry, release_transform_registry
from fuckmark.transforms.rules import default_contraction_rules
from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus


def test_product_contract_file_matches_embedded_payload() -> None:
    contract = load_product_contract()
    payload = {key: value for key, value in contract.items() if key != "contract_hash"}
    assert payload == product_contract_payload()
    assert contract["contract_hash"] == product_contract_hash() == sha256_json(payload) == FROZEN_PRODUCT_CONTRACT_HASH
    path = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-user-visible-invariance-v1.contract.json"
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk == contract


def test_load_product_contract_uses_embedded_payload_without_checkout_file(monkeypatch, tmp_path: Path) -> None:
    from fuckmark.product import contract as contract_module

    monkeypatch.setattr(contract_module, "PRODUCT_CONTRACT_PATH", tmp_path / "missing-contract.json")
    contract = contract_module.load_product_contract()
    payload = {key: value for key, value in contract.items() if key != "contract_hash"}
    assert payload == product_contract_payload()
    assert contract["contract_hash"] == product_contract_hash() == FROZEN_PRODUCT_CONTRACT_HASH


def test_load_product_contract_rejects_mismatched_checkout_file(monkeypatch, tmp_path: Path) -> None:
    from fuckmark.product import contract as contract_module

    path = tmp_path / "fuckmark-user-visible-invariance-v1.contract.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(contract_module, "PRODUCT_CONTRACT_PATH", path)
    with pytest.raises(ValueError, match="does not match embedded v1 payload"):
        contract_module.load_product_contract()


def test_load_product_contract_rejects_unfrozen_embedded_hash(monkeypatch) -> None:
    from fuckmark.product import contract as contract_module

    monkeypatch.setattr(contract_module, "FROZEN_PRODUCT_CONTRACT_HASH", "0" * 64)
    with pytest.raises(ValueError, match="frozen v1 digest"):
        contract_module.load_product_contract()


def test_visible_projection_rejects_contractions_spaces_and_punctuation() -> None:
    cases = (
        ("I do not agree.", "I don't agree."),
        ("We cannot continue.", "We can't continue."),
        ("toward the lake", "towards the lake"),
        ("proof of concept", "proof-of-concept"),
        ("well known", "well-known"),
        ("However the result matters.", "However, the result matters."),
        ("one space", "one  space"),
        ("line one\nline two", "line one line two"),
        ("It's fine.", "It\u2019s fine."),
    )
    for original, transformed in cases:
        report = validate_user_visible_invariants(original, transformed)
        assert report.status is InvariantStatus.FAIL
        assert report.reasons == (UserVisibleInvariantReason.USER_VISIBLE_TEXT_CHANGED,)


def test_visible_projection_accepts_approved_carrier_insertions_only() -> None:
    original = "I do not agree."
    transformed = "I do \u034fnot agree."
    assert is_carrier_insertion_v1(original, transformed, (0x034F,))
    assert project_visible_v1(transformed, (0x034F,)) == original
    assert validate_user_visible_invariants(original, transformed, (0x034F,)).status is InvariantStatus.PASS
    assert validate_user_visible_invariants(original, transformed).status is InvariantStatus.PASS
    unauthorized = "I do \u200cnot agree."
    assert validate_user_visible_invariants(original, unauthorized).status is InvariantStatus.FAIL


def test_product_registry_refuses_visible_edit_rules() -> None:
    with pytest.raises(ValueError, match="visible-edit"):
        product_transform_registry(rules=default_contraction_rules())
    registry = ProductTransformRegistry(default_contraction_rules())
    enumeration = registry.enumerate("I do not agree.")
    assert enumeration.candidates == ()
    assert any(value.reason is CandidateRejectionReason.USER_VISIBLE_TEXT_CHANGED for value in enumeration.rejections)


def test_release_registry_is_empty_product_registry() -> None:
    registry = release_transform_registry()
    assert registry.rules == ()
    text = "I do not agree. We cannot continue."
    assert registry.enumerate(text).candidates == ()
    assert historical_visible_edit_transform_registry().ruleset_hash != registry.ruleset_hash


def test_product_domain_rejects_non_ascii_and_cli_leaves_it_unchanged() -> None:
    text = "cafe\u0301 already combines."
    assert not is_supported_product_domain_v1(text)
    assert release_transform_registry().enumerate(text).candidates == ()


def test_space_carrier_rule_round_trips_projection_and_survives_cf_strip() -> None:
    rule = space_carrier_rule(0x034F, 2)
    assert rule_preserves_visible_projection(rule, (0x034F,))
    original = "do not"
    transformed = "do \u034f\u034fnot"
    assert is_carrier_insertion_v1(original, transformed, (0x034F,))
    assert strip_unicode_format_characters(transformed) == transformed
    assert nfkc_normalize(transformed) == transformed
    assert collapse_horizontal_ascii_whitespace(transformed) == transformed


def test_protected_url_and_number_and_path_are_not_carrier_sites() -> None:
    from fuckmark.cycle8.registry import cycle8_space_carrier_registry

    registry = cycle8_space_carrier_registry(0x034F)
    text = "See https://example.com/a-b and 42 and /tmp/foo.txt in the notes."
    enumeration = registry.enumerate(text)
    for candidate in enumeration.candidates:
        span = text[candidate.start:candidate.end]
        assert "https://example.com" not in text[max(0, candidate.start - 30):candidate.end + 30] or span == " "
        assert candidate.start >= text.index("See")
    applied = text
    if enumeration.candidates:
        from fuckmark.cycle8.registry import apply_all_candidates

        applied = apply_all_candidates(registry, text)
    assert "https://example.com/a-b" in applied.replace("\u034f", "")
    assert "42" in applied.replace("\u034f", "")
    assert "/tmp/foo.txt" in applied.replace("\u034f", "")
    assert is_carrier_insertion_v1(text, applied, (0x034F,))


def test_u034f_space_carrier_fail_closes_sites_that_create_extended_paths() -> None:
    from fuckmark.cycle8.registry import apply_all_candidates, cycle8_space_carrier_registry
    from fuckmark.transforms.hard_invariants import validate_hard_invariants
    from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus

    registry = cycle8_space_carrier_registry(0x034F)
    text = "Use / tmp / nested / file.txt after the check."
    enumeration = registry.enumerate(text)
    assert any(
        rejection.reason is CandidateRejectionReason.HARD_INVARIANT_FAILED for rejection in enumeration.rejections
    )
    applied = apply_all_candidates(registry, text)
    assert is_carrier_insertion_v1(text, applied, (0x034F,))
    assert project_visible_v1(applied, (0x034F,)) == text
    assert validate_hard_invariants(text, applied).status is InvariantStatus.PASS
    assert "file.txt" in applied.replace("\u034f", "")
