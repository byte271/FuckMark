from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_geometry import GeometryPairStatus, run_synthid_geometry_pilot
from .experiments.synthid_smoke import SynthIDSmokePrompt
from .synthid_smoke_hf import (
    DEFAULT_KEYS,
    DEFAULT_NGRAM_LEN,
    DEFAULT_PROMPTS,
    HuggingFaceSynthIDSmokeBackend,
)
from .transforms import development_transform_registry, release_transform_registry
from .transforms.mechanism_registry import mechanism_stress_transform_registry


class HuggingFaceSynthIDGeometryBackend(HuggingFaceSynthIDSmokeBackend):
    @property
    def ngram_len(self) -> int:
        return self._adapter.ngram_len

    def tokenize(self, text: str) -> tuple[int, ...]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        return tuple(self._tokenizer.encode(text, add_special_tokens=False))


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
        values = DEFAULT_PROMPTS
    else:
        values = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if limit <= 0:
        raise ValueError("prompt limit must be positive")
    values = values[:limit]
    if not values:
        raise ValueError("prompt source contains no usable prompts")
    return tuple(
        SynthIDSmokePrompt(f"geometry-{index + 1:03d}", text, seed_base + index)
        for index, text in enumerate(values)
    )


def _registry(name: str):
    if name == "release":
        return release_transform_registry()
    if name == "development":
        return development_transform_registry()
    if name == "mechanism":
        return mechanism_stress_transform_registry()
    raise ValueError("unknown registry")


def _write_variant_csv(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "prompt_id",
        "generation_seed",
        "label",
        "budget",
        "policy",
        "schedule_seed",
        "candidate_count",
        "geometry_positive_candidate_count",
        "source_token_count",
        "transformed_token_count",
        "original_observation_count",
        "predicted_coverage_count",
        "selected_count",
        "realized_edit_cost",
        "preserved_count",
        "replaced_count",
        "unmapped_count",
        "disrupted_count",
        "disruption_per_edit",
        "pristine_score",
        "transformed_score",
        "score_drop",
        "variant_hash",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report.variants:
            writer.writerow(
                {
                    "prompt_id": row.prompt_id,
                    "generation_seed": row.generation_seed,
                    "label": row.label.value,
                    "budget": row.budget,
                    "policy": row.policy.value,
                    "schedule_seed": row.schedule_seed,
                    "candidate_count": row.candidate_count,
                    "geometry_positive_candidate_count": row.geometry_positive_candidate_count,
                    "source_token_count": row.source_token_count,
                    "transformed_token_count": row.transformed_token_count,
                    "original_observation_count": row.original_observation_count,
                    "predicted_coverage_count": row.predicted_coverage_count,
                    "selected_count": row.selected_count,
                    "realized_edit_cost": row.realized_edit_cost,
                    "preserved_count": row.preserved_count,
                    "replaced_count": row.replaced_count,
                    "unmapped_count": row.unmapped_count,
                    "disrupted_count": row.disrupted_count,
                    "disruption_per_edit": row.disruption_per_edit,
                    "pristine_score": row.pristine_score,
                    "transformed_score": row.transformed_score,
                    "score_drop": row.score_drop,
                    "variant_hash": row.variant_hash,
                }
            )


def _write_pair_csv(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "prompt_id",
        "generation_seed",
        "label",
        "budget",
        "status",
        "matched_random_count",
        "disruption_advantage",
        "score_drop_advantage",
        "pair_hash",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report.pairs:
            writer.writerow(
                {
                    "prompt_id": row.prompt_id,
                    "generation_seed": row.generation_seed,
                    "label": row.label.value,
                    "budget": row.budget,
                    "status": row.status.value,
                    "matched_random_count": len(row.matched_random_variant_hashes),
                    "disruption_advantage": row.disruption_advantage,
                    "score_drop_advantage": row.score_drop_advantage,
                    "pair_hash": row.pair_hash,
                }
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-geometry")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=10)
    parser.add_argument("--seed-base", type=int, default=272000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="release")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2))
    parser.add_argument("--random-seed-count", type=int, default=8)
    parser.add_argument("--schedule-seed-base", type=int, default=9200)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-geometry.json"))
    parser.add_argument("--variants-csv", type=Path, default=Path("artifacts/synthid-geometry-variants.csv"))
    parser.add_argument("--pairs-csv", type=Path, default=Path("artifacts/synthid-geometry-pairs.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.random_seed_count <= 0:
        raise ValueError("random-seed-count must be positive")
    if args.schedule_seed_base < 0 or args.schedule_seed_base + args.random_seed_count >= 1 << 64:
        raise ValueError("schedule seed range must fit in 64 bits")
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    backend = HuggingFaceSynthIDGeometryBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        ngram_len=DEFAULT_NGRAM_LEN,
        keys=DEFAULT_KEYS,
    )
    registry = _registry(args.registry)
    random_seeds = tuple(args.schedule_seed_base + offset + 1 for offset in range(args.random_seed_count))
    report = run_synthid_geometry_pilot(
        prompts,
        backend,
        registry,
        budgets=args.budgets,
        random_seeds=random_seeds,
        greedy_seed=args.schedule_seed_base,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    _write_variant_csv(args.variants_csv, report)
    _write_pair_csv(args.pairs_csv, report)
    summary = report.summary
    matched = tuple(row for row in report.pairs if row.status is GeometryPairStatus.MATCHED)
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"prompt_count={summary.prompt_count}\n")
    sys.stdout.write(f"variant_count={summary.variant_count}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"min_budget_control_eligible_rate={summary.min_budget_control_eligible_rate:.3f}\n")
    sys.stdout.write(f"min_budget_watermarked_eligible_rate={summary.min_budget_watermarked_eligible_rate:.3f}\n")
    sys.stdout.write(f"matched_pair_count={len(matched)}\n")
    sys.stdout.write(f"mean_control_disruption_advantage={summary.mean_control_disruption_advantage}\n")
    sys.stdout.write(f"mean_watermarked_disruption_advantage={summary.mean_watermarked_disruption_advantage}\n")
    sys.stdout.write(f"mean_control_score_drop_advantage={summary.mean_control_score_drop_advantage}\n")
    sys.stdout.write(f"mean_watermarked_score_drop_advantage={summary.mean_watermarked_score_drop_advantage}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"variants_csv={args.variants_csv.as_posix()}\n")
    sys.stdout.write(f"pairs_csv={args.pairs_csv.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
