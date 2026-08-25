from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fuckmark.experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    CYCLE6_SANITIZER_IDS,
    CYCLE6_THRESHOLD,
    aggregate_cycle6_confirmation,
    validate_cycle6_confirmation_contract,
    validate_cycle6_frozen_source_blobs,
)
from fuckmark.experiments.cycle6_fidelity import (
    build_cycle6_fidelity_mechanical_row,
    build_cycle6_full_fidelity_mechanical_report,
)
from fuckmark.hashing import sha256_json, sha256_text


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "specs" / "fuckmark-cycle6-confirmation-v1.contract.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _summary(rows: tuple[dict[str, object], ...], label: str) -> dict[str, object]:
    selected = tuple(row for row in rows if row["source_label"] == label)
    payload = {
        "source_label": label,
        "row_count": 64,
        "pristine_detected_count": sum(bool(row["pristine_detected"]) for row in selected),
        "mean_pristine_score": 0.9 if label == "watermarked" else 0.1,
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
        "detected_per_sanitizer": tuple(
            sum(bool(row["sanitizers"][variant]["detected"]) for row in selected)
            for variant in CYCLE6_SANITIZER_IDS
        ),
        "mean_score_per_sanitizer": (0.2, 0.2, 0.2, 0.2),
        "mean_selected_operation_count": 14.0,
    }
    return {**payload, "summary_hash": sha256_json(payload)}


def _evidence(
    seed: int,
    contract_hash: str,
    *,
    detected_variant: str | None = None,
    pristine_watermarked: int = 64,
    corpus_namespace: str | None = None,
) -> dict[str, object]:
    namespace = corpus_namespace or str(seed)
    rows = []
    for label in ("unwatermarked", "watermarked"):
        for index in range(64):
            detected = label == "watermarked" and detected_variant is not None and index == 0
            sanitizers = {
                variant: {
                    "text_hash": sha256_text(f"{namespace}-{label}-{index}-{variant}"),
                    "score": 0.6 if detected and variant == detected_variant else 0.2,
                    "detected": detected and variant == detected_variant,
                }
                for variant in CYCLE6_SANITIZER_IDS
            }
            row = {
                "source_sample_id": f"{seed}-{label}-{index}",
                "source_label": label,
                "source_text_hash": sha256_text(f"{namespace}-{label}-{index}"),
                "pristine_detected": (
                    label == "watermarked" and index < pristine_watermarked
                ),
                "sanitizers": sanitizers,
            }
            rows.append({**row, "row_hash": sha256_json(row)})
    row_tuple = tuple(rows)
    payload = {
        "algorithm_version": "cycle6-confirmation-evidence-v1",
        "contract_hash": contract_hash,
        "confirmation_seed_base": seed,
        "tiny_dev_artifact_hash": sha256_text(f"corpus-{seed}"),
        "corpus_manifest_hash": sha256_text(f"manifest-{seed}"),
        "plan_hash": sha256_text(f"plan-{seed}"),
        "ruleset_hash": "f09569fb20f313bc16db7f0e98305c0832ce508ca653546828cfd92c73ef632b",
        "tokenizer_identity_hash": "1be91dc38048d8f69fc45d5fb8175b0edb7c6ec807af1f6b85aa657343dbb95e",
        "measurement_identity": "open-detector-measurement-stability-v1",
        "threshold": CYCLE6_THRESHOLD,
        "threshold_comparison": ">=",
        "threshold_target_fpr": 0.01,
        "prior_fixed_threshold_file_sha256": "0b1b9e6ead71caf567e1b21bb3996098298aa207ae86db15c07584faaae09f37",
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
        "adapter_configuration_fingerprint": sha256_text("adapter"),
        "adapter_source_commit": "a61d5f9e4fc184cff66938ff6c521cc358b5e024",
        "sampling_table_hash": sha256_text("table"),
        "selection_detector_access_observed": False,
        "selection_secret_access_observed": False,
        "rows": row_tuple,
        "summaries": (
            _summary(row_tuple, "unwatermarked"),
            _summary(row_tuple, "watermarked"),
        ),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def test_cycle6_contract_freezes_source_and_confirmation_identities() -> None:
    contract = _contract()
    digest = validate_cycle6_confirmation_contract(contract)
    assert len(digest) == 64
    assert tuple(contract["confirmation"]["seed_bases"]) == CYCLE6_CONFIRMATION_SEED_BASES
    assert contract["attack"]["budget"] == 14
    assert contract["measurement"]["threshold"] == CYCLE6_THRESHOLD
    assert validate_cycle6_frozen_source_blobs(ROOT, contract)


@pytest.mark.parametrize("field", ("threshold", "comparison", "target_fpr"))
def test_cycle6_contract_rejects_detector_identity_drift(field: str) -> None:
    contract = _contract()
    contract["measurement"][field] = 0 if field != "comparison" else ">"
    with pytest.raises(ValueError):
        validate_cycle6_confirmation_contract(contract)


def test_cycle6_contract_rejects_seed_and_source_blob_drift() -> None:
    contract = _contract()
    contract["confirmation"]["seed_bases"][0] += 1
    with pytest.raises(ValueError, match="seeds drifted"):
        validate_cycle6_confirmation_contract(contract)

    contract = _contract()
    contract["attack"]["source_blobs"]["fuckmark/transforms/quote_policy.py"] = "0" * 40
    with pytest.raises(ValueError, match="declarations drifted"):
        validate_cycle6_frozen_source_blobs(ROOT, contract)


def test_cycle6_aggregate_classifies_zero_nonzero_and_invalid_control() -> None:
    contract = _contract()
    contract_hash = validate_cycle6_confirmation_contract(contract)
    zero = tuple(_evidence(seed, contract_hash) for seed in CYCLE6_CONFIRMATION_SEED_BASES)
    result = aggregate_cycle6_confirmation(zero, contract=contract)
    assert result["outcome"] == "ZERO_RESIDUAL"
    assert result["pooled"]["watermarked_detected_per_sanitizer"] == (0, 0, 0, 0)

    nonzero = list(zero)
    nonzero[1] = _evidence(770_000, contract_hash, detected_variant="raw")
    assert aggregate_cycle6_confirmation(nonzero, contract=contract)["outcome"] == "NONZERO_RESIDUAL"

    invalid = list(zero)
    invalid[2] = _evidence(780_000, contract_hash, pristine_watermarked=59)
    assert aggregate_cycle6_confirmation(invalid, contract=contract)["outcome"] == "INVALID_CONTROL"


def test_cycle6_aggregate_rejects_hash_tampering_and_cross_corpus_overlap() -> None:
    contract = _contract()
    contract_hash = validate_cycle6_confirmation_contract(contract)
    evidence = [_evidence(seed, contract_hash) for seed in CYCLE6_CONFIRMATION_SEED_BASES]
    tampered = copy.deepcopy(evidence)
    tampered[0]["rows"][0]["pristine_detected"] = True
    with pytest.raises(ValueError, match="artifact hash drifted"):
        aggregate_cycle6_confirmation(tampered, contract=contract)

    overlap = [
        _evidence(seed, contract_hash, corpus_namespace="same")
        for seed in CYCLE6_CONFIRMATION_SEED_BASES
    ]
    with pytest.raises(ValueError, match="overlap"):
        aggregate_cycle6_confirmation(overlap, contract=contract)


def test_full_fidelity_mechanical_gate_preserves_text_and_exposes_space_collapse() -> None:
    source = '"It is fine."'
    transformed = '"It is  fine."'
    operation = SimpleNamespace(
        source_start=4,
        source_end=6,
        before_text="is",
        after_text="is ",
        rule_id="surface-space-after-is",
    )
    geometry = {
        "root_window_count": 8,
        "intact_window_count": 2,
        "tuple_leak_window_count": 2,
        "closure_free": False,
        "budget_exhausted": True,
    }
    row = build_cycle6_fidelity_mechanical_row(
        sample_index=0,
        source_text=source,
        transformed_text=transformed,
        operations=(operation,),
        geometry=geometry,
    )
    assert row["mechanical_gate_passed"] is True
    assert row["non_whitespace_text_preserved"] is True
    assert row["quote_container_delimiters_untouched"] is True
    assert row["repeated_ascii_space_collapse_removes_spacing_edits"] is True

    rows = []
    for index in range(16):
        payload = {
            **{key: value for key, value in row.items() if key != "row_hash"},
            "sample_index": index,
        }
        rows.append({**payload, "row_hash": sha256_json(payload)})
    report = build_cycle6_full_fidelity_mechanical_report(
        tuple(rows),
        source_corpus_content_hash=sha256_text("corpus"),
        ruleset_hash=sha256_text("rules"),
        packet_hash=sha256_text("packet"),
    )
    assert report["all_mechanical_gates_passed"] is True
    assert report["all_spacing_edits_removed_by_repeated_ascii_space_collapse"] is True
    assert report["human_review_status"] == "PENDING_INDEPENDENT_HUMAN_REVIEW"


def test_full_fidelity_gate_allows_hard_invariant_safe_nonspacing_edits_outside_quotes() -> None:
    source = 'I do not agree. "It is fine."'
    contraction_start = source.index("do not")
    quote_spacing_start = source.index("is", source.index('"'))
    operations = (
        SimpleNamespace(
            source_start=contraction_start,
            source_end=contraction_start + len("do not"),
            before_text="do not",
            after_text="don't",
            rule_id="contraction-do-not",
        ),
        SimpleNamespace(
            source_start=quote_spacing_start,
            source_end=quote_spacing_start + len("is"),
            before_text="is",
            after_text="is ",
            rule_id="surface-space-after-is",
        ),
    )
    transformed = 'I don\'t agree. "It is  fine."'
    row = build_cycle6_fidelity_mechanical_row(
        sample_index=0,
        source_text=source,
        transformed_text=transformed,
        operations=operations,
        geometry={
            "root_window_count": 8,
            "intact_window_count": 2,
            "tuple_leak_window_count": 2,
            "closure_free": False,
            "budget_exhausted": True,
        },
    )
    assert row["mechanical_gate_passed"] is True
    assert row["non_whitespace_text_preserved"] is False
    assert row["spacing_operation_count"] == 1
    assert row["nonspacing_operation_count"] == 1
    assert row["quote_operation_count"] == 1
    assert row["repeated_ascii_space_collapse_removes_spacing_edits"] is True
