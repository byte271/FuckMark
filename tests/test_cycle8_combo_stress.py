import json
from pathlib import Path

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.letter_mix import (
    apply_historical_dual_layer_letter_mix,
    apply_historical_mark_letter_mix,
    apply_letter_alternating_mix,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.visible_projection import project_visible_v1


_ROOT = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-combo-stress-exploratory-2026-08-28"
_SCORECARD_HASH = "3a23b5c4e25af052440c8761b5e7f24a7d8c4133393b503817ac01473481032a"


def test_combo_stress_scorecard_keeps_detection_down_under_combined_attacks() -> None:
    disk = json.loads((_ROOT / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _SCORECARD_HASH
    assert disk["confirmation_rewritten"] is False
    assert disk["role"] == "exploratory_rescore_of_frozen_sources"
    assert disk["watermarked_rows"] == 64
    assert disk["mechanism_id"] == "u034f-ufe00-cc-me-letter-alt-v1"
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity"]["rate"] == "64/64"
    assert effectiveness["historical_mark_mn_us"]["detected"] >= 60
    assert effectiveness["historical_dual_mn_us"]["detected"] >= 60
    assert effectiveness["triple_raw"]["rate"] == "0/64"
    assert effectiveness["triple_mn_strip"]["rate"] == "0/64"
    assert effectiveness["triple_di_strip"]["rate"] == "0/64"
    assert effectiveness["triple_us"]["rate"] == "0/64"
    assert effectiveness["triple_mn_us"]["rate"] == "0/64"
    assert effectiveness["triple_di_us"]["rate"] == "0/64"
    assert effectiveness["triple_us_mn"]["rate"] == "0/64"
    assert effectiveness["triple_bundle"]["rate"] == "0/64"
    assert effectiveness["triple_bundle_us"]["rate"] == "0/64"
    assert effectiveness["triple_mn_us"]["restores_source"] == 0
    assert effectiveness["triple_bundle_us"]["restores_source"] == 0
    sums = (_ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8")
    digest, name = sums.splitlines()[0].split()
    assert sha256_file(_ROOT / name) == digest


def test_live_triple_layer_resists_mn_then_unicode_sanitizer() -> None:
    source = "I do not agree."
    historical = apply_historical_mark_letter_mix(source)
    dual = apply_historical_dual_layer_letter_mix(source)
    live = apply_letter_alternating_mix(source)
    assert project_visible_v1(live) == source
    assert lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(historical)) == source
    assert lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(dual)) == source
    assert lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(live)) != source
    assert lm_watermarking_unicode_sanitizer(strip_default_ignorable(live)) != source
    assert lm_watermarking_unicode_sanitizer(apply_required_sanitizer_bundle(live)) != source
