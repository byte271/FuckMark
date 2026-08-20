from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_shards import CalibrationRole
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_audit import build_frozen_calibration_threshold_registry
from .experiments.mid_dev_calibration_compaction_io import (
    load_mid_dev_calibration_compaction_provenance_json,
)
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .experiments.mid_dev_calibration_threshold_compacted_provenance_io import (
    MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_VERSION,
)
from .experiments.mid_dev_source_opportunity_coverage_io import (
    load_mid_dev_source_opportunity_coverage_json,
)
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
)
from .hashing import sha256_json
from .mid_dev_calibration_threshold_hf import _runtime
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .detector_calibration import encode_text


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-threshold-compacted-hf")
    parser.add_argument("--select-json", type=Path, required=True)
    parser.add_argument("--select-compaction-provenance-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--source-coverage-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    select = load_mid_dev_calibration_merged_artifact_json(args.select_json)
    compaction = load_mid_dev_calibration_compaction_provenance_json(
        args.select_compaction_provenance_json
    )
    opportunity = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    coverage = load_mid_dev_source_opportunity_coverage_json(args.source_coverage_json)

    if select.role is not CalibrationRole.SELECT:
        raise RuntimeError("threshold construction requires compacted CAL-SELECT")
    if select.readiness_hash != readiness.readiness_hash or select.plan_hash != readiness.select_plan_hash:
        raise RuntimeError("compacted CAL-SELECT does not bind frozen v2 readiness/plan")
    if compaction["role"] != CalibrationRole.SELECT.value:
        raise RuntimeError("threshold construction requires CAL-SELECT compaction provenance")
    if compaction["readiness_hash"] != readiness.readiness_hash or compaction["plan_hash"] != readiness.select_plan_hash:
        raise RuntimeError("CAL-SELECT compaction readiness/plan binding drifted")
    if compaction["compacted_artifact_hash"] != select.artifact_hash:
        raise RuntimeError("CAL-SELECT compaction artifact binding drifted")
    if compaction["compacted_manifest_hash"] != select.manifest.manifest_hash:
        raise RuntimeError("CAL-SELECT compaction manifest binding drifted")
    if compaction["calibration_opportunity_audit_hash"] != opportunity.artifact_hash:
        raise RuntimeError("CAL-SELECT compaction opportunity binding drifted")
    if compaction["regime_decision_hash"] != decision.decision_hash:
        raise RuntimeError("CAL-SELECT compaction regime binding drifted")
    if compaction["source_coverage_artifact_hash"] != coverage.artifact_hash:
        raise RuntimeError("CAL-SELECT compaction source coverage binding drifted")
    if decision.opportunity_audit_hash != opportunity.artifact_hash:
        raise RuntimeError("regime decision does not bind opportunity audit")
    if coverage.calibration_opportunity_audit_hash != opportunity.artifact_hash:
        raise RuntimeError("source coverage opportunity binding drifted")
    if coverage.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("source coverage regime binding drifted")

    tokenizer, adapter, identity = _runtime(args, select, opportunity)
    registry = build_frozen_calibration_threshold_registry(
        select.samples,
        select.manifest,
        opportunity,
        decision,
        retokenize=lambda text: encode_text(tokenizer, text),
        adapter=adapter,
    )
    serious = tuple(compaction["serious_regime_ids"])
    descriptive = tuple(compaction["descriptive_regime_ids"])
    if tuple(item.regime_id for item in registry.records) != serious:
        raise RuntimeError("threshold registry regime set differs from frozen serious compaction set")
    write_canonical_json_fsynced(args.json, registry)

    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "select_plan_hash": readiness.select_plan_hash,
        "select_compaction_provenance_hash": compaction["provenance_hash"],
        "select_artifact_hash": select.artifact_hash,
        "select_manifest_hash": select.manifest.manifest_hash,
        "opportunity_audit_hash": opportunity.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "source_coverage_artifact_hash": coverage.artifact_hash,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "threshold_registry_hash": registry.registry_hash,
        "serious_regime_ids": serious,
        "descriptive_regime_ids": descriptive,
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

    sys.stdout.write(f"threshold_registry_hash={registry.registry_hash}\n")
    sys.stdout.write(f"serious_regime_ids={','.join(serious)}\n")
    sys.stdout.write(f"descriptive_regime_ids={','.join(descriptive)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
