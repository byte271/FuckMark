from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus import load_tiny_dev_corpus_by_version_json
from .detectors import weighted_mean_evidence
from .durable_io import write_canonical_json_fsynced
from .experiments.effectiveness_plan import validate_key_blind_high_coverage_plan
from .hashing import sha256_json
from .native_observations import build_native_observations
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .tiny_dev_detector_hf import default_watermark_payload
from .tiny_dev_transform_hf import (
    PRIMARY_TARGET_FPR,
    _attack_samples,
    _encode_text,
    _text_only_calibration,
    _text_only_weighted_evidence,
    _threshold,
    _word_edit_distance,
)
from .transforms import (
    KEY_BLIND_HIGH_COVERAGE_PROFILE,
    KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
    KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
    EffectivenessTransformProfile,
    resolve_effectiveness_profile,
)


KEY_BLIND_HIGH_COVERAGE_EVIDENCE_VERSION = "key-blind-high-coverage-evidence-v1"
EFFECTIVENESS_SCORE_PROVENANCE_VERSION = "effectiveness-score-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _mean(values: tuple[float, ...]) -> float | None:
    return sum(values) / len(values) if values else None


def _summaries(rows: tuple[Mapping[str, object], ...]) -> tuple[dict[str, object], ...]:
    coordinates = tuple(
        sorted({(str(row["source_label"]), int(row["requested_budget"])) for row in rows})
    )
    output: list[dict[str, object]] = []
    for label, budget in coordinates:
        selected = tuple(
            row
            for row in rows
            if row["source_label"] == label and row["requested_budget"] == budget
        )
        payload = {
            "source_label": label,
            "requested_budget": budget,
            "row_count": len(selected),
            "independent_source_count": len({row["source_sample_id"] for row in selected}),
            "eligible_row_count": sum(int(row["realized_edit_cost"]) > 0 for row in selected),
            "pristine_detected_count": sum(bool(row["pristine_detected"]) for row in selected),
            "transformed_detected_count": sum(bool(row["transformed_detected"]) for row in selected),
            "mean_pristine_score": _mean(tuple(float(row["pristine_score"]) for row in selected)),
            "mean_transformed_score": _mean(tuple(float(row["transformed_score"]) for row in selected)),
            "mean_score_drop": _mean(tuple(float(row["score_drop"]) for row in selected)),
            "mean_realized_edit_cost": _mean(tuple(float(row["realized_edit_cost"]) for row in selected)),
            "mean_word_edit_count": _mean(tuple(float(row["word_edit_count"]) for row in selected)),
        }
        output.append({**payload, "summary_hash": sha256_json(payload)})
    return tuple(output)


def score_key_blind_high_coverage_plan(
    corpus: Any,
    tokenizer: Any,
    plan: Mapping[str, object],
    adapter: HuggingFaceSynthIDAdapter,
    *,
    profile: EffectivenessTransformProfile | None = None,
) -> dict[str, object]:
    active_profile = profile if profile is not None else KEY_BLIND_HIGH_COVERAGE_PROFILE
    validate_key_blind_high_coverage_plan(plan, corpus, active_profile)
    if adapter.ngram_len != active_profile.ngram_len:
        raise ValueError("detector ngram length does not match the frozen effectiveness profile")
    calibration = _text_only_calibration(corpus, adapter)
    threshold = _threshold(calibration, PRIMARY_TARGET_FPR)
    sources = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    pristine = {
        sample_id: _text_only_weighted_evidence(sample, adapter)
        for sample_id, sample in sources.items()
    }
    rows: list[dict[str, object]] = []
    for raw_entry in plan["variants"]:
        entry = dict(raw_entry)
        source = sources[entry["source_sample_id"]]
        transformed_tokens = _encode_text(tokenizer, entry["transformed_text"])
        eos_token_id = source.model.eos_token_id
        if eos_token_id is None:
            raise ValueError("TinyDev tokenizer must define eos_token_id")
        batch = build_native_observations(
            f"{source.sample_id}-effectiveness-{entry['variant_hash'][:12]}",
            transformed_tokens,
            eos_token_id,
            adapter,
        )
        transformed = weighted_mean_evidence(batch)
        original = pristine[source.sample_id]
        row = {
            "source_sample_id": source.sample_id,
            "source_label": source.label.value,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "variant_hash": entry["variant_hash"],
            "source_index": entry["source_index"],
            "replicate": entry["replicate"],
            "candidate_count": entry["candidate_count"],
            "requested_budget": entry["requested_budget"],
            "budget": entry["budget"],
            "realized_edit_cost": entry["realized_edit_cost"],
            "transformed_text_hash": entry["transformed_text_hash"],
            "hard_invariant_status": entry["hard_invariant_status"],
            "word_edit_count": _word_edit_distance(source.text, entry["transformed_text"]),
            "pristine_score": original.raw_score,
            "transformed_score": transformed.raw_score,
            "score_drop": original.raw_score - transformed.raw_score,
            "pristine_detected": original.raw_score >= threshold.value,
            "transformed_detected": transformed.raw_score >= threshold.value,
        }
        rows.append({**row, "row_hash": sha256_json(row)})
    row_tuple = tuple(rows)
    payload = {
        "algorithm_version": KEY_BLIND_HIGH_COVERAGE_EVIDENCE_VERSION,
        "scientific_scope": (
            "Fixed open-detector exploratory development evidence only; no watermark-removal, "
            "unknown-key, proprietary-detector, or release claim"
        ),
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "plan_hash": plan["plan_hash"],
        "profile_id": active_profile.profile_id,
        "profile_hash": active_profile.profile_hash,
        "ruleset_hash": active_profile.ruleset_hash,
        "detector_identity_hash": calibration.detector_identity.identity_hash,
        "calibration_bundle_hash": calibration.bundle_hash,
        "threshold_hash": threshold.threshold_hash,
        "threshold_target_fpr": threshold.target_fpr,
        "threshold_value": threshold.value,
        "selection_detector_access_observed": plan["detector_access_observed"],
        "selection_secret_access_observed": plan["secret_access_observed"],
        "rows": row_tuple,
        "summaries": _summaries(row_tuple),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _provenance(
    *,
    source_code_commit: str,
    plan_hash: str,
    artifact_hash: str,
    scoring_started_at: str,
    scoring_fsynced_at: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": EFFECTIVENESS_SCORE_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "plan_hash": plan_hash,
        "artifact_hash": artifact_hash,
        "scoring_started_at_utc": scoring_started_at,
        "scoring_fsynced_at_utc": scoring_fsynced_at,
        "scoring_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parse_budgets(raw: str) -> tuple[int, ...]:
    if not raw:
        return ()
    values: list[int] = []
    for chunk in raw.split(","):
        stripped = chunk.strip()
        if not stripped:
            raise ValueError("budget list contains an empty entry")
        value = int(stripped)
        if value <= 0:
            raise ValueError("budgets must be positive integers")
        values.append(value)
    budgets = tuple(sorted(set(values)))
    if budgets != tuple(values):
        raise ValueError("budgets must be provided in ascending order without duplicates")
    return budgets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-effectiveness-score-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument(
        "--profile-id",
        default=KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
        choices=(
            KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
            KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
            KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
        ),
    )
    parser.add_argument("--budgets", default="")
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-effectiveness-evidence.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/tiny-dev-effectiveness-score-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    profile = resolve_effectiveness_profile(args.profile_id, _parse_budgets(args.budgets))
    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    plan = _load_json(args.plan_json)
    validate_key_blind_high_coverage_plan(plan, corpus, profile)
    if plan["source_code_commit"] != args.source_code_commit:
        raise ValueError("score invocation commit does not match the frozen plan")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("effectiveness scoring requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the frozen TinyDev corpus")

    watermark_payload = default_watermark_payload()
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
    started_at = _now()
    evidence = score_key_blind_high_coverage_plan(corpus, tokenizer, plan, adapter, profile=profile)
    write_canonical_json_fsynced(args.json, evidence)
    fsynced_at = _now()
    provenance = _provenance(
        source_code_commit=args.source_code_commit,
        plan_hash=plan["plan_hash"],
        artifact_hash=evidence["artifact_hash"],
        scoring_started_at=started_at,
        scoring_fsynced_at=fsynced_at,
    )
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"profile_id={profile.profile_id}\n")
    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    for summary in evidence["summaries"]:
        sys.stdout.write(
            f"label={summary['source_label']} requested_budget={summary['requested_budget']} "
            f"detected={summary['transformed_detected_count']}/{summary['row_count']} "
            f"mean_score_drop={summary['mean_score_drop']:.8f}\n"
        )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
