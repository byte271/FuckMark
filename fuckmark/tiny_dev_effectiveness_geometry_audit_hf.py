from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.effectiveness_geometry_audit import build_effectiveness_geometry_audit
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
from .transforms.effectiveness_profile import CONTENT_REGION_GENERAL_SPACING_RULE_ID


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


def _general_spacing_hidden_counts(artifact: Mapping[str, object]) -> tuple[int, int, int]:
    rows = artifact.get("rows")
    if not isinstance(rows, (list, tuple)):
        raise TypeError("audit rows must be a sequence")
    hidden_count = 0
    actionable_count = 0
    row_count = 0
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            raise TypeError("audit row must be a mapping")
        hidden_rows = raw_row.get("hidden_exact_gain_rows")
        if not isinstance(hidden_rows, (list, tuple)):
            raise TypeError("hidden exact gain rows must be a sequence")
        matches = tuple(
            value
            for value in hidden_rows
            if isinstance(value, Mapping)
            and value.get("rule_id") == CONTENT_REGION_GENERAL_SPACING_RULE_ID
        )
        if matches:
            row_count += 1
            hidden_count += len(matches)
            if raw_row.get("proxy_saturated_before_budget") is True:
                actionable_count += len(matches)
    return row_count, hidden_count, actionable_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-effectiveness-geometry-audit-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-effectiveness-geometry-audit.json"),
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
        raise RuntimeError("exact geometry audit requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the frozen TinyDev corpus")

    sources = {sample.sample_id: sample.text for sample in _attack_samples(corpus)}
    artifact = build_effectiveness_geometry_audit(
        plan=plan,
        source_texts=sources,
        registry=registry,
        tokenizer=tokenizer,
        tokenizer_identity_hash=identity.identity_hash,
        ngram_len=profile.ngram_len,
    )
    write_canonical_json_fsynced(args.json, artifact)
    summary = artifact["summary"]
    general_rows, general_hidden, general_actionable = _general_spacing_hidden_counts(artifact)
    sys.stdout.write(f"profile_id={profile.profile_id}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={artifact['artifact_hash']}\n")
    sys.stdout.write(
        f"proxy_covered={summary['proxy_covered_observation_count']} "
        f"exact_destroyed={summary['exact_destroyed_observation_count']} "
        f"exact_minus_proxy={summary['exact_minus_proxy_count']}\n"
    )
    sys.stdout.write(
        f"proxy_overstatement_rows={summary['proxy_overstatement_row_count']} "
        f"proxy_understatement_rows={summary['proxy_understatement_row_count']} "
        f"proxy_saturation_rows={summary['proxy_saturation_row_count']}\n"
    )
    sys.stdout.write(
        f"hidden_exact_gain_rows={summary['hidden_exact_gain_row_count']} "
        f"hidden_exact_gain_candidates={summary['hidden_exact_gain_candidate_count']} "
        f"actionable_hidden_exact_gain_rows={summary['actionable_hidden_exact_gain_row_count']} "
        f"actionable_hidden_exact_gain_candidates={summary['actionable_hidden_exact_gain_candidate_count']} "
        f"maximum_hidden_exact_gain={summary['maximum_hidden_exact_gain']}\n"
    )
    sys.stdout.write(
        f"general_spacing_hidden_rows={general_rows} "
        f"general_spacing_hidden_candidates={general_hidden} "
        f"general_spacing_actionable_hidden_candidates={general_actionable}\n"
    )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
