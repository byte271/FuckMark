import json
from pathlib import Path

from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle, required_sanitizers_keep
from fuckmark.cycle8.control_mix import CONTROL_MIX_APPROVED_CARRIERS, apply_control_alternating_mix
from fuckmark.hashing import sha256_file, sha256_json, sha256_text
from fuckmark.product.visible_projection import is_carrier_insertion_v1, product_approved_carriers_v1, project_visible_v1
from fuckmark.transforms.registry import release_transform_registry
from tests.audit_mix_replay import live_mix_hash


_DIAGNOSTIC = "evidence/cycle8-control-mix-diagnostic-920000-n16-2026-08-27"
_DIAGNOSTIC_HASH = "d6afe1930faa3762dbcc3f844e31563d64b703ab477fb294a99be283c041ca0b"
_SAMPLES = "evidence/cycle8-mix-deepmind-30key-920000-n16-2026-08-27/samples.json"


def test_control_mix_diagnostic_920000_is_seen_hypothesis_zero() -> None:
    root = Path(__file__).resolve().parents[1] / _DIAGNOSTIC
    disk = json.loads((root / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _DIAGNOSTIC_HASH
    assert disk["algorithm_version"] == "cycle8-control-mix-diagnostic-v1"
    assert disk["seed_base"] == 920000
    assert disk["seen_corpus"] is True
    assert disk["independent_generation"] is False
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["mix_freeze_confirmation"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["pair_count"] == 16
    assert disk["visible_pass"] is True
    assert disk["required_sanitizers_keep"] is True
    assert disk["keys_depth"] == 30
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity_wm"]["rate"] == "16/16"
    assert effectiveness["control_mix_wm"]["rate"] == "0/16"
    assert effectiveness["mix_wm"]["rate"] == "0/16"
    assert effectiveness["identity_uw"]["rate"] == "0/16"
    assert effectiveness["control_mix_uw"]["rate"] == "0/16"
    assert effectiveness["mix_uw"]["rate"] == "0/16"
    assert float(effectiveness["control_mix_wm_max_score"]) == 0.505336937084192
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
    assert release_transform_registry().rules == ()
    samples = json.loads((Path(__file__).resolve().parents[1] / _SAMPLES).read_text(encoding="utf-8"))["samples"]
    by_id = {row["sample_id"]: row for row in samples}
    for row in disk["rows"]:
        source = by_id[row["sample_id"]]["text"]
        assert sha256_text(source) == row["source_sha256"]
        control = apply_control_alternating_mix(source)
        live_mix_hash(source)
        assert sha256_text(control) == row["control_mix"]["text_sha256"]
        assert is_carrier_insertion_v1(source, control, CONTROL_MIX_APPROVED_CARRIERS)
        assert project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS) == source
        assert required_sanitizers_keep(control) is True
        assert apply_required_sanitizer_bundle(control) == control
        assert row["visible_ok"] is True
        assert row["required_sanitizers_keep"] is True
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    files = {line.split()[-1]: line.split()[0] for line in sums if line}
    for name, digest in files.items():
        assert sha256_file(root / name) == digest
