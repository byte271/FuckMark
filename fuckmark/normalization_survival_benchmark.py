from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.diverse_beam_corpus import load_diverse_beam_frozen_corpus
from .experiments.normalization_survival import (
    build_normalization_survival_benchmark,
    load_normalization_survival_benchmark,
)
from .transforms.contractions import context_survival_contraction_rules
from .transforms.registry import TransformRegistry, durable_portfolio_transform_registry
from .transforms.surface_rules import development_surface_rules


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-normalization-survival-benchmark")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--source-workflow-run-id", type=int, required=True)
    parser.add_argument(
        "--registry",
        choices=("context-baseline", "durable-portfolio"),
        default="context-baseline",
    )
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpus = load_diverse_beam_frozen_corpus(args.corpus_json)
    registry = (
        durable_portfolio_transform_registry()
        if args.registry == "durable-portfolio"
        else TransformRegistry(
            (*context_survival_contraction_rules(), *development_surface_rules())
        )
    )
    benchmark = build_normalization_survival_benchmark(
        corpus,
        registry,
        benchmark_source_code_commit=args.source_code_commit,
        source_workflow_run_id=args.source_workflow_run_id,
    )
    write_canonical_json_fsynced(args.json, benchmark)
    load_normalization_survival_benchmark(args.json)
    conclusions = benchmark["mandatory_conclusions"]
    sys.stdout.write(f"artifact_hash={benchmark['artifact_hash']}\n")
    sys.stdout.write(f"source_sample_count={benchmark['source_sample_count']}\n")
    sys.stdout.write(f"candidate_row_count={benchmark['candidate_row_count']}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(
        f"n4_b2_reachable_sample_count={conclusions['n4_b2_reachable_sample_count']}\n"
    )
    sys.stdout.write(
        "survival_aware_scheduler_answer="
        f"{conclusions['survival_aware_scheduler_answer']}\n"
    )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
