import json
from pathlib import Path

from fuckmark.cycle8.letter_mix import LETTER_MIX_MECHANISM_ID, apply_letter_alternating_mix
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.visible_projection import project_visible_v1


_ROOT = Path(__file__).resolve().parents[1] / "evidence" / "cycle8-quad-layer-restore-exploratory-2026-08-29"
_SCORECARD_HASH = "62b0ccf99ce5f5f805c612e9226463afb05b6e1c6574ab2d0a718126bc2cbeef"


def test_quad_layer_restore_census_keeps_mn_me_us_at_zero() -> None:
    disk = json.loads((_ROOT / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _SCORECARD_HASH
    assert disk["confirmation_rewritten"] is False
    assert disk["detector_not_run"] is True
    assert disk["watermarked_rows"] == 192
    assert disk["visible_ok"] == 192
    assert disk["us_stable_sources"] == 26
    assert disk["cf_residual_after_mn_me_us"] == 192
    assert disk["mechanism_id"] == LETTER_MIX_MECHANISM_ID
    assert disk["evidence_label"] == "HYPOTHESIS"
    effectiveness = disk["effectiveness"]
    assert effectiveness["quad_mn_me_us"]["restore_rate"] == "0/192"
    assert effectiveness["quad_mn_me_us"]["us_source_rate"] == "0/192"
    assert effectiveness["quad_di_me_us"]["restore_rate"] == "0/192"
    assert effectiveness["quad_mn_me_cc"]["restore_rate"] == "0/192"
    assert effectiveness["quad_bundle_us"]["restore_rate"] == "0/192"
    assert effectiveness["historical_triple_mn_me_us"]["us_source_rate"] == "192/192"
    assert effectiveness["quad_mn_me_us_cf"]["us_source_rate"] == "192/192"
    sums = (_ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(_ROOT / name) == digest
    source = "I do not agree."
    assert project_visible_v1(apply_letter_alternating_mix(source)) == source
