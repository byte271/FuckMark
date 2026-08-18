import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-detectors-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_real_tiny_dev_detector_manifest_is_self_hashed_and_development_only() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-detector-evidence-v1"
    assert evidence["scientific_scope"] == (
        "DEV_KEYS-only TinyDev Mean/Weighted Mean fixed-FPR evidence; "
        "not M6 readiness and not confirmatory evidence"
    )
    assert evidence["detector_artifact"]["scientific_status"] == "DEVELOPMENT_ONLY"


def test_real_tiny_dev_detector_manifest_binds_source_run_and_reproduced_corpus() -> None:
    evidence = _evidence()
    source = evidence["source"]
    corpus = evidence["corpus"]
    assert source["source_head_commit"] == "4e69de04f1121c7cffcca2d9b032209006f8cfca"
    assert source["workflow_run_id"] == 32087405132
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_id"] == 9307352458
    assert source["artifact_zip_sha256"] == (
        "d1174d706aa4a0b5e5124a8e8c457423cea32bb2e4d3b3161cf546c503e282d9"
    )
    assert source["corpus_json_sha256"] == (
        "ee09527d06abc58e612f7157b69908d5abe06101865714ce13a1287d1f0d7664"
    )
    assert source["detector_json_sha256"] == (
        "086770a9d8e9e7d639bad6c04365f1a239042ae2799b729831199d704188ed99"
    )
    assert corpus["artifact_hash"] == (
        "42240f72e17df1a048f44197f216a0b5f30128c26e2da93afbe92820946e4561"
    )
    assert corpus["calibration_negative_count"] == 100
    assert corpus["attack_positive_count"] == 4
    assert corpus["attack_negative_count"] == 4
    assert corpus["target_length"] == 64


def test_real_tiny_dev_detector_manifest_binds_exact_runtime_and_adapter() -> None:
    evidence = _evidence()
    runtime = evidence["runtime"]
    detector = evidence["detector_artifact"]
    assert runtime["python_version"] == "3.12.13"
    assert runtime["torch_version"] == "2.13.0+cpu"
    assert runtime["transformers_version"] == "5.16.0.dev0"
    assert runtime["transformers_source_commit"] == "a61d5f9e4fc184cff66938ff6c521cc358b5e024"
    assert runtime["sampling_table_hash"] == (
        "a3e9e18ea34546849c5136cf9b06c7bfd03e50e601da14af47cd926f9e623a85"
    )
    assert detector["adapter_id"] == "huggingface-transformers-synthid"
    assert detector["adapter_config_hash"] == (
        "0d9b6e5681240db5b28123042cd2ea23ad9b5886f0c3cb80d6efbe5089cb651f"
    )
    assert detector["headline_fprs"] == [0.05, 0.01]
    assert detector["primary_fpr"] == 0.01


def test_real_tiny_dev_primary_baselines_pass_but_keep_small_n_uncertainty() -> None:
    families = _evidence()["families"]
    expected = {
        "mean": (0.5555555555555555, "ee158a3a242773fa5a7093cb422dd476a431278619930888e20c3b6d59fa74b3"),
        "weighted_mean": (0.5616883116883117, "fb518c977ed45daa128e9530e5d55989c1b6a2072f976a9ce3ebf9953311045a"),
    }
    for family_name, (threshold, threshold_hash) in expected.items():
        primary = next(
            row for row in families[family_name]["thresholds"]
            if row["target_fpr"] == 0.01
        )
        assert primary["threshold_value"] == threshold
        assert primary["threshold_hash"] == threshold_hash
        assert primary["achieved_calibration_fpr"] == 0.01
        assert primary["pristine_detected_count"] == 4
        assert primary["pristine_sample_count"] == 4
        assert primary["pristine_tpr"] == 1.0
        assert primary["baseline_status"] == "PASS"
        assert primary["pristine_tpr_interval"]["lower"] == 0.3976353643835254
        assert primary["attack_negative_detected_count"] == 0
        assert primary["attack_negative_fpr"] == 0.0
        assert primary["attack_negative_fpr_interval"]["upper"] == 0.6023646356164745
