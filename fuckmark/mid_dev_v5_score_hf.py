from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .config import canonical_json_text
from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_plan_v5_io import load_mid_dev_development_plan_v5_json
from .experiments.mid_dev_v5_execution_contract import validate_mid_dev_v5_execution_contract
from .experiments.mid_dev_v5_runtime_io import load_mid_dev_normalized_trace_artifact_json
from .experiments.mid_dev_v5_scoring import score_mid_dev_development_plan_v5
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
    load_frozen_calibration_threshold_registry_json,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_payload


MID_DEV_V5_SCORING_PROVENANCE_VERSION = "mid-dev-v5-scoring-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _load_plan_provenance(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("v5 plan provenance must be a JSON object")
    expected_hash = sha256_json({key: item for key, item in value.items() if key != "provenance_hash"})
    if value.get("provenance_hash") != expected_hash:
        raise ValueError("v5 plan provenance hash does not replay")
    if text not in (canonical_json_text(value), canonical_json_text(value) + "\n"):
        raise ValueError("v5 plan provenance JSON is not canonical")
    return value


def _validate_plan_provenance(
    provenance: dict[str, object],
    *,
    plan,
    traces,
    corpus_artifact_hash: str,
    scoring_started_at: str,
) -> None:
    if provenance.get("corpus_artifact_hash") != corpus_artifact_hash:
        raise ValueError("v5 plan provenance does not bind supplied corpus")
    if provenance.get("development_plan_hash") != plan.plan_hash:
        raise ValueError("v5 plan provenance does not bind supplied development plan")
    if provenance.get("legacy_plan_hash") != plan.legacy_plan_hash:
        raise ValueError("v5 plan provenance does not bind embedded legacy plan")
    if provenance.get("normalized_trace_artifact_hash") != traces.artifact_hash:
        raise ValueError("v5 plan provenance does not bind normalized trace artifact")
    if provenance.get("source_code_commit") != plan.source_code_commit:
        raise ValueError("v5 plan provenance source commit drifted")
    if provenance.get("plan_fsync_success") is not True:
        raise ValueError("v5 plan provenance does not attest plan fsync")
    if provenance.get("legacy_trace_fsync_success") is not True:
        raise ValueError("v5 plan provenance does not attest legacy trace fsync")
    if provenance.get("normalized_trace_fsync_success") is not True:
        raise ValueError("v5 plan provenance does not attest normalized trace fsync")
    fsynced = _parse_time(provenance.get("planning_fsynced_at_utc"), "planning_fsynced_at_utc")
    scoring_started = _parse_time(scoring_started_at, "scoring_started_at_utc")
    if scoring_started < fsynced:
        raise ValueError("v5 scoring started before frozen plan/traces were fsynced")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-v5-score-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--normalized-trace-json", type=Path, required=True)
    parser.add_argument("--plan-provenance-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--threshold-registry-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, default=Path("artifacts/mid-dev-v5-scoring.json"))
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/mid-dev-v5-scoring-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scoring_started_at = _now()
    corpus = load_mid_dev_corpus_json(args.corpus_json)
    plan = load_mid_dev_development_plan_v5_json(args.plan_json)
    traces = load_mid_dev_normalized_trace_artifact_json(args.normalized_trace_json)
    execution = validate_mid_dev_v5_execution_contract(plan, traces)
    plan_provenance = _load_plan_provenance(args.plan_provenance_json)
    _validate_plan_provenance(
        plan_provenance,
        plan=plan,
        traces=traces,
        corpus_artifact_hash=corpus.artifact_hash,
        scoring_started_at=scoring_started_at,
    )
    source_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    registry = load_frozen_calibration_threshold_registry_json(args.threshold_registry_json)
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied opportunity audit")
    if registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("threshold registry does not bind supplied opportunity audit")
    if registry.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("threshold registry does not bind supplied regime decision")

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before v5 scoring") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("v5 scoring requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if {sample.model.identity_hash for sample in corpus.manifest.samples} != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match frozen MidDev corpus")
    if source_audit.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen opportunity audit")

    watermark_payload = default_watermark_payload()
    if source_audit.ngram_len != int(watermark_payload["ngram_len"]):
        raise RuntimeError("frozen opportunity ngram_len differs from scoring watermark configuration")
    if source_audit.context_history_size != int(watermark_payload["context_history_size"]):
        raise RuntimeError("frozen opportunity context history differs from scoring watermark configuration")
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
    evidence = score_mid_dev_development_plan_v5(
        corpus,
        plan,
        traces,
        source_audit,
        decision,
        registry,
        tokenizer,
        adapter,
    )
    write_canonical_json_fsynced(args.json, evidence)
    scoring_finished_at = _now()
    payload = {
        "algorithm_version": MID_DEV_V5_SCORING_PROVENANCE_VERSION,
        "source_code_commit": plan.source_code_commit,
        "corpus_artifact_hash": corpus.artifact_hash,
        "development_plan_hash": plan.plan_hash,
        "normalized_trace_artifact_hash": traces.artifact_hash,
        "execution_attestation_hash": execution.attestation_hash,
        "plan_provenance_hash": plan_provenance["provenance_hash"],
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "threshold_registry_hash": registry.registry_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "evidence_hash": evidence.artifact_hash,
        "scoring_started_at_utc": scoring_started_at,
        "scoring_finished_at_utc": scoring_finished_at,
        "separate_scoring_process": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"evidence_hash={evidence.artifact_hash}\n")
    sys.stdout.write(f"scoring_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"threshold_registry_hash={registry.registry_hash}\n")
    sys.stdout.write(f"detector_identity_hash={registry.detector_identity_hash}\n")
    sys.stdout.write(f"row_count={len(evidence.rows)}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
