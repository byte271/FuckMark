import json

import pytest

from fuckmark.cycle8.compare import CYCLE8_IDENTITY_ARM_ID, CYCLE8_U034F_SPACE_ARM_ID
from fuckmark.cycle8.decision import PROMISING_DEVELOPMENT, classify_scale_detector_compare
from fuckmark.cycle8.ledger import CYCLE8_SCALE_PAIR_COUNT
from fuckmark.seeds.ledger import (
    CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    assert_new_cycle8_scale_generation_seed,
)


def test_scale_pair_count_and_seed_are_frozen_before_generation() -> None:
    assert CYCLE8_SCALE_PAIR_COUNT == 16
    assert_new_cycle8_scale_generation_seed(CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_scale_generation_seed(830000)


def test_cycle8_scale_n16_and_n32_are_zero_raw_on_frozen_u034f_x1() -> None:
    from pathlib import Path

    from fuckmark.hashing import sha256_json

    n16 = json.loads(
        (Path(__file__).resolve().parents[1] / "evidence" / "cycle8-scale-930000-2026-08-26" / "detector-compare.json").read_text(
            encoding="utf-8"
        )
    )
    n16_body = {key: value for key, value in n16.items() if key != "artifact_hash"}
    assert n16["artifact_hash"] == sha256_json(n16_body)
    assert n16["seed_base"] == 930000
    assert n16["pair_count"] == 16
    assert n16["detector_access_used_for_selection"] is False
    identity = n16["summaries"][CYCLE8_IDENTITY_ARM_ID]
    u034f = n16["summaries"][CYCLE8_U034F_SPACE_ARM_ID]
    assert identity["raw_watermarked_detected"] == 16
    assert identity["pristine_watermarked_detected"] == 16
    assert u034f["raw_watermarked_detected"] == 0
    assert u034f["raw_unwatermarked_detected"] == 0
    assert u034f["cf_strip_watermarked_detected"] == 0
    assert u034f["nfkc_watermarked_detected"] == 0
    assert u034f["ws_collapse_watermarked_detected"] == 0
    assert u034f["nfc_watermarked_detected"] == 0
    assert u034f["visible_pass_count"] == 32
    n32 = json.loads(
        (
            Path(__file__).resolve().parents[1] / "evidence" / "cycle8-scale-930000-n32-2026-08-26" / "detector-compare.json"
        ).read_text(encoding="utf-8")
    )
    n32_body = {key: value for key, value in n32.items() if key != "artifact_hash"}
    assert n32["artifact_hash"] == sha256_json(n32_body)
    assert n32["pair_count"] == 32
    assert n32["summaries"][CYCLE8_IDENTITY_ARM_ID]["raw_watermarked_detected"] == 32
    assert n32["summaries"][CYCLE8_U034F_SPACE_ARM_ID]["raw_watermarked_detected"] == 0
    assert n32["summaries"][CYCLE8_U034F_SPACE_ARM_ID]["raw_unwatermarked_detected"] == 0
    assert n32["summaries"][CYCLE8_U034F_SPACE_ARM_ID]["visible_pass_count"] == 64
    n16_decision = json.loads(
        (Path(__file__).resolve().parents[1] / "evidence" / "cycle8-scale-930000-2026-08-26" / "decision.json").read_text(
            encoding="utf-8"
        )
    )
    n32_decision = json.loads(
        (Path(__file__).resolve().parents[1] / "evidence" / "cycle8-scale-930000-n32-2026-08-26" / "decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert n16_decision["decision"] == PROMISING_DEVELOPMENT
    assert n32_decision["decision"] == PROMISING_DEVELOPMENT
    assert n16_decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
    assert n32_decision["u034f_raw_watermarked_detected"] == 0


def test_classify_scale_detector_compare_marks_zero_raw_as_promising() -> None:
    artifact = {
        "summaries": {
            CYCLE8_IDENTITY_ARM_ID: {
                "raw_watermarked_detected": 12,
                "raw_unwatermarked_detected": 0,
                "visible_pass_count": 32,
                "visible_total_count": 32,
            },
            CYCLE8_U034F_SPACE_ARM_ID: {
                "raw_watermarked_detected": 0,
                "raw_unwatermarked_detected": 0,
                "cf_strip_watermarked_detected": 0,
                "nfkc_watermarked_detected": 0,
                "ws_collapse_watermarked_detected": 0,
                "nfkc_cf_strip_watermarked_detected": 0,
                "ws_collapse_nfkc_cf_strip_watermarked_detected": 0,
                "visible_pass_count": 32,
                "visible_total_count": 32,
            },
        }
    }
    decision = classify_scale_detector_compare(artifact)
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["visible_pass_rate"] == "32/32"
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
