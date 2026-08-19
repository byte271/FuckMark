from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus.mid_dev_calibration_shards import (
    CalibrationRole,
    build_real_mid_dev_calibration_shard,
)
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION, HuggingFaceMidDevBackend


MID_DEV_CALIBRATION_SHARD_PROVENANCE_VERSION = "mid-dev-calibration-shard-generation-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role(value: str) -> CalibrationRole:
    normalized = value.strip().upper()
    if normalized in {"CAL-SELECT", "SELECT"}:
        return CalibrationRole.SELECT
    if normalized in {"CAL-AUDIT", "AUDIT"}:
        return CalibrationRole.AUDIT
    raise argparse.ArgumentTypeError("role must be CAL-SELECT or CAL-AUDIT")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-shard-hf")
    parser.add_argument("--role", type=_role, required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    plan = readiness.select_plan if args.role is CalibrationRole.SELECT else readiness.audit_plan
    matches = tuple(shard for shard in plan.shards if shard.shard_id == args.shard_id)
    if len(matches) != 1:
        raise RuntimeError("shard-id is not present exactly once in the frozen readiness plan")
    shard_spec = matches[0]
    started_at = _now()
    backend = HuggingFaceMidDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    generated = build_real_mid_dev_calibration_shard(backend, plan, shard_spec.shard_id)
    write_canonical_json_fsynced(args.json, generated)
    finished_at = _now()
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_SHARD_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "role": args.role.value,
        "plan_hash": plan.plan_hash,
        "shard_id": shard_spec.shard_id,
        "shard_spec_hash": shard_spec.shard_hash,
        "shard_output_hash": generated.manifest.output_hash,
        "model_tokenizer_identity_hash": generated.manifest.model_tokenizer_identity_hash,
        "watermark_config_hash": generated.manifest.watermark_config_hash,
        "watermark_condition_hash": generated.manifest.watermark_condition_hash,
        "sample_count": len(generated.samples),
        "generation_started_at_utc": started_at,
        "generation_finished_at_utc": finished_at,
        "json_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"shard_id={shard_spec.shard_id}\n")
    sys.stdout.write(f"shard_output_hash={generated.manifest.output_hash}\n")
    sys.stdout.write(f"sample_count={len(generated.samples)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
