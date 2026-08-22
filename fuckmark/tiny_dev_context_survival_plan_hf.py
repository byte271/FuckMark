from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import canonical_json_text
from .corpus import ModelTokenizerIdentity, PaddingSide, load_tiny_dev_corpus_json
from .experiments import context_survival_plan as context_survival_plan_module
from .experiments.context_survival_plan import (
    DEFAULT_BEAM_WIDTH,
    DEFAULT_BUDGETS,
    DEFAULT_MAX_RISK_TIER,
    DEFAULT_RANDOM_SEED_COUNT,
)
from .hashing import sha256_json, sha256_text
from .scheduling.beam_v2 import (
    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
    diverse_beam_search,
)
from .transforms import TransformRegistry, development_sentence_boundary_softbreak_rules
from .transforms.contractions import context_survival_contraction_rules
from .transforms.surface_rules import development_surface_rules


DEFAULT_MODEL_ID = "openai-community/gpt2"
DEFAULT_MODEL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
DEFAULT_NGRAM_LEN = 5
DEFAULT_CONTEXT_HISTORY_SIZE = 1024
TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION = "tiny-dev-context-survival-plan-v3"
TINY_DEV_SEQUENCE_BOUNDARY_PLAN_VERSION = "tiny-dev-sequence-boundary-softbreak-plan-v1"
TINY_DEV_CONTEXT_SURVIVAL_PLAN_PROVENANCE_VERSION = "tiny-dev-context-survival-plan-provenance-v1"
HISTORICAL_CONTEXT_REGISTRY_PROFILE = "historical-context-v3"
SEQUENCE_BOUNDARY_REGISTRY_PROFILE = "sequence-boundary-softbreak-v1"


def _parse_budgets(value: str) -> tuple[int, ...]:
    try:
        budgets = tuple(sorted({int(part.strip()) for part in value.split(",") if part.strip()}))
    except ValueError as error:
        raise argparse.ArgumentTypeError("budgets must be comma-separated positive integers") from error
    if not budgets or any(item <= 0 for item in budgets):
        raise argparse.ArgumentTypeError("budgets must be comma-separated positive integers")
    return budgets


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_fsynced(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_text(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if os.name == "posix":
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def runtime_tokenizer_identity_public(
    tokenizer,
    model_id: str,
    model_revision: str,
) -> ModelTokenizerIdentity:
    if tokenizer.eos_token_id is None:
        raise RuntimeError("runtime tokenizer must define eos_token_id")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    chat_template = getattr(tokenizer, "chat_template", None)
    if chat_template is not None and not isinstance(chat_template, str):
        raise RuntimeError("runtime tokenizer chat_template must be a string when present")
    padding_side = getattr(tokenizer, "padding_side", None)
    if padding_side != "left":
        raise RuntimeError("runtime tokenizer must use left padding to match frozen TinyDev identity")
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


def _build_attested_context_survival_plan(
    corpus,
    tokenizer,
    *,
    algorithm_version: str,
    registry_profile: str | None,
    registry: TransformRegistry | None = None,
    **kwargs,
) -> dict[str, object]:
    original_beam_search = context_survival_plan_module.beam_search
    original_expander = context_survival_plan_module.ContextSurvivalExpander
    observed_expanders = []

    class _ObservedExpander(original_expander):
        def __init__(self, *args, **inner_kwargs) -> None:
            super().__init__(*args, **inner_kwargs)
            observed_expanders.append(self)

    context_survival_plan_module.beam_search = diverse_beam_search
    context_survival_plan_module.ContextSurvivalExpander = _ObservedExpander
    try:
        base_plan = context_survival_plan_module.build_context_survival_plan(
            corpus,
            tokenizer,
            registry=registry,
            **kwargs,
        )
    finally:
        context_survival_plan_module.beam_search = original_beam_search
        context_survival_plan_module.ContextSurvivalExpander = original_expander
    if not observed_expanders:
        raise RuntimeError("context-survival plan produced no expander attestation")
    detector_access_observed = any(value.detector_access_observed for value in observed_expanders)
    secret_access_observed = any(value.secret_access_observed for value in observed_expanders)
    if detector_access_observed or secret_access_observed:
        raise RuntimeError("context-survival plan access attestation is contaminated")
    payload = {key: value for key, value in base_plan.items() if key != "plan_hash"}
    payload["algorithm_version"] = algorithm_version
    if registry_profile is not None:
        payload["registry_profile"] = registry_profile
    payload["beam_algorithm_version"] = CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    payload["detector_access_observed"] = detector_access_observed
    payload["secret_access_observed"] = secret_access_observed
    payload["attested_expander_count"] = len(observed_expanders)
    return {**payload, "plan_hash": sha256_json(payload)}


def _build_context_survival_plan_v3(corpus, tokenizer, **kwargs) -> dict[str, object]:
    return _build_attested_context_survival_plan(
        corpus,
        tokenizer,
        algorithm_version=TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION,
        registry_profile=None,
        **kwargs,
    )


def _sequence_boundary_registry() -> TransformRegistry:
    return TransformRegistry(
        (
            *context_survival_contraction_rules(),
            *development_surface_rules(),
            *development_sentence_boundary_softbreak_rules(),
        )
    )


def _build_sequence_boundary_plan_v1(corpus, tokenizer, **kwargs) -> dict[str, object]:
    return _build_attested_context_survival_plan(
        corpus,
        tokenizer,
        algorithm_version=TINY_DEV_SEQUENCE_BOUNDARY_PLAN_VERSION,
        registry_profile=SEQUENCE_BOUNDARY_REGISTRY_PROFILE,
        registry=_sequence_boundary_registry(),
        **kwargs,
    )


def _plan_provenance(
    *,
    source_code_commit: str,
    plan_hash: str,
    plan_started_at: str,
    plan_fsynced_at: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": TINY_DEV_CONTEXT_SURVIVAL_PLAN_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "plan_hash": plan_hash,
        "plan_started_at_utc": plan_started_at,
        "plan_fsynced_at_utc": plan_fsynced_at,
        "plan_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-context-survival-plan-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--budgets", type=_parse_budgets, default=DEFAULT_BUDGETS)
    parser.add_argument("--random-seeds", type=int, default=DEFAULT_RANDOM_SEED_COUNT)
    parser.add_argument("--beam-width", type=int, default=DEFAULT_BEAM_WIDTH)
    parser.add_argument("--max-risk-tier", type=int, default=DEFAULT_MAX_RISK_TIER)
    parser.add_argument("--ngram-len", type=int, default=DEFAULT_NGRAM_LEN)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument(
        "--registry-profile",
        choices=(HISTORICAL_CONTEXT_REGISTRY_PROFILE, SEQUENCE_BOUNDARY_REGISTRY_PROFILE),
        default=HISTORICAL_CONTEXT_REGISTRY_PROFILE,
    )
    parser.add_argument(
        "--plan-json",
        type=Path,
        default=Path("artifacts/tiny-dev-context-survival-plan.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/tiny-dev-context-survival-plan-provenance.json"),
    )
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
        raise RuntimeError("TinyDev context-survival geometry requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen TinyDev corpus")

    plan_started_at = _now()
    builder = (
        _build_sequence_boundary_plan_v1
        if args.registry_profile == SEQUENCE_BOUNDARY_REGISTRY_PROFILE
        else _build_context_survival_plan_v3
    )
    plan = builder(
        corpus,
        tokenizer,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
        budgets=args.budgets,
        random_seed_count=args.random_seeds,
        beam_width=args.beam_width,
        max_risk_tier=args.max_risk_tier,
        source_code_commit=args.source_code_commit,
    )
    _write_fsynced(args.plan_json, plan)
    plan_fsynced_at = _now()
    provenance = _plan_provenance(
        source_code_commit=args.source_code_commit,
        plan_hash=plan["plan_hash"],
        plan_started_at=plan_started_at,
        plan_fsynced_at=plan_fsynced_at,
    )
    _write_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"plan_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"beam_algorithm_version={plan['beam_algorithm_version']}\n")
    sys.stdout.write(f"attested_expanders={plan['attested_expander_count']}\n")
    sys.stdout.write(f"variant_count={len(plan['variants'])}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
