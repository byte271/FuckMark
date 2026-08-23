from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.exact_survival_effectiveness_plan import build_exact_survival_effectiveness_plan, validate_exact_survival_confirmation_contract
from .hashing import sha256_json
from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION, runtime_tokenizer_identity_public


EXACT_SURVIVAL_PLAN_PROVENANCE_VERSION = "exact-survival-plan-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _provenance(
    *,
    source_code_commit: str,
    plan_hash: str,
    contract_hash: str,
    plan_started_at: str,
    plan_fsynced_at: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": EXACT_SURVIVAL_PLAN_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "plan_hash": plan_hash,
        "contract_hash": contract_hash,
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
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-exact-survival-effectiveness-plan-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error
    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    contract = _load_json(args.contract_json)
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("exact-survival effectiveness planning requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the confirmation corpus")
    started_at = _now()
    plan = build_exact_survival_effectiveness_plan(
        corpus,
        tokenizer,
        source_code_commit=args.source_code_commit,
        contract=contract,
    )
    write_canonical_json_fsynced(args.plan_json, plan)
    fsynced_at = _now()
    provenance = _provenance(
        source_code_commit=args.source_code_commit,
        plan_hash=plan["plan_hash"],
        contract_hash=contract_hash,
        plan_started_at=started_at,
        plan_fsynced_at=fsynced_at,
    )
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"contract_hash={contract_hash}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"variant_count={len(plan['variants'])}\n")
    sys.stdout.write(f"selected_total={sum(int(row['realized_edit_cost']) for row in plan['variants'])}\n")
    sys.stdout.write(f"exact_destroyed_total={sum(int(row['exact_destroyed_observation_count']) for row in plan['variants'])}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
