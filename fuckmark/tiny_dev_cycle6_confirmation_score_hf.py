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
from .experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    CYCLE6_SANITIZER_IDS,
    CYCLE6_THRESHOLD,
    validate_cycle6_confirmation_contract,
    validate_cycle6_confirmation_plan,
    validate_cycle6_frozen_source_blobs,
)
from .hashing import sha256_json, sha256_text
from .native_observations import build_native_observations
from .sanitizer_robustness import sanitize_variant
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .tiny_dev_detector_hf import default_watermark_payload
from .tiny_dev_transform_hf import _attack_samples, _encode_text, _text_only_weighted_evidence


CYCLE6_CONFIRMATION_EVIDENCE_VERSION = "cycle6-confirmation-evidence-v1"
CYCLE6_SCORE_PROVENANCE_VERSION = "cycle6-confirmation-score-provenance-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _require_lower_hex_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"Cycle 6 scoring requires a valid {name}")
    return value


def _require_scoring_authorization(contract: Mapping[str, object]) -> None:
    fidelity = contract.get("fidelity_gate")
    confirmation = contract.get("confirmation")
    if not isinstance(fidelity, Mapping) or not isinstance(confirmation, Mapping):
        raise ValueError("Cycle 6 scoring requires fidelity and confirmation mappings")
    if fidelity.get("status") != "ACCEPTED_INDEPENDENT_HUMAN_REVIEW":
        raise ValueError("Cycle 6 scoring is blocked until independent fidelity review is accepted")
    if confirmation.get("scoring_authorized") is not True:
        raise ValueError("Cycle 6 scoring is not authorized by the frozen contract")
    for name in ("full_packet_hash", "mechanical_artifact_hash", "independent_audit_hash"):
        _require_lower_hex_digest(name, fidelity.get(name))


def _score_text(source: Any, text: str, tokenizer: Any, adapter: Any, suffix: str) -> float:
    tokens = _encode_text(tokenizer, text)
    eos_token_id = source.model.eos_token_id
    if eos_token_id is None:
        raise ValueError("Cycle 6 confirmation tokenizer must define eos_token_id")
    batch = build_native_observations(
        f"{source.sample_id}-cycle6-{suffix}",
        tokens,
        eos_token_id,
        adapter,
    )
    return weighted_mean_evidence(batch).raw_score


def _summary(rows: tuple[Mapping[str, object], ...], label: str) -> dict[str, object]:
    selected = tuple(row for row in rows if row["source_label"] == label)
    if len(selected) != 64:
        raise ValueError(f"Cycle 6 evidence requires 64 {label} rows")
    counts = tuple(
        sum(bool(row["sanitizers"][variant]["detected"]) for row in selected)
        for variant in CYCLE6_SANITIZER_IDS
    )
    means = tuple(
        sum(float(row["sanitizers"][variant]["score"]) for row in selected) / len(selected)
        for variant in CYCLE6_SANITIZER_IDS
    )
    payload = {
        "source_label": label,
        "row_count": len(selected),
        "pristine_detected_count": sum(bool(row["pristine_detected"]) for row in selected),
        "mean_pristine_score": sum(float(row["pristine_score"]) for row in selected) / len(selected),
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
        "detected_per_sanitizer": counts,
        "mean_score_per_sanitizer": means,
        "mean_selected_operation_count": sum(
            int(row["selected_operation_count"]) for row in selected
        )
        / len(selected),
    }
    return {**payload, "summary_hash": sha256_json(payload)}


def score_cycle6_confirmation(
    corpus: Any,
    tokenizer: Any,
    plan: Mapping[str, object],
    adapter: HuggingFaceSynthIDAdapter,
    *,
    contract: Mapping[str, object],
    confirmation_seed_base: int,
) -> dict[str, object]:
    contract_hash = validate_cycle6_confirmation_contract(contract)
    _require_scoring_authorization(contract)
    if confirmation_seed_base not in CYCLE6_CONFIRMATION_SEED_BASES:
        raise ValueError("Cycle 6 confirmation seed is not frozen in the contract")
    plan_hash = validate_cycle6_confirmation_plan(plan, corpus, contract=contract)
    identity = runtime_tokenizer_identity_public(
        tokenizer,
        str(contract["measurement"]["model"]),
        str(contract["measurement"]["model_revision"]),
    )
    if identity.identity_hash != plan["tokenizer_identity_hash"]:
        raise ValueError("Cycle 6 scoring tokenizer drifted from the frozen plan")
    sources = {source.sample_id: source for source in _attack_samples(corpus)}
    rows: list[dict[str, object]] = []
    for planned in plan["rows"]:
        source = sources[str(planned["source_sample_id"])]
        pristine = _text_only_weighted_evidence(source, adapter).raw_score
        transformed = str(planned["transformed_text"])
        sanitizer_scores = {}
        for variant in CYCLE6_SANITIZER_IDS:
            text = sanitize_variant(variant, transformed)
            score = _score_text(source, text, tokenizer, adapter, variant)
            sanitizer_scores[variant] = {
                "text_hash": sha256_text(text),
                "score": score,
                "detected": score >= CYCLE6_THRESHOLD,
            }
        row = {
            "source_sample_id": source.sample_id,
            "source_label": source.label.value,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "transformed_text_hash": planned["transformed_text_hash"],
            "plan_row_hash": planned["row_hash"],
            "candidate_count": planned["candidate_count"],
            "selected_operation_count": planned["selected_operation_count"],
            "repair_selection_count": planned["repair_selection_count"],
            "budget_exhausted": planned["budget_exhausted"],
            "root_window_count": planned["root_window_count"],
            "intact_window_count": planned["intact_window_count"],
            "tuple_leak_window_count": planned["tuple_leak_window_count"],
            "closure_free": planned["closure_free"],
            "pristine_score": pristine,
            "pristine_detected": pristine >= CYCLE6_THRESHOLD,
            "sanitizers": sanitizer_scores,
        }
        rows.append({**row, "row_hash": sha256_json(row)})
    row_tuple = tuple(rows)
    summaries = (
        _summary(row_tuple, "unwatermarked"),
        _summary(row_tuple, "watermarked"),
    )
    payload = {
        "algorithm_version": CYCLE6_CONFIRMATION_EVIDENCE_VERSION,
        "scientific_scope": (
            "Sealed source-bound confirmation of the frozen Cycle 6 quote-safe B14 attack "
            "under one pinned open SynthID measurement identity"
        ),
        "contract_hash": contract_hash,
        "confirmation_seed_base": confirmation_seed_base,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "plan_hash": plan_hash,
        "ruleset_hash": plan["ruleset_hash"],
        "tokenizer_identity_hash": plan["tokenizer_identity_hash"],
        "measurement_identity": contract["measurement"]["identity"],
        "threshold": CYCLE6_THRESHOLD,
        "threshold_comparison": ">=",
        "threshold_target_fpr": contract["measurement"]["target_fpr"],
        "prior_fixed_threshold_file_sha256": contract["measurement"][
            "prior_fixed_threshold_file_sha256"
        ],
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
        "adapter_configuration_fingerprint": adapter.configuration_fingerprint(),
        "adapter_source_commit": adapter.source_pin.commit,
        "sampling_table_hash": adapter.sampling_table_hash,
        "selection_detector_access_observed": False,
        "selection_secret_access_observed": False,
        "rows": row_tuple,
        "summaries": summaries,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-cycle6-confirmation-score-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
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
    plan = _load_json(args.plan_json)
    contract = _load_json(args.contract_json)
    validate_cycle6_frozen_source_blobs(Path.cwd(), contract)
    if plan.get("source_code_commit") != args.source_code_commit:
        raise ValueError("Cycle 6 score invocation commit does not match the frozen plan")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("Cycle 6 confirmation scoring requires a fast public tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the confirmation corpus")
    watermark = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=watermark["ngram_len"],
            keys=watermark["keys"],
            context_history_size=watermark["context_history_size"],
            sampling_table_seed=watermark["sampling_table_seed"],
            sampling_table_size=watermark["sampling_table_size"],
            skip_first_ngram_calls=watermark["skip_first_ngram_calls"],
            debug_mode=watermark["debug_mode"],
        ),
        device=args.device,
    )
    started = _now()
    evidence = score_cycle6_confirmation(
        corpus,
        tokenizer,
        plan,
        adapter,
        contract=contract,
        confirmation_seed_base=args.confirmation_seed_base,
    )
    write_canonical_json_fsynced(args.json, evidence)
    fsynced = _now()
    provenance_payload = {
        "algorithm_version": CYCLE6_SCORE_PROVENANCE_VERSION,
        "source_code_commit": args.source_code_commit,
        "contract_hash": evidence["contract_hash"],
        "plan_hash": evidence["plan_hash"],
        "artifact_hash": evidence["artifact_hash"],
        "scoring_started_at_utc": started,
        "scoring_fsynced_at_utc": fsynced,
        "scoring_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {
        **provenance_payload,
        "provenance_hash": sha256_json(provenance_payload),
    }
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    for summary in evidence["summaries"]:
        sys.stdout.write(
            f"label={summary['source_label']} detected={summary['detected_per_sanitizer']} "
            f"rows={summary['row_count']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
