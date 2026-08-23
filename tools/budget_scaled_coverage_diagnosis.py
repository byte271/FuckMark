from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.corpus import load_tiny_dev_corpus_by_version_json
from fuckmark.experiments.effectiveness_plan import _attack_samples, _encode_with_offsets
from fuckmark.hashing import sha256_json
from fuckmark.transforms import (
    SchedulePolicy,
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    build_candidate_tokenizer_geometry,
    key_blind_high_coverage_transform_registry,
)
from fuckmark.coverage import union_size, merge_intervals


DIAGNOSIS_VERSION = "budget-scaled-coverage-diagnosis-v1"


def diagnose_sources(corpus, tokenizer, plan, evidence) -> dict[str, object]:
    registry = key_blind_high_coverage_transform_registry()
    scheduler = CandidateScheduler()
    evidence_rows = {
        row["variant_hash"]: row for row in evidence["rows"]
    }
    rows = []
    for variant in plan["variants"]:
        if variant["requested_budget"] != plan["budgets"][0]:
            continue
        row_evidence = evidence_rows[variant["variant_hash"]]
        source = next(
            sample
            for sample in corpus.manifest.samples
            if sample.sample_id == variant["source_sample_id"]
        )
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        enumeration = registry.enumerate(source.text)
        geometry = build_candidate_tokenizer_geometry(
            source.text,
            enumeration,
            token_ids,
            offsets,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=5,
        )
        coverage = geometry.coverage_mapping()
        observation_count = max(0, len(token_ids) - 5 + 1)
        achievable = union_size(
            interval
            for intervals in coverage.values()
            for interval in intervals
        ) if coverage else 0
        selected_ids = set(variant["selected_candidate_ids"])
        realized = union_size(
            interval
            for candidate_id, intervals in coverage.items()
            if candidate_id in selected_ids
            for interval in intervals
        ) if coverage else 0
        hole_intervals = []
        covered = merge_intervals(
            interval
            for intervals in coverage.values()
            for interval in intervals
        ) if coverage else ()
        cursor = 0
        for interval in covered:
            start, end = interval.start, interval.end_exclusive
            if start > cursor:
                hole_intervals.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < observation_count:
            hole_intervals.append((cursor, observation_count))
        rows.append(
            {
                "source_sample_id": variant["source_sample_id"],
                "source_label": variant["source_label"],
                "domain": variant["domain"],
                "observation_count": observation_count,
                "candidate_count": variant["candidate_count"],
                "realized_edit_cost": variant["realized_edit_cost"],
                "achievable_coverage_fraction": achievable / observation_count if observation_count else 0.0,
                "realized_coverage_fraction": realized / observation_count if observation_count else 0.0,
                "hole_count": len(hole_intervals),
                "hole_token_total": sum(end - start for start, end in hole_intervals),
                "pristine_score": row_evidence["pristine_score"],
                "transformed_score": row_evidence["transformed_score"],
                "transformed_detected": row_evidence["transformed_detected"],
                "score_drop": row_evidence["score_drop"],
            }
        )
    watermarked = [row for row in rows if row["source_label"] == "watermarked"]
    detected = [row for row in watermarked if row["transformed_detected"]]
    escaped = [row for row in watermarked if not row["transformed_detected"]]

    def _mean(values):
        return sum(values) / len(values) if values else None

    payload = {
        "algorithm_version": DIAGNOSIS_VERSION,
        "analysis_scope": "post-hoc explanatory analysis of the completed budget-scaled confirmation cycle; not used to tune any candidate against this corpus",
        "plan_hash": plan["plan_hash"],
        "evidence_hash": evidence["artifact_hash"],
        "corpus_hash": corpus.artifact_hash,
        "rows": tuple(rows),
        "watermarked_summary": {
            "total": len(watermarked),
            "detected": len(detected),
            "mean_achievable_coverage_detected": _mean([r["achievable_coverage_fraction"] for r in detected]),
            "mean_achievable_coverage_escaped": _mean([r["achievable_coverage_fraction"] for r in escaped]),
            "mean_realized_coverage_detected": _mean([r["realized_coverage_fraction"] for r in detected]),
            "mean_realized_coverage_escaped": _mean([r["realized_coverage_fraction"] for r in escaped]),
            "mean_hole_token_total_detected": _mean([r["hole_token_total"] for r in detected]),
            "mean_hole_token_total_escaped": _mean([r["hole_token_total"] for r in escaped]),
            "achievable_below_70pct_detected": sum(1 for r in detected if r["achievable_coverage_fraction"] < 0.7),
            "achievable_below_70pct_escaped": sum(1 for r in escaped if r["achievable_coverage_fraction"] < 0.7),
        },
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="budget-scaled-coverage-diagnosis")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    from transformers import AutoTokenizer

    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence_json.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(
        "openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
        use_fast=True,
        padding_side="left",
    )
    report = diagnose_sources(corpus, tokenizer, plan, evidence)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = report["watermarked_summary"]
    print(f"artifact_hash={report['artifact_hash']}")
    for key, value in summary.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
