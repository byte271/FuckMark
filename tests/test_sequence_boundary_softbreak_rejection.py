import json
from pathlib import Path

from fuckmark.hashing import sha256_json


def test_sequence_boundary_softbreak_rejection_replays_and_keeps_no_implementation() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "specs" / "fuckmark-sequence-boundary-softbreak-v1.rejection.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in record.items() if key != "rejection_hash"}
    assert record["rejection_hash"] == sha256_json(payload)
    assert record["decision"] == "REJECTED_KILL_CRITERION_EFFECTIVENESS"
    assert record["implementation_retained"] is False
    assert record["selection_detector_access_observed"] is False
    assert record["selection_secret_access_observed"] is False
    assert record["candidate"]["github_workflow_run_id"] == 32554548758
    assert record["candidate"]["workflow_artifact_id"] == 9471417449
    comparisons = {row["policy"]: row for row in record["watermarked_policy_comparison"]}
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B4"]["baseline_detected_count"] == 3
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B4"]["candidate_detected_count"] == 3
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B6"]["baseline_detected_count"] == 1
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B6"]["candidate_detected_count"] == 1
    assert not (root / "fuckmark" / "transforms" / "sequence_boundaries.py").exists()
    assert not (root / "fuckmark" / "sequence_boundary_opportunity_audit.py").exists()
