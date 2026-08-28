import json
from pathlib import Path

from fuckmark.cycle8.second_model_transfer import (
    CYCLE8_MIX_SECOND_MODEL_ID,
    CYCLE8_MIX_SECOND_MODEL_REVISION,
    CYCLE8_MIX_SECOND_MODEL_TRANSFER_HASH,
    CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH,
    CYCLE8_MIX_SECOND_MODEL_TRANSFER_VERSION,
    assert_mix_second_model_transfer_committed,
)
from fuckmark.hashing import sha256_file, sha256_json, sha256_text
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry
from tests.audit_mix_replay import live_mix_hash


_ROOT = "evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27"


def test_distilgpt2_n16_is_second_model_hypothesis_not_confirmation() -> None:
    root = Path(__file__).resolve().parents[1] / _ROOT
    disk = json.loads((root / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == CYCLE8_MIX_SECOND_MODEL_TRANSFER_HASH
    assert CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH == f"{_ROOT}/scorecard.json"
    assert disk["algorithm_version"] == CYCLE8_MIX_SECOND_MODEL_TRANSFER_VERSION
    assert disk["seed_base"] == 1090000
    assert disk["pair_count"] == 16
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["mix_freeze_confirmation"] is False
    assert disk["second_model"] is True
    assert disk["second_configuration"] is False
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["model"] == CYCLE8_MIX_SECOND_MODEL_ID
    assert disk["model_revision"] == CYCLE8_MIX_SECOND_MODEL_REVISION
    assert disk["generation"] == "synthid_text.SynthIDGPT2LMHeadModel"
    assert disk["detector"] == "synthid_text.logits_processing.SynthIDLogitsProcessor"
    assert disk["keys_depth"] == 30
    assert disk["tokenizer"] == "GPT2TokenizerFast"
    assert disk["tokenizer_vocab_size"] == 50257
    assert disk["visible_pass"] is True
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity_wm"]["rate"] == "16/16"
    assert effectiveness["mix_wm"]["rate"] == "0/16"
    assert effectiveness["identity_uw"]["rate"] == "0/16"
    assert effectiveness["mix_uw"]["rate"] == "0/16"
    assert float(effectiveness["mix_wm_max_score"]) == 0.5047997827277791
    samples = json.loads((root / "samples.json").read_text(encoding="utf-8"))
    by_id = {row["sample_id"]: row for row in disk["rows"]}
    assert len(disk["rows"]) == 32
    assert len(samples["samples"]) == 32
    for sample in samples["samples"]:
        source = str(sample["text"])
        row = by_id[str(sample["sample_id"])]
        assert "text" not in row
        assert "text" not in row["mix"]
        assert row["source_sha256"] == sample["text_sha256"] == sha256_text(source)
        live_mix_hash(source)
        assert row["visible_ok"] is True
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest
    assert_mix_second_model_transfer_committed()
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
