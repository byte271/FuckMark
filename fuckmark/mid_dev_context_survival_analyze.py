from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .corpus.mid_dev_io import load_mid_dev_corpus_json
from .durable_io import write_canonical_json_fsynced
from .experiments.mid_dev_analysis import build_mid_dev_analysis_artifact
from .experiments.mid_dev_scoring_artifact_io import (
    load_mid_dev_scoring_artifact_json,
    validate_mid_dev_scoring_artifact_binding,
)
from .experiments.mid_dev_scoring_io import load_mid_dev_scoring_plan_json
from .hashing import sha256_json


MID_DEV_ANALYSIS_PROVENANCE_VERSION = "mid-dev-analysis-provenance-v1"


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


def _validate_scoring_provenance(
    provenance: dict[str, object],
    *,
    corpus_artifact_hash: str,
    plan_hash: str,
    source_code_commit: str,
    scoring_artifact_hash: str,
    calibration_corpus_artifact_hash: str,
    trace_artifact_hash: str,
    analysis_started_at: str,
) -> None:
    expected = sha256_json(
        {key: value for key, value in provenance.items() if key != "provenance_hash"}
    )
    if provenance.get("provenance_hash") != expected:
        raise ValueError("MidDev scoring provenance hash does not replay")
    if provenance.get("corpus_artifact_hash") != corpus_artifact_hash:
        raise ValueError("MidDev scoring provenance does not bind the supplied corpus")
    if provenance.get("plan_hash") != plan_hash:
        raise ValueError("MidDev scoring provenance does not bind the supplied plan")
    if provenance.get("source_code_commit") != source_code_commit:
        raise ValueError("MidDev scoring provenance source commit does not match the frozen plan")
    if provenance.get("evidence_hash") != scoring_artifact_hash:
        raise ValueError("MidDev scoring provenance does not bind the supplied evidence")
    if provenance.get("calibration_corpus_artifact_hash") != calibration_corpus_artifact_hash:
        raise ValueError("MidDev scoring provenance does not bind the calibration corpus")
    if provenance.get("trace_artifact_hash") != trace_artifact_hash:
        raise ValueError("MidDev scoring provenance does not bind the frozen trace artifact")
    if provenance.get("separate_scoring_process") is not True:
        raise ValueError("MidDev scoring provenance does not attest a separate scoring process")
    scoring_started = _parse_time(provenance.get("scoring_started_at_utc"), "scoring_started_at_utc")
    scoring_finished = _parse_time(provenance.get("scoring_finished_at_utc"), "scoring_finished_at_utc")
    analysis_started = _parse_time(analysis_started_at, "analysis_started_at")
    if scoring_finished < scoring_started:
        raise ValueError("MidDev scoring provenance has reversed timestamps")
    if analysis_started < scoring_finished:
        raise ValueError("MidDev analysis started before scoring finished")


def _analysis_provenance(
    *,
    source_code_commit: str,
    corpus_artifact_hash: str,
    plan_hash: str,
    scoring_artifact_hash: str,
    scoring_provenance_hash: str,
    analysis_artifact_hash: str,
    ecs1_raw_artifact_hash: str,
    analysis_started_at: str,
    analysis_finished_at: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": MID_DEV_ANALYSIS_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "corpus_artifact_hash": corpus_artifact_hash,
        "plan_hash": plan_hash,
        "scoring_artifact_hash": scoring_artifact_hash,
        "scoring_provenance_hash": scoring_provenance_hash,
        "analysis_artifact_hash": analysis_artifact_hash,
        "ecs1_raw_artifact_hash": ecs1_raw_artifact_hash,
        "analysis_started_at_utc": analysis_started_at,
        "analysis_finished_at_utc": analysis_finished_at,
        "bootstrap_replicates": 10_000,
        "bootstrap_seed_base": 0x4D494444455641,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-context-survival-analyze")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--scoring-provenance-json", type=Path, required=True)
    parser.add_argument(
        "--analysis-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-analysis.json"),
    )
    parser.add_argument(
        "--ecs1-json",
        type=Path,
        default=Path("artifacts/mid-dev-ecs1-raw.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/mid-dev-context-survival-analysis-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    analysis_started_at = _now()
    corpus = load_mid_dev_corpus_json(args.corpus_json)
    plan = load_mid_dev_scoring_plan_json(args.plan_json)
    scoring = load_mid_dev_scoring_artifact_json(args.evidence_json)
    validate_mid_dev_scoring_artifact_binding(scoring, plan)
    scoring_provenance = _load_json_object(args.scoring_provenance_json)
    _validate_scoring_provenance(
        scoring_provenance,
        corpus_artifact_hash=corpus.artifact_hash,
        plan_hash=plan.plan_hash,
        source_code_commit=plan.source_code_commit,
        scoring_artifact_hash=scoring.artifact_hash,
        calibration_corpus_artifact_hash=scoring.calibration_corpus_artifact_hash,
        trace_artifact_hash=scoring.trace_artifact_hash,
        analysis_started_at=analysis_started_at,
    )
    analysis, ecs1 = build_mid_dev_analysis_artifact(corpus, plan, scoring)
    write_canonical_json_fsynced(args.analysis_json, analysis)
    write_canonical_json_fsynced(args.ecs1_json, ecs1)
    analysis_finished_at = _now()
    provenance = _analysis_provenance(
        source_code_commit=plan.source_code_commit,
        corpus_artifact_hash=corpus.artifact_hash,
        plan_hash=plan.plan_hash,
        scoring_artifact_hash=scoring.artifact_hash,
        scoring_provenance_hash=str(scoring_provenance["provenance_hash"]),
        analysis_artifact_hash=analysis.artifact_hash,
        ecs1_raw_artifact_hash=ecs1.artifact_hash,
        analysis_started_at=analysis_started_at,
        analysis_finished_at=analysis_finished_at,
    )
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"analysis_artifact_hash={analysis.artifact_hash}\n")
    sys.stdout.write(f"ecs1_raw_artifact_hash={ecs1.artifact_hash}\n")
    sys.stdout.write(f"analysis_provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(f"primary_valid_cells={len(analysis.primary_results)}\n")
    sys.stdout.write(f"primary_ineligible_cells={len(analysis.ineligible_primary_cells)}\n")
    sys.stdout.write(f"ecs1_row_count={len(ecs1.rows)}\n")
    sys.stdout.write(f"analysis_json={args.analysis_json.as_posix()}\n")
    sys.stdout.write(f"ecs1_json={args.ecs1_json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
