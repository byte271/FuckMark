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
