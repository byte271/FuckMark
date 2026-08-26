import json
from pathlib import Path

from fuckmark.cycle8.compare import (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_LETTER_ALT_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
)
from fuckmark.cycle8.decision import PROMISING_DEVELOPMENT
from fuckmark.cycle8.mix_report import CYCLE8_MIX_SCORECARD_VERSION, build_mix_margin_scorecard
from fuckmark.cycle8_mix_hf import CYCLE8_MIX_DETECTOR_VERSION
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.seeds.ledger import (
    CYCLE8_MIX_PRIMARY_TOPIC,
    CYCLE8_MIX_REPLICATION_TOPIC,
    CYCLE8_MIX_SCALE_PRIMARY_TOPIC,
    CYCLE8_MIX_SCALE_REPLICATION_TOPIC,
)
from fuckmark.transforms.registry import release_transform_registry


def _load(relative: str) -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))


def _assert_sha256sums(relative: str) -> None:
    root = Path(__file__).resolve().parents[1] / relative
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest


def test_mix_1020000_letter_alt_is_zero_raw_with_wider_margin() -> None:
    artifact = _load("evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "2538c614a73bed360cdeebdaa60c0fa36ad34cf6995c76a120d49bd1da063ce2"
    assert artifact["seed_base"] == 1020000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MIX_PRIMARY_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MIX_DETECTOR_VERSION
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["secret_access_used_for_selection"] is False
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
    assert identity["raw_watermarked_detected"] == 64
    assert letter["raw_watermarked_detected"] == 0
    assert mix["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert mix["raw_unwatermarked_detected"] == 0
    assert mix["visible_pass_count"] == 128
    assert mix["nfc_watermarked_detected"] == 0
    assert mix["cf_strip_watermarked_detected"] == 0
    assert mix["nfkc_watermarked_detected"] == 0
    assert mix["fail_closed_identity_count"] == 0
    assert float(mix["raw_watermarked_max_score"]) < 0.52
    assert float(letter["raw_watermarked_max_score"]) < 0.53
    assert float(mix["raw_watermarked_max_score"]) < float(letter["raw_watermarked_max_score"])
    assert 0.5570987654320988 - float(mix["raw_watermarked_max_score"]) > 0.04
    decision = _load("evidence/cycle8-mix-1020000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["transformed_arm_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert decision["visible_pass_rate"] == "128/128"
    assert release_transform_registry().rules == ()


def test_mix_1030000_letter_alt_replicates_zero_raw() -> None:
    artifact = _load("evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "142809783554a890cfd68b80b560295605e068b8e0deede8ea81e3e75358eb95"
    assert artifact["seed_base"] == 1030000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MIX_REPLICATION_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MIX_DETECTOR_VERSION
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
    assert identity["raw_watermarked_detected"] == 64
    assert letter["raw_watermarked_detected"] == 0
    assert mix["raw_watermarked_detected"] == 0
    assert mix["raw_unwatermarked_detected"] == 0
    assert mix["visible_pass_count"] == 128
    assert mix["nfc_watermarked_detected"] == 0
    assert mix["cf_strip_watermarked_detected"] == 0
    assert float(mix["raw_watermarked_max_score"]) < 0.52
    assert 0.5570987654320988 - float(mix["raw_watermarked_max_score"]) > 0.04
    decision = _load("evidence/cycle8-mix-1030000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["transformed_arm_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert release_transform_registry().rules == ()


def test_mix_fresh_combined_is_zero_of_128_with_wider_margin() -> None:
    primary = _load("evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json")
    replica = _load("evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json")
    mix_detected = (
        primary["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_detected"]
        + replica["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_detected"]
    )
    mix_uw = (
        primary["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_unwatermarked_detected"]
        + replica["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_unwatermarked_detected"]
    )
    letter_detected = (
        primary["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_detected"]
        + replica["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_detected"]
    )
    mix_max = max(
        float(primary["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_max_score"]),
        float(replica["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_max_score"]),
    )
    letter_max = max(
        float(primary["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_max_score"]),
        float(replica["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_max_score"]),
    )
    assert mix_detected == 0
    assert mix_uw == 0
    assert letter_detected == 0
    assert mix_max < 0.52
    assert mix_max < letter_max
    assert 0.5570987654320988 - mix_max > 0.04
    assert release_transform_registry().rules == ()


def test_mix_margin_scorecard_is_measurement_not_confirmation() -> None:
    scorecard = _load("evidence/cycle8-mix-margin-2026-08-26/scorecard.json")
    body = {key: value for key, value in scorecard.items() if key != "scorecard_hash"}
    assert scorecard["scorecard_hash"] == sha256_json(body)
    assert scorecard["scorecard_hash"] == "cf5db6055bde17ac75a9075406513cd1ddf83eb0b7da70bb4d8a48c07bd82b76"
    assert scorecard["algorithm_version"] == CYCLE8_MIX_SCORECARD_VERSION
    assert scorecard["confirmation"] is False
    assert scorecard["freeze"] is False
    assert scorecard["product_authorized"] is False
    assert scorecard["release_registry_empty"] is True
    assert scorecard["evidence_label"] == "HYPOTHESIS"
    assert scorecard["formal_confirmation_readiness"]["ready"] is False
    assert scorecard["formal_confirmation_readiness"]["label"] == "NOT_READY"
    mix = scorecard["effectiveness"]["fresh_mix"]
    letter = scorecard["effectiveness"]["fresh_letter_x1_same_corpora"]
    spent = scorecard["effectiveness"]["letter_space_spent"]
    assert mix["rate"] == "0/128"
    assert mix["raw_watermarked_detected"] == 0
    assert mix["raw_unwatermarked_detected"] == 0
    assert float(mix["max_score"]) < 0.52
    assert float(mix["min_gap_below_threshold"]) > 0.04
    assert letter["rate"] == "0/128"
    assert spent["rate"] == "1/128"
    local = _load("evidence/cycle8-mix-margin-2026-08-26/local-system.json")
    local_body = {key: value for key, value in local.items() if key != "artifact_hash"}
    assert local["artifact_hash"] == sha256_json(local_body)
    assert local["visible_pass_rate"] == "3/3"
    assert local["cli_identity"] is True
    rebuilt = build_mix_margin_scorecard(local=local)
    assert rebuilt["scorecard_hash"] == scorecard["scorecard_hash"]
    assert release_transform_registry().rules == ()
    sums = (
        Path(__file__).resolve().parents[1] / "evidence/cycle8-mix-margin-2026-08-26/SHA256SUMS.txt"
    ).read_text(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "evidence/cycle8-mix-margin-2026-08-26"
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest


def test_mix_1040000_letter_alt_is_zero_raw() -> None:
    artifact = _load("evidence/cycle8-mix-1040000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "46ddefff3200de9d45c919761d3cb4f842b1ffa7f5404542b0aed571cfbbdf7b"
    assert artifact["seed_base"] == 1040000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MIX_SCALE_PRIMARY_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MIX_DETECTOR_VERSION
    mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    assert mix["raw_watermarked_detected"] == 0
    assert mix["raw_unwatermarked_detected"] == 0
    assert letter["raw_watermarked_detected"] == 0
    assert mix["visible_pass_count"] == 128
    assert mix["nfc_watermarked_detected"] == 0
    assert mix["cf_strip_watermarked_detected"] == 0
    assert mix["nfkc_watermarked_detected"] == 0
    assert mix["fail_closed_identity_count"] == 0
    assert float(mix["raw_watermarked_max_score"]) < 0.52
    assert 0.5570987654320988 - float(mix["raw_watermarked_max_score"]) > 0.03
    decision = _load("evidence/cycle8-mix-1040000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["transformed_arm_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert release_transform_registry().rules == ()
    _assert_sha256sums("evidence/cycle8-mix-1040000-n64-2026-08-26")


def test_mix_1050000_letter_alt_is_zero_raw() -> None:
    artifact = _load("evidence/cycle8-mix-1050000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "157572031cd0d4cbcc26345f3b33e79b5ca7154cc4365c0d62086c7e03e17575"
    assert artifact["seed_base"] == 1050000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_MIX_SCALE_REPLICATION_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_MIX_DETECTOR_VERSION
    mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    assert mix["raw_watermarked_detected"] == 0
    assert mix["raw_unwatermarked_detected"] == 0
    assert letter["raw_watermarked_detected"] == 0
    assert mix["visible_pass_count"] == 128
    assert mix["nfc_watermarked_detected"] == 0
    assert mix["cf_strip_watermarked_detected"] == 0
    assert mix["nfkc_watermarked_detected"] == 0
    assert mix["fail_closed_identity_count"] == 0
    assert float(mix["raw_watermarked_max_score"]) < 0.52
    assert 0.5570987654320988 - float(mix["raw_watermarked_max_score"]) > 0.04
    assert identity["raw_unwatermarked_detected"] == 2
    decision = _load("evidence/cycle8-mix-1050000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["transformed_arm_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert release_transform_registry().rules == ()
    _assert_sha256sums("evidence/cycle8-mix-1050000-n64-2026-08-26")


def test_mix_fresh_three_corpus_combined_is_zero_of_192() -> None:
    artifacts = [
        _load("evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json"),
        _load("evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json"),
        _load("evidence/cycle8-mix-1040000-n64-2026-08-26/detector-compare.json"),
    ]
    mix_detected = sum(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_detected"] for artifact in artifacts)
    mix_uw = sum(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_unwatermarked_detected"] for artifact in artifacts)
    mix_max = max(float(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_max_score"]) for artifact in artifacts)
    assert mix_detected == 0
    assert mix_uw == 0
    assert mix_max < 0.52
    assert 0.5570987654320988 - mix_max > 0.03
    assert release_transform_registry().rules == ()


def test_mix_fresh_four_corpus_combined_is_zero_of_256() -> None:
    artifacts = [
        _load("evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json"),
        _load("evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json"),
        _load("evidence/cycle8-mix-1040000-n64-2026-08-26/detector-compare.json"),
        _load("evidence/cycle8-mix-1050000-n64-2026-08-26/detector-compare.json"),
    ]
    mix_detected = sum(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_detected"] for artifact in artifacts)
    mix_uw = sum(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_unwatermarked_detected"] for artifact in artifacts)
    letter_detected = sum(artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_detected"] for artifact in artifacts)
    mix_max = max(float(artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]["raw_watermarked_max_score"]) for artifact in artifacts)
    letter_max = max(float(artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]["raw_watermarked_max_score"]) for artifact in artifacts)
    assert mix_detected == 0
    assert mix_uw == 0
    assert letter_detected == 0
    assert mix_max < 0.52
    assert mix_max < letter_max
    assert 0.5570987654320988 - mix_max > 0.03
    assert release_transform_registry().rules == ()


