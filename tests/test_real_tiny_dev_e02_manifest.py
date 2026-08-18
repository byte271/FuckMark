import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-e02-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_real_tiny_dev_e02_manifest_is_self_hashed_and_development_only() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-e02-evidence-record-v1"
    assert evidence["evidence_kind"] == "development-pristine-detectability"
    assert evidence["scientific_scope"].startswith("DEVELOPMENT_ONLY;")
    assert "not M3 complete" in evidence["scientific_scope"]
    assert "not M6 readiness" in evidence["scientific_scope"]


def test_real_tiny_dev_e02_manifest_binds_successful_workflow_artifact() -> None:
    evidence = _evidence()
    source = evidence["source"]
    bindings = evidence["bindings"]
    assert source["head_commit"] == "4f4189ab9f09f1533713b2df7f67b35a5605cdfb"
    assert source["workflow_run_id"] == 32088935838
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_id"] == 9307861756
    assert source["artifact_zip_sha256"] == (
        "cd2f9b647de2f1cfea754b2ef2e4baae79abf394b7c3dae6d17beb439b288b87"
    )
    assert source["corpus_json_sha256"] == (
        "ee09527d06abc58e612f7157b69908d5abe06101865714ce13a1287d1f0d7664"
    )
    assert source["detector_json_sha256"] == (
        "086770a9d8e9e7d639bad6c04365f1a239042ae2799b729831199d704188ed99"
    )
    assert source["e02_json_sha256"] == (
        "93ec9830d5300cb3482264bbcc239a82c275af5c741643e18856e74af7e35d7b"
    )
    assert bindings["e02_artifact_hash"] == (
        "11bcbc69b953cc703983bfbb2a38933f63c4334263a30c457de479ce3c967ef9"
    )


def test_real_tiny_dev_e02_manifest_records_both_mean_families_and_wide_uncertainty() -> None:
    evaluation = _evidence()["evaluation"]
    assert evaluation["positive_count"] == 4
    assert evaluation["negative_count"] == 4
    families = evaluation["families"]
    assert [value["detector_family"] for value in families] == ["mean", "weighted_mean"]
    for family in families:
        assert family["status"] == "PASS"
        assert family["auc"] == 1.0
        assert [value["target_fpr"] for value in family["operating_points"]] == [0.05, 0.01]
        for point in family["operating_points"]:
            assert point["positive_detected_count"] == 4
            assert point["negative_detected_count"] == 0
            assert point["tpr"] == 1.0
            assert point["evaluation_fpr"] == 0.0
            assert point["tpr_ci95"][0] < 0.4
            assert point["evaluation_fpr_ci95"][1] > 0.6


def test_real_tiny_dev_e02_manifest_does_not_claim_bayesian_or_generalization() -> None:
    limitations = _evidence()["limitations"]
    assert any("Bayesian detector remains required for M3" in value for value in limitations)
    assert any("does not establish model, tokenizer, length, key, or adapter generalization" in value for value in limitations)
