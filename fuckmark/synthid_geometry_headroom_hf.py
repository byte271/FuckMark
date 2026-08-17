from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_geometry import GeometryLabel
from .experiments.synthid_geometry_headroom import build_public_eligibility_geometry_headroom
from .hashing import sha256_json, sha256_text
from .synthid_eligible_geometry_hf import HuggingFaceSynthIDEligibilityGeometryBackend
from .synthid_geometry_hf import _load_prompts, _parse_budgets, _registry
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-geometry-headroom")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=10)
    parser.add_argument("--seed-base", type=int, default=277000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--schedule-seed", type=int, default=9600)
    parser.add_argument("--exact-max-candidates", type=int, default=16)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-geometry-headroom.json"))
    return parser


def _mean(values):
    materialized = tuple(value for value in values if value is not None)
    if not materialized:
        return None
    return statistics.fmean(materialized)


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
    registry = _registry(args.registry)
    sources = []
    for prompt in prompts:
        sources.append(
            (
                prompt.prompt_id,
                prompt.seed,
                GeometryLabel.CONTROL,
                backend.generate(prompt.text, prompt.seed, watermarked=False),
            )
        )
        sources.append(
            (
                prompt.prompt_id,
                prompt.seed,
                GeometryLabel.WATERMARKED,
                backend.generate(prompt.text, prompt.seed, watermarked=True),
            )
        )
    records = []
    for prompt_id, seed, label, source_text in sources:
        report = build_public_eligibility_geometry_headroom(
            source_text,
            backend.tokenize,
            backend.eos_token_id,
            backend.ngram_len,
            backend.context_history_size,
            registry,
            budgets=args.budgets,
            seed=args.schedule_seed,
            exact_max_candidates=args.exact_max_candidates,
        )
        records.append(
            {
                "prompt_id": prompt_id,
                "generation_seed": seed,
                "label": label.value,
                "source_hash": sha256_text(source_text),
                "report": report,
            }
        )
    reports = tuple(record["report"] for record in records)
    top_defined = tuple(
        report.summary.top_positive_candidate_same
        for report in reports
        if report.summary.top_positive_candidate_same is not None
    )
    summary = {
        "prompt_count": len(prompts),
        "source_count": len(records),
        "candidate_count": sum(report.summary.candidate_count for report in reports),
        "all_positive_candidate_count": sum(report.summary.all_positive_candidate_count for report in reports),
        "eligible_positive_candidate_count": sum(report.summary.eligible_positive_candidate_count for report in reports),
        "positive_all_zero_eligible_candidate_count": sum(
            report.summary.positive_all_zero_eligible_candidate_count for report in reports
        ),
        "top_positive_same_rate": None if not top_defined else sum(top_defined) / len(top_defined),
        "mean_spearman_rank_correlation": _mean(
            report.summary.spearman_rank_correlation for report in reports
        ),
        "mean_absolute_rank_displacement": _mean(
            report.summary.mean_absolute_rank_displacement for report in reports
        ),
        "scheduled_budget_count": sum(report.summary.scheduled_budget_count for report in reports),
        "greedy_selection_disagreement_count": sum(
            report.summary.greedy_selection_disagreement_count for report in reports
        ),
        "exact_budget_count": sum(report.summary.exact_budget_count for report in reports),
        "exact_selection_disagreement_count": sum(
            report.summary.exact_selection_disagreement_count for report in reports
        ),
    }
    payload = {
        "algorithm": "synthid-geometry-headroom-hf-batch-v1",
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "transform_ruleset_hash": registry.ruleset_hash,
        "ngram_len": backend.ngram_len,
        "eos_token_id": backend.eos_token_id,
        "context_history_size": backend.context_history_size,
        "budgets": args.budgets,
        "schedule_seed": args.schedule_seed,
        "exact_max_candidates": args.exact_max_candidates,
        "records": records,
        "summary": summary,
    }
    batch_hash = sha256_json(payload)
    artifact = {**payload, "batch_hash": batch_hash}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    sys.stdout.write(f"batch_hash={batch_hash}\n")
    for key, value in summary.items():
        sys.stdout.write(f"{key}={value}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
