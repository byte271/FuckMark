import json
from pathlib import Path

from fuckmark.cycle8.benchmark import (
    strip_default_ignorable,
    strip_enclosing_marks,
    strip_nonspacing_marks,
    strip_other_controls,
)
from fuckmark.cycle8.combo_stress import (
    CYCLE8_COMBO_STRESS_N192_HASH,
    CYCLE8_COMBO_STRESS_N192_PATH,
    CYCLE8_DISTIL_COMBO_STRESS_HASH,
    CYCLE8_DISTIL_COMBO_STRESS_PATH,
    LIVE_TRIPLE_ARMS,
    assert_combo_stress_n192_committed,
    assert_distil_combo_stress_committed,
    combo_stress_corpus_paths,
)
from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.letter_mix import (
    apply_historical_dual_layer_letter_mix,
    apply_historical_mark_letter_mix,
    apply_historical_triple_layer_letter_mix,
    apply_letter_alternating_mix,
)
from fuckmark.cycle8.second_model_transfer import CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.visible_projection import project_visible_v1


_ROOT = Path(__file__).resolve().parents[1]
_PRIMARY = _ROOT / "evidence" / "cycle8-combo-stress-exploratory-2026-08-28"
_SCORECARD_HASH = "3a23b5c4e25af052440c8761b5e7f24a7d8c4133393b503817ac01473481032a"
_N192 = _ROOT / CYCLE8_COMBO_STRESS_N192_PATH
_SEED_RATES = {
    1200000: ("64/64", "61/64"),
    1210000: ("61/64", "60/64"),
    1220000: ("63/64", "61/64"),
}


def _assert_sums(folder: Path) -> None:
    sums = (folder / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(folder / name) == digest


def test_combo_stress_scorecard_keeps_detection_down_under_combined_attacks() -> None:
    disk = json.loads((_PRIMARY / "scorecard.json").read_text(encoding="utf-8"))
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
    for arm in LIVE_TRIPLE_ARMS:
        assert effectiveness[arm]["rate"] == "0/64"
        assert effectiveness[arm]["restores_source"] == 0
    _assert_sums(_PRIMARY)


def test_combo_stress_heldout_seeds_keep_live_triple_layer_at_zero() -> None:
    for seed_base, relative, expected in combo_stress_corpus_paths():
        path = _ROOT / relative
        disk = json.loads(path.read_text(encoding="utf-8"))
        body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
        assert disk["scorecard_hash"] == sha256_json(body) == expected
        assert disk["confirmation_rewritten"] is False
        assert disk["seed_base"] == seed_base
        assert disk["watermarked_rows"] == 64
        identity_rate, historical_rate = _SEED_RATES[seed_base]
        assert disk["effectiveness"]["identity"]["rate"] == identity_rate
        assert disk["effectiveness"]["historical_dual_mn_us"]["rate"] == historical_rate
        for arm in LIVE_TRIPLE_ARMS:
            assert disk["effectiveness"][arm]["rate"] == "0/64"
            assert disk["effectiveness"][arm]["restores_source"] == 0
        _assert_sums(path.parent)


def test_combo_stress_n192_keeps_live_triple_layer_at_zero() -> None:
    disk = json.loads(_N192.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == CYCLE8_COMBO_STRESS_N192_HASH
    assert disk["confirmation_rewritten"] is False
    assert disk["watermarked_rows"] == 192
    assert disk["evidence_label"] == "HYPOTHESIS"
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity"]["rate"] == "188/192"
    assert effectiveness["historical_mark_mn_us"]["rate"] == "182/192"
    assert effectiveness["historical_dual_mn_us"]["rate"] == "182/192"
    for arm in LIVE_TRIPLE_ARMS:
        assert effectiveness[arm]["rate"] == "0/192"
        assert effectiveness[arm]["restores_source"] == 0
    assert_combo_stress_n192_committed()
    _assert_sums(_N192.parent)


def test_distilgpt2_combo_stress_keeps_live_triple_layer_at_zero() -> None:
    path = _ROOT / CYCLE8_DISTIL_COMBO_STRESS_PATH
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == CYCLE8_DISTIL_COMBO_STRESS_HASH
    assert disk["confirmation_rewritten"] is False
    assert disk["frozen_second_model_scorecard_not_rewritten"] is True
    assert disk["watermarked_rows"] == 16
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["model"] == "distilbert/distilgpt2"
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity"]["rate"] == "16/16"
    assert effectiveness["historical_dual_mn_us"]["rate"] == "16/16"
    assert effectiveness["triple_raw"]["rate"] == "0/16"
    assert effectiveness["triple_mn_us"]["rate"] == "0/16"
    assert effectiveness["triple_di_us"]["rate"] == "0/16"
    assert effectiveness["triple_bundle_us"]["rate"] == "0/16"
    assert effectiveness["triple_mn_us"]["restores_source"] == 0
    assert effectiveness["triple_bundle_us"]["restores_source"] == 0
    frozen = json.loads((_ROOT / CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH).read_text(encoding="utf-8"))
    frozen_by_id = {row["sample_id"]: row for row in frozen["rows"]}
    for row in disk["rows"]:
        frozen_row = frozen_by_id[row["sample_id"]]
        assert frozen_row["label"] == "watermarked"
        assert row["arms"]["identity"]["score"] == frozen_row["identity"]["score"]
        assert row["source_sha256"] == frozen_row["source_sha256"]
    assert_distil_combo_stress_committed()
    _assert_sums(path.parent)


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


def test_live_four_layer_resists_mn_me_unicode_sanitizer() -> None:
    source = "I do not agree."
    historical = apply_historical_triple_layer_letter_mix(source)
    live = apply_letter_alternating_mix(source)
    assert project_visible_v1(live) == source
    assert lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(historical))) == source
    assert strip_other_controls(strip_enclosing_marks(strip_nonspacing_marks(historical))) == source
    assert lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(live))) != source
    assert lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_default_ignorable(live))) != source
    assert strip_other_controls(strip_enclosing_marks(strip_nonspacing_marks(live))) != source
    assert lm_watermarking_unicode_sanitizer(apply_required_sanitizer_bundle(live)) != source
