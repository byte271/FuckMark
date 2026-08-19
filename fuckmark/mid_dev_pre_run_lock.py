from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .experiments.mid_dev_pre_run_lock_io import load_pre_run_scientific_lock_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-pre-run-lock")
    parser.add_argument("--lock-json", type=Path, required=True)
    parser.add_argument("--expected-lock-hash")
    parser.add_argument("--expected-source-code-commit")
    parser.add_argument("--print-source-code-commit-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    lock = load_pre_run_scientific_lock_json(args.lock_json)
    if args.expected_lock_hash is not None and lock.lock_hash != args.expected_lock_hash:
        raise RuntimeError("pre-run scientific lock hash does not match expected hash")
    if args.expected_source_code_commit is not None and lock.source_code_commit != args.expected_source_code_commit:
        raise RuntimeError("pre-run scientific lock source commit does not match expected commit")
    if args.print_source_code_commit_only:
        sys.stdout.write(lock.source_code_commit + "\n")
        return 0
    sys.stdout.write("pre_run_scientific_lock=PASS\n")
    sys.stdout.write(f"lock_hash={lock.lock_hash}\n")
    sys.stdout.write(f"source_code_commit={lock.source_code_commit}\n")
    sys.stdout.write(f"development_plan_hash={lock.development_plan_hash}\n")
    sys.stdout.write(f"threshold_registry_hash={lock.threshold_registry_hash}\n")
    sys.stdout.write(f"beam_v3_decision={lock.beam_v3_gate_decision}\n")
    sys.stdout.write(f"planner_algorithm_version={lock.planner_algorithm_version}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
