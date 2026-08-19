from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus.mid_dev_calibration_io import load_mid_dev_calibration_json
from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_scoring_io import (
    load_mid_dev_scoring_plan_json,
    load_mid_dev_scoring_trace_json,
    validate_mid_dev_scoring_plan_trace_binding,
)
from .experiments.mid_dev_scoring_safe import score_mid_dev_frozen_plan
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_payload


MID_DEV_SCORING_PROVENANCE_VERSION = "mid-dev-scoring-provenance-v3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _validate_plan_provenance(
    provenance: dict[str, object],
    *,
    corpus_artifact_hash: str,
    plan_hash: str,
    trace_artifact_hash: str,
    source_code_commit: str,
    scoring_started_at: str,
) -> None:
    expected = sha256_json(
        {key: value for key, value in provenance.items() if key != "provenance_hash"}
    )
    if provenance.get("provenance_hash") != expected:
        raise ValueError("MidDev plan provenance hash does not replay")
    if provenance.get("corpus_artifact_hash") != corpus_artifact_hash:
        raise ValueError("MidDev plan provenance does not bind the supplied corpus")
    if provenance.get("plan_hash") != plan_hash:
        raise ValueError("MidDev plan provenance does not bind the supplied plan")
    if provenance.get("trace_artifact_hash") != trace_artifact_hash:
        raise ValueError("MidDev plan provenance does not bind the supplied trace artifact")
    if provenance.get("source_code_commit") != source_code_commit:
        raise ValueError("MidDev plan provenance source commit does not match the frozen plan")
    if provenance.get("plan_fsync_success") is not True:
        raise ValueError("MidDev plan provenance does not attest plan fsync")
    if provenance.get("trace_fsync_success") is not True:
        raise ValueError("MidDev plan provenance does not attest trace fsync")
    fsynced = _parse_time(provenance.get("planning_fsynced_at_utc"), "planning_fsynced_at_utc")
    scoring_started = _parse_time(scoring_started_at, "scoring_started_at")
    if scoring_started < fsynced:
        raise ValueError("MidDev scoring started before the frozen plan was fsynced")


def _scoring_provenance(
    *,
    source_code_commit: str,
    corpus_artifact_hash: str,
    calibration_corpus_artifact_hash: str,
    calibration_source_profile_hash: str,
    length_calibration_registry_hash: str,
    plan_hash: str,
    trace_artifact_hash: str,
    plan_provenance_hash: str,
    evidence_hash: str,
    scoring_started_at: str,
    scoring_finished_at: str,
) -> dict[str, object]:
    github_sha = os.environ.get("GITHUB_SHA")
    payload = {
        "algorithm_version": MID_DEV_SCORING_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "corpus_artifact_hash": corpus_artifact_hash,
        "calibration_corpus_artifact_hash": calibration_corpus_artifact_hash,
        "calibration_source_profile_hash": calibration_source_profile_hash,
        "length_calibration_registry_hash": length_calibration_registry_hash,
        "plan_hash": plan_hash,
        "trace_artifact_hash": trace_artifact_hash,
        "plan_provenance_hash": plan_provenance_hash,
        "evidence_hash": evidence_hash,
        "scoring_started_at_utc": scoring_started_at,
        "scoring_finished_at_utc": scoring_finished_at,
        "separate_scoring_process": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": github_sha,
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
        "synthetic_pr_merge_checkout": bool(
            os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
            and github_sha
            and github_sha != source_code_commit
        ),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-context-survival-score-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--calibration-corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--trace-json", type=Path, required=True)
    parser.add_argument("--plan-provenance-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-evidence.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-scoring-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scoring_started_at = _now()
    mid_dev_corpus = load_mid_dev_corpus_json(args.corpus_json)
    calibration_corpus = load_mid_dev_calibration_json(args.calibration_corpus_json)
    plan = load_mid_dev_scoring_plan_json(args.plan_json)
    traces = load_mid_dev_scoring_trace_json(args.trace_json)
    validate_mid_dev_scoring_plan_trace_binding(plan, traces)
    plan_provenance = _load_json_object(args.plan_provenance_json)
    _validate_plan_provenance(
        plan_provenance,
        corpus_artifact_hash=mid_dev_corpus.artifact_hash,
        plan_hash=plan.plan_hash,
        trace_artifact_hash=traces.artifact_hash,
        source_code_commit=plan.source_code_commit,
        scoring_started_at=scoring_started_at,
    )

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned Transformers dependencies before MidDev scoring") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("MidDev scoring requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    mid_model_hashes = {sample.model.identity_hash for sample in mid_dev_corpus.manifest.samples}
    calibration_model_hashes = {
        sample.model.identity_hash for sample in calibration_corpus.manifest.samples
    }
    if mid_model_hashes != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match frozen MidDev corpus")
    if calibration_model_hashes != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match frozen length calibration corpus")

    watermark_payload = default_watermark_payload()
    if plan.ngram_len != int(watermark_payload["ngram_len"]):
        raise RuntimeError("frozen MidDev plan ngram_len does not match scoring watermark configuration")
    if plan.context_history_size != int(watermark_payload["context_history_size"]):
        raise RuntimeError("frozen MidDev context history does not match scoring watermark configuration")
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
    evidence = score_mid_dev_frozen_plan(
        mid_dev_corpus,
        calibration_corpus,
        tokenizer,
        plan,
        traces,
        adapter,
    )
    write_canonical_json_fsynced(args.json, evidence)
    scoring_finished_at = _now()
    provenance = _scoring_provenance(
        source_code_commit=plan.source_code_commit,
        corpus_artifact_hash=mid_dev_corpus.artifact_hash,
        calibration_corpus_artifact_hash=calibration_corpus.artifact_hash,
        calibration_source_profile_hash=calibration_corpus.source_profile_hash,
        length_calibration_registry_hash=evidence.length_calibration_registry_hash,
        plan_hash=plan.plan_hash,
        trace_artifact_hash=traces.artifact_hash,
        plan_provenance_hash=str(plan_provenance["provenance_hash"]),
        evidence_hash=evidence.artifact_hash,
        scoring_started_at=scoring_started_at,
        scoring_finished_at=scoring_finished_at,
    )
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"evidence_hash={evidence.artifact_hash}\n")
    sys.stdout.write(f"scoring_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"calibration_corpus_artifact_hash={evidence.calibration_corpus_artifact_hash}\n")
    sys.stdout.write(f"calibration_source_profile_hash={evidence.calibration_source_profile_hash}\n")
    sys.stdout.write(f"detector_identity_hash={evidence.detector_identity_hash}\n")
    sys.stdout.write(f"length_calibration_registry_hash={evidence.length_calibration_registry_hash}\n")
    for binding in evidence.length_calibrations:
        sys.stdout.write(
            f"length_{binding.target_length}_threshold_hash={binding.threshold_hash}\n"
        )
        sys.stdout.write(
            f"length_{binding.target_length}_threshold_value={binding.threshold_value}\n"
        )
    sys.stdout.write(f"row_count={len(evidence.rows)}\n")
    sys.stdout.write(f"pristine_watermarked_detected={evidence.pristine_watermarked_detected_count}/36\n")
    sys.stdout.write(f"pristine_control_detected={evidence.pristine_control_detected_count}/36\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
