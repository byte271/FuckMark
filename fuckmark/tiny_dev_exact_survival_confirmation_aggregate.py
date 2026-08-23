from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.exact_survival_effectiveness_plan import CONFIRMATION_SEED_BASES, validate_exact_survival_confirmation_contract
from .hashing import sha256_json


EXACT_SURVIVAL_CONFIRMATION_AGGREGATE_VERSION = "exact-survival-confirmation-aggregate-v1"


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def classify_confirmation(per_corpus: Sequence[Mapping[str, object]]) -> str:
    if len(per_corpus) != 3:
        raise ValueError("confirmation classification requires exactly three corpora")
    if any(int(row["pristine_watermarked_detected_count"]) < 60 for row in per_corpus):
        return "INVALID_CONTROL"
    baseline = sum(int(row["baseline_watermarked_detected_count"]) for row in per_corpus)
    exact = sum(int(row["exact_watermarked_detected_count"]) for row in per_corpus)
    if exact > baseline:
        return "REGRESSION"
    if exact == baseline:
        return "NEUTRAL"
    per_corpus_nonworse = all(int(row["exact_watermarked_detected_count"]) <= int(row["baseline_watermarked_detected_count"]) for row in per_corpus)
    baseline_controls = sum(int(row["baseline_unwatermarked_detected_count"]) for row in per_corpus)
    exact_controls = sum(int(row["exact_unwatermarked_detected_count"]) for row in per_corpus)
    if per_corpus_nonworse and exact_controls <= baseline_controls:
        return "CONFIRMATORY_IMPROVEMENT"
    return "PARTIAL_IMPROVEMENT"


def aggregate_confirmation(evidence: Sequence[Mapping[str, object]], contract: Mapping[str, object]) -> dict[str, object]:
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    if len(evidence) != 3:
        raise ValueError("confirmation aggregate requires exactly three evidence artifacts")
    seeds = tuple(sorted(int(item["confirmation_seed_base"]) for item in evidence))
    if seeds != CONFIRMATION_SEED_BASES:
        raise ValueError("confirmation evidence seed bases do not match the frozen contract")
    if len({str(item["tiny_dev_artifact_hash"]) for item in evidence}) != 3:
        raise ValueError("confirmation evidence must use three distinct corpus artifacts")
    for item in evidence:
        if item.get("contract_hash") != contract_hash:
            raise ValueError("confirmation evidence contract binding drifted")
        if item.get("selection_detector_access_observed") is not False or item.get("selection_secret_access_observed") is not False:
            raise ValueError("confirmation evidence selection access attestation drifted")
    stable_fields = (
        "ruleset_hash",
        "tokenizer_identity_hash",
        "measurement_identity",
        "threshold",
        "threshold_comparison",
        "threshold_target_fpr",
        "prior_fixed_threshold_file_sha256",
        "adapter_configuration_fingerprint",
        "adapter_source_commit",
        "sampling_table_hash",
    )
    first = evidence[0]
    for field in stable_fields:
        if any(item.get(field) != first.get(field) for item in evidence[1:]):
            raise ValueError(f"confirmation evidence {field} drifted across corpora")
    per_corpus: list[dict[str, object]] = []
    for item in sorted(evidence, key=lambda value: int(value["confirmation_seed_base"])):
        summaries = {str(summary["source_label"]): summary for summary in item["summaries"]}
        watermarked = summaries.get("watermarked")
        unwatermarked = summaries.get("unwatermarked")
        if not isinstance(watermarked, Mapping) or not isinstance(unwatermarked, Mapping):
            raise ValueError("confirmation evidence must summarize both labels")
        if watermarked.get("row_count") != 64 or unwatermarked.get("row_count") != 64:
            raise ValueError("each confirmation corpus must contain 64 attack rows per label")
        row = {
            "confirmation_seed_base": item["confirmation_seed_base"],
            "artifact_hash": item["artifact_hash"],
            "corpus_artifact_hash": item["tiny_dev_artifact_hash"],
            "pristine_watermarked_detected_count": watermarked["pristine_detected_count"],
            "baseline_watermarked_detected_count": watermarked["baseline_detected_count"],
            "exact_watermarked_detected_count": watermarked["exact_detected_count"],
            "baseline_unwatermarked_detected_count": unwatermarked["baseline_detected_count"],
            "exact_unwatermarked_detected_count": unwatermarked["exact_detected_count"],
            "watermarked_mean_baseline_score": watermarked["mean_baseline_score"],
            "watermarked_mean_exact_score": watermarked["mean_exact_score"],
            "watermarked_mean_exact_minus_baseline_score": watermarked["mean_exact_minus_baseline_score"],
        }
        per_corpus.append({**row, "row_hash": sha256_json(row)})
    per_tuple = tuple(per_corpus)
    outcome = classify_confirmation(per_tuple)
    pooled = {
        "pristine_watermarked_detected_count": sum(int(row["pristine_watermarked_detected_count"]) for row in per_tuple),
        "watermarked_row_count": 192,
        "baseline_watermarked_detected_count": sum(int(row["baseline_watermarked_detected_count"]) for row in per_tuple),
        "exact_watermarked_detected_count": sum(int(row["exact_watermarked_detected_count"]) for row in per_tuple),
        "exact_minus_baseline_watermarked_detected_count": sum(int(row["exact_watermarked_detected_count"]) - int(row["baseline_watermarked_detected_count"]) for row in per_tuple),
        "baseline_unwatermarked_detected_count": sum(int(row["baseline_unwatermarked_detected_count"]) for row in per_tuple),
        "exact_unwatermarked_detected_count": sum(int(row["exact_unwatermarked_detected_count"]) for row in per_tuple),
        "unwatermarked_row_count": 192,
    }
    pooled_with_hash = {**pooled, "pooled_hash": sha256_json(pooled)}
    payload = {
        "algorithm_version": EXACT_SURVIVAL_CONFIRMATION_AGGREGATE_VERSION,
        "contract_hash": contract_hash,
        "outcome": outcome,
        "classification_policy": contract["outcome_policy"],
        "per_corpus": per_tuple,
        "pooled": pooled_with_hash,
        "selection_frozen_before_scoring": True,
        "detector_access_used_for_selection": False,
        "secret_access_used_for_selection": False,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-exact-survival-confirmation-aggregate")
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, action="append", required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    contract = _load_json(args.contract_json)
    evidence = tuple(_load_json(path) for path in args.evidence_json)
    artifact = aggregate_confirmation(evidence, contract)
    write_canonical_json_fsynced(args.json, artifact)
    pooled = artifact["pooled"]
    sys.stdout.write(f"outcome={artifact['outcome']}\n")
    sys.stdout.write(
        f"watermarked baseline={pooled['baseline_watermarked_detected_count']}/192 "
        f"exact={pooled['exact_watermarked_detected_count']}/192 "
        f"difference={pooled['exact_minus_baseline_watermarked_detected_count']}\n"
    )
    sys.stdout.write(
        f"unwatermarked baseline={pooled['baseline_unwatermarked_detected_count']}/192 "
        f"exact={pooled['exact_unwatermarked_detected_count']}/192\n"
    )
    sys.stdout.write(f"artifact_hash={artifact['artifact_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
