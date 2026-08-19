from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-readiness")
    parser.add_argument(
        "--readiness-json",
        type=Path,
        default=Path("artifacts/mid-dev-calibration-readiness.json"),
    )
    parser.add_argument(
        "--select-plan-json",
        type=Path,
        default=Path("artifacts/mid-dev-cal-select-plan.json"),
    )
    parser.add_argument(
        "--audit-plan-json",
        type=Path,
        default=Path("artifacts/mid-dev-cal-audit-plan.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    write_canonical_json_fsynced(args.select_plan_json, readiness.select_plan)
    write_canonical_json_fsynced(args.audit_plan_json, readiness.audit_plan)
    write_canonical_json_fsynced(args.readiness_json, readiness)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"select_plan_hash={readiness.select_plan_hash}\n")
    sys.stdout.write(f"audit_plan_hash={readiness.audit_plan_hash}\n")
    sys.stdout.write(f"role_independence_hash={readiness.role_independence_hash}\n")
    sys.stdout.write(f"negatives_per_target={readiness.negatives_per_target}\n")
    sys.stdout.write(f"shard_size={readiness.shard_size}\n")
    sys.stdout.write(f"select_shards={len(readiness.select_plan.shards)}\n")
    sys.stdout.write(f"audit_shards={len(readiness.audit_plan.shards)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
