import json
from pathlib import Path

from fuckmark.cycle8.compare import (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
    CYCLE8_U034F_LETTER_SPACE_ARM_ID,
)
from fuckmark.cycle8.decision import PROMISING_DEVELOPMENT
from fuckmark.cycle8_margin_hf import CYCLE8_MARGIN_DETECTOR_VERSION
from fuckmark.hashing import sha256_json
from fuckmark.seeds.ledger import CYCLE8_MARGIN_PRIMARY_TOPIC, CYCLE8_MARGIN_REPLICATION_TOPIC
from fuckmark.transforms.registry import release_transform_registry


def _load(relative: str) -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))


def test_margin_1000000_letter_space_is_zero_raw() -> None:
    artifact = _load("evidence/cycle8-margin-1000000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "dc23489a43c263dc1d8c6211e12e40bc52e2911b2017ecf912bc1ea1d769c00a"
    assert artifact["seed_base"] == 1000000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MARGIN_PRIMARY_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MARGIN_DETECTOR_VERSION
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["secret_access_used_for_selection"] is False
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    space = artifact["summaries"][CYCLE8_U034F_LETTER_SPACE_ARM_ID]
    assert identity["raw_watermarked_detected"] == 63
    assert letter["raw_watermarked_detected"] == 0
    assert space["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert space["raw_unwatermarked_detected"] == 0
    assert space["visible_pass_count"] == 128
    assert space["nfc_watermarked_detected"] == 0
    assert space["cf_strip_watermarked_detected"] == 0
    assert float(space["raw_watermarked_max_score"]) < 0.5570987654320988
    decision = _load("evidence/cycle8-margin-1000000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["transformed_arm_id"] == CYCLE8_U034F_LETTER_SPACE_ARM_ID
    assert release_transform_registry().rules == ()


def test_margin_1010000_letter_space_has_one_residual() -> None:
    artifact = _load("evidence/cycle8-margin-1010000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "3d44e8e76bd3771e2adc1068038491284683061350c87a467a29eac126db8095"
    assert artifact["seed_base"] == 1010000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MARGIN_REPLICATION_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MARGIN_DETECTOR_VERSION
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    space = artifact["summaries"][CYCLE8_U034F_LETTER_SPACE_ARM_ID]
    assert identity["raw_watermarked_detected"] == 64
    assert letter["raw_watermarked_detected"] == 1
    assert space["raw_watermarked_detected"] == 1
    assert letter["raw_unwatermarked_detected"] == 0
    assert space["raw_unwatermarked_detected"] == 0
    assert space["visible_pass_count"] == 128
    assert space["nfc_watermarked_detected"] == 1
    assert space["cf_strip_watermarked_detected"] == 1
    assert float(space["raw_watermarked_max_score"]) >= 0.5570987654320988
    decision = _load("evidence/cycle8-margin-1010000-n64-2026-08-26/decision.json")
    assert decision["u034f_raw_watermarked_detected"] == 1
    assert decision["transformed_arm_id"] == CYCLE8_U034F_LETTER_SPACE_ARM_ID
    assert release_transform_registry().rules == ()


def test_letter_space_fresh_combined_is_one_of_128_not_zero() -> None:
    primary = _load("evidence/cycle8-margin-1000000-n64-2026-08-26/detector-compare.json")
    replica = _load("evidence/cycle8-margin-1010000-n64-2026-08-26/detector-compare.json")
    combined_space = (
        primary["summaries"][CYCLE8_U034F_LETTER_SPACE_ARM_ID]["raw_watermarked_detected"]
        + replica["summaries"][CYCLE8_U034F_LETTER_SPACE_ARM_ID]["raw_watermarked_detected"]
    )
    combined_letter = (
        primary["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_detected"]
        + replica["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_detected"]
    )
    assert combined_space == 1
    assert combined_letter == 1
    assert combined_space != 0
    assert release_transform_registry().rules == ()
