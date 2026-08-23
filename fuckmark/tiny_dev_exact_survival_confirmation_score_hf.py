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
from .experiments.exact_survival_effectiveness_plan import INHERITED_THRESHOLD_VALUE, validate_exact_survival_confirmation_contract, validate_exact_survival_effectiveness_plan
from .hashing import sha256_json
from .native_observations import build_native_observations
from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION, runtime_tokenizer_identity_public
from .tiny_dev_detector_hf import default_watermark_payload
from .tiny_dev_transform_hf import _attack_samples, _encode_text, _text_only_weighted_evidence, _word_edit_distance
from .transforms import content_region_coverage_profile


EXACT_SURVIVAL_CONFIRMATION_EVIDENCE_VERSION = "exact-survival-confirmation-evidence-v1"
EXACT_SURVIVAL_CONFIRMATION_SCORE_PROVENANCE_VERSION = "exact-survival-confirmation-score-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _mean(values: tuple[float, ...]) -> float | None:
    return sum(values) / len(values) if values else None


def _score_transformed(source, text: str, tokenizer, adapter, sample_suffix: str):
    tokens = _encode_text(tokenizer, text)
    eos_token_id = source.model.eos_token_id
    if eos_token_id is None:
        raise ValueError("confirmation tokenizer must define eos_token_id")
    batch = build_native_observations(
        f"{source.sample_id}-cycle4-{sample_suffix}",
        tokens,
        eos_token_id,
        adapter,
    )
    return weighted_mean_evidence(batch)


def _summary(rows: tuple[Mapping[str, object], ...], label: str) -> dict[str, object]:
    selected = tuple(row for row in rows if row["source_label"] == label)
    if not selected:
        raise ValueError(f"confirmation evidence has no rows for label {label}")
    payload = {
        "source_label": label,
        "row_count": len(selected),
        "pristine_detected_count": sum(bool(row["pristine_detected"]) for row in selected),
        "baseline_detected_count": sum(bool(row["baseline_detected"]) for row in selected),
        "exact_detected_count": sum(bool(row["exact_detected"]) for row in selected),
        "exact_minus_baseline_detected_count": sum(bool(row["exact_detected"]) for row in selected) - sum(bool(row["baseline_detected"]) for row in selected),
        "exact_lower_score_count": sum(float(row["exact_score"]) < float(row["baseline_score"]) for row in selected),
        "equal_score_count": sum(float(row["exact_score"]) == float(row["baseline_score"]) for row in selected),
        "exact_higher_score_count": sum(float(row["exact_score"]) > float(row["baseline_score"]) for row in selected),
        "mean_pristine_score": _mean(tuple(float(row["pristine_score"]) for row in selected)),
        "mean_baseline_score": _mean(tuple(float(row["baseline_score"]) for row in selected)),
        "mean_exact_score": _mean(tuple(float(row["exact_score"]) for row in selected)),
        "mean_baseline_score_drop": _mean(tuple(float(row["baseline_score_drop"]) for row in selected)),
        "mean_exact_score_drop": _mean(tuple(float(row["exact_score_drop"]) for row in selected)),
        "mean_exact_minus_baseline_score": _mean(tuple(float(row["exact_score"]) - float(row["baseline_score"]) for row in selected)),
        "mean_baseline_selected_count": _mean(tuple(float(row["baseline_selected_count"]) for row in selected)),
        "mean_exact_selected_count": _mean(tuple(float(row["exact_selected_count"]) for row in selected)),
        "mean_baseline_word_edit_count": _mean(tuple(float(row["baseline_word_edit_count"]) for row in selected)),
        "mean_exact_word_edit_count": _mean(tuple(float(row["exact_word_edit_count"]) for row in selected)),
    }
    return {**payload, "summary_hash": sha256_json(payload)}


def score_exact_survival_confirmation(
    corpus: Any,
    tokenizer: Any,
    baseline_plan: Mapping[str, object],
    exact_plan: Mapping[str, object],
    adapter: HuggingFaceSynthIDAdapter,
    *,
    contract: Mapping[str, object],
    confirmation_seed_base: int,
) -> dict[str, object]:
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    if confirmation_seed_base not in tuple(contract["confirmation"]["seed_bases"]):
        raise ValueError("confirmation seed base is not registered in the frozen contract")
    profile = content_region_coverage_profile((16,))
    validate_key_blind_high_coverage_plan(baseline_plan, corpus, profile)
    validate_exact_survival_effectiveness_plan(exact_plan, corpus, contract=contract)
    if baseline_plan["source_code_commit"] != exact_plan["source_code_commit"]:
        raise ValueError("paired confirmation plans must bind the same source commit")
    if baseline_plan["ruleset_hash"] != exact_plan["ruleset_hash"]:
        raise ValueError("paired confirmation plans must use the same candidate ruleset")
    if baseline_plan["tokenizer_identity_hash"] != exact_plan["tokenizer_identity_hash"]:
        raise ValueError("paired confirmation plans must use the same tokenizer identity")
    if baseline_plan["tiny_dev_artifact_hash"] != exact_plan["tiny_dev_artifact_hash"]:
        raise ValueError("paired confirmation plans must use the same corpus artifact")
    if baseline_plan["detector_access_observed"] is not False or exact_plan["detector_access_observed"] is not False:
        raise ValueError("paired confirmation selection must be detector-blind")
    if baseline_plan["secret_access_observed"] is not False or exact_plan["secret_access_observed"] is not False:
        raise ValueError("paired confirmation selection must be key-blind")
    baseline_by_source = {str(row["source_sample_id"]): dict(row) for row in baseline_plan["variants"]}
    exact_by_source = {str(row["source_sample_id"]): dict(row) for row in exact_plan["variants"]}
    if set(baseline_by_source) != set(exact_by_source):
        raise ValueError("paired confirmation plans do not cover the same sources")
    sources = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    if set(sources) != set(baseline_by_source):
        raise ValueError("paired confirmation plans do not cover the full attack split")

    threshold = contract["measurement"]["threshold"]
    if threshold != INHERITED_THRESHOLD_VALUE:
        raise ValueError("confirmation scorer refuses threshold drift")
    rows: list[dict[str, object]] = []
    for source_id in sorted(sources):
        source = sources[source_id]
        baseline = baseline_by_source[source_id]
        exact = exact_by_source[source_id]
        if baseline["source_text_hash"] != exact["source_text_hash"] or baseline["source_text_hash"] != source.text_sha256:
            raise ValueError("paired confirmation source text binding drifted")
        if baseline["enumeration_hash"] != exact["enumeration_hash"]:
            raise ValueError("paired confirmation candidate enumeration drifted")
        if baseline["candidate_count"] != exact["candidate_count"]:
            raise ValueError("paired confirmation candidate pool size drifted")
        pristine = _text_only_weighted_evidence(source, adapter)
        baseline_evidence = _score_transformed(source, str(baseline["transformed_text"]), tokenizer, adapter, f"baseline-{baseline['variant_hash'][:12]}")
        exact_evidence = _score_transformed(source, str(exact["transformed_text"]), tokenizer, adapter, f"exact-{exact['variant_hash'][:12]}")
        row = {
            "source_sample_id": source_id,
            "source_label": source.label.value,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "candidate_count": baseline["candidate_count"],
            "baseline_variant_hash": baseline["variant_hash"],
            "exact_variant_hash": exact["variant_hash"],
            "baseline_selected_count": baseline["realized_edit_cost"],
            "exact_selected_count": exact["realized_edit_cost"],
            "baseline_transformed_text_hash": baseline["transformed_text_hash"],
            "exact_transformed_text_hash": exact["transformed_text_hash"],
            "exact_destroyed_observation_count": exact["exact_destroyed_observation_count"],
            "exact_root_observation_count": exact["root_observation_count"],
            "baseline_word_edit_count": _word_edit_distance(source.text, str(baseline["transformed_text"])),
            "exact_word_edit_count": _word_edit_distance(source.text, str(exact["transformed_text"])),
            "pristine_score": pristine.raw_score,
            "baseline_score": baseline_evidence.raw_score,
            "exact_score": exact_evidence.raw_score,
            "baseline_score_drop": pristine.raw_score - baseline_evidence.raw_score,
            "exact_score_drop": pristine.raw_score - exact_evidence.raw_score,
            "exact_minus_baseline_score": exact_evidence.raw_score - baseline_evidence.raw_score,
            "pristine_detected": pristine.raw_score >= threshold,
            "baseline_detected": baseline_evidence.raw_score >= threshold,
            "exact_detected": exact_evidence.raw_score >= threshold,
        }
        rows.append({**row, "row_hash": sha256_json(row)})
    row_tuple = tuple(rows)
    summaries = (_summary(row_tuple, "unwatermarked"), _summary(row_tuple, "watermarked"))
    payload = {
        "algorithm_version": EXACT_SURVIVAL_CONFIRMATION_EVIDENCE_VERSION,
        "scientific_scope": "Fresh paired fixed-open-detector confirmation of a previously frozen detector-blind exact-retokenization selection rule; no watermark-removal, proprietary-detector, unknown-key, or release claim",
        "contract_hash": contract_hash,
        "confirmation_seed_base": confirmation_seed_base,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "baseline_plan_hash": baseline_plan["plan_hash"],
        "exact_plan_hash": exact_plan["plan_hash"],
        "ruleset_hash": exact_plan["ruleset_hash"],
        "tokenizer_identity_hash": exact_plan["tokenizer_identity_hash"],
        "measurement_identity": contract["measurement"]["identity"],
        "threshold": threshold,
        "threshold_comparison": contract["measurement"]["comparison"],
        "threshold_target_fpr": contract["measurement"]["target_fpr"],
        "prior_fixed_threshold_file_sha256": contract["measurement"]["prior_fixed_threshold_file_sha256"],
        "prior_threshold_replay": contract["measurement"]["prior_threshold_replay"],
        "prior_audit_exceedances": contract["measurement"]["prior_audit_exceedances"],
        "prior_audit_count": contract["measurement"]["prior_audit_count"],
        "adapter_configuration_fingerprint": adapter.configuration_fingerprint(),
        "adapter_source_commit": adapter.source_pin.commit,
        "sampling_table_hash": adapter.sampling_table_hash,
        "selection_detector_access_observed": False,
        "selection_secret_access_observed": False,
        "rows": row_tuple,
        "summaries": summaries,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _provenance(source_code_commit: str, evidence: Mapping[str, object], started: str, fsynced: str) -> dict[str, object]:
    payload = {
        "algorithm_version": EXACT_SURVIVAL_CONFIRMATION_SCORE_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "artifact_hash": evidence["artifact_hash"],
        "baseline_plan_hash": evidence["baseline_plan_hash"],
        "exact_plan_hash": evidence["exact_plan_hash"],
        "scoring_started_at_utc": started,
        "scoring_fsynced_at_utc": fsynced,
        "scoring_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-exact-survival-confirmation-score-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--baseline-plan-json", type=Path, required=True)
    parser.add_argument("--exact-plan-json", type=Path, required=True)
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--confirmation-seed-base", type=int, required=True)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error
    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    baseline_plan = _load_json(args.baseline_plan_json)
    exact_plan = _load_json(args.exact_plan_json)
    contract = _load_json(args.contract_json)
    if baseline_plan.get("source_code_commit") != args.source_code_commit or exact_plan.get("source_code_commit") != args.source_code_commit:
        raise ValueError("score invocation commit does not match the frozen paired plans")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("confirmation scoring requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the confirmation corpus")
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
    started = _now()
    evidence = score_exact_survival_confirmation(
        corpus,
        tokenizer,
        baseline_plan,
        exact_plan,
        adapter,
        contract=contract,
        confirmation_seed_base=args.confirmation_seed_base,
    )
    write_canonical_json_fsynced(args.json, evidence)
    fsynced = _now()
    provenance = _provenance(args.source_code_commit, evidence, started, fsynced)
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    for summary in evidence["summaries"]:
        sys.stdout.write(
            f"label={summary['source_label']} baseline_detected={summary['baseline_detected_count']}/{summary['row_count']} "
            f"exact_detected={summary['exact_detected_count']}/{summary['row_count']} "
            f"difference={summary['exact_minus_baseline_detected_count']} "
            f"mean_exact_minus_baseline_score={summary['mean_exact_minus_baseline_score']:.8f}\n"
        )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
