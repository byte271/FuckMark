from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_repetition_strata import run_synthid_repetition_strata
from .synthid_eligible_geometry_hf import HuggingFaceSynthIDEligibilityGeometryBackend
from .synthid_geometry_hf import _load_prompts, _parse_budgets, _registry
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-repetition-strata")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=20)
    parser.add_argument("--seed-base", type=int, default=278000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--schedule-seed", type=int, default=9700)
    parser.add_argument("--exact-max-candidates", type=int, default=16)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-repetition-strata.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.schedule_seed < 0 or args.schedule_seed >= 1 << 64:
        raise ValueError("schedule-seed must fit in 64 bits")
    if not 1 <= args.exact_max_candidates <= 16:
        raise ValueError("exact-max-candidates must lie in [1, 16]")
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    backend = HuggingFaceSynthIDEligibilityGeometryBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        ngram_len=DEFAULT_NGRAM_LEN,
        keys=DEFAULT_KEYS,
    )
    report = run_synthid_repetition_strata(
        prompts,
        backend,
        _registry(args.registry),
        budgets=args.budgets,
        schedule_seed=args.schedule_seed,
        exact_max_candidates=args.exact_max_candidates,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"prompt_count={report.summary.prompt_count}\n")
    sys.stdout.write(f"source_count={report.summary.source_count}\n")
    sys.stdout.write(f"total_candidate_count={report.summary.total_candidate_count}\n")
    sys.stdout.write(f"disagreement_source_count={report.summary.disagreement_source_count}\n")
    sys.stdout.write(f"high_stratum_disagreement_source_count={report.summary.high_stratum_disagreement_source_count}\n")
    for row in report.strata:
        prefix = f"{row.label.value.lower()}_{row.stratum.value.lower()}"
        sys.stdout.write(f"{prefix}_source_count={row.source_count}\n")
        sys.stdout.write(f"{prefix}_mean_repeated_fraction={row.mean_repeated_fraction}\n")
        sys.stdout.write(f"{prefix}_mean_rank_correlation={row.mean_rank_correlation}\n")
        sys.stdout.write(f"{prefix}_disagreement_source_count={row.disagreement_source_count}\n")
        sys.stdout.write(f"{prefix}_greedy_disagreements={row.greedy_selection_disagreement_count}\n")
        sys.stdout.write(f"{prefix}_exact_disagreements={row.exact_selection_disagreement_count}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
