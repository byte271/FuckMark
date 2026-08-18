import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_real_tiny_dev_evidence_is_self_hashed_and_scoped() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-evidence-v1"
    assert evidence["evidence_kind"] == "development-corpus-generation"
    assert evidence["scientific_scope"] == (
        "DEV_KEYS-only TinyDev generation prerequisite; not M6 readiness or a confirmatory result"
    )


def test_real_tiny_dev_evidence_binds_successful_source_run() -> None:
    source = _evidence()["source"]
    assert source["generator_head_commit"] == "9b829b3e594eeb1335d2c0509124deae6e7c0057"
    assert source["merged_main_commit"] == "33b4a8c10b9382dcc1068baacb99b30e67113a92"
    assert source["workflow_run_id"] == 32084697518
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_zip_sha256"] == (
        "3fc78ee29929e9a394fa0615db80422ffc6a55ae967b989e522f23175bec6c0f"
    )
    assert source["artifact_json_sha256"] == (
        "ee09527d06abc58e612f7157b69908d5abe06101865714ce13a1287d1f0d7664"
    )


def test_real_tiny_dev_evidence_records_frozen_corpus_shape() -> None:
    corpus = _evidence()["corpus"]
    assert corpus["algorithm_version"] == "tiny-dev-corpus-v2"
    assert corpus["prompt_count"] == 104
    assert corpus["sample_count"] == 208
    assert corpus["matched_pair_count"] == 104
    assert corpus["target_length"] == 64
    assert corpus["calibration_pairs_per_domain"] == 25
    assert corpus["attack_pairs_per_domain"] == 1
    assert corpus["required_domains"] == [
        "general_explanatory",
        "technical_explanation",
        "conversational_prose",
        "structured_instructional",
    ]
    assert corpus["required_splits"] == ["threshold_calibration", "attack_development"]


def test_real_tiny_dev_evidence_records_pinned_runtime_identity() -> None:
    runtime = _evidence()["runtime"]
    assert runtime["model_id"] == "openai-community/gpt2"
    assert runtime["model_revision"] == "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    assert runtime["tokenizer_revision"] == "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    assert runtime["seed_policy_id"] == "tiny-dev-paired-seed-v1"
    assert runtime["seed_base"] == 401000
    assert runtime["watermark_key_split"] == "DEV_KEYS"
    assert runtime["backend_version"] == (
        "transformers=5.16.0.dev0;torch=2.13.0+cpu;device=cpu;"
        "revision=607a30d783dfa663caf39e06633721c8d4cfcd7e"
    )


def test_real_tiny_dev_evidence_records_independent_integrity_checks() -> None:
    execution = _evidence()["execution"]
    verification = _evidence()["verification"]
    assert execution["pair_attempt_offset_counts"] == {"0": 99, "1": 4, "2": 1}
    assert execution["maximum_pair_attempt_offset"] == 2
    assert execution["exact_generation_token_track_count"] == 208
    assert execution["text_only_track_count"] == 208
    assert execution["text_only_exact_token_match_count"] == 197
    assert all(verification.values())
