import json
from pathlib import Path

from fuckmark.cycle8.benchmark import enrich_detector_artifact
from fuckmark.cycle8.compare import CYCLE8_U034F_LETTER_ARM_ID, CYCLE8_U034F_SPACE_ARM_ID
from fuckmark.cycle8_benchmark_hf import CYCLE8_BENCHMARK_DETECTOR_VERSION
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.seeds.ledger import CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC
from fuckmark.transforms.registry import release_transform_registry


def _load(relative: str) -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))


def test_benchmark_980000_letter_and_space_are_zero_raw() -> None:
    artifact = _load("evidence/cycle8-letter-benchmark-980000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "f150143125024450210e725d2ada643e5e31abcf90e3a3755481244da6089f67"
    assert artifact["seed_base"] == 980000
    assert artifact["pair_count"] == 64
    assert artifact["topic"] == CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_BENCHMARK_DETECTOR_VERSION
    assert artifact["detector_access_used_for_selection"] is False
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    space = artifact["summaries"][CYCLE8_U034F_SPACE_ARM_ID]
    identity = artifact["summaries"]["identity"]
    assert letter["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert letter["cf_strip_watermarked_detected"] == 0
    assert letter["nfc_watermarked_detected"] == 0
    assert letter["visible_pass_count"] == 128
    assert letter["fail_closed_identity_count"] == 0
    assert float(letter["raw_watermarked_max_score"]) < 0.5570987654320988
    assert space["raw_watermarked_detected"] == 0
    assert identity["raw_watermarked_detected"] >= 60
    stats = enrich_detector_artifact(artifact, transformed_arm_id=CYCLE8_U034F_LETTER_ARM_ID)
    assert stats["closest_watermarked_row"]["detected"] is False
    assert stats["raw_watermarked_scores"]["max_gap_below_threshold"] > 0
    assert release_transform_registry().rules == ()


def test_benchmark_990000_letter_is_zero_and_space_has_one_residual() -> None:
    artifact = _load("evidence/cycle8-letter-benchmark-990000-n64-2026-08-26/detector-compare.json")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["artifact_hash"] == "b30cbb3f53425d40d1f8a15e556b9072b6ab37a6c799a9e078ea5e6f03f74f04"
    assert artifact["seed_base"] == 990000
    assert artifact["pair_count"] == 64
    assert artifact["algorithm_version"] == CYCLE8_BENCHMARK_DETECTOR_VERSION
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    space = artifact["summaries"][CYCLE8_U034F_SPACE_ARM_ID]
    identity = artifact["summaries"]["identity"]
    assert letter["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert letter["visible_pass_count"] == 128
    assert float(letter["raw_watermarked_max_score"]) < 0.5570987654320988
    assert space["raw_watermarked_detected"] == 1
    assert identity["raw_watermarked_detected"] == 64
    assert release_transform_registry().rules == ()


def test_letter_system_benchmark_scorecard_is_measurement_not_confirmation() -> None:
    scorecard = _load("evidence/cycle8-letter-system-benchmark-2026-08-26/scorecard.json")
    body = {key: value for key, value in scorecard.items() if key != "scorecard_hash"}
    assert scorecard["scorecard_hash"] == sha256_json(body)
    assert scorecard["confirmation"] is False
    assert scorecard["freeze"] is False
    assert scorecard["product_authorized"] is False
    assert scorecard["release_registry_empty"] is True
    assert scorecard["evidence_label"] == "HYPOTHESIS"
    assert scorecard["formal_confirmation_readiness"]["ready"] is False
    assert scorecard["formal_confirmation_readiness"]["label"] == "NOT_READY"
    letter = scorecard["effectiveness"]["fresh_letter_x1"]
    space = scorecard["effectiveness"]["fresh_space_x1_same_corpora"]
    experimental = scorecard["effectiveness"]["experimental_0_of_192"]
    assert letter["rate"] == "0/128"
    assert letter["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert float(letter["max_score"]) < 0.5570987654320988
    assert float(letter["min_gap_below_threshold"]) > 0
    assert space["rate"] == "1/128"
    assert experimental["rate"] == "0/192"
    assert experimental["seen_pairs"] == 128
    assert experimental["independent_pairs"] == 64
    assert scorecard["visibility"]["fixture_pass_rate"] == "21/21"
    assert scorecard["visibility"]["fixture_failures"] == []
    assert scorecard["safety"]["protected_pass_rate"] == "21/21"
    assert scorecard["reproducibility"]["deterministic_output"] is True
    local = _load("evidence/cycle8-letter-system-benchmark-2026-08-26/local-system.json")
    local_body = {key: value for key, value in local.items() if key != "artifact_hash"}
    assert local["artifact_hash"] == sha256_json(local_body)
    assert local["visible_pass_rate"] == "21/21"
    assert local["cli_identity"] is True
    assert release_transform_registry().rules == ()
    sums = (Path(__file__).resolve().parents[1] / "evidence/cycle8-letter-system-benchmark-2026-08-26/SHA256SUMS.txt").read_text(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "evidence/cycle8-letter-system-benchmark-2026-08-26"
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest
