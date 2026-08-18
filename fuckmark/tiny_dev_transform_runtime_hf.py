from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus import ModelTokenizerIdentity, PaddingSide, load_tiny_dev_corpus_json
from .hashing import sha256_json, sha256_text
from .tiny_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_payload
from .tiny_dev_transform_hf import _score_plan, _write_fsynced, build_transform_plan


BASELINE_TINY_DEV_BUDGETS = (1, 2, 4)
EXTENDED_TINY_DEV_BUDGETS = (1, 2, 4, 6)
DEFAULT_RANDOM_SEED_COUNT = 8


def runtime_tokenizer_identity(tokenizer, model_id: str, model_revision: str) -> ModelTokenizerIdentity:
    if tokenizer.eos_token_id is None:
        raise RuntimeError("runtime tokenizer must define eos_token_id")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    chat_template = getattr(tokenizer, "chat_template", None)
    if chat_template is not None and not isinstance(chat_template, str):
        raise RuntimeError("runtime tokenizer chat_template must be a string when present")
    padding_side = getattr(tokenizer, "padding_side", None)
    if padding_side != "left":
        raise RuntimeError("runtime tokenizer must use left padding to match the frozen TinyDev identity")
    return ModelTokenizerIdentity.create(
        model_id=model_id,
        model_revision=model_revision,
        tokenizer_id=model_id,
        tokenizer_revision=model_revision,
        chat_template_present=bool(chat_template),
        chat_template_hash=sha256_text(chat_template or ""),
        special_token_map_hash=sha256_json(tokenizer.special_tokens_map),
        padding_side=PaddingSide.LEFT,
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
        add_bos_token=bool(getattr(tokenizer, "add_bos_token", False)),
        add_eos_token=bool(getattr(tokenizer, "add_eos_token", False)),
    )


def budget_profile(name: str) -> tuple[int, ...]:
    if name == "baseline":
        return BASELINE_TINY_DEV_BUDGETS
    if name == "extended":
        return EXTENDED_TINY_DEV_BUDGETS
    raise ValueError("unsupported TinyDev transform budget profile")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-transform-runtime-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--budget-profile", choices=("baseline", "extended"), default="baseline")
    parser.add_argument("--random-seeds", type=int, default=DEFAULT_RANDOM_SEED_COUNT)
    parser.add_argument("--plan-json", type=Path, default=Path("artifacts/tiny-dev-transform-plan.json"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/tiny-dev-transform-evidence.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("TinyDev transform geometry requires a fast tokenizer with offset mappings")
    identity = runtime_tokenizer_identity(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the frozen TinyDev corpus identity")

    budgets = budget_profile(args.budget_profile)
    plan = build_transform_plan(
        corpus,
        tokenizer,
        budgets=budgets,
        random_seed_count=args.random_seeds,
    )
    _write_fsynced(args.plan_json, plan)

    watermark_payload = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=watermark_payload["ngram_len"],
            keys=watermark_payload["keys"],
            context_history_size=watermark_payload["context_history_size"],
            sampling_table_seed=watermark_payload["sampling_table_seed"],
            sampling_table_size=watermark_payload["sampling_table_size"],
            skip_first_ngram_calls=watermark_payload["skip_first_ngram_calls"],
            debug_mode=watermark_payload["debug_mode"],
        ),
        device=args.device,
    )
    evidence = _score_plan(corpus, tokenizer, plan, adapter)
    _write_fsynced(args.json, evidence)

    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    sys.stdout.write(f"budget_profile={args.budget_profile}\n")
    sys.stdout.write(f"budgets={','.join(str(value) for value in budgets)}\n")
    sys.stdout.write(
        f"pristine_positive={evidence['pristine_positive_detected_count']}/{evidence['pristine_positive_count']}\n"
    )
    sys.stdout.write(
        f"pristine_negative={evidence['pristine_negative_detected_count']}/{evidence['pristine_negative_count']}\n"
    )
    for summary in evidence["policy_summaries"]:
        sys.stdout.write(
            f"policy={summary['policy']} rows={summary['row_count']} "
            f"mean_damage={summary['mean_observation_damage_ratio']:.8f} "
            f"replacement_per_edit={summary['mean_replacement_per_edit']:.8f} "
            f"mean_score_drop={summary['mean_score_drop']:.8f} "
            f"detected={summary['transformed_detected_count']}/{summary['row_count']}\n"
        )
    sys.stdout.write(
        f"e07_lower_error_metric={evidence['e07'].lower_error_metric.value} "
        f"word_rmse={evidence['e07'].word_edit_rmse:.8f} "
        f"observation_rmse={evidence['e07'].observation_replacement_rmse:.8f}\n"
    )
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
