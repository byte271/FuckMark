from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_pair_io import load_mid_dev_calibration_pair_artifact_json
from .corpus.mid_dev_calibration_shards import CalibrationRole
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .detector_calibration import encode_text
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_audit import audit_frozen_calibration_threshold_registry
from .experiments.mid_dev_calibration_audit_registry import build_mid_dev_calibration_audit_registry
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
    load_frozen_calibration_threshold_registry_json,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_payload


MID_DEV_CALIBRATION_AUDIT_PROVENANCE_VERSION = "mid-dev-calibration-audit-provenance-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-audit-hf")
    parser.add_argument("--select-json", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--pair-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--threshold-registry-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def _runtime(args, select, audit, source_audit):
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before CAL-AUDIT") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("CAL-AUDIT requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if select.manifest.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen CAL-SELECT")
    if audit.manifest.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen CAL-AUDIT")
    if source_audit.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen opportunity audit")
    watermark_payload = default_watermark_payload()
    if source_audit.ngram_len != int(watermark_payload["ngram_len"]):
        raise RuntimeError("opportunity ngram_len differs from frozen detector configuration")
    if source_audit.context_history_size != int(watermark_payload["context_history_size"]):
        raise RuntimeError("opportunity context history differs from frozen detector configuration")
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
    return tokenizer, adapter, identity


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    select = load_mid_dev_calibration_merged_artifact_json(args.select_json)
    audit = load_mid_dev_calibration_merged_artifact_json(args.audit_json)
    pair = load_mid_dev_calibration_pair_artifact_json(args.pair_json)
    if select.role is not CalibrationRole.SELECT or audit.role is not CalibrationRole.AUDIT:
        raise RuntimeError("CAL-AUDIT requires SELECT then AUDIT merged artifacts")
    if select.readiness_hash != readiness.readiness_hash or audit.readiness_hash != readiness.readiness_hash:
        raise RuntimeError("merged calibration artifacts do not bind frozen readiness")
    if select.plan_hash != readiness.select_plan_hash or audit.plan_hash != readiness.audit_plan_hash:
        raise RuntimeError("merged calibration artifacts do not bind frozen role plans")
    if pair.readiness_hash != readiness.readiness_hash:
        raise RuntimeError("calibration pair does not bind frozen readiness")
    if pair.select_artifact_hash != select.artifact_hash or pair.audit_artifact_hash != audit.artifact_hash:
        raise RuntimeError("calibration pair does not bind supplied merged artifacts")
    if pair.select_manifest_hash != select.manifest.manifest_hash or pair.audit_manifest_hash != audit.manifest.manifest_hash:
        raise RuntimeError("calibration pair does not bind supplied manifests")

    source_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    registry = load_frozen_calibration_threshold_registry_json(args.threshold_registry_json)
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied opportunity audit")
    if registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("threshold registry does not bind supplied opportunity audit")
    if registry.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("threshold registry does not bind supplied regime decision")
    if registry.select_manifest_hash != select.manifest.manifest_hash:
        raise RuntimeError("threshold registry does not bind supplied CAL-SELECT manifest")

    tokenizer, adapter, identity = _runtime(args, select, audit, source_audit)
    artifacts = audit_frozen_calibration_threshold_registry(
        registry,
        audit.samples,
        audit.manifest,
        select.manifest,
        source_audit,
        decision,
        retokenize=lambda text: encode_text(tokenizer, text),
        adapter=adapter,
    )
    audit_registry = build_mid_dev_calibration_audit_registry(registry, artifacts)
    write_canonical_json_fsynced(args.json, audit_registry)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "pair_artifact_hash": pair.artifact_hash,
        "select_artifact_hash": select.artifact_hash,
        "audit_artifact_hash": audit.artifact_hash,
        "select_manifest_hash": select.manifest.manifest_hash,
        "audit_manifest_hash": audit.manifest.manifest_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "threshold_registry_hash": registry.registry_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "calibration_audit_registry_hash": audit_registry.registry_hash,
        "calibration_consistency_rule": audit_registry.calibration_consistency_rule,
        "consistency_pass": audit_registry.consistency_pass,
        "unstable_regime_ids": audit_registry.unstable_regime_ids,
        "reason_code": audit_registry.reason_code,
        "json_fsync_success": True,
        "threshold_recalibration_performed": False,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"pair_artifact_hash={pair.artifact_hash}\n")
    sys.stdout.write(f"threshold_registry_hash={registry.registry_hash}\n")
    sys.stdout.write(f"calibration_audit_registry_hash={audit_registry.registry_hash}\n")
    sys.stdout.write(f"consistency_pass={str(audit_registry.consistency_pass).lower()}\n")
    sys.stdout.write(f"unstable_regime_count={len(audit_registry.unstable_regime_ids)}\n")
    if audit_registry.reason_code is not None:
        sys.stdout.write(f"reason_code={audit_registry.reason_code}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
