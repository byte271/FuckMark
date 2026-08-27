import json
from pathlib import Path

from fuckmark.cycle8.deepmind_transfer import (
    CYCLE8_MIX_DEEPMIND_TRANSFER_HASH,
    CYCLE8_MIX_DEEPMIND_TRANSFER_PATH,
    CYCLE8_MIX_DEEPMIND_TRANSFER_VERSION,
    CYCLE8_MIX_DEEPMIND_920000_HASH,
    assert_mix_deepmind_transfer_committed,
    transfer_corpus_paths,
)
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.hashing import sha256_file, sha256_json, sha256_text
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


_920000 = "evidence/cycle8-mix-deepmind-30key-920000-n16-2026-08-27"
_920000_HASH = "ee521a04ab6017134e7aa2b48f07da0612c188f8bf2b353611f33f33a4cbb7bf"


def test_deepmind_920000_n16_is_independent_configuration_hypothesis() -> None:
    root = Path(__file__).resolve().parents[1] / _920000
    disk = json.loads((root / "scorecard.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == _920000_HASH
    assert disk["algorithm_version"] == "cycle8-mix-deepmind-30key-transfer-v1"
    assert disk["seed_base"] == 920000
    assert disk["pair_count"] == 16
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["second_model"] is False
    assert disk["second_configuration"] is True
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["model"] == "openai-community/gpt2"
    assert disk["generation"] == "synthid_text.SynthIDGPT2LMHeadModel"
    assert disk["detector"] == "synthid_text.logits_processing.SynthIDLogitsProcessor"
    assert disk["keys_depth"] == 30
    assert disk["visible_pass"] is True
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity_wm"]["rate"] == "16/16"
    assert effectiveness["mix_wm"]["rate"] == "0/16"
    assert effectiveness["identity_uw"]["rate"] == "0/16"
    assert effectiveness["mix_uw"]["rate"] == "0/16"
    assert float(effectiveness["mix_wm_max_score"]) == 0.5063963600986625
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
        assert row["mix"]["text_sha256"] == sha256_text(apply_letter_alternating_mix(source))
        assert row["visible_ok"] is True
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})


def test_deepmind_n192_transfer_is_independent_configuration_hypothesis() -> None:
    root = Path(__file__).resolve().parents[1]
    disk = json.loads((root / CYCLE8_MIX_DEEPMIND_TRANSFER_PATH).read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == CYCLE8_MIX_DEEPMIND_TRANSFER_HASH
    assert disk["algorithm_version"] == CYCLE8_MIX_DEEPMIND_TRANSFER_VERSION
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["mix_freeze_confirmation"] is False
    assert disk["second_model"] is False
    assert disk["second_configuration"] is True
    assert disk["keys_depth"] == 30
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["visible_pass"] is True
    assert disk["exploratory_920000_n16_hash"] == CYCLE8_MIX_DEEPMIND_920000_HASH
    effectiveness = disk["effectiveness"]
    assert effectiveness["identity_wm"]["rate"] == "189/192"
    assert effectiveness["mix_wm"]["rate"] == "0/192"
    assert effectiveness["identity_uw"]["rate"] == "0/192"
    assert effectiveness["mix_uw"]["rate"] == "0/192"
    assert float(effectiveness["mix_wm_max_score"]) == 0.5067599700507657
    assert_mix_deepmind_transfer_committed()
    expected = {
        1060000: ("63/64", "0/64", "2c828e6076005b5aa1b94aad145b20a8748766134fea62c2690202a7ded36e52"),
        1070000: ("63/64", "0/64", "b05e9e80e41fe8487769bdb2908642d59bc2e753746f02dcd05d8f956fb5cb92"),
        1080000: ("63/64", "0/64", "d97f005332d45b93be3588e413055d7ff0035b234f1b4213d3db9e83f85df4d0"),
    }
    for seed_base, relative, digest in transfer_corpus_paths():
        artifact = json.loads((root / relative).read_text(encoding="utf-8"))
        body = {key: value for key, value in artifact.items() if key != "scorecard_hash"}
        assert artifact["scorecard_hash"] == sha256_json(body) == digest
        identity_rate, mix_rate, _expected = expected[seed_base]
        assert artifact["effectiveness"]["identity_wm"]["rate"] == identity_rate
        assert artifact["effectiveness"]["mix_wm"]["rate"] == mix_rate
        assert artifact["effectiveness"]["mix_uw"]["rate"] == "0/64"
        assert artifact["visible_pass"] is True
        samples = json.loads((root / Path(relative).parent / "samples.json").read_text(encoding="utf-8"))
        by_id = {row["sample_id"]: row for row in artifact["rows"]}
        assert len(artifact["rows"]) == 128
        for sample in samples["samples"]:
            source = str(sample["text"])
            row = by_id[str(sample["sample_id"])]
            assert "text" not in row
            assert "text" not in row["mix"]
            assert row["source_sha256"] == sample["text_sha256"] == sha256_text(source)
            assert row["mix"]["text_sha256"] == sha256_text(apply_letter_alternating_mix(source))
        sums_root = root / Path(relative).parent
        for line in (sums_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            file_digest, name = line.split()
            assert sha256_file(sums_root / name) == file_digest
    combined_root = root / Path(CYCLE8_MIX_DEEPMIND_TRANSFER_PATH).parent
    for line in (combined_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        file_digest, name = line.split()
        assert sha256_file(combined_root / name) == file_digest
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
