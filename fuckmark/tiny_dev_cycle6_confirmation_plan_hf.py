from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import (
    build_cycle6_confirmation_plan,
    validate_cycle6_confirmation_contract,
    validate_cycle6_frozen_source_blobs,
)
from .hashing import sha256_json
from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION


CYCLE6_PLAN_PROVENANCE_VERSION = "cycle6-confirmation-plan-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-cycle6-confirmation-plan-hf")
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
    contract_hash = validate_cycle6_confirmation_contract(contract)
    validate_cycle6_frozen_source_blobs(Path.cwd(), contract)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("Cycle 6 confirmation planning requires a fast public tokenizer")
    started = _now()
    plan = build_cycle6_confirmation_plan(
        corpus,
        tokenizer,
        source_code_commit=args.source_code_commit,
        contract=contract,
    )
    write_canonical_json_fsynced(args.plan_json, plan)
    fsynced = _now()
    provenance_payload = {
        "algorithm_version": CYCLE6_PLAN_PROVENANCE_VERSION,
        "source_code_commit": args.source_code_commit,
        "contract_hash": contract_hash,
        "plan_hash": plan["plan_hash"],
        "planning_started_at_utc": started,
        "planning_fsynced_at_utc": fsynced,
        "planning_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {
        **provenance_payload,
        "provenance_hash": sha256_json(provenance_payload),
    }
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"contract_hash={contract_hash}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"row_count={len(plan['rows'])}\n")
    sys.stdout.write(
        f"selected_total={sum(int(row['selected_operation_count']) for row in plan['rows'])}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
