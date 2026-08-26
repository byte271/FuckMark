import json
from pathlib import Path

from fuckmark.hashing import sha256_json


def test_cycle8_chrome_render_pins_u034f_invisible_and_u200c_visible() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "chrome-render-v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    rows = {row["arm_id"]: row for row in payload["rows"]}
    assert rows["u034f-space-x1"]["status"] == "VERIFIED"
    assert rows["u034f-space-x1"]["equal"] is True
    assert rows["u034f-space-x8"]["status"] == "VERIFIED"
    assert rows["ufe00-space-x1"]["status"] == "VERIFIED"
    assert rows["u200c-space-x1"]["status"] == "REJECTED"
    assert rows["u200c-space-x1"]["equal"] is False


def test_cycle8_seed_890000_detector_compare_is_development_only() -> None:
    path = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-exploratory-890000-2026-08-25" / "detector-compare.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["seed_base"] == 890000
    assert payload["visible_pass_rate"] == "32/32"
    assert payload["detector_access_used_for_selection"] is False
    identity = payload["summaries"]["identity"]
    u034f = payload["summaries"]["u034f-space-x1"]
    u200c = payload["summaries"]["u200c-space-x1"]
    assert identity["raw_watermarked_detected"] == 3
    assert identity["raw_unwatermarked_detected"] == 0
    assert u034f["raw_watermarked_detected"] == 0
    assert u034f["raw_unwatermarked_detected"] == 0
    assert u034f["cf_strip_watermarked_detected"] == 0
    assert u034f["ws_collapse_watermarked_detected"] == 0
    assert u200c["raw_watermarked_detected"] == 0
    assert u200c["cf_strip_watermarked_detected"] == 3
    decision = json.loads(
        (Path(__file__).resolve().parents[1] / "evidence" / "cycle8-exploratory-890000-2026-08-25" / "decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision["decision"] == "PROMISING_DEVELOPMENT"
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
    assert "no Cycle 8 detector scores" not in " ".join(decision["reasons"])


def test_cycle8_seed_900000_replicates_u034f_without_unwatermarked_inflation() -> None:
    path = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-replication-900000-2026-08-25" / "detector-compare.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["seed_base"] == 900000
    assert payload["visible_pass_rate"] == "32/32"
    identity = payload["summaries"]["identity"]
    u034f = payload["summaries"]["u034f-space-x1"]
    u200c = payload["summaries"]["u200c-space-x1"]
    assert identity["raw_watermarked_detected"] == 4
    assert identity["raw_unwatermarked_detected"] == 0
    assert u034f["raw_watermarked_detected"] == 0
    assert u034f["cf_strip_watermarked_detected"] == 0
    assert u200c["cf_strip_watermarked_detected"] == 4
    overflow = [
        row["arms"]["u034f-space-x8"]["tokenizer"]["transformed_token_count"]
        for row in payload["geometry_rows"]
    ]
    assert max(overflow) > 1024
    assert max(row["arms"]["u034f-space-x1"]["tokenizer"]["transformed_token_count"] for row in payload["geometry_rows"]) < 1024


def test_cycle8_seed_910000_validation_matches_u034f_direction() -> None:
    path = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-validation-910000-2026-08-25" / "detector-compare.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["seed_base"] == 910000
    assert payload["visible_pass_rate"] == "32/32"
    identity = payload["summaries"]["identity"]
    u034f = payload["summaries"]["u034f-space-x1"]
    assert identity["raw_watermarked_detected"] == 3
    assert u034f["raw_watermarked_detected"] == 0
    assert u034f["cf_strip_watermarked_detected"] == 0
    assert identity["raw_unwatermarked_detected"] == 0
    assert u034f["raw_unwatermarked_detected"] == 0
