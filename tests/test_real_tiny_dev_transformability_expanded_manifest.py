import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-transformability-expanded-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_expanded_transformability_manifest_is_self_hashed_and_diagnostic_only() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-transformability-expanded-evidence-v1"
    assert evidence["evidence_kind"] == "development-transformability-readiness-diagnostic"
    assert "not a scientific weakness result" in evidence["scientific_scope"]
    assert "not M6 readiness" in evidence["scientific_scope"]
    assert "not a frozen spec threshold" in evidence["scientific_scope"]


def test_expanded_transformability_manifest_binds_successful_real_run() -> None:
    evidence = _evidence()
    source = evidence["source"]
    audit = evidence["audit"]
    assert source["head_commit"] == "81812500abbaf7a4423267fc82cbf554962d1a32"
    assert source["workflow_run_id"] == 32091281960
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_id"] == 9308598577
    assert source["artifact_zip_sha256"] == (
        "f8fedef712dde2229fd731a322178a57bb88f6ea4f485e2302745cba48cc10a6"
    )
    assert source["corpus_json_sha256"] == (
        "ee09527d06abc58e612f7157b69908d5abe06101865714ce13a1287d1f0d7664"
    )
    assert source["transformability_json_sha256"] == (
        "1671625e33b3de9fb083711fddadc39f282b3de1673d93af37cc409bbedf5e36"
    )
    assert audit["audit_hash"] == "3302c98344e315f3e02d8e46f2352c56efd5681fe11de4422336659694e2668c"
    assert audit["ruleset_hash"] == "d106bba92b97d3423396fb1d75197bb32f58864051e93360a7fc07fc7cc2499b"


def test_expanded_transformability_manifest_clears_all_four_real_sources() -> None:
    audit = _evidence()["audit"]
    assert audit["status"] == "READY"
    assert audit["expected_source_count"] == 4
    assert audit["transformable_source_count"] == 4
    assert audit["minimum_independent_candidates_per_source"] == 4
    rows = audit["rows"]
    assert [value["candidate_count"] for value in rows] == [6, 6, 11, 9]
    assert [value["independent_candidate_count"] for value in rows] == [6, 6, 11, 9]
    assert all(
        value["independent_candidate_count"] >= audit["minimum_independent_candidates_per_source"]
        for value in rows
    )


def test_expanded_transformability_manifest_preserves_pre_expansion_blocker() -> None:
    comparison = _evidence()["comparison_to_pre_expansion_audit"]
    assert comparison["pre_expansion_audit_hash"] == (
        "69204934ce20c3a6a2de7c41b672a05ed96459cd6498064d2b0de2962afe0753"
    )
    assert comparison["pre_expansion_transformable_source_count"] == 0
    assert comparison["expanded_transformable_source_count"] == 4
    assert comparison["candidate_counts_before"] == [0, 0, 1, 0]
    assert comparison["independent_candidate_counts_after"] == [6, 6, 11, 9]
