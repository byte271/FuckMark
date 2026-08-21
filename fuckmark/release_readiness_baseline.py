from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.release_readiness import (
    FROZEN_V010_RELEASE_READINESS_BASELINE,
    ReleaseGateStatus,
    load_release_readiness_baseline,
    verify_v010_baseline_repository,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-release-readiness-baseline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--json", type=Path)
    mode.add_argument("--verify-json", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-baseline-source", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verify_baseline_source:
        verify_v010_baseline_repository(args.repository_root)
    if args.json is not None:
        baseline = FROZEN_V010_RELEASE_READINESS_BASELINE
        write_canonical_json_fsynced(args.json, baseline)
    else:
        baseline = load_release_readiness_baseline(args.verify_json)
        if baseline != FROZEN_V010_RELEASE_READINESS_BASELINE:
            raise ValueError("release readiness artifact does not match the frozen v0.1.0 baseline")
    counts = Counter(value.status for value in baseline.gates)
    sys.stdout.write(f"artifact_hash={baseline.artifact_hash}\n")
    sys.stdout.write(f"baseline_commit={baseline.baseline_commit}\n")
    sys.stdout.write(f"gate_count={len(baseline.gates)}\n")
    sys.stdout.write(f"pass_count={counts[ReleaseGateStatus.PASS]}\n")
    sys.stdout.write(f"blocked_count={counts[ReleaseGateStatus.BLOCKED]}\n")
    sys.stdout.write(f"pending_count={counts[ReleaseGateStatus.PENDING]}\n")
    sys.stdout.write(
        f"scientific_rejection_count={counts[ReleaseGateStatus.SCIENTIFIC_REJECTION]}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
