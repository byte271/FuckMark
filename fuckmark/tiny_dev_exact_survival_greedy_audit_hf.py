from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.effectiveness_exact_greedy_audit import build_effectiveness_exact_greedy_audit
from .experiments.effectiveness_plan import validate_key_blind_high_coverage_plan
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .tiny_dev_transform_hf import _attack_samples
from .transforms import (
    CONTENT_REGION_COMBINED_PROFILE_ID,
    CONTENT_REGION_COVERAGE_PROFILE_ID,
    CONTENT_REGION_GENERAL_ONLY_PROFILE_ID,
    KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
    KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
    KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    content_region_combined_transform_registry,
    content_region_coverage_transform_registry,
    content_region_general_only_transform_registry,
    key_blind_coverage_completion_transform_registry,
    key_blind_high_coverage_transform_registry,
    resolve_effectiveness_profile,
    validate_effectiveness_profile_registry,
)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _plan_budgets(plan: Mapping[str, object]) -> tuple[int, ...]:
    profile_id = plan.get("profile_id")
    if profile_id == KEY_BLIND_HIGH_COVERAGE_PROFILE_ID:
        return ()
    raw = plan.get("budgets")
    if not isinstance(raw, list):
        raise ValueError("non-frozen effectiveness plans must record budgets as a list")
    budgets = tuple(int(value) for value in raw)
    if not budgets or budgets != tuple(sorted(set(budgets))) or any(value <= 0 for value in budgets):
        raise ValueError("plan budgets must be unique positive integers in ascending order")
    return budgets


def _registry_for_profile(profile_id: str):
    if profile_id in (KEY_BLIND_HIGH_COVERAGE_PROFILE_ID, KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID):
        return key_blind_high_coverage_transform_registry()
    if profile_id == KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID:
        return key_blind_coverage_completion_transform_registry()
    if profile_id == CONTENT_REGION_COVERAGE_PROFILE_ID:
        return content_region_coverage_transform_registry()
    if profile_id == CONTENT_REGION_GENERAL_ONLY_PROFILE_ID:
        return content_region_general_only_transform_registry()
    if profile_id == CONTENT_REGION_COMBINED_PROFILE_ID:
        return content_region_combined_transform_registry()
    raise ValueError("unknown effectiveness profile id")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-exact-survival-greedy-audit-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-exact-survival-greedy-audit.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    plan = _load_json(args.plan_json)
    profile_id = plan.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        raise ValueError("plan profile_id must be a non-empty string")
    profile = resolve_effectiveness_profile(profile_id, _plan_budgets(plan))
    registry = _registry_for_profile(profile_id)
    validate_effectiveness_profile_registry(profile, registry)
    validate_key_blind_high_coverage_plan(plan, corpus, profile)

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("exact-survival greedy audit requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the frozen TinyDev corpus")

    sources = {sample.sample_id: sample.text for sample in _attack_samples(corpus)}
    artifact = build_effectiveness_exact_greedy_audit(
        plan=plan,
        source_texts=sources,
        registry=registry,
        tokenizer=tokenizer,
        tokenizer_identity_hash=identity.identity_hash,
        ngram_len=profile.ngram_len,
    )
    write_canonical_json_fsynced(args.json, artifact)
    summary = artifact["summary"]
    sys.stdout.write(f"profile_id={profile.profile_id}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={artifact['artifact_hash']}\n")
    sys.stdout.write(
        f"baseline_exact_destroyed={summary['baseline_exact_destroyed_observation_count']} "
        f"exact_greedy_destroyed={summary['exact_greedy_destroyed_observation_count']} "
        f"gain={summary['exact_destruction_gain']}\n"
    )
    sys.stdout.write(
        f"improved_rows={summary['improved_row_count']} "
        f"equal_rows={summary['equal_row_count']} "
        f"regressed_rows={summary['regressed_row_count']} "
        f"changed_selection_rows={summary['changed_selection_row_count']}\n"
    )
    sys.stdout.write(
        f"baseline_selected={summary['baseline_selected_candidate_count']} "
        f"exact_greedy_selected={summary['exact_greedy_selected_candidate_count']} "
        f"policy_saturated_rows={summary['exact_greedy_policy_saturated_row_count']}\n"
    )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
