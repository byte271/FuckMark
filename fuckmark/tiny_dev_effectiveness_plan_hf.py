from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.effectiveness_plan import (
    build_key_blind_high_coverage_plan,
)
from .hashing import sha256_json
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .transforms import (
    KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
    KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
    CONTENT_REGION_COVERAGE_PROFILE_ID,
    resolve_effectiveness_profile,
)


EFFECTIVENESS_PLAN_PROVENANCE_VERSION = "effectiveness-plan-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance(
    *,
    source_code_commit: str,
    plan_hash: str,
    profile_hash: str,
    plan_started_at: str,
    plan_fsynced_at: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": EFFECTIVENESS_PLAN_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "plan_hash": plan_hash,
        "profile_hash": profile_hash,
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


def _parse_budgets(raw: str) -> tuple[int, ...]:
    if not raw:
        return ()
    values: list[int] = []
    for chunk in raw.split(","):
        stripped = chunk.strip()
        if not stripped:
            raise ValueError("budget list contains an empty entry")
        value = int(stripped)
        if value <= 0:
            raise ValueError("budgets must be positive integers")
        values.append(value)
    budgets = tuple(sorted(set(values)))
    if budgets != tuple(values):
        raise ValueError("budgets must be provided in ascending order without duplicates")
    return budgets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-effectiveness-plan-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument(
        "--profile-id",
        default=KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
        choices=(
            KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
            KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
            KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
            CONTENT_REGION_COVERAGE_PROFILE_ID,
        ),
    )
    parser.add_argument("--budgets", default="")
    parser.add_argument(
        "--plan-json",
        type=Path,
        default=Path("artifacts/tiny-dev-effectiveness-plan.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/tiny-dev-effectiveness-plan-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    profile = resolve_effectiveness_profile(args.profile_id, _parse_budgets(args.budgets))
    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("effectiveness planning requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the frozen TinyDev corpus")

    started_at = _now()
    plan = build_key_blind_high_coverage_plan(
        corpus,
        tokenizer,
        profile=profile,
        source_code_commit=args.source_code_commit,
    )
    write_canonical_json_fsynced(args.plan_json, plan)
    fsynced_at = _now()
    provenance = _provenance(
        source_code_commit=args.source_code_commit,
        plan_hash=plan["plan_hash"],
        profile_hash=profile.profile_hash,
        plan_started_at=started_at,
        plan_fsynced_at=fsynced_at,
    )
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"profile_id={profile.profile_id}\n")
    sys.stdout.write(f"profile_hash={profile.profile_hash}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"variant_count={len(plan['variants'])}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
