import json
from pathlib import Path

import pytest

from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from fuckmark.cycle8.ledger import (
    CYCLE8_EXPLORATORY_SEED_BASE,
    CYCLE8_HISTORICAL_LEDGER_VERSION,
    CYCLE8_LEDGER_VERSION,
    CYCLE8_REPLICATION_SEED_BASE,
    CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    CYCLE8_VALIDATION_SEED_BASE,
    assert_cycle8_development_seed,
    cycle8_seed_ledger_hash,
    cycle8_seed_ledger_payload,
)
from fuckmark.cycle8.registry import (
    apply_all_candidates,
    cycle8_space_carrier_registry,
    cycle8_space_wordfinal_carrier_registry,
)
from fuckmark.cycle8.unicode_meta import (
    audit_codepoints,
    classify_carrier_hypothesis,
    codepoint_properties,
    iter_default_ignorable_codepoints_v1,
)
from fuckmark.hashing import sha256_json
from fuckmark.product.carriers import InvisibleCarrierAfterWordFinalAsciiLetterRule
from fuckmark.product.visible_projection import is_carrier_insertion_v1
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters


def test_cycle8_historical_v1_ledger_file_remains_frozen() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "fuckmark-cycle8-seed-ledger-v1.json"
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk["algorithm_version"] == CYCLE8_HISTORICAL_LEDGER_VERSION == "cycle8-seed-ledger-v1"
    assert disk["cycle7_unseen_validation_seed_base"] == 880000
    assert disk["ledger_hash"] == "dbf551dde1e3b41c7bb3daac4f6c5b242c4e0be1ecc726c571091e9b2e25b0cc"


def test_cycle8_ledger_file_matches_embedded_payload() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "fuckmark-cycle8-seed-ledger-v2.json"
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in disk.items() if key != "ledger_hash"}
    assert payload == cycle8_seed_ledger_payload()
    assert disk["ledger_hash"] == cycle8_seed_ledger_hash() == sha256_json(payload)
    assert payload["algorithm_version"] == CYCLE8_LEDGER_VERSION == "cycle8-seed-ledger-v2"


def test_cycle8_ledger_freezes_new_seeds_and_blocks_spent_history() -> None:
    payload = cycle8_seed_ledger_payload()
    assert payload["exploratory_development_seed_base"] == CYCLE8_EXPLORATORY_SEED_BASE == 890_000
    assert payload["exploratory_replication_seed_base"] == CYCLE8_REPLICATION_SEED_BASE == 900_000
    assert payload["validation_development_seed_base"] == CYCLE8_VALIDATION_SEED_BASE == 910_000
    assert payload["scale_exploratory_seed_base"] == CYCLE8_SCALE_EXPLORATORY_SEED_BASE == 930_000
    assert payload["density_exploratory_seed_base"] == 960_000
    assert payload["confirmation_reserved_seed_bases"] == [830_000, 840_000, 850_000]
    assert payload["cycle7_publicly_exposed_validation_seed_base"] == 880_000
    assert cycle8_seed_ledger_hash()
    assert_cycle8_development_seed(890_000, role="exploratory_development")
    assert_cycle8_development_seed(930_000, role="scale_exploratory_development")
    assert_cycle8_development_seed(960_000, role="density_exploratory_development")
    with pytest.raises(ValueError):
        assert_cycle8_development_seed(760_000, role="exploratory_development")
    with pytest.raises(ValueError, match="publicly exposed|spent or reserved"):
        assert_cycle8_development_seed(880_000, role="validation_development")
    with pytest.raises(ValueError):
        assert_cycle8_development_seed(830_000, role="exploratory_development")
    with pytest.raises(ValueError, match="frozen"):
        assert_cycle8_development_seed(950_000, role="scale_validation")


def test_u200c_is_diagnostic_cf_and_not_durable() -> None:
    properties = codepoint_properties(0x200C)
    assert properties["category"] == "Cf"
    assert classify_carrier_hypothesis(properties) == "DIAGNOSTIC_CF"
    assert properties["cf_strip_survives"] is False
    source = "alpha beta"
    transformed = "alpha \u200cbeta"
    assert is_carrier_insertion_v1(source, transformed, (0x200C,))
    assert strip_unicode_format_characters(transformed) == source


def test_combining_grapheme_joiner_is_durable_track_on_frozen_sanitizers() -> None:
    properties = codepoint_properties(0x034F)
    assert properties["category"] == "Mn"
    assert properties["default_ignorable"] is True
    assert classify_carrier_hypothesis(properties) == "DURABLE_TRACK_CANDIDATE"
    source = "I do not agree."
    registry = cycle8_space_carrier_registry(0x034F, repeats=2)
    transformed = apply_all_candidates(registry, source)
    assert transformed != source
    assert is_carrier_insertion_v1(source, transformed, (0x034F,))
    assert strip_unicode_format_characters(transformed) == transformed
    assert nfkc_normalize(transformed) == transformed
    assert collapse_horizontal_ascii_whitespace(transformed) == transformed


def test_nbsp_homoglyph_and_soft_hyphen_are_rejected_from_durable_track() -> None:
    assert classify_carrier_hypothesis(codepoint_properties(0x00A0)) == "REJECTED_RENDERING_OR_CONTROL_RISK"
    assert classify_carrier_hypothesis(codepoint_properties(0x00AD)) == "DIAGNOSTIC_CF"
    assert classify_carrier_hypothesis(codepoint_properties(0x2010)) == "REJECTED_RENDERING_OR_CONTROL_RISK"


def test_default_ignorable_scan_finds_non_cf_durable_candidates() -> None:
    rows = audit_codepoints(iter_default_ignorable_codepoints_v1())
    durable = {row["label"] for row in rows if row["classification"] == "DURABLE_TRACK_CANDIDATE"}
    assert "U+034F" in durable
    assert "U+FE00" in durable
    assert "U+200C" not in durable


def test_cgj_space_carrier_survives_utf8_file_roundtrip(tmp_path: Path) -> None:
    source = "I do not agree.\n"
    registry = cycle8_space_carrier_registry(0x034F, repeats=2)
    transformed = apply_all_candidates(registry, source)
    path = tmp_path / "roundtrip.txt"
    path.write_text(transformed, encoding="utf-8")
    loaded = path.read_text(encoding="utf-8")
    assert loaded == transformed
    assert is_carrier_insertion_v1(source, loaded, (0x034F,))
    assert loaded.encode("utf-8").decode("utf-8") == transformed


def test_word_final_letter_carrier_is_denser_than_space_and_fail_closes_apostrophe_splits() -> None:
    from fuckmark.product.visible_projection import project_visible_v1
    from fuckmark.transforms.hard_invariants import validate_hard_invariants
    from fuckmark.transforms.registry import release_transform_registry
    from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus

    rule = InvisibleCarrierAfterWordFinalAsciiLetterRule.create(0x034F)
    assert [match.group() for match in rule.pattern().finditer("alpha")] == ["a"]
    assert [match.group() for match in rule.pattern().finditer("don't")] == ["n", "t"]
    source = "hello world"
    space_only = apply_all_candidates(cycle8_space_carrier_registry(0x034F), source)
    combined = apply_all_candidates(cycle8_space_wordfinal_carrier_registry(0x034F), source)
    assert space_only.count("\u034f") == 1
    assert combined.count("\u034f") == 3
    assert is_carrier_insertion_v1(source, combined, (0x034F,))
    assert project_visible_v1(combined, (0x034F,)) == source
    assert validate_hard_invariants(source, combined).status is InvariantStatus.PASS
    contracted = "I don't wait."
    registry = cycle8_space_wordfinal_carrier_registry(0x034F)
    enumeration = registry.enumerate(contracted)
    assert any(
        rejection.reason is CandidateRejectionReason.HARD_INVARIANT_FAILED for rejection in enumeration.rejections
    )
    applied = apply_all_candidates(registry, contracted)
    assert is_carrier_insertion_v1(contracted, applied, (0x034F,))
    assert project_visible_v1(applied, (0x034F,)) == contracted
    assert validate_hard_invariants(contracted, applied).status is InvariantStatus.PASS
    assert "don't" in applied.replace("\u034f", "")
    assert applied.count("\u034f") >= 1
    assert release_transform_registry().rules == ()
