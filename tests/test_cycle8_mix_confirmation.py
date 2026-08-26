import json
from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.compare import (
    CYCLE8_BENCHMARK_ARM_IDS,
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_LETTER_ALT_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
)
from fuckmark.cycle8.mix_confirmation import (
    CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION,
    build_mix_confirmation_scorecard,
)
from fuckmark.cycle8.mix_freeze import (
    CYCLE8_MIX_CONFIRMATION_DETECTOR_VERSION,
    CYCLE8_MIX_FREEZE_VERSION,
    assert_cycle8_mix_confirmation_generation_seed,
    mix_freeze_hash,
)
from fuckmark.cycle8_mix_confirmation_hf import main as mix_confirmation_main
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.seeds.ledger import (
    CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
    CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
)
from fuckmark.transforms.registry import release_transform_registry


_THRESHOLD = 0.5570987654320988
_SCORECARD_HASH = "a4911189af7f38d34252452821d90df1188bfe05025fe33c028c4b670eecbcce"
_FREEZE_HASH = "2286aa201bd9cb70136f2895740489136aa1ba7cfd9471c6e233fe201af41986"
_CORPORA = (
    (
        830000,
        "evidence/cycle8-mix-confirmation-830000-n64-2026-08-26",
        "b237512f7250b50bfb87c5f2aec60a01689e185533028ac73c3f7ee1201e02eb",
        CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
        0.5195995038100301,
        2,
    ),
    (
        840000,
        "evidence/cycle8-mix-confirmation-840000-n64-2026-08-26",
        "5fef030650a75b371708b88dee328391db4649ab3bc4f832e30704625582e4b0",
        CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
        0.5243003808577579,
        0,
    ),
    (
        850000,
        "evidence/cycle8-mix-confirmation-850000-n64-2026-08-26",
        "25b7519c4eba50f0094b5314fe0f8d9b9086b1abb5cb78e2ee24c12a0b9a8b6a",
        CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
        0.5169476454687723,
        0,
    ),
)


def _load(relative: str) -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))


def _assert_sha256sums(relative: str) -> None:
    root = Path(__file__).resolve().parents[1] / relative
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        assert sha256_file(root / name) == digest


def test_mix_confirmation_corpora_are_zero_raw_once() -> None:
    mix_detected = 0
    mix_uw = 0
    letter_detected = 0
    visible_wm = 0
    identity_uw = 0
    mix_max = None
    letter_max = None
    token_max = 0
    for seed_base, directory, artifact_hash, topic, expected_max, expected_identity_uw in _CORPORA:
        artifact = _load(f"{directory}/detector-compare.json")
        body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
        assert artifact["artifact_hash"] == sha256_json(body)
        assert artifact["artifact_hash"] == artifact_hash
        assert artifact["seed_base"] == seed_base
        assert artifact["pair_count"] == 64
        assert artifact["topic"] == topic
        assert artifact["algorithm_version"] == CYCLE8_MIX_CONFIRMATION_DETECTOR_VERSION
        assert artifact["model"] == "openai-community/gpt2"
        assert artifact["model_revision"] == "607a30d783dfa663caf39e06633721c8d4cfcd7e"
        assert artifact["threshold"] == _THRESHOLD
        assert artifact["detector_access_used_for_selection"] is False
        assert artifact["secret_access_used_for_selection"] is False
        identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
        letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
        mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
        assert mix["raw_watermarked_detected"] == 0
        assert mix["raw_unwatermarked_detected"] == 0
        assert letter["raw_watermarked_detected"] == 0
        assert letter["raw_unwatermarked_detected"] == 0
        assert mix["visible_pass_count"] == 128
        assert mix["fail_closed_identity_count"] == 0
        assert mix["nfc_watermarked_detected"] == 0
        assert mix["cf_strip_watermarked_detected"] == 0
        assert mix["nfkc_watermarked_detected"] == 0
        assert mix["nfkc_cf_strip_watermarked_detected"] == 0
        assert mix["ws_collapse_watermarked_detected"] == 0
        assert mix["ws_collapse_nfkc_cf_strip_watermarked_detected"] == 0
        assert float(mix["raw_watermarked_max_score"]) == expected_max
        assert float(mix["raw_watermarked_max_score"]) < _THRESHOLD
        assert identity["raw_unwatermarked_detected"] == expected_identity_uw
        mix_detected += int(mix["raw_watermarked_detected"])
        mix_uw += int(mix["raw_unwatermarked_detected"])
        letter_detected += int(letter["raw_watermarked_detected"])
        identity_uw += int(identity["raw_unwatermarked_detected"])
        mix_score = float(mix["raw_watermarked_max_score"])
        letter_score = float(letter["raw_watermarked_max_score"])
        mix_max = mix_score if mix_max is None else max(mix_max, mix_score)
        letter_max = letter_score if letter_max is None else max(letter_max, letter_score)
        domains: dict[str, int] = {}
        for row in artifact["scored_rows"]:
            if row["arm_id"] != CYCLE8_LETTER_ALT_ARM_ID or row["label"] != "watermarked":
                continue
            visible_wm += int(bool(row["geometry"]["visible_ok"]))
            domains[row["domain"]] = domains.get(row["domain"], 0) + int(bool(row["sanitizers"]["raw"]["detected"]))
            token_max = max(token_max, int(row["geometry"]["tokenizer"]["transformed_token_count"]))
        assert set(domains) == {
            "conversational_prose",
            "general_explanatory",
            "structured_instructional",
            "technical_explanation",
        }
        assert all(value == 0 for value in domains.values())
        decision = _load(f"{directory}/decision.json")
        assert decision["u034f_raw_watermarked_detected"] == 0
        assert decision["transformed_arm_id"] == CYCLE8_LETTER_ALT_ARM_ID
        assert decision["visible_pass_rate"] == "128/128"
        _assert_sha256sums(directory)
    assert mix_detected == 0
    assert mix_uw == 0
    assert letter_detected == 0
    assert visible_wm == 192
    assert identity_uw == 2
    assert mix_max == 0.5243003808577579
    assert letter_max == 0.5244247453791022
    assert _THRESHOLD - mix_max == 0.03279838457434092
    assert token_max == 612
    assert release_transform_registry().rules == ()
    assert process_text("I do not agree.") == "I do not agree."
    assert CYCLE8_LETTER_ALT_ARM_ID not in CYCLE8_BENCHMARK_ARM_IDS


def test_mix_confirmation_scorecard_is_verified_zero_of_192() -> None:
    scorecard = _load("evidence/cycle8-mix-confirmation-2026-08-26/scorecard.json")
    body = {key: value for key, value in scorecard.items() if key != "scorecard_hash"}
    assert scorecard["scorecard_hash"] == sha256_json(body)
    assert scorecard["scorecard_hash"] == _SCORECARD_HASH
    rebuilt = build_mix_confirmation_scorecard()
    assert rebuilt == scorecard
    assert scorecard["algorithm_version"] == CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
    assert scorecard["freeze_version"] == CYCLE8_MIX_FREEZE_VERSION
    assert scorecard["mechanism_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert scorecard["confirmation"] is True
    assert scorecard["run_once"] is True
    assert scorecard["rerun_looking_for_zero"] is False
    assert scorecard["freeze"] is True
    assert scorecard["product_authorized"] is False
    assert scorecard["release_registry_empty"] is True
    assert scorecard["evidence_label"] == "VERIFIED"
    assert scorecard["do_not_generate_950000"] is True
    mix = scorecard["effectiveness"]["transformed_wm"]
    uw = scorecard["effectiveness"]["transformed_uw"]
    letter = scorecard["effectiveness"]["letter_x1_same_corpora"]
    identity = scorecard["effectiveness"]["identity"]
    assert mix["rate"] == "0/192"
    assert mix["raw_watermarked_detected"] == 0
    assert uw["rate"] == "0/192"
    assert uw["raw_unwatermarked_detected"] == 0
    assert letter["rate"] == "0/192"
    assert letter["raw_watermarked_detected"] == 0
    assert identity["raw_watermarked_detected"] == 185
    assert identity["raw_unwatermarked_detected"] == 2
    assert float(mix["max_score"]) == 0.5243003808577579
    assert float(mix["min_gap_below_threshold"]) == 0.03279838457434092
    assert scorecard["visibility"]["watermarked_pass_rate"] == "192/192"
    sanitizers = scorecard["durability"]["sanitizer_watermarked_detected"]
    assert scorecard["durability"]["frozen_sanitizers_match_raw"] is True
    assert all(value == 0 for value in sanitizers.values())
    assert mix_freeze_hash() == _FREEZE_HASH
    _assert_sha256sums("evidence/cycle8-mix-confirmation-2026-08-26")
    assert release_transform_registry().rules == ()
    assert process_text("I do not agree.") == "I do not agree."


def test_mix_confirmation_refuses_rerun() -> None:
    with pytest.raises(ValueError, match="already generated"):
        assert_cycle8_mix_confirmation_generation_seed(830000)
    with pytest.raises(ValueError, match="already exists"):
        mix_confirmation_main(["--seed-base", "830000", "--pair-count", "64"])
