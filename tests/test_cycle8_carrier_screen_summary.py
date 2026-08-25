import json
from pathlib import Path


def test_cycle8_carrier_screen_summary_pins_sanitizer_and_tokenizer_claims() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "carrier-screen-v1.summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["gpt2_encoder"] == "gpt2"
    assert payload["durable_track_count"] >= 1
    assert "U+034F" in payload["durable_track_labels"]
    assert "U+FE00" in payload["durable_track_labels"]
    by_label = {row["label"]: row for row in payload["focus"]}
    assert by_label["U+200C"]["classification"] == "DIAGNOSTIC_CF"
    assert by_label["U+034F"]["classification"] == "DURABLE_TRACK_CANDIDATE"
    assert by_label["U+034F"]["cf_strip_survives"] is True
    assert by_label["U+034F"]["nfkc_stable"] is True
    tokenizer = {row["label"]: row for row in payload["tokenizer"]}
    cgj = tokenizer["U+034F"]
    assert cgj["status"] == "VERIFIED"
    assert cgj["space_visible_ok"] is True
    assert cgj["space_metrics"]["ids_equal"] is False
    assert cgj["space_metrics"]["token_count_delta"] > 0
    assert tokenizer["U+200C"]["space_metrics"]["ids_equal"] is False
