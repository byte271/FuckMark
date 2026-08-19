from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import canonical_json_text
from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .experiments.mid_dev_plan_builder import build_mid_dev_context_survival_plan
from .experiments.mid_dev_plan_io import (
    MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE,
    MID_DEV_FROZEN_NGRAM_LEN,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public


MID_DEV_PLAN_PROVENANCE_VERSION = "mid-dev-plan-provenance-v1"


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


def _validate_commit(value: str) -> str:
    if len(value) not in (40, 64) or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("source-code-commit must be an immutable lowercase hexadecimal commit")
    return value


def _provenance(
    *,
    source_code_commit: str,
    corpus_artifact_hash: str,
    plan_hash: str,
    trace_artifact_hash: str,
    planning_started_at: str,
    planning_fsynced_at: str,
    planning_wall_time_ms: float,
) -> dict[str, object]:
    payload = {
        "algorithm_version": MID_DEV_PLAN_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "corpus_artifact_hash": corpus_artifact_hash,
        "plan_hash": plan_hash,
        "trace_artifact_hash": trace_artifact_hash,
        "planning_started_at_utc": planning_started_at,
        "planning_fsynced_at_utc": planning_fsynced_at,
        "planning_wall_time_ms": planning_wall_time_ms,
        "plan_fsync_success": True,
        "trace_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-context-survival-plan-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--ngram-len", type=int, default=MID_DEV_FROZEN_NGRAM_LEN)
    parser.add_argument(
        "--context-history-size",
        type=int,
        default=MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE,
    )
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument(
        "--plan-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-plan.json"),
    )
    parser.add_argument(
        "--trace-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-traces.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-plan-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_code_commit = _validate_commit(args.source_code_commit)
    if args.ngram_len != MID_DEV_FROZEN_NGRAM_LEN:
        raise ValueError("production MidDev planning requires ngram_len=5")
    if args.context_history_size != MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE:
        raise ValueError("production MidDev planning requires context_history_size=1024")
    corpus = load_mid_dev_corpus_json(args.corpus_json)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned Transformers dependencies before MidDev planning") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("MidDev planning requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    corpus_model_hashes = {sample.model.identity_hash for sample in corpus.manifest.samples}
    if corpus_model_hashes != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match the frozen MidDev corpus")

    planning_started_at = _now()
    started = time.perf_counter()
    plan, traces = build_mid_dev_context_survival_plan(
        corpus,
        tokenizer,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
        source_code_commit=source_code_commit,
    )
    if plan.ngram_len != args.ngram_len or plan.context_history_size != args.context_history_size:
        raise RuntimeError("frozen MidDev plan geometry binding does not match planner inputs")
    planning_wall_time_ms = (time.perf_counter() - started) * 1000.0
    _write_fsynced(args.plan_json, plan)
    _write_fsynced(args.trace_json, traces)
    planning_fsynced_at = _now()
    provenance = _provenance(
        source_code_commit=source_code_commit,
        corpus_artifact_hash=corpus.artifact_hash,
        plan_hash=plan.plan_hash,
        trace_artifact_hash=traces.artifact_hash,
        planning_started_at=planning_started_at,
        planning_fsynced_at=planning_fsynced_at,
        planning_wall_time_ms=planning_wall_time_ms,
    )
    _write_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"corpus_artifact_hash={corpus.artifact_hash}\n")
    sys.stdout.write(f"plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"trace_artifact_hash={traces.artifact_hash}\n")
    sys.stdout.write(f"plan_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"row_count={len(plan.rows)}\n")
    sys.stdout.write(f"ngram_len={plan.ngram_len}\n")
    sys.stdout.write(f"context_history_size={plan.context_history_size}\n")
    sys.stdout.write(f"attested_expander_count={plan.selection_attestation.attested_expander_count}\n")
    sys.stdout.write(f"detector_access_observed={plan.selection_attestation.detector_access_observed}\n")
    sys.stdout.write(f"secret_access_observed={plan.selection_attestation.secret_access_observed}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"trace_json={args.trace_json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
