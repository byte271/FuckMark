from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev_calibration_merged_io import load_mid_dev_calibration_merged_artifact_json
from .corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
    MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
    CalibrationRole,
)
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_calibration_compaction import (
    MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
    _deduplicate_calibration_candidates,
    build_mid_dev_calibration_compaction,
)
from .experiments.mid_dev_calibration_compaction_io import (
    MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION,
    compaction_records_from_provenance,
    load_mid_dev_calibration_compaction_provenance_json,
)
from .experiments.mid_dev_calibration_merge_provenance_io import (
    load_mid_dev_calibration_merge_provenance_json,
)
from .experiments.mid_dev_calibration_readiness import (
    FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN,
)
from .experiments.mid_dev_source_opportunity_coverage_io import (
    load_mid_dev_source_opportunity_coverage_json,
    load_mid_dev_source_opportunity_provenance_json,
)
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-compact-hf")
    parser.add_argument("--candidate-json", type=Path, required=True)
    parser.add_argument("--candidate-merge-provenance-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--source-coverage-json", type=Path, required=True)
    parser.add_argument("--source-coverage-provenance-json", type=Path, required=True)
    parser.add_argument("--select-compaction-provenance-json", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def _runtime_tokenizer(model: str, revision: str):
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before calibration compaction") from error
    tokenizer = AutoTokenizer.from_pretrained(
        model,
        revision=revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("calibration compaction requires a fast tokenizer")
    return tokenizer


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    candidate = load_mid_dev_calibration_merged_artifact_json(args.candidate_json)
    candidate_merge = load_mid_dev_calibration_merge_provenance_json(
        args.candidate_merge_provenance_json
    )
    opportunity = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    coverage = load_mid_dev_source_opportunity_coverage_json(args.source_coverage_json)
    coverage_provenance = load_mid_dev_source_opportunity_provenance_json(
        args.source_coverage_provenance_json
    )

    plan = readiness.select_plan if candidate.role is CalibrationRole.SELECT else readiness.audit_plan
    if candidate.readiness_hash != readiness.readiness_hash or candidate.plan_hash != plan.plan_hash:
        raise RuntimeError("candidate pool does not bind frozen v2 readiness/role plan")
    if len(candidate.samples) != len(plan.prompt_ids):
        raise RuntimeError("candidate pool does not contain the complete frozen role plan")
    if candidate_merge["role"] != candidate.role.value:
        raise RuntimeError("candidate merge provenance role differs from candidate pool")
    if candidate_merge["readiness_hash"] != readiness.readiness_hash or candidate_merge["plan_hash"] != plan.plan_hash:
        raise RuntimeError("candidate merge provenance readiness/plan binding drifted")
    if candidate_merge["merged_artifact_hash"] != candidate.artifact_hash:
        raise RuntimeError("candidate merge provenance artifact binding drifted")
    if candidate_merge["merged_manifest_hash"] != candidate.manifest.manifest_hash:
        raise RuntimeError("candidate merge provenance manifest binding drifted")
    if candidate_merge["opportunity_audit_hash"] != opportunity.artifact_hash:
        raise RuntimeError("candidate pool was not generated under supplied opportunity audit")
    if candidate_merge["regime_decision_hash"] != decision.decision_hash:
        raise RuntimeError("candidate pool was not generated under supplied regime decision")
    if decision.opportunity_audit_hash != opportunity.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied opportunity audit")
    if coverage.calibration_opportunity_audit_hash != opportunity.artifact_hash:
        raise RuntimeError("source coverage does not bind supplied opportunity audit")
    if coverage.regime_decision_hash != decision.decision_hash:
        raise RuntimeError("source coverage does not bind supplied regime decision")
    if coverage_provenance["coverage_artifact_hash"] != coverage.artifact_hash:
        raise RuntimeError("source coverage provenance artifact binding drifted")
    if coverage_provenance["calibration_opportunity_audit_hash"] != opportunity.artifact_hash:
        raise RuntimeError("source coverage provenance opportunity binding drifted")
    if coverage_provenance["regime_decision_hash"] != decision.decision_hash:
        raise RuntimeError("source coverage provenance regime binding drifted")

    tokenizer = _runtime_tokenizer(args.model, args.model_revision)
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != candidate.manifest.model_tokenizer_identity_hash:
        raise RuntimeError("runtime tokenizer identity differs from candidate pool")
    if identity.identity_hash != opportunity.model_tokenizer_identity_hash:
        raise RuntimeError("runtime tokenizer identity differs from frozen opportunity audit")
    if identity.identity_hash != coverage.model_tokenizer_identity_hash:
        raise RuntimeError("runtime tokenizer identity differs from source coverage")

    select_records = None
    select_compaction_hash = None
    if candidate.role is CalibrationRole.SELECT:
        if args.select_compaction_provenance_json is not None:
            raise RuntimeError("CAL-SELECT compaction cannot consume prior SELECT compaction")
    else:
        if args.select_compaction_provenance_json is None:
            raise RuntimeError("CAL-AUDIT compaction requires --select-compaction-provenance-json")
        select_provenance = load_mid_dev_calibration_compaction_provenance_json(
            args.select_compaction_provenance_json
        )
        if select_provenance["role"] != CalibrationRole.SELECT.value:
            raise RuntimeError("AUDIT compaction input must be CAL-SELECT compaction provenance")
        if select_provenance["source_coverage_artifact_hash"] != coverage.artifact_hash:
            raise RuntimeError("CAL-SELECT/AUDIT compaction source coverage binding drifted")
        if select_provenance["calibration_opportunity_audit_hash"] != opportunity.artifact_hash:
            raise RuntimeError("CAL-SELECT/AUDIT compaction opportunity binding drifted")
        if select_provenance["regime_decision_hash"] != decision.decision_hash:
            raise RuntimeError("CAL-SELECT/AUDIT compaction regime binding drifted")
        select_records = compaction_records_from_provenance(select_provenance)
        select_compaction_hash = select_provenance["provenance_hash"]

    unique_candidates, duplicate_excluded_sample_ids = _deduplicate_calibration_candidates(
        candidate.samples
    )
    compacted, records, serious, descriptive = build_mid_dev_calibration_compaction(
        candidate,
        opportunity,
        decision,
        coverage,
        retokenize=lambda text: tuple(
            int(value) for value in tokenizer.encode(text, add_special_tokens=False)
        ),
        select_records=select_records,
        select_compaction_provenance_hash=select_compaction_hash,
    )
    write_canonical_json_fsynced(args.json, compacted)

    record_payloads = tuple(
        record.payload() | {"record_hash": record.record_hash}
        for record in records
    )
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION,
        "role": candidate.role.value,
        "readiness_hash": readiness.readiness_hash,
        "plan_hash": plan.plan_hash,
        "candidate_pool_artifact_hash": candidate.artifact_hash,
        "candidate_pool_manifest_hash": candidate.manifest.manifest_hash,
        "candidate_merge_provenance_hash": candidate_merge["provenance_hash"],
        "calibration_opportunity_audit_hash": opportunity.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "source_coverage_artifact_hash": coverage.artifact_hash,
        "source_coverage_provenance_hash": coverage_provenance["provenance_hash"],
        "selection_rule": MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
        "preferred_n": MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
        "minimum_n": MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
        "candidate_count_total": len(candidate.samples),
        "unique_candidate_count_total": len(unique_candidates),
        "duplicate_excluded_count": len(duplicate_excluded_sample_ids),
        "duplicate_excluded_sample_ids_hash": sha256_json(duplicate_excluded_sample_ids),
        "selected_count_total": len(compacted.samples),
        "required_regime_ids": coverage.required_regime_ids,
        "serious_regime_ids": serious,
        "descriptive_regime_ids": descriptive,
        "records": record_payloads,
        "compacted_artifact_hash": compacted.artifact_hash,
        "compacted_manifest_hash": compacted.manifest.manifest_hash,
        "select_compaction_provenance_hash": select_compaction_hash,
        "attack_transform_count": 0,
        "attack_score_count": 0,
        "detector_score_count": 0,
        "calibration_threshold_constructed": False,
        "json_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"role={candidate.role.value}\n")
    sys.stdout.write(f"candidate_count={len(candidate.samples)}\n")
    sys.stdout.write(f"unique_candidate_count={len(unique_candidates)}\n")
    sys.stdout.write(f"duplicate_excluded_count={len(duplicate_excluded_sample_ids)}\n")
    sys.stdout.write(f"selected_count={len(compacted.samples)}\n")
    sys.stdout.write(f"serious_regime_ids={','.join(serious)}\n")
    sys.stdout.write(f"descriptive_regime_ids={','.join(descriptive)}\n")
    sys.stdout.write(f"compacted_artifact_hash={compacted.artifact_hash}\n")
    sys.stdout.write(f"compaction_provenance_hash={provenance['provenance_hash']}\n")
    for record in records:
        sys.stdout.write(
            f"{record.regime_id}:candidate={record.candidate_count}:"
            f"selected={record.selected_count}:status={record.status.value}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
