from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .config import canonical_json_text
from .corpus.mid_dev_calibration_merged import merge_mid_dev_generated_calibration_shards
from .corpus.mid_dev_calibration_shard_io import load_mid_dev_generated_calibration_shard_json
from .corpus.mid_dev_calibration_shards import CalibrationRole
from .corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .hashing import sha256_json


MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION = "mid-dev-calibration-merge-provenance-v1"
MID_DEV_CALIBRATION_SHARD_PROVENANCE_VERSION = "mid-dev-calibration-shard-generation-provenance-v1"


def _role(value: str) -> CalibrationRole:
    normalized = value.strip().upper()
    if normalized in {"CAL-SELECT", "SELECT"}:
        return CalibrationRole.SELECT
    if normalized in {"CAL-AUDIT", "AUDIT"}:
        return CalibrationRole.AUDIT
    raise argparse.ArgumentTypeError("role must be CAL-SELECT or CAL-AUDIT")


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _load_shard_provenance(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "calibration_shard_provenance",
            decoded,
            (
                "algorithm_version",
                "readiness_hash",
                "role",
                "plan_hash",
                "shard_id",
                "shard_spec_hash",
                "shard_output_hash",
                "model_tokenizer_identity_hash",
                "watermark_config_hash",
                "watermark_condition_hash",
                "sample_count",
                "generation_started_at_utc",
                "generation_finished_at_utc",
                "json_fsync_success",
                "github_run_id",
                "github_run_attempt",
                "github_event_name",
                "github_checkout_sha",
                "provenance_hash",
            ),
        )
    except Exception as error:
        raise ValueError(f"invalid calibration shard provenance: {path}") from error
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["algorithm_version"] != MID_DEV_CALIBRATION_SHARD_PROVENANCE_VERSION:
        raise ValueError("unsupported calibration shard provenance version")
    if data["provenance_hash"] != sha256_json(payload):
        raise ValueError("calibration shard provenance hash does not replay")
    if text not in (canonical_json_text(data), canonical_json_text(data) + "\n"):
        raise ValueError("calibration shard provenance JSON is not canonical")
    if data["json_fsync_success"] is not True:
        raise ValueError("calibration shard provenance does not attest fsync")
    started = _parse_time(data["generation_started_at_utc"], "generation_started_at_utc")
    finished = _parse_time(data["generation_finished_at_utc"], "generation_finished_at_utc")
    if finished < started:
        raise ValueError("calibration shard generation timestamps are reversed")
    return dict(data)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-merge")
    parser.add_argument("--role", type=_role, required=True)
    parser.add_argument("--shard-json", type=Path, action="append", required=True)
    parser.add_argument("--shard-provenance-json", type=Path, action="append", required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    plan = readiness.select_plan if args.role is CalibrationRole.SELECT else readiness.audit_plan
    expected_count = len(plan.shards)
    if len(args.shard_json) != expected_count or len(args.shard_provenance_json) != expected_count:
        raise RuntimeError(f"merge requires exactly {expected_count} shard JSONs and provenance JSONs")
    if len({path.resolve() for path in args.shard_json}) != expected_count:
        raise RuntimeError("duplicate shard JSON path supplied")
    if len({path.resolve() for path in args.shard_provenance_json}) != expected_count:
        raise RuntimeError("duplicate shard provenance path supplied")

    shards = tuple(load_mid_dev_generated_calibration_shard_json(path) for path in args.shard_json)
    provenances = tuple(_load_shard_provenance(path) for path in args.shard_provenance_json)
    shard_by_id = {shard.manifest.shard_id: shard for shard in shards}
    provenance_by_id = {str(value["shard_id"]): value for value in provenances}
    if len(shard_by_id) != expected_count or len(provenance_by_id) != expected_count:
        raise RuntimeError("duplicate calibration shard ID supplied")
    expected_ids = tuple(spec.shard_id for spec in plan.shards)
    if set(shard_by_id) != set(expected_ids) or set(provenance_by_id) != set(expected_ids):
        raise RuntimeError("supplied calibration shards do not exactly cover the frozen plan")

    ordered_shards = []
    provenance_hashes = []
    for spec in plan.shards:
        shard = shard_by_id[spec.shard_id]
        provenance = provenance_by_id[spec.shard_id]
        if shard.manifest.role is not args.role or shard.manifest.plan_hash != plan.plan_hash:
            raise RuntimeError("calibration shard role/plan binding drifted")
        if shard.manifest.shard_spec_hash != spec.shard_hash:
            raise RuntimeError("calibration shard spec hash drifted")
        if provenance["readiness_hash"] != readiness.readiness_hash:
            raise RuntimeError("calibration shard provenance readiness hash drifted")
        if provenance["role"] != args.role.value or provenance["plan_hash"] != plan.plan_hash:
            raise RuntimeError("calibration shard provenance role/plan binding drifted")
        if provenance["shard_spec_hash"] != spec.shard_hash:
            raise RuntimeError("calibration shard provenance spec hash drifted")
        if provenance["shard_output_hash"] != shard.manifest.output_hash:
            raise RuntimeError("calibration shard provenance output hash drifted")
        if provenance["model_tokenizer_identity_hash"] != shard.manifest.model_tokenizer_identity_hash:
            raise RuntimeError("calibration shard provenance model identity drifted")
        if provenance["watermark_config_hash"] != shard.manifest.watermark_config_hash:
            raise RuntimeError("calibration shard provenance watermark config drifted")
        if provenance["watermark_condition_hash"] != shard.manifest.watermark_condition_hash:
            raise RuntimeError("calibration shard provenance watermark condition drifted")
        if provenance["sample_count"] != len(shard.samples):
            raise RuntimeError("calibration shard provenance sample count drifted")
        ordered_shards.append(shard)
        provenance_hashes.append(provenance["provenance_hash"])

    merged = merge_mid_dev_generated_calibration_shards(
        readiness_hash=readiness.readiness_hash,
        plan=plan,
        shards=tuple(ordered_shards),
    )
    write_canonical_json_fsynced(args.json, merged)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "role": args.role.value,
        "plan_hash": plan.plan_hash,
        "shard_provenance_hashes": tuple(provenance_hashes),
        "merged_manifest_hash": merged.manifest.manifest_hash,
        "merged_artifact_hash": merged.artifact_hash,
        "sample_count": len(merged.samples),
        "json_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"role={args.role.value}\n")
    sys.stdout.write(f"plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"merged_manifest_hash={merged.manifest.manifest_hash}\n")
    sys.stdout.write(f"merged_artifact_hash={merged.artifact_hash}\n")
    sys.stdout.write(f"sample_count={len(merged.samples)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
