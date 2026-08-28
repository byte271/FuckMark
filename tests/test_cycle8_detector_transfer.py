import json
from pathlib import Path

from fuckmark.cycle8.detector_transfer import (
    CYCLE8_MIX_DETECTOR_TRANSFER_HASH,
    CYCLE8_MIX_DETECTOR_TRANSFER_PATH,
    CYCLE8_MIX_DETECTOR_TRANSFER_VERSION,
    assert_mix_mean_transfer_committed,
    confirmation_source_paths,
    load_mix_mean_transfer_scorecard,
)
from fuckmark.cycle8.mix_confirmation import CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
from fuckmark.hashing import sha256_file, sha256_json, sha256_text
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry
from tests.audit_mix_replay import assert_live_mix_matches_stored


def test_mix_mean_transfer_scorecard_is_hypothesis_on_the_same_adapter() -> None:
    disk = load_mix_mean_transfer_scorecard()
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    assert disk["scorecard_hash"] == sha256_json(body) == CYCLE8_MIX_DETECTOR_TRANSFER_HASH
    assert disk["algorithm_version"] == CYCLE8_MIX_DETECTOR_TRANSFER_VERSION
    assert disk["confirmation_scorecard_version"] == CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
    assert disk["product_authorized"] is False
    assert disk["confirmation_rewritten"] is False
    assert disk["second_model"] is False
    assert disk["evidence_label"] == "HYPOTHESIS"
    assert disk["families"] == ["mean", "weighted_mean"]
    assert disk["model"] == "openai-community/gpt2"
    assert disk["adapter"] == "HuggingFaceSynthIDAdapter"
    effectiveness = disk["effectiveness"]
    assert effectiveness["mix_mean_wm"]["rate"] == "0/192"
    assert effectiveness["mix_weighted_mean_wm"]["rate"] == "0/192"
    assert effectiveness["mix_mean_uw"]["rate"] == "0/192"
    assert effectiveness["mix_weighted_mean_uw"]["rate"] == "0/192"
    assert effectiveness["identity_weighted_mean_wm"]["rate"] == "185/192"
    assert effectiveness["identity_weighted_mean_uw"]["rate"] == "2/192"
    assert float(effectiveness["mix_weighted_mean_wm_max_score"]) == 0.5243003808577579
    assert_mix_mean_transfer_committed()
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})


def test_mix_mean_transfer_rows_replay_live_mix_without_rewriting_hashes() -> None:
    disk = load_mix_mean_transfer_scorecard()
    by_id = {row["sample_id"]: row for row in disk["rows"]}
    assert len(disk["rows"]) == 384
    assert len(by_id) == 384
    for _seed_base, relative in confirmation_source_paths():
        artifact = json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))
        for sample in artifact["samples"]:
            source = str(sample["text"])
            row = by_id[str(sample["sample_id"])]
            assert "text" not in row
            assert "text" not in row["mix"]
            assert row["source_sha256"] == sample["text_sha256"] == sha256_text(source)
            assert_live_mix_matches_stored(
                str(sample["sample_id"]),
                source,
                row["mix"]["text_sha256"],
                label=str(row.get("label", sample.get("label", ""))),
            )
    root = Path(__file__).resolve().parents[1] / Path(CYCLE8_MIX_DETECTOR_TRANSFER_PATH).parent
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest
