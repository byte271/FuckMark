from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_shards import CalibrationRole
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .detector_calibration import encode_text
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_audit import build_frozen_calibration_threshold_registry
from .experiments.mid_dev_calibration_merge_provenance_io import load_mid_dev_calibration_merge_provenance_json
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_payload


MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION = "mid-dev-calibration-threshold-provenance-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-threshold-hf")
    parser.add_argument("--select-json", type=Path, required=True)
    parser.add_argument("--select-merge-provenance-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def _runtime(args, select, source_audit):
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before calibration threshold construction") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("calibration threshold construction requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if select.manifest.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen CAL-SELECT")
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
    select_merge = load_mid_dev_calibration_merge_provenance_json(args.select_merge_provenance_json)
    if select.role is not CalibrationRole.SELECT:
        raise RuntimeError("threshold construction requires CAL-SELECT merged artifact")
    if select.readiness_hash != readiness.readiness_hash or select.plan_hash != readiness.select_plan_hash:
        raise RuntimeError("CAL-SELECT merged artifact does not bind frozen readiness/plan")
    if len(select.samples) != len(readiness.select_plan.prompt_ids):
        raise RuntimeError("CAL-SELECT sample count differs from frozen readiness")
    if select_merge["role"] != CalibrationRole.SELECT.value:
        raise RuntimeError("threshold construction requires CAL-SELECT merge provenance")
    if select_merge["readiness_hash"] != readiness.readiness_hash or select_merge["plan_hash"] != readiness.select_plan_hash:
        raise RuntimeError("CAL-SELECT merge provenance readiness/plan binding drifted")
    if select_merge["merged_artifact_hash"] != select.artifact_hash:
        raise RuntimeError("CAL-SELECT merge provenance artifact binding drifted")
    if select_merge["merged_manifest_hash"] != select.manifest.manifest_hash:
        raise RuntimeError("CAL-SELECT merge provenance manifest binding drifted")

    source_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied opportunity audit")
    if select_merge["opportunity_audit_hash"] != source_audit.artifact_hash:
        raise RuntimeError("CAL-SELECT was not generated under the supplied opportunity audit")
    if select_merge["regime_decision_hash"] != decision.decision_hash:
        raise RuntimeError("CAL-SELECT was not generated under the supplied regime decision")

    tokenizer, adapter, identity = _runtime(args, select, source_audit)
    registry = build_frozen_calibration_threshold_registry(
        select.samples,
        select.manifest,
        source_audit,
        decision,
        retokenize=lambda text: encode_text(tokenizer, text),
        adapter=adapter,
    )
    write_canonical_json_fsynced(args.json, registry)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "select_plan_hash": readiness.select_plan_hash,
        "select_merge_provenance_hash": select_merge["provenance_hash"],
        "select_artifact_hash": select.artifact_hash,
        "select_manifest_hash": select.manifest.manifest_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "threshold_registry_hash": registry.registry_hash,
        "regime_count": len(registry.records),
        "json_fsync_success": True,
        "cal_select_only": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"readiness_hash={readiness.readiness_hash}\n")
    sys.stdout.write(f"select_manifest_hash={select.manifest.manifest_hash}\n")
    sys.stdout.write(f"opportunity_audit_hash={source_audit.artifact_hash}\n")
    sys.stdout.write(f"regime_decision_hash={decision.decision_hash}\n")
    sys.stdout.write(f"detector_identity_hash={registry.detector_identity_hash}\n")
    sys.stdout.write(f"threshold_registry_hash={registry.registry_hash}\n")
    sys.stdout.write(f"regime_count={len(registry.records)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
