from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.release_readiness import (
    FROZEN_V010_RELEASE_READINESS_BASELINE,
    load_release_readiness_baseline,
    verify_v010_baseline_repository,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-release-readiness-baseline")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--verify-json", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-baseline-source", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if (args.json is None) == (args.verify_json is None):
        raise ValueError("provide exactly one of --json or --verify-json")
    if args.verify_baseline_source:
        verify_v010_baseline_repository(args.repository_root)
    if args.json is not None:
        baseline = FROZEN_V010_RELEASE_READINESS_BASELINE
        write_canonical_json_fsynced(args.json, baseline)
    else:
        baseline = load_release_readiness_baseline(args.verify_json)
        if baseline != FROZEN_V010_RELEASE_READINESS_BASELINE:
            raise ValueError("release readiness artifact does not match the frozen v0.1.0 baseline")
    passed = sum(value.status.value == "PASS" for value in baseline.gates)
    blocked = sum(value.status.value == "BLOCKED" for value in baseline.gates)
    pending = sum(value.status.value == "PENDING" for value in baseline.gates)
    sys.stdout.write(f"artifact_hash={baseline.artifact_hash}\n")
    sys.stdout.write(f"baseline_commit={baseline.baseline_commit}\n")
    sys.stdout.write(f"gate_count={len(baseline.gates)}\n")
    sys.stdout.write(f"pass_count={passed}\n")
    sys.stdout.write(f"blocked_count={blocked}\n")
    sys.stdout.write(f"pending_count={pending}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
