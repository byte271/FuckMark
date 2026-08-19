from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import canonical_json_text
from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .experiments.mid_dev_plan_io import MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE, MID_DEV_FROZEN_NGRAM_LEN
from .experiments.mid_dev_v5_builder import (
    MID_DEV_V5_BUILDER_VERSION,
    MID_DEV_V5_REQUIRED_CELL_REGISTRY,
    MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
    build_mid_dev_development_plan_v5,
)
from .hashing import sha256_json
from .mid_dev_context_survival_plan_hf import _validate_commit, _write_fsynced
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public


MID_DEV_V5_PLAN_PROVENANCE_VERSION = "mid-dev-v5-plan-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-development-plan-v5-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--ngram-len", type=int, default=MID_DEV_FROZEN_NGRAM_LEN)
    parser.add_argument("--context-history-size", type=int, default=MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--plan-json", type=Path, default=Path("artifacts/mid-dev-development-plan-v5.json"))
    parser.add_argument("--legacy-trace-json", type=Path, default=Path("artifacts/mid-dev-legacy-traces-v4.json"))
    parser.add_argument("--normalized-trace-json", type=Path, default=Path("artifacts/mid-dev-normalized-traces-v1.json"))
    parser.add_argument("--provenance-json", type=Path, default=Path("artifacts/mid-dev-development-plan-v5-provenance.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_code_commit = _validate_commit(args.source_code_commit)
    if args.ngram_len != MID_DEV_FROZEN_NGRAM_LEN:
        raise ValueError("production MidDev v5 planning requires ngram_len=5")
    if args.context_history_size != MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE:
        raise ValueError("production MidDev v5 planning requires context_history_size=1024")
    corpus = load_mid_dev_corpus_json(args.corpus_json)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned Transformers dependencies before MidDev v5 planning") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("MidDev v5 planning requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if {sample.model.identity_hash for sample in corpus.manifest.samples} != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match frozen MidDev corpus")
    started_at = _now()
    started = time.perf_counter()
    plan, legacy_traces, normalized_traces = build_mid_dev_development_plan_v5(
        corpus,
        tokenizer,
        source_code_commit=source_code_commit,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0
    _write_fsynced(args.plan_json, plan)
    _write_fsynced(args.legacy_trace_json, legacy_traces)
    _write_fsynced(args.normalized_trace_json, normalized_traces)
    fsynced_at = _now()
    payload = {
        "algorithm_version": MID_DEV_V5_PLAN_PROVENANCE_VERSION,
        "builder_version": MID_DEV_V5_BUILDER_VERSION,
        "source_code_commit": source_code_commit,
        "corpus_artifact_hash": corpus.artifact_hash,
        "development_plan_hash": plan.plan_hash,
        "legacy_plan_hash": plan.legacy_plan_hash,
        "legacy_trace_artifact_hash": legacy_traces.artifact_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "required_cell_registry": MID_DEV_V5_REQUIRED_CELL_REGISTRY,
        "required_cell_registry_hash": MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
        "legacy_row_count": len(plan.legacy_plan.rows),
        "normalized_row_count": len(plan.normalized_rows),
        "planning_started_at_utc": started_at,
        "planning_fsynced_at_utc": fsynced_at,
        "planning_wall_time_ms": wall_ms,
        "plan_fsync_success": True,
        "legacy_trace_fsync_success": True,
        "normalized_trace_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    _write_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"corpus_artifact_hash={corpus.artifact_hash}\n")
    sys.stdout.write(f"development_plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"legacy_plan_hash={plan.legacy_plan_hash}\n")
    sys.stdout.write(f"legacy_trace_artifact_hash={legacy_traces.artifact_hash}\n")
    sys.stdout.write(f"normalized_trace_artifact_hash={normalized_traces.artifact_hash}\n")
    sys.stdout.write(f"required_cell_registry_hash={MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH}\n")
    sys.stdout.write(f"legacy_row_count={len(plan.legacy_plan.rows)}\n")
    sys.stdout.write(f"normalized_row_count={len(plan.normalized_rows)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
