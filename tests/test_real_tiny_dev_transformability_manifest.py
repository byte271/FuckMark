import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-transformability-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_real_tiny_dev_transformability_manifest_is_self_hashed_and_diagnostic_only() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-transformability-evidence-v1"
    assert evidence["evidence_kind"] == "development-transformability-readiness-diagnostic"
    assert "not a scientific weakness result" in evidence["scientific_scope"]
    assert "not M6 readiness" in evidence["scientific_scope"]
    assert "not a frozen spec threshold" in evidence["scientific_scope"]


def test_real_tiny_dev_transformability_manifest_binds_successful_run() -> None:
    evidence = _evidence()
    source = evidence["source"]
    audit = evidence["audit"]
    assert source["head_commit"] == "03f086a729015bbfd622aff95eae5e2d0d525f6c"
    assert source["workflow_run_id"] == 32089743819
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_id"] == 9308058057
    assert source["artifact_zip_sha256"] == (
        "6d92f9d7585c9bd889ac4b0c89783901c9aff15b20ca752c55ecec5f62c96f7d"
    )
    assert source["transformability_json_sha256"] == (
        "4fbe0b62a03e431e62c5c910b68c5e9a890326b0dff08b6edcce9570d4dc6f78"
    )
    assert audit["audit_hash"] == "69204934ce20c3a6a2de7c41b672a05ed96459cd6498064d2b0de2962afe0753"


def test_real_tiny_dev_transformability_manifest_preserves_fail_closed_source_coverage() -> None:
    audit = _evidence()["audit"]
    assert audit["status"] == "INSUFFICIENT_CANDIDATES"
    assert audit["expected_source_count"] == 4
    assert audit["transformable_source_count"] == 0
    assert audit["minimum_independent_candidates_per_source"] == 4
    rows = audit["rows"]
    assert len(rows) == 4
    assert [value["independent_candidate_count"] for value in rows] == [0, 0, 1, 0]
    structured = next(value for value in rows if value["domain"] == "structured_instructional")
    assert structured["candidate_count"] == 1
    assert structured["rule_ids"] == ["contract-do-not"]
    assert all(
        value["independent_candidate_count"] < audit["minimum_independent_candidates_per_source"]
        for value in rows
    )
