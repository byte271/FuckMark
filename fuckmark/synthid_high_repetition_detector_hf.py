from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_high_repetition_detector import (
    build_high_repetition_detector_plan,
    score_high_repetition_detector_plan,
)
from .synthid_eligible_geometry_hf import HuggingFaceSynthIDEligibilityGeometryBackend
from .synthid_geometry_hf import _load_prompts, _parse_budgets, _registry
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-high-repetition-detector")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=24)
    parser.add_argument("--seed-base", type=int, default=279000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--schedule-seed", type=int, default=9800)
    parser.add_argument("--exact-max-candidates", type=int, default=16)
    parser.add_argument("--plan-json", type=Path, default=Path("artifacts/synthid-high-repetition-detector-plan.json"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-high-repetition-detector.json"))
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
    plan = build_high_repetition_detector_plan(
        prompts,
        backend,
        _registry(args.registry),
        budgets=args.budgets,
        schedule_seed=args.schedule_seed,
        exact_max_candidates=args.exact_max_candidates,
    )
    args.plan_json.parent.mkdir(parents=True, exist_ok=True)
    with args.plan_json.open("w", encoding="utf-8") as handle:
        handle.write(canonical_json_text(plan) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    report = score_high_repetition_detector_plan(plan, backend)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    summary = report.summary
    sys.stdout.write(f"plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"high_source_count={summary.high_source_count}\n")
    sys.stdout.write(f"plan_pair_count={summary.plan_pair_count}\n")
    sys.stdout.write(f"matched_pair_count={summary.matched_pair_count}\n")
    sys.stdout.write(f"differing_selection_pair_count={summary.differing_selection_pair_count}\n")
    sys.stdout.write(f"control_differing_selection_pair_count={summary.control_differing_selection_pair_count}\n")
    sys.stdout.write(f"watermarked_differing_selection_pair_count={summary.watermarked_differing_selection_pair_count}\n")
    sys.stdout.write(f"mean_control_score_drop_advantage={summary.mean_control_score_drop_advantage}\n")
    sys.stdout.write(f"mean_watermarked_score_drop_advantage={summary.mean_watermarked_score_drop_advantage}\n")
    sys.stdout.write(
        "mean_control_score_drop_advantage_when_selection_differs="
        f"{summary.mean_control_score_drop_advantage_when_selection_differs}\n"
    )
    sys.stdout.write(
        "mean_watermarked_score_drop_advantage_when_selection_differs="
        f"{summary.mean_watermarked_score_drop_advantage_when_selection_differs}\n"
    )
    sys.stdout.write(
        "watermarked_direction_when_selection_differs="
        f"{summary.watermarked_better_count_when_selection_differs}/"
        f"{summary.watermarked_worse_count_when_selection_differs}/"
        f"{summary.watermarked_tie_count_when_selection_differs}\n"
    )
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
