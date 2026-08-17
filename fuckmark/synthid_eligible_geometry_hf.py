from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_eligible_geometry import run_synthid_eligible_geometry_pilot
from .synthid_geometry_hf import (
    HuggingFaceSynthIDGeometryBackend,
    _load_prompts,
    _parse_budgets,
    _registry,
)
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


class HuggingFaceSynthIDEligibilityGeometryBackend(HuggingFaceSynthIDGeometryBackend):
    @property
    def eos_token_id(self) -> int:
        value = self._tokenizer.eos_token_id
        if value is None:
            raise RuntimeError("tokenizer eos_token_id became unavailable")
        return int(value)

    @property
    def context_history_size(self) -> int:
        return self._adapter.config.context_history_size


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-eligible-geometry")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=10)
    parser.add_argument("--seed-base", type=int, default=275000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--schedule-seed", type=int, default=9500)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-eligible-geometry.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.schedule_seed < 0 or args.schedule_seed >= 1 << 64:
        raise ValueError("schedule-seed must fit in 64 bits")
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
    report = run_synthid_eligible_geometry_pilot(
        prompts,
        backend,
        _registry(args.registry),
        budgets=args.budgets,
        schedule_seed=args.schedule_seed,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    summary = report.summary
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"prompt_count={summary.prompt_count}\n")
    sys.stdout.write(f"variant_count={summary.variant_count}\n")
    sys.stdout.write(f"pair_count={summary.pair_count}\n")
    sys.stdout.write(f"matched_pair_count={summary.matched_pair_count}\n")
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"mean_control_public_valid_fraction={summary.mean_control_public_valid_fraction}\n")
    sys.stdout.write(f"mean_watermarked_public_valid_fraction={summary.mean_watermarked_public_valid_fraction}\n")
    sys.stdout.write(f"matched_same_selection_rate={summary.matched_same_selection_rate}\n")
    sys.stdout.write(f"mean_control_valid_disruption_advantage={summary.mean_control_valid_disruption_advantage}\n")
    sys.stdout.write(f"mean_watermarked_valid_disruption_advantage={summary.mean_watermarked_valid_disruption_advantage}\n")
    sys.stdout.write(f"mean_control_score_drop_advantage={summary.mean_control_score_drop_advantage}\n")
    sys.stdout.write(f"mean_watermarked_score_drop_advantage={summary.mean_watermarked_score_drop_advantage}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
