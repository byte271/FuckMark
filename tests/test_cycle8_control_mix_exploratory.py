import json
from pathlib import Path

from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle, required_sanitizers_keep
from fuckmark.cycle8.control_mix import CONTROL_MIX_APPROVED_CARRIERS, apply_control_alternating_mix
from fuckmark.hashing import sha256_file, sha256_json, sha256_text
from fuckmark.product.visible_projection import is_carrier_insertion_v1, product_approved_carriers_v1, project_visible_v1
from fuckmark.seeds.ledger import CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE, row_for_seed_base
from fuckmark.transforms.registry import release_transform_registry


_ROOT = "evidence/cycle8-control-mix-1100000-n16-2026-08-27"
_SCORECARD_HASH = "8aadf220a3a69e7f88689e6b10b21011f0b4ee66d68c1dd46627f5ad214554d0"


def test_control_mix_1100000_is_independent_hypothesis_zero() -> None:
    root = Path(__file__).resolve().parents[1] / _ROOT
    disk = json.loads((root / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _SCORECARD_HASH
    assert disk["algorithm_version"] == "cycle8-control-mix-exploratory-v1"
    assert disk["seed_base"] == CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE == 1100000
    assert disk["seen_corpus"] is False
    assert disk["independent_generation"] is True
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["mix_freeze_confirmation"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["second_model"] is False
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["pair_count"] == 16
    assert disk["visible_pass"] is True
    assert disk["required_sanitizers_keep"] is True
    assert disk["keys_depth"] == 30
    assert disk["model"] == "openai-community/gpt2"
    assert disk["do_not_generate_950000"] is True
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity_wm"]["rate"] == "15/16"
    assert effectiveness["control_mix_wm"]["rate"] == "0/16"
    assert effectiveness["identity_uw"]["rate"] == "0/16"
    assert effectiveness["control_mix_uw"]["rate"] == "0/16"
    assert float(effectiveness["control_mix_wm_max_score"]) == 0.5058514183090623
    ledger = row_for_seed_base(1100000)
    assert ledger["generated"] is True
    assert ledger["scored"] is True
    assert ledger["eligible_for_confirmation"] is False
    samples = json.loads((root / "samples.json").read_text(encoding="utf-8"))
    by_id = {row["sample_id"]: row for row in samples["samples"]}
    assert len(disk["rows"]) == 32
    assert len(samples["samples"]) == 32
    for row in disk["rows"]:
        source = by_id[row["sample_id"]]["text"]
        assert "text" not in row
        assert "text" not in row["control_mix"]
        assert sha256_text(source) == row["source_sha256"] == by_id[row["sample_id"]]["text_sha256"]
        control = apply_control_alternating_mix(source)
        assert sha256_text(control) == row["control_mix"]["text_sha256"]
        assert is_carrier_insertion_v1(source, control, CONTROL_MIX_APPROVED_CARRIERS)
        assert project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS) == source
        assert required_sanitizers_keep(control) is True
        assert apply_required_sanitizer_bundle(control) == control
        assert row["visible_ok"] is True
        assert row["required_sanitizers_keep"] is True
    identity_miss = [
        row
        for row in disk["rows"]
        if row["label"] == "watermarked" and row["identity"]["detected"] is False
    ]
    assert len(identity_miss) == 1
    assert identity_miss[0]["sample_id"] == "cycle8-1100000-11-structured_instructional-watermarked"
    assert float(identity_miss[0]["identity"]["score"]) == 0.5568728032677877
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    files = {line.split()[-1]: line.split()[0] for line in sums if line}
    assert set(files) == {"README.md", "scorecard.json", "samples.json"}
    for name, digest in files.items():
        assert sha256_file(root / name) == digest
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
