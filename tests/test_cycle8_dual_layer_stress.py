import json
from pathlib import Path

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.letter_mix import apply_historical_mark_letter_mix, apply_letter_alternating_mix
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.visible_projection import project_visible_v1


_ROOT = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-dual-layer-stress-exploratory-2026-08-28"
_SCORECARD_HASH = "aa56fd036cfa733538fd62e213849f1974dafccb13b14c223e61c42d7de0bfea"


def test_dual_layer_stress_scorecard_keeps_detection_down_after_mn_and_di_strip() -> None:
    disk = json.loads((_ROOT / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _SCORECARD_HASH
    assert disk["confirmation_rewritten"] is False
    assert disk["role"] == "exploratory_rescore_of_frozen_sources"
    assert disk["watermarked_rows"] == 64
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity"]["rate"] == "64/64"
    assert effectiveness["historical_mark_raw"]["rate"] == "0/64"
    assert effectiveness["historical_mark_mn_strip"]["rate"] == "64/64"
    assert effectiveness["historical_mark_di_strip"]["rate"] == "64/64"
    assert effectiveness["dual_layer_raw"]["rate"] == "0/64"
    assert effectiveness["dual_layer_mn_strip"]["rate"] == "0/64"
    assert effectiveness["dual_layer_di_strip"]["rate"] == "0/64"
    assert effectiveness["historical_mark_mn_strip"]["restores_source"] == 64
    assert effectiveness["dual_layer_mn_strip"]["restores_source"] == 0
    sums = (_ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8")
    digest, name = sums.splitlines()[0].split()
    assert sha256_file(_ROOT / name) == digest


def test_live_dual_layer_leaves_residual_after_stress_strips() -> None:
    source = "I do not agree."
    historical = apply_historical_mark_letter_mix(source)
    live = apply_letter_alternating_mix(source)
    assert project_visible_v1(live) == source
    assert strip_nonspacing_marks(historical) == source
    assert strip_default_ignorable(historical) == source
    assert strip_nonspacing_marks(live) != source
    assert strip_default_ignorable(live) != source
