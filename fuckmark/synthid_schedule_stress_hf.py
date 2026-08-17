from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_schedule_stress import run_synthid_schedule_stress
from .experiments.synthid_smoke import SynthIDSmokePrompt
from .synthid_geometry_hf import HuggingFaceSynthIDGeometryBackend
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN
from .transforms import development_transform_registry, release_transform_registry


MECHANISM_STRESS_PROMPTS = (
    "Continue this policy paragraph in the same repetitive style for several sentences: Teams do not skip review and should not rush, while managers cannot ignore evidence and will not bypass checks. Reviewers do not",
    "Continue this safety memo in the same repetitive style for several sentences: Operators cannot bypass checks and will not ignore alarms, while supervisors do not rush and should not skip review. Inspectors cannot",
    "Continue this laboratory note in the same repetitive style for several sentences: Researchers do not discard controls and should not change thresholds, while analysts cannot hide failures and will not rewrite results. Auditors do not",
    "Continue this quality memo in the same repetitive style for several sentences: Engineers cannot ignore regressions and will not bypass tests, while maintainers do not skip validation and should not suppress errors. Reviewers cannot",
    "Continue this reliability note in the same repetitive style for several sentences: Teams should not alter evidence and do not drop failed cases, while operators will not skip checks and cannot ignore warnings. Managers should not",
    "Continue this evaluation memo in the same repetitive style for several sentences: Researchers will not inspect secret keys and cannot use detector feedback, while reviewers do not change rules and should not remove controls. Analysts will not",
    "Continue this testing note in the same repetitive style for several sentences: Developers do not ignore failures and should not change seeds, while auditors cannot remove controls and will not hide null results. Maintainers do not",
    "Continue this verification memo in the same repetitive style for several sentences: Reviewers cannot bypass checks and will not alter logs, while engineers do not skip tests and should not rewrite evidence. Operators cannot",
)


class HuggingFaceSynthIDScheduleStressBackend(HuggingFaceSynthIDGeometryBackend):
    def score(self, text: str) -> float:
        raise RuntimeError("schedule stress analysis must not request detector scores")


def _parse_budgets(value: str) -> tuple[int, ...]:
    try:
        budgets = tuple(sorted({int(part.strip()) for part in value.split(",") if part.strip()}))
    except ValueError as error:
        raise argparse.ArgumentTypeError("budgets must be comma-separated positive integers") from error
    if not budgets or any(item <= 0 for item in budgets):
        raise argparse.ArgumentTypeError("budgets must be comma-separated positive integers")
    return budgets


def _load_prompts(path: Path | None, limit: int, seed_base: int) -> tuple[SynthIDSmokePrompt, ...]:
    if path is None:
        values = MECHANISM_STRESS_PROMPTS
    else:
        values = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if limit <= 0:
        raise ValueError("prompt limit must be positive")
    values = values[:limit]
    if not values:
        raise ValueError("prompt source contains no usable prompts")
    return tuple(
        SynthIDSmokePrompt(f"stress-{index + 1:03d}", text, seed_base + index)
        for index, text in enumerate(values)
    )


def _write_opportunities(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "prompt_id",
        "generation_seed",
        "label",
        "budget",
        "candidate_count",
        "geometry_positive_candidate_count",
        "isolated_coverage_sum",
        "candidate_union_coverage",
        "overlap_loss",
        "greedy_cost",
        "greedy_coverage",
        "matched_random_count",
        "mean_matched_random_coverage",
        "greedy_advantage_over_random",
        "clustered_cost",
        "clustered_coverage",
        "even_cost",
        "even_coverage",
        "exact_optimal_cost",
        "exact_optimal_coverage",
        "greedy_regret",
        "random_headroom_to_optimum",
        "status",
        "opportunity_hash",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report.opportunities:
            writer.writerow(
                {
                    "prompt_id": row.prompt_id,
                    "generation_seed": row.generation_seed,
                    "label": row.label.value,
                    "budget": row.budget,
                    "candidate_count": row.candidate_count,
                    "geometry_positive_candidate_count": row.geometry_positive_candidate_count,
                    "isolated_coverage_sum": row.isolated_coverage_sum,
                    "candidate_union_coverage": row.candidate_union_coverage,
                    "overlap_loss": row.overlap_loss,
                    "greedy_cost": row.greedy_cost,
                    "greedy_coverage": row.greedy_coverage,
                    "matched_random_count": row.matched_random_count,
                    "mean_matched_random_coverage": row.mean_matched_random_coverage,
                    "greedy_advantage_over_random": row.greedy_advantage_over_random,
                    "clustered_cost": row.clustered_cost,
                    "clustered_coverage": row.clustered_coverage,
                    "even_cost": row.even_cost,
                    "even_coverage": row.even_coverage,
                    "exact_optimal_cost": row.exact_optimal_cost,
                    "exact_optimal_coverage": row.exact_optimal_coverage,
                    "greedy_regret": row.greedy_regret,
                    "random_headroom_to_optimum": row.random_headroom_to_optimum,
                    "status": row.status.value,
                    "opportunity_hash": row.opportunity_hash,
                }
            )


def _write_schedules(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "prompt_id",
        "generation_seed",
        "label",
        "budget",
        "policy",
        "schedule_seed",
        "realized_cost",
        "predicted_coverage",
        "selected_candidate_count",
        "schedule_result_hash",
        "row_hash",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report.schedule_rows:
            writer.writerow(
                {
                    "prompt_id": row.prompt_id,
                    "generation_seed": row.generation_seed,
                    "label": row.label.value,
                    "budget": row.budget,
                    "policy": row.policy.value,
                    "schedule_seed": row.schedule_seed,
                    "realized_cost": row.realized_cost,
                    "predicted_coverage": row.predicted_coverage,
                    "selected_candidate_count": len(row.selected_candidate_ids),
                    "schedule_result_hash": row.schedule_result_hash,
                    "row_hash": row.row_hash,
                }
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-schedule-stress")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=8)
    parser.add_argument("--seed-base", type=int, default=273000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development"), default="release")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--random-seed-count", type=int, default=8)
    parser.add_argument("--schedule-seed-base", type=int, default=9300)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-schedule-stress.json"))
    parser.add_argument("--opportunities-csv", type=Path, default=Path("artifacts/synthid-schedule-stress-opportunities.csv"))
    parser.add_argument("--schedules-csv", type=Path, default=Path("artifacts/synthid-schedule-stress-schedules.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.random_seed_count <= 0:
        raise ValueError("random-seed-count must be positive")
    if args.schedule_seed_base < 0 or args.schedule_seed_base + args.random_seed_count >= 1 << 64:
        raise ValueError("schedule seed range must fit in 64 bits")
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    backend = HuggingFaceSynthIDScheduleStressBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        ngram_len=DEFAULT_NGRAM_LEN,
        keys=DEFAULT_KEYS,
    )
    registry = release_transform_registry() if args.registry == "release" else development_transform_registry()
    random_seeds = tuple(args.schedule_seed_base + offset + 1 for offset in range(args.random_seed_count))
    report = run_synthid_schedule_stress(
        prompts,
        backend,
        registry,
        budgets=args.budgets,
        random_seeds=random_seeds,
        spacing_seed=args.schedule_seed_base,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    _write_opportunities(args.opportunities_csv, report)
    _write_schedules(args.schedules_csv, report)
    summary = report.summary
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"prompt_count={summary.prompt_count}\n")
    sys.stdout.write(f"opportunity_count={summary.opportunity_count}\n")
    sys.stdout.write(f"exact_opportunity_count={summary.exact_opportunity_count}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"eligible_control_rate={summary.eligible_control_rate:.3f}\n")
    sys.stdout.write(f"eligible_watermarked_rate={summary.eligible_watermarked_rate:.3f}\n")
    sys.stdout.write(f"overlap_control_rate={summary.overlap_control_rate:.3f}\n")
    sys.stdout.write(f"overlap_watermarked_rate={summary.overlap_watermarked_rate:.3f}\n")
    sys.stdout.write(f"positive_headroom_control_rate={summary.positive_headroom_control_rate:.3f}\n")
    sys.stdout.write(f"positive_headroom_watermarked_rate={summary.positive_headroom_watermarked_rate:.3f}\n")
    sys.stdout.write(f"mean_control_greedy_advantage={summary.mean_control_greedy_advantage}\n")
    sys.stdout.write(f"mean_watermarked_greedy_advantage={summary.mean_watermarked_greedy_advantage}\n")
    sys.stdout.write(f"mean_control_random_headroom={summary.mean_control_random_headroom}\n")
    sys.stdout.write(f"mean_watermarked_random_headroom={summary.mean_watermarked_random_headroom}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"opportunities_csv={args.opportunities_csv.as_posix()}\n")
    sys.stdout.write(f"schedules_csv={args.schedules_csv.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
