from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_pair_io import load_mid_dev_calibration_pair_artifact_json
from .corpus.mid_dev_calibration_shards import CalibrationRole, validate_calibration_merged_independence
from .detector_calibration import encode_text
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_audit import audit_frozen_calibration_threshold_registry
from .experiments.mid_dev_calibration_audit_registry import build_mid_dev_calibration_audit_registry
from .experiments.mid_dev_calibration_compaction_io import (
    load_mid_dev_calibration_compaction_provenance_json,
)
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .experiments.mid_dev_calibration_threshold_compacted_provenance_io import (
    load_mid_dev_calibration_threshold_compacted_provenance_json,
)
from .experiments.mid_dev_source_opportunity_coverage_io import (
    load_mid_dev_source_opportunity_coverage_json,
)
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
    load_frozen_calibration_threshold_registry_json,
)
from .hashing import sha256_json
from .mid_dev_calibration_audit_hf import _runtime
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION


MID_DEV_CALIBRATION_AUDIT_COMPACTED_PROVENANCE_VERSION = (
    "mid-dev-calibration-audit-compacted-provenance-v1"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-audit-compacted-hf")
    parser.add_argument("--select-json", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--select-compaction-provenance-json", type=Path, required=True)
    parser.add_argument("--audit-compaction-provenance-json", type=Path, required=True)
    parser.add_argument("--candidate-pair-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--source-coverage-json", type=Path, required=True)
    parser.add_argument("--threshold-registry-json", type=Path, required=True)
    parser.add_argument("--threshold-provenance-json", type=Path, required=True)
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
    audit = load_mid_dev_calibration_merged_artifact_json(args.audit_json)
    select_compaction = load_mid_dev_calibration_compaction_provenance_json(
        args.select_compaction_provenance_json
    )
    audit_compaction = load_mid_dev_calibration_compaction_provenance_json(
        args.audit_compaction_provenance_json
    )
    pair = load_mid_dev_calibration_pair_artifact_json(args.candidate_pair_json)
    source_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    coverage = load_mid_dev_source_opportunity_coverage_json(args.source_coverage_json)
    registry = load_frozen_calibration_threshold_registry_json(args.threshold_registry_json)
    threshold_provenance = load_mid_dev_calibration_threshold_compacted_provenance_json(
        args.threshold_provenance_json
    )

    if select.role is not CalibrationRole.SELECT or audit.role is not CalibrationRole.AUDIT:
        raise RuntimeError("compacted CAL-AUDIT requires SELECT then AUDIT artifacts")
    if select.readiness_hash != readiness.readiness_hash or audit.readiness_hash != readiness.readiness_hash:
        raise RuntimeError("compacted calibration artifacts do not bind frozen readiness")
    if select.plan_hash != readiness.select_plan_hash or audit.plan_hash != readiness.audit_plan_hash:
        raise RuntimeError("compacted calibration artifacts do not bind frozen role plans")
    if select_compaction["role"] != CalibrationRole.SELECT.value:
        raise RuntimeError("SELECT compaction provenance role drifted")
    if audit_compaction["role"] != CalibrationRole.AUDIT.value:
        raise RuntimeError("AUDIT compaction provenance role drifted")
    if select_compaction["compacted_artifact_hash"] != select.artifact_hash:
        raise RuntimeError("SELECT compaction artifact binding drifted")
    if audit_compaction["compacted_artifact_hash"] != audit.artifact_hash:
        raise RuntimeError("AUDIT compaction artifact binding drifted")
    if select_compaction["compacted_manifest_hash"] != select.manifest.manifest_hash:
        raise RuntimeError("SELECT compaction manifest binding drifted")
    if audit_compaction["compacted_manifest_hash"] != audit.manifest.manifest_hash:
        raise RuntimeError("AUDIT compaction manifest binding drifted")
    if audit_compaction["select_compaction_provenance_hash"] != select_compaction["provenance_hash"]:
        raise RuntimeError("AUDIT compaction does not bind frozen SELECT compaction")
    if select_compaction["serious_regime_ids"] != audit_compaction["serious_regime_ids"]:
        raise RuntimeError("SELECT/AUDIT serious regime sets differ")
    if select_compaction["descriptive_regime_ids"] != audit_compaction["descriptive_regime_ids"]:
        raise RuntimeError("SELECT/AUDIT descriptive regime sets differ")

    select_records = {item["regime_id"]: item for item in select_compaction["records"]}
    audit_records = {item["regime_id"]: item for item in audit_compaction["records"]}
    if set(select_records) != set(audit_records):
        raise RuntimeError("SELECT/AUDIT compaction record regime sets differ")
    for regime_id in select_records:
        if select_records[regime_id]["selected_count"] != audit_records[regime_id]["selected_count"]:
            raise RuntimeError(f"CAL-AUDIT regime {regime_id} does not mirror frozen SELECT N")

    if pair.readiness_hash != readiness.readiness_hash:
        raise RuntimeError("candidate-pool pair does not bind frozen readiness")
    if pair.select_artifact_hash != select_compaction["candidate_pool_artifact_hash"]:
        raise RuntimeError("candidate-pool pair does not bind SELECT candidate pool")
    if pair.audit_artifact_hash != audit_compaction["candidate_pool_artifact_hash"]:
        raise RuntimeError("candidate-pool pair does not bind AUDIT candidate pool")
    if pair.select_manifest_hash != select_compaction["candidate_pool_manifest_hash"]:
        raise RuntimeError("candidate-pool pair does not bind SELECT candidate manifest")
    if pair.audit_manifest_hash != audit_compaction["candidate_pool_manifest_hash"]:
        raise RuntimeError("candidate-pool pair does not bind AUDIT candidate manifest")
    if pair.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("candidate-pool pair opportunity binding drifted")
    if pair.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("candidate-pool pair regime binding drifted")

    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied opportunity audit")
    if coverage.calibration_opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("source coverage opportunity binding drifted")
    if coverage.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("source coverage regime binding drifted")
    for compaction in (select_compaction, audit_compaction):
        if compaction["source_coverage_artifact_hash"] != coverage.artifact_hash:
            raise RuntimeError("compaction source coverage binding drifted")
        if compaction["calibration_opportunity_audit_hash"] != source_audit.artifact_hash:
            raise RuntimeError("compaction opportunity binding drifted")
        if compaction["regime_decision_hash"] != decision.decision_hash:
            raise RuntimeError("compaction regime binding drifted")

    validate_calibration_merged_independence(select.manifest, audit.manifest)
    if registry.select_manifest_hash != select.manifest.manifest_hash:
        raise RuntimeError("threshold registry does not bind compacted CAL-SELECT manifest")
    if registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise RuntimeError("threshold registry opportunity binding drifted")
    if registry.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("threshold registry regime binding drifted")
    serious = tuple(select_compaction["serious_regime_ids"])
    if tuple(item.regime_id for item in registry.records) != serious:
        raise RuntimeError("threshold registry regime set differs from serious compaction set")

    if threshold_provenance["readiness_hash"] != readiness.readiness_hash:
        raise RuntimeError("threshold provenance readiness binding drifted")
    if threshold_provenance["select_compaction_provenance_hash"] != select_compaction["provenance_hash"]:
        raise RuntimeError("threshold provenance SELECT compaction binding drifted")
    if threshold_provenance["select_artifact_hash"] != select.artifact_hash:
        raise RuntimeError("threshold provenance SELECT artifact binding drifted")
    if threshold_provenance["select_manifest_hash"] != select.manifest.manifest_hash:
        raise RuntimeError("threshold provenance SELECT manifest binding drifted")
    if threshold_provenance["threshold_registry_hash"] != registry.registry_hash:
        raise RuntimeError("threshold provenance registry binding drifted")
    if threshold_provenance["serious_regime_ids"] != list(serious):
        raise RuntimeError("threshold provenance serious regime set drifted")
    if threshold_provenance["descriptive_regime_ids"] != select_compaction["descriptive_regime_ids"]:
        raise RuntimeError("threshold provenance descriptive regime set drifted")

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
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_COMPACTED_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "candidate_pair_artifact_hash": pair.artifact_hash,
        "select_compaction_provenance_hash": select_compaction["provenance_hash"],
        "audit_compaction_provenance_hash": audit_compaction["provenance_hash"],
        "select_artifact_hash": select.artifact_hash,
        "audit_artifact_hash": audit.artifact_hash,
        "select_manifest_hash": select.manifest.manifest_hash,
        "audit_manifest_hash": audit.manifest.manifest_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "source_coverage_artifact_hash": coverage.artifact_hash,
        "threshold_provenance_hash": threshold_provenance["provenance_hash"],
        "threshold_registry_hash": registry.registry_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "serious_regime_ids": serious,
        "descriptive_regime_ids": tuple(select_compaction["descriptive_regime_ids"]),
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

    sys.stdout.write(f"calibration_audit_registry_hash={audit_registry.registry_hash}\n")
    sys.stdout.write(f"consistency_pass={str(audit_registry.consistency_pass).lower()}\n")
    sys.stdout.write(f"serious_regime_ids={','.join(serious)}\n")
    sys.stdout.write(
        f"descriptive_regime_ids={','.join(select_compaction['descriptive_regime_ids'])}\n"
    )
    if audit_registry.reason_code is not None:
        sys.stdout.write(f"reason_code={audit_registry.reason_code}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
