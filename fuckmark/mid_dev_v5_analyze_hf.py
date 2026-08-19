from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import canonical_json_text
from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_analysis_v5 import build_mid_dev_v5_analysis_artifact
from .experiments.mid_dev_legacy_trace_io import load_mid_dev_selection_trace_artifact_json
from .experiments.mid_dev_plan_v5_io import load_mid_dev_development_plan_v5_json
from .experiments.mid_dev_v5_analysis_io import load_mid_dev_v5_scoring_artifact_json
from .experiments.mid_dev_v5_geometry_audit import build_mid_dev_v5_geometry_audit
from .experiments.mid_dev_v5_rule_usage import build_mid_dev_v5_rule_usage_artifact
from .experiments.mid_dev_v5_runtime_io import load_mid_dev_normalized_trace_artifact_json
from .experiments.mid_dev_vnext_artifact_io import load_detector_opportunity_audit_json
from .hashing import sha256_json
from .mid_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION


MID_DEV_V5_ANALYSIS_PROVENANCE_VERSION = "mid-dev-v5-analysis-provenance-v1"
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


def _load_scoring_provenance(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("v5 scoring provenance must be a JSON object")
    expected_keys = {
        "algorithm_version",
        "source_code_commit",
        "corpus_artifact_hash",
        "development_plan_hash",
        "normalized_trace_artifact_hash",
        "execution_attestation_hash",
        "plan_provenance_hash",
        "opportunity_audit_hash",
        "regime_decision_hash",
        "threshold_registry_hash",
        "detector_identity_hash",
        "evidence_hash",
        "scoring_started_at_utc",
        "scoring_finished_at_utc",
        "separate_scoring_process",
        "github_run_id",
        "github_run_attempt",
        "github_event_name",
        "github_checkout_sha",
        "provenance_hash",
    }
    if set(value) != expected_keys:
        raise ValueError("v5 scoring provenance field set drifted")
    if value["algorithm_version"] != MID_DEV_V5_SCORING_PROVENANCE_VERSION:
        raise ValueError("unsupported v5 scoring provenance version")
    payload = {key: item for key, item in value.items() if key != "provenance_hash"}
    if value["provenance_hash"] != sha256_json(payload):
        raise ValueError("v5 scoring provenance hash does not replay")
    canonical = canonical_json_text(value)
    if text not in (canonical, canonical + "\n"):
        raise ValueError("v5 scoring provenance JSON is not canonical")
    if value["separate_scoring_process"] is not True:
        raise ValueError("v5 scoring provenance does not attest a separate scoring process")
    started = _parse_time(value["scoring_started_at_utc"], "scoring_started_at_utc")
    finished = _parse_time(value["scoring_finished_at_utc"], "scoring_finished_at_utc")
    if finished < started:
        raise ValueError("v5 scoring provenance has reversed timestamps")
    return value


def _validate_scoring_provenance(
    provenance: dict[str, object],
    *,
    corpus,
    plan,
    normalized_traces,
    scoring,
    source_audit,
    analysis_started_at: str,
) -> None:
    expected = {
        "source_code_commit": plan.source_code_commit,
        "corpus_artifact_hash": corpus.artifact_hash,
        "development_plan_hash": plan.plan_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": scoring.regime_decision_hash,
        "threshold_registry_hash": scoring.threshold_registry_hash,
        "detector_identity_hash": scoring.detector_identity_hash,
        "evidence_hash": scoring.artifact_hash,
    }
    for name, expected_value in expected.items():
        if provenance.get(name) != expected_value:
            raise ValueError(f"v5 scoring provenance {name} does not bind supplied artifact")
    analysis_started = _parse_time(analysis_started_at, "analysis_started_at_utc")
    scoring_finished = _parse_time(provenance["scoring_finished_at_utc"], "scoring_finished_at_utc")
    if analysis_started < scoring_finished:
        raise ValueError("v5 analysis started before scoring finished")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-v5-analyze-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--legacy-trace-json", type=Path, required=True)
    parser.add_argument("--normalized-trace-json", type=Path, required=True)
    parser.add_argument("--scoring-json", type=Path, required=True)
    parser.add_argument("--scoring-provenance-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--geometry-audit-json",
        type=Path,
        default=Path("artifacts/mid-dev-v5-geometry-audit.json"),
    )
    parser.add_argument(
        "--rule-usage-json",
        type=Path,
        default=Path("artifacts/mid-dev-v5-rule-usage.json"),
    )
    parser.add_argument(
        "--analysis-json",
        type=Path,
        default=Path("artifacts/mid-dev-v5-analysis.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/mid-dev-v5-analysis-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    analysis_started_at = _now()
    corpus = load_mid_dev_corpus_json(args.corpus_json)
    plan = load_mid_dev_development_plan_v5_json(args.plan_json)
    legacy_traces = load_mid_dev_selection_trace_artifact_json(args.legacy_trace_json)
    normalized_traces = load_mid_dev_normalized_trace_artifact_json(args.normalized_trace_json)
    scoring = load_mid_dev_v5_scoring_artifact_json(args.scoring_json)
    source_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    scoring_provenance = _load_scoring_provenance(args.scoring_provenance_json)
    _validate_scoring_provenance(
        scoring_provenance,
        corpus=corpus,
        plan=plan,
        normalized_traces=normalized_traces,
        scoring=scoring,
        source_audit=source_audit,
        analysis_started_at=analysis_started_at,
    )
    if legacy_traces.plan_hash != plan.legacy_plan.plan_hash:
        raise RuntimeError("legacy trace artifact does not bind embedded legacy plan")
    if normalized_traces.development_plan_hash != plan.plan_hash:
        raise RuntimeError("normalized trace artifact does not bind v5 plan")

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before v5 analysis") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("v5 analysis requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if {sample.model.identity_hash for sample in corpus.manifest.samples} != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match frozen MidDev corpus")
    if source_audit.model_tokenizer_identity_hash != identity.identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen opportunity audit")

    geometry_audit = build_mid_dev_v5_geometry_audit(
        corpus,
        plan,
        scoring,
        source_audit,
        tokenizer,
    )
    rule_usage = build_mid_dev_v5_rule_usage_artifact(
        corpus,
        plan,
        legacy_traces,
        normalized_traces,
    )
    analysis = build_mid_dev_v5_analysis_artifact(
        plan,
        normalized_traces,
        scoring,
        geometry_audit,
        rule_usage,
    )
    write_canonical_json_fsynced(args.geometry_audit_json, geometry_audit)
    write_canonical_json_fsynced(args.rule_usage_json, rule_usage)
    write_canonical_json_fsynced(args.analysis_json, analysis)
    analysis_finished_at = _now()
    payload = {
        "algorithm_version": MID_DEV_V5_ANALYSIS_PROVENANCE_VERSION,
        "source_code_commit": plan.source_code_commit,
        "corpus_artifact_hash": corpus.artifact_hash,
        "development_plan_hash": plan.plan_hash,
        "legacy_trace_artifact_hash": legacy_traces.artifact_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "scoring_artifact_hash": scoring.artifact_hash,
        "scoring_provenance_hash": scoring_provenance["provenance_hash"],
        "opportunity_audit_hash": source_audit.artifact_hash,
        "geometry_audit_hash": geometry_audit.artifact_hash,
        "rule_usage_artifact_hash": rule_usage.artifact_hash,
        "analysis_artifact_hash": analysis.artifact_hash,
        "analysis_started_at_utc": analysis_started_at,
        "analysis_finished_at_utc": analysis_finished_at,
        "separate_analysis_process": True,
        "human_audit_status": analysis.human_audit_status,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"geometry_audit_hash={geometry_audit.artifact_hash}\n")
    sys.stdout.write(f"rule_usage_artifact_hash={rule_usage.artifact_hash}\n")
    sys.stdout.write(f"analysis_artifact_hash={analysis.artifact_hash}\n")
    sys.stdout.write(f"analysis_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"human_audit_status={analysis.human_audit_status}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
