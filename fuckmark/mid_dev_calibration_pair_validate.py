from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_pair import build_mid_dev_calibration_pair_artifact
from .corpus.mid_dev_calibration_shards import CalibrationRole
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_merge_provenance_io import load_mid_dev_calibration_merge_provenance_json
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .hashing import sha256_json


MID_DEV_CALIBRATION_PAIR_PROVENANCE_VERSION = "mid-dev-calibration-pair-provenance-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-pair-validate")
    parser.add_argument("--select-json", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--select-merge-provenance-json", type=Path, required=True)
    parser.add_argument("--audit-merge-provenance-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    select = load_mid_dev_calibration_merged_artifact_json(args.select_json)
    audit = load_mid_dev_calibration_merged_artifact_json(args.audit_json)
    select_merge = load_mid_dev_calibration_merge_provenance_json(args.select_merge_provenance_json)
    audit_merge = load_mid_dev_calibration_merge_provenance_json(args.audit_merge_provenance_json)
    if select.readiness_hash != readiness.readiness_hash or audit.readiness_hash != readiness.readiness_hash:
        raise RuntimeError("merged calibration artifacts do not bind frozen readiness")
    if select.plan_hash != readiness.select_plan_hash:
        raise RuntimeError("CAL-SELECT merged artifact does not bind frozen SELECT plan")
    if audit.plan_hash != readiness.audit_plan_hash:
        raise RuntimeError("CAL-AUDIT merged artifact does not bind frozen AUDIT plan")
    expected_count = len(readiness.select_plan.prompt_ids)
    if expected_count != len(readiness.audit_plan.prompt_ids):
        raise RuntimeError("frozen readiness role counts differ")
    if len(select.samples) != expected_count or len(audit.samples) != expected_count:
        raise RuntimeError("merged calibration sample count differs from frozen readiness")
    if select_merge["role"] != CalibrationRole.SELECT.value or audit_merge["role"] != CalibrationRole.AUDIT.value:
        raise RuntimeError("merge provenance roles must be CAL-SELECT then CAL-AUDIT")
    if select_merge["readiness_hash"] != readiness.readiness_hash or audit_merge["readiness_hash"] != readiness.readiness_hash:
        raise RuntimeError("merge provenance readiness hash drifted")
    if select_merge["plan_hash"] != readiness.select_plan_hash or audit_merge["plan_hash"] != readiness.audit_plan_hash:
        raise RuntimeError("merge provenance plan hash drifted")
    if select_merge["merged_artifact_hash"] != select.artifact_hash or audit_merge["merged_artifact_hash"] != audit.artifact_hash:
        raise RuntimeError("merge provenance artifact binding drifted")
    if select_merge["merged_manifest_hash"] != select.manifest.manifest_hash or audit_merge["merged_manifest_hash"] != audit.manifest.manifest_hash:
        raise RuntimeError("merge provenance manifest binding drifted")
    if select_merge["opportunity_audit_hash"] != audit_merge["opportunity_audit_hash"]:
        raise RuntimeError("CAL-SELECT and CAL-AUDIT were generated under different opportunity audits")
    if select_merge["regime_decision_hash"] != audit_merge["regime_decision_hash"]:
        raise RuntimeError("CAL-SELECT and CAL-AUDIT were generated under different regime decisions")
    opportunity_audit_hash = str(select_merge["opportunity_audit_hash"])
    regime_decision_hash = str(select_merge["regime_decision_hash"])
    pair = build_mid_dev_calibration_pair_artifact(
        select,
        audit,
        opportunity_audit_hash=opportunity_audit_hash,
        regime_decision_hash=regime_decision_hash,
    )
    write_canonical_json_fsynced(args.json, pair)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_PAIR_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "opportunity_audit_hash": opportunity_audit_hash,
        "regime_decision_hash": regime_decision_hash,
        "select_plan_hash": readiness.select_plan_hash,
        "audit_plan_hash": readiness.audit_plan_hash,
        "select_merge_provenance_hash": select_merge["provenance_hash"],
        "audit_merge_provenance_hash": audit_merge["provenance_hash"],
        "select_artifact_hash": select.artifact_hash,
        "audit_artifact_hash": audit.artifact_hash,
        "pair_artifact_hash": pair.artifact_hash,
        "merged_independence_hash": pair.merged_independence_hash,
        "sample_count_per_role": pair.sample_count_per_role,
        "json_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"opportunity_audit_hash={opportunity_audit_hash}\n")
    sys.stdout.write(f"regime_decision_hash={regime_decision_hash}\n")
    sys.stdout.write(f"pair_artifact_hash={pair.artifact_hash}\n")
    sys.stdout.write(f"merged_independence_hash={pair.merged_independence_hash}\n")
    sys.stdout.write(f"sample_count_per_role={pair.sample_count_per_role}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
