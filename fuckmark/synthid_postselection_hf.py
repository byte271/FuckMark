from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_postselection import build_synthid_postselection_audit
from .synthid_geometry_hf import (
    HuggingFaceSynthIDGeometryBackend,
    _load_prompts,
    _parse_budgets,
    _registry,
)
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN
from .experiments.synthid_geometry import run_synthid_geometry_pilot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-postselection")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=10)
    parser.add_argument("--seed-base", type=int, default=274000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--random-seed-count", type=int, default=8)
    parser.add_argument("--schedule-seed-base", type=int, default=9400)
    parser.add_argument("--geometry-json", type=Path, default=Path("artifacts/synthid-postselection-geometry.json"))
    parser.add_argument("--audit-json", type=Path, default=Path("artifacts/synthid-postselection-audit.json"))
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
    random_seeds = tuple(args.schedule_seed_base + offset + 1 for offset in range(args.random_seed_count))
    report = run_synthid_geometry_pilot(
        prompts,
        backend,
        _registry(args.registry),
        budgets=args.budgets,
        random_seeds=random_seeds,
        greedy_seed=args.schedule_seed_base,
    )
    audit = build_synthid_postselection_audit(report)
    args.geometry_json.parent.mkdir(parents=True, exist_ok=True)
    args.geometry_json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    args.audit_json.parent.mkdir(parents=True, exist_ok=True)
    args.audit_json.write_text(canonical_json_text(audit) + "\n", encoding="utf-8")
    control, watermarked = audit.summaries
    sys.stdout.write(f"geometry_report_hash={report.report_hash}\n")
    sys.stdout.write(f"audit_hash={audit.audit_hash}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"control_geometry_positive_pairs={control.geometry_positive_pair_count}\n")
    sys.stdout.write(f"control_geometry_positive_score_nonpositive={control.geometry_positive_score_nonpositive_count}\n")
    sys.stdout.write(f"control_mean_score_advantage_when_geometry_positive={control.mean_score_advantage_when_geometry_positive}\n")
    sys.stdout.write(f"control_pearson_geometry_vs_score={control.pearson_geometry_vs_score}\n")
    sys.stdout.write(f"watermarked_geometry_positive_pairs={watermarked.geometry_positive_pair_count}\n")
    sys.stdout.write(f"watermarked_geometry_positive_score_nonpositive={watermarked.geometry_positive_score_nonpositive_count}\n")
    sys.stdout.write(f"watermarked_mean_score_advantage_when_geometry_positive={watermarked.mean_score_advantage_when_geometry_positive}\n")
    sys.stdout.write(f"watermarked_pearson_geometry_vs_score={watermarked.pearson_geometry_vs_score}\n")
    sys.stdout.write(f"geometry_json={args.geometry_json.as_posix()}\n")
    sys.stdout.write(f"audit_json={args.audit_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
