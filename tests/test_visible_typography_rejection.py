import json
from pathlib import Path

from fuckmark.hashing import sha256_json


def test_visible_typography_rejection_record_replays_and_keeps_no_implementation() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "specs" / "fuckmark-visible-typography-v1.rejection.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in record.items() if key != "rejection_hash"}
    assert record["rejection_hash"] == sha256_json(payload)
    assert record["decision"] == "REJECTED_KILL_CRITERION_EFFECTIVENESS"
    assert record["implementation_retained"] is False
    assert record["selection_detector_access_observed"] is False
    assert record["selection_secret_access_observed"] is False
    assert record["candidate"]["github_workflow_run_id"] == 32549437360
    assert record["candidate"]["workflow_artifact_id"] == 9470010666
    comparisons = {row["policy"]: row for row in record["watermarked_policy_comparison"]}
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B6"]["baseline_detected_count"] == 1
    assert comparisons["CONTEXT_SURVIVAL_BEAM_B6"]["candidate_detected_count"] == 2
    assert not (root / "fuckmark" / "transforms" / "visible_typography.py").exists()
