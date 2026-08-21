from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.durable_portfolio import (
    compare_durable_portfolio_benchmarks,
    load_durable_portfolio_comparison,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-durable-portfolio-analyze")
    parser.add_argument("--baseline-json", type=Path, required=True)
    parser.add_argument("--portfolio-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--require-success", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    comparison = compare_durable_portfolio_benchmarks(
        args.baseline_json,
        args.portfolio_json,
    )
    write_canonical_json_fsynced(args.json, comparison)
    load_durable_portfolio_comparison(args.json)
    sys.stdout.write(f"artifact_hash={comparison['artifact_hash']}\n")
    sys.stdout.write(f"sample_count={comparison['sample_count']}\n")
    sys.stdout.write(f"raw_candidate_gain={comparison['raw_candidate_gain']}\n")
    sys.stdout.write(
        f"independent_n4_surviving_gain={comparison['independent_n4_surviving_gain']}\n"
    )
    sys.stdout.write(
        "total_matched_exact_budget_gain_count="
        f"{comparison['total_matched_exact_budget_gain_count']}\n"
    )
    sys.stdout.write(f"portfolio_decision={comparison['portfolio_decision']}\n")
    sys.stdout.write(f"release_decision={comparison['release_decision']}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0 if comparison["portfolio_success"] or not args.require_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
