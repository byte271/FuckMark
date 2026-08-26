import json
from pathlib import Path

from fuckmark.cycle8.compare import (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_LETTER_ARM_IDS,
    CYCLE8_U034F_LETTER_ARM_ID,
)
from fuckmark.cycle8.decision import PROMISING_DEVELOPMENT, classify_scale_detector_compare
from fuckmark.cycle8_letter_hf import CYCLE8_LETTER_DETECTOR_VERSION
from fuckmark.hashing import sha256_json
from fuckmark.seeds.ledger import CYCLE8_LETTER_EXPLORATORY_TOPIC
from fuckmark.transforms.registry import release_transform_registry


def _load(relative: str) -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))


def _assert_letter_zero(artifact: dict[str, object], *, seed_base: int, pair_count: int, visible_total: int) -> None:
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body)
    assert artifact["seed_base"] == seed_base
    assert artifact["pair_count"] == pair_count
    assert artifact["algorithm_version"] == CYCLE8_LETTER_DETECTOR_VERSION
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["secret_access_used_for_selection"] is False
    assert tuple(artifact["arm_ids"]) == CYCLE8_LETTER_ARM_IDS
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
    assert identity["raw_watermarked_detected"] >= pair_count - 2
    assert letter["raw_watermarked_detected"] == 0
    assert letter["raw_unwatermarked_detected"] == 0
    assert letter["cf_strip_watermarked_detected"] == 0
    assert letter["nfkc_watermarked_detected"] == 0
    assert letter["ws_collapse_watermarked_detected"] == 0
    assert letter["nfc_watermarked_detected"] == 0
    assert letter["visible_pass_count"] == visible_total
    assert letter["visible_total_count"] == visible_total
    assert letter["fail_closed_identity_count"] == 0
    assert float(letter["raw_watermarked_max_score"]) < 0.5570987654320988
    assert release_transform_registry().rules == ()


def test_letter_diagnostic_960000_clears_space_residual_without_unseen_claim() -> None:
    artifact = _load("evidence/cycle8-letter-960000-2026-08-26/detector-compare.json")
    assert artifact["artifact_hash"] == "357293589806c8df978d7d96770c3bb372b541c869b83b4be4941ed8287ecd62"
    assert artifact["topic"] == "carrier density follow-up"
    _assert_letter_zero(artifact, seed_base=960000, pair_count=16, visible_total=32)
    decision = _load("evidence/cycle8-letter-960000-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["transformed_arm_id"] == CYCLE8_U034F_LETTER_ARM_ID
    frozen_space = _load("evidence/cycle8-density-960000-2026-08-26/detector-compare.json")
    assert frozen_space["summaries"]["u034f-space-x1"]["raw_watermarked_detected"] == 1


def test_letter_diagnostic_930000_n64_is_zero_raw_on_seen_residual_corpus() -> None:
    artifact = _load("evidence/cycle8-letter-930000-n64-2026-08-26/detector-compare.json")
    assert artifact["artifact_hash"] == "bc440e8a8ffce27b4b759e0ebe46ba8bfc2b88fce896c8100add69ce56a5c89b"
    _assert_letter_zero(artifact, seed_base=930000, pair_count=64, visible_total=128)
    frozen_space = _load("evidence/cycle8-scale-930000-n64-2026-08-26/detector-compare.json")
    assert frozen_space["summaries"]["u034f-space-x1"]["raw_watermarked_detected"] == 1
    decision = classify_scale_detector_compare(artifact, transformed_arm_id=CYCLE8_U034F_LETTER_ARM_ID)
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"


def test_letter_diagnostic_940000_n64_is_zero_raw_on_seen_replication_corpus() -> None:
    artifact = _load("evidence/cycle8-letter-940000-n64-2026-08-26/detector-compare.json")
    assert artifact["artifact_hash"] == "e61ae665b82936b64a6996463c5c90baf3cd0c921e49886d4896346edcc3d9f9"
    _assert_letter_zero(artifact, seed_base=940000, pair_count=64, visible_total=128)
    frozen_space = _load("evidence/cycle8-scale-940000-n64-2026-08-26/detector-compare.json")
    assert frozen_space["summaries"]["u034f-space-x1"]["raw_watermarked_detected"] == 0


def test_letter_independent_970000_n16_is_zero_raw() -> None:
    artifact = _load("evidence/cycle8-letter-970000-2026-08-26/detector-compare.json")
    assert artifact["artifact_hash"] == "d646f3ee28eb1453afdb3015deffbf2981c18d5d0d9172a2f7fa5410e3d435b5"
    assert artifact["topic"] == CYCLE8_LETTER_EXPLORATORY_TOPIC
    _assert_letter_zero(artifact, seed_base=970000, pair_count=16, visible_total=32)
    decision = _load("evidence/cycle8-letter-970000-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["visible_pass_rate"] == "32/32"
    assert release_transform_registry().rules == ()


def test_letter_independent_970000_n64_is_zero_raw() -> None:
    artifact = _load("evidence/cycle8-letter-970000-n64-2026-08-26/detector-compare.json")
    assert artifact["artifact_hash"] == "6e3c67efc4ece996d8dd8389b26614746ed6488b5f0f466c7a8157ef5af38c1b"
    assert artifact["topic"] == CYCLE8_LETTER_EXPLORATORY_TOPIC
    _assert_letter_zero(artifact, seed_base=970000, pair_count=64, visible_total=128)
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    assert identity["raw_watermarked_detected"] == 64
    assert identity["raw_unwatermarked_detected"] == 1
    decision = _load("evidence/cycle8-letter-970000-n64-2026-08-26/decision.json")
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["visible_pass_rate"] == "128/128"
    prefix = _load("evidence/cycle8-letter-970000-2026-08-26/detector-compare.json")
    prefix_hashes = [
        row["arms"][CYCLE8_IDENTITY_ARM_ID]["source_text_hash"]
        for row in prefix["geometry_rows"]
    ]
    expanded_hashes = [
        row["arms"][CYCLE8_IDENTITY_ARM_ID]["source_text_hash"]
        for row in artifact["geometry_rows"]
    ]
    assert prefix_hashes == expanded_hashes[: len(prefix_hashes)]
    assert release_transform_registry().rules == ()


def test_letter_experimental_zero_of_192_is_128_seen_plus_64_independent() -> None:
    tally = _load("evidence/cycle8-letter-experimental-0-of-192-2026-08-26/tally.json")
    body = {key: value for key, value in tally.items() if key != "artifact_hash"}
    assert tally["artifact_hash"] == sha256_json(body)
    assert tally["artifact_hash"] == "19b53b1c8e6e41fe23a12b0f7dd7f556e40facc7c4d7bf95ff9bcec3ab3c0f88"
    assert tally["pair_count_total"] == 192
    assert tally["seen_pair_count"] == 128
    assert tally["independent_pair_count"] == 64
    assert tally["letter_raw_watermarked_detected_total"] == 0
    assert tally["letter_raw_unwatermarked_detected_total"] == 0
    assert tally["confirmation"] is False
    assert tally["freeze"] is False
    assert tally["product_authorized"] is False
    seen_930 = _load("evidence/cycle8-letter-930000-n64-2026-08-26/detector-compare.json")
    seen_940 = _load("evidence/cycle8-letter-940000-n64-2026-08-26/detector-compare.json")
    independent = _load("evidence/cycle8-letter-970000-n64-2026-08-26/detector-compare.json")
    assert seen_930["artifact_hash"] == "bc440e8a8ffce27b4b759e0ebe46ba8bfc2b88fce896c8100add69ce56a5c89b"
    assert seen_940["artifact_hash"] == "e61ae665b82936b64a6996463c5c90baf3cd0c921e49886d4896346edcc3d9f9"
    assert independent["artifact_hash"] == "6e3c67efc4ece996d8dd8389b26614746ed6488b5f0f466c7a8157ef5af38c1b"
    corpora = tally["corpora"]
    assert corpora[0]["kind"] == "seen_diagnostic" and corpora[0]["artifact_hash"] == seen_930["artifact_hash"]
    assert corpora[1]["kind"] == "seen_diagnostic" and corpora[1]["artifact_hash"] == seen_940["artifact_hash"]
    assert corpora[2]["kind"] == "independent" and corpora[2]["artifact_hash"] == independent["artifact_hash"]
    assert release_transform_registry().rules == ()
