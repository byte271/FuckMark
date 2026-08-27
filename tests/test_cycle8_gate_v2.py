from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.gate_v2 import (
    CYCLE8_PUBLISHABILITY_GATE_V2_HASH,
    CYCLE8_PUBLISHABILITY_GATE_V2_PATH,
    GATE_V2_CONFIRMATION_SEED_BASES,
    GATE_V2_IDENTITY_WM_MIN,
    GATE_V2_REQUIRED_SANITIZER_IDS,
    GATE_V2_STATUS_PREREGISTERED,
    GATE_V2_UNICODE_SANITIZER_ID,
    assert_gate_v2_committed,
    assert_gate_v2_confirmation_generation_seed,
    build_gate_v2_confirmation_scorecard,
    gate_v2_confirmation_artifacts_present,
    gate_v2_payload,
    load_gate_v2,
    sanitize_gate_v2_variant,
)
from fuckmark.cycle8.ledger import assert_cycle8_development_seed
from fuckmark.cycle8.publishability import measure_mix_fixtures
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.hashing import sha256_json
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.seeds.ledger import (
    CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES,
    CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    assert_new_cycle8_gate_v2_confirmation_generation_seed,
    row_for_seed_base,
)
from fuckmark.transforms.registry import release_transform_registry


def test_gate_v2_spec_is_committed_and_preregistered():
    assert Path(CYCLE8_PUBLISHABILITY_GATE_V2_PATH).is_file()
    assert_gate_v2_committed()
    disk = load_gate_v2()
    assert disk["gate_hash"] == CYCLE8_PUBLISHABILITY_GATE_V2_HASH
    assert disk == gate_v2_payload()
    assert disk["status"] == GATE_V2_STATUS_PREREGISTERED
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["confirmation_grade"] is False
    assert disk["fully_satisfied"] is False
    assert disk["product_authorized"] is False
    assert disk["mix_sanitizer_gate_v1"] == "FAIL"
    assert disk["required_sanitizer_bundle_not_weakened"] is True
    assert gate_v2_confirmation_artifacts_present() is False


def test_gate_v2_does_not_authorize_the_product():
    assert product_approved_carriers_v1() == frozenset()
    assert release_transform_registry().rules == ()
    assert process_text("I do not agree.") == "I do not agree."


def test_gate_v2_does_not_weaken_the_required_bundle():
    assert required_sanitizers_keep("I\u034f do not agree.") is False
    assert required_sanitizers_keep("I\ufe00 do not agree.") is False
    measured = measure_mix_fixtures()
    assert measured["frozen_sanitizer_survive"] == measured["frozen_sanitizer_total"]
    assert measured["mn_strip_kills"] == measured["stress_total"]


def test_gate_v2_seeds_are_reserved_unspent_and_unseen():
    assert GATE_V2_CONFIRMATION_SEED_BASES == (
        CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
    )
    for seed_base in GATE_V2_CONFIRMATION_SEED_BASES:
        row = row_for_seed_base(seed_base)
        assert row["generated"] is False
        assert row["scored"] is False
        assert row["spent"] is False
        assert row["eligible_for_confirmation"] is True
        assert row["eligible_as_unseen_validation"] is True
        assert_gate_v2_confirmation_generation_seed(seed_base)
        assert_new_cycle8_gate_v2_confirmation_generation_seed(seed_base)
        with pytest.raises(ValueError, match="Gate v2 confirmation"):
            assert_cycle8_development_seed(seed_base, role="exploratory_development")
    assert set(GATE_V2_CONFIRMATION_SEED_BASES).isdisjoint(CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES)
    assert CYCLE8_SCALE_VALIDATION_SEED_BASE not in GATE_V2_CONFIRMATION_SEED_BASES
    assert 890000 not in GATE_V2_CONFIRMATION_SEED_BASES
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_gate_v2_confirmation_generation_seed(830000)
    with pytest.raises(ValueError, match="950000|frozen"):
        assert_new_cycle8_gate_v2_confirmation_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)


def test_gate_v2_form_is_detector_after_sanitizer():
    payload = load_gate_v2()
    assert payload["decision"]["form"] == "detector_after_sanitizer"
    assert payload["decision"]["rejected_form"] == "carrier_fixed_point_of_every_sanitizer"
    assert GATE_V2_UNICODE_SANITIZER_ID in payload["required_sanitizers"]
    assert "ws_collapse_nfkc_cf_strip" in payload["required_sanitizers"]
    assert payload["classifications"]["lm_watermarking_unicode_sanitizer"] == "real_deployed_preprocessing"
    assert payload["classifications"]["nonspacing_mark_removal"] == "stress_only_not_frozen"
    assert payload["classifications"]["default_ignorable_removal"] == "stress_only_not_frozen"
    assert payload["classifications"]["required_bundle"] == "known_destructive_countermeasure"
    assert payload["confirmation_protocol"]["thresholds"]["identity_watermarked_detected_min"] == GATE_V2_IDENTITY_WM_MIN
    assert list(GATE_V2_REQUIRED_SANITIZER_IDS) == payload["required_sanitizers"]


def test_gate_v2_unicode_sanitizer_matches_upstream_whitespaces_default():
    import re

    from fuckmark.cycle8.threat_model_audit import LM_WATERMARKING_UNICODE_SANITIZER_PATTERN

    upstream = re.compile(
        "[\u00A0\u1680\u180E\u2000-\u200B\u200C\u200D\u200E\u200F\u2060\u2063\u202F\u205F\u3000\uFEFF\uFFA0\uFFF9\uFFFA\uFFFB"
        "\uFE00\uFE01\uFE02\uFE03\uFE04\uFE05\uFE06\uFE07\uFE08\uFE09\uFE0A\uFE0B\uFE0C\uFE0D\uFE0E\uFE0F\u3164\u202A\u202B\u202C\u202D"
        "\u202E\u202F]"
    )
    for codepoint in range(0x10000):
        character = chr(codepoint)
        assert bool(upstream.search(character)) == bool(LM_WATERMARKING_UNICODE_SANITIZER_PATTERN.search(character))
    assert lm_watermarking_unicode_sanitizer("A\u034fB") == "A\u034fB"
    assert lm_watermarking_unicode_sanitizer("A\ufe00B") != "A\ufe00B"
    assert sanitize_gate_v2_variant("raw", "I\u034f do not agree.") == "I\u034f do not agree."
    assert sanitize_gate_v2_variant(GATE_V2_UNICODE_SANITIZER_ID, "A\ufe00B") != "A\ufe00B"
    with pytest.raises(ValueError, match="unknown Gate v2 sanitizer"):
        sanitize_gate_v2_variant("mn_strip", "I\u034f do not agree.")


def test_shaping_scan_tool_iterates_all_advertised_contexts():
    text = Path("tools/h16_shaping_closure_scan.py").read_text(encoding="utf-8")
    assert "SHAPING_CONTEXTS" in text
    assert "for context_id, left, right in SHAPING_CONTEXTS" in text
    from fuckmark.cycle8.threat_model_audit import PRODUCT_SHAPING_CONTEXT_IDS, SHAPING_CONTEXTS

    assert len(SHAPING_CONTEXTS) == 12
    assert SHAPING_CONTEXTS[0] == ("latin", "A", "B")
    ids = [context_id for context_id, _left, _right in SHAPING_CONTEXTS]
    assert ids == [
        "latin",
        "latin_lower",
        "digit",
        "space_left",
        "space_right",
        "start",
        "end",
        "arabic",
        "devanagari",
        "cjk",
        "hangul",
        "punct",
    ]
    assert set(PRODUCT_SHAPING_CONTEXT_IDS) <= set(ids)


def test_gate_v2_hash_is_canonical():
    payload = gate_v2_payload()
    body = {key: value for key, value in payload.items() if key != "gate_hash"}
    assert payload["gate_hash"] == sha256_json(body)


def test_gate_v2_scorecard_refuses_absent_artifacts():
    assert gate_v2_confirmation_artifacts_present() is False
    with pytest.raises(ValueError, match="not present"):
        build_gate_v2_confirmation_scorecard()
