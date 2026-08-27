from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.gate_v2 import (
    CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH,
    CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH,
    CYCLE8_PUBLISHABILITY_GATE_V2_HASH,
    CYCLE8_PUBLISHABILITY_GATE_V2_PATH,
    GATE_V2_CONFIRMATION_ARTIFACT_HASHES,
    GATE_V2_CONFIRMATION_SEED_BASES,
    GATE_V2_IDENTITY_WM_MIN,
    GATE_V2_REQUIRED_SANITIZER_IDS,
    GATE_V2_STATUS_CONFIRMED,
    GATE_V2_UNICODE_SANITIZER_ID,
    assert_gate_v2_committed,
    assert_gate_v2_confirmation_generation_seed,
    build_gate_v2_confirmation_scorecard,
    gate_v2_confirmation_artifact_dir,
    gate_v2_confirmation_artifacts_present,
    gate_v2_payload,
    load_gate_v2,
    load_gate_v2_confirmation_scorecard,
    sanitize_gate_v2_variant,
)
from fuckmark.cycle8.ledger import assert_cycle8_development_seed
from fuckmark.cycle8.publishability import measure_mix_fixtures
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.hashing import sha256_file, sha256_json
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


def test_gate_v2_spec_is_committed_and_confirmed():
    assert Path(CYCLE8_PUBLISHABILITY_GATE_V2_PATH).is_file()
    assert_gate_v2_committed()
    disk = load_gate_v2()
    assert disk["gate_hash"] == CYCLE8_PUBLISHABILITY_GATE_V2_HASH
    assert disk == gate_v2_payload()
    assert disk["status"] == GATE_V2_STATUS_CONFIRMED
    assert disk["evidence_label"] == "VERIFIED"
    assert disk["confirmation_grade"] is True
    assert disk["fully_satisfied"] is True
    assert disk["product_authorized"] is False
    assert disk["mix_sanitizer_gate_v1"] == "FAIL"
    assert disk["required_sanitizer_bundle_not_weakened"] is True
    assert gate_v2_confirmation_artifacts_present() is True


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


def test_gate_v2_seeds_are_spent_after_one_shot_confirmation():
    assert GATE_V2_CONFIRMATION_SEED_BASES == (
        CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
    )
    for seed_base in GATE_V2_CONFIRMATION_SEED_BASES:
        row = row_for_seed_base(seed_base)
        assert row["generated"] is True
        assert row["scored"] is True
        assert row["spent"] is True
        assert row["eligible_for_confirmation"] is False
        assert row["eligible_as_unseen_validation"] is False
        with pytest.raises(ValueError, match="already generated"):
            assert_gate_v2_confirmation_generation_seed(seed_base)
        with pytest.raises(ValueError, match="already generated"):
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
    assert payload["confirmation_protocol"]["status"] == "generated_and_scored_once"
    assert list(GATE_V2_REQUIRED_SANITIZER_IDS) == payload["required_sanitizers"]


def test_gate_v2_confirmation_scorecard_passes_preregistered_thresholds():
    assert Path(CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH).is_file()
    disk = load_gate_v2_confirmation_scorecard()
    live = build_gate_v2_confirmation_scorecard()
    assert disk == live
    assert disk["scorecard_hash"] == CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH
    assert disk["confirmation"] is True
    assert disk["confirmation_grade"] is True
    assert disk["product_authorized"] is False
    assert disk["evidence_label"] == "VERIFIED"
    assert disk["identity_watermarked_detected"] == 188
    assert disk["mix_unwatermarked_detected"] == 0
    assert disk["visible_pass_rate"] == "192/192"
    assert disk["carrier_free_unicode_watermarked_detected"] == 182
    assert disk["carrier_free_unicode_drop_from_identity"] == 6
    assert all(value == 0 for value in disk["mix_watermarked_detected_by_required_sanitizer"].values())
    assert disk["mix_watermarked_detected_by_diagnostic_sanitizer"]["required_bundle"] == 188
    assert disk["rerun_looking_for_zero"] is False
    assert disk["mix_max_score"] == 0.5267390214198725
    for row in disk["corpora"]:
        assert row["artifact_hash"] == GATE_V2_CONFIRMATION_ARTIFACT_HASHES[row["seed_base"]]


def _assert_sha256sums(relative: str) -> None:
    root = Path(relative)
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest


def test_gate_v2_confirmation_artifact_checksums_match():
    for seed_base in GATE_V2_CONFIRMATION_SEED_BASES:
        _assert_sha256sums(gate_v2_confirmation_artifact_dir(seed_base))
    combined = Path("evidence/cycle8-gate-v2-confirmation-2026-08-27")
    _assert_sha256sums(str(combined))
    assert (combined / "scorecard.json").read_text(encoding="utf-8") == Path(CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH).read_text(encoding="utf-8")


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


def test_twelve_context_rescan_is_recorded_and_does_not_rewrite_ab():
    disk = Path("evidence/h16-local/shaping-closure-12context.json").read_text(encoding="utf-8")
    import json

    payload = json.loads(disk)
    assert payload["shaping_contexts_scanned_count"] == 12
    assert payload["shaping_invisible_count"] == 396
    assert payload["shaping_invisible_in_product_contexts_count"] == 396
    assert payload["intersection_count"] == 0
    assert payload["shaping_invisible_categories"] == {"Cf": 134, "Mn": 262}
    assert payload["original_h16_scan_was_latin_ab_only"] is True
    assert payload["shaping_invisible_per_context"]["latin"] == 396
    assert payload["shaping_invisible_per_context"]["arabic"] == 390


def test_gate_v2_hash_is_canonical():
    payload = gate_v2_payload()
    body = {key: value for key, value in payload.items() if key != "gate_hash"}
    assert payload["gate_hash"] == sha256_json(body)
