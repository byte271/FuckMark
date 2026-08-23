from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .._validation import require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..transforms.registry import TransformRegistry
from .general_spacing_exact_geometry import (
    diagnose_selected_candidate_geometry,
    diagnose_unselected_exact_marginals,
)


EFFECTIVENESS_EXACT_GEOMETRY_AUDIT_VERSION = "effectiveness-exact-geometry-audit-v1"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _source_texts(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("source_texts must be a mapping")
    output: dict[str, str] = {}
    for source_id, text in value.items():
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_texts keys must be non-empty strings")
        if not isinstance(text, str):
            raise TypeError("source_texts values must be strings")
        output[source_id] = text
    return output


def build_effectiveness_geometry_audit(
    *,
    plan: Mapping[str, object],
    source_texts: Mapping[str, str],
    registry: TransformRegistry,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> dict[str, object]:
    plan = _mapping(plan, "plan")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    plan_hash = plan.get("plan_hash")
    ruleset_hash = plan.get("ruleset_hash")
    require_sha256("plan_hash", plan_hash)
    require_sha256("ruleset_hash", ruleset_hash)
    if ruleset_hash != registry.ruleset_hash:
        raise ValueError("plan ruleset does not match audit registry")
    if plan.get("detector_access_observed") is not False:
        raise ValueError("plan must attest detector-blind selection")
    if plan.get("secret_access_observed") is not False:
        raise ValueError("plan must attest key-blind selection")
    variants = plan.get("variants")
    if isinstance(variants, (str, bytes, bytearray)) or not isinstance(variants, Sequence):
        raise TypeError("plan variants must be a sequence")
    if not variants:
        raise ValueError("plan variants must not be empty")
    sources = _source_texts(source_texts)

    rows: list[dict[str, object]] = []
    seen_variants: set[str] = set()
    for raw_entry in variants:
        entry = _mapping(raw_entry, "plan variant")
        variant_hash = entry.get("variant_hash")
        require_sha256("variant_hash", variant_hash)
        if variant_hash in seen_variants:
            raise ValueError("plan variant hashes must be unique")
        seen_variants.add(variant_hash)
        source_id = entry.get("source_sample_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("plan variant source_sample_id must be a non-empty string")
        if source_id not in sources:
            raise KeyError(f"plan variant references unknown source {source_id}")
        source_text = sources[source_id]
        source_text_hash = entry.get("source_text_hash")
        require_sha256("source_text_hash", source_text_hash)
        if source_text_hash != sha256_text(source_text):
            raise ValueError("plan variant source_text_hash does not match supplied source text")

        enumeration = registry.enumerate(source_text)
        if entry.get("enumeration_hash") != enumeration.enumeration_hash:
            raise ValueError("plan variant enumeration_hash does not replay")
        selected = entry.get("selected_candidate_ids")
        if isinstance(selected, (str, bytes, bytearray)) or not isinstance(selected, Sequence):
            raise TypeError("selected_candidate_ids must be a sequence")
        selected_ids = tuple(selected)
        if not selected_ids:
            raise ValueError("exact geometry audit currently requires a non-empty selected set")
        for candidate_id in selected_ids:
            require_sha256("selected_candidate_id", candidate_id)

        selected_geometry = diagnose_selected_candidate_geometry(
            source_sample_id=source_id,
            source_text=source_text,
            registry=registry,
            enumeration=enumeration,
            selected_candidate_ids=selected_ids,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
        )
        if entry.get("transformed_text_hash") != selected_geometry.transformed_text_hash:
            raise ValueError("plan transformed_text_hash does not replay under audit registry")
        plan_trace_hash = entry.get("transform_trace_hash")
        require_sha256("transform_trace_hash", plan_trace_hash)
        scheduler_covered = entry.get("scheduler_covered_interval_size")
        require_int("scheduler_covered_interval_size", scheduler_covered)
        if scheduler_covered != selected_geometry.proxy_covered_observation_count:
            raise ValueError("plan scheduler coverage does not match replayed proxy geometry")
        candidate_count = entry.get("candidate_count")
        requested_budget = entry.get("requested_budget")
        realized_edit_cost = entry.get("realized_edit_cost")
        require_int("candidate_count", candidate_count)
        require_int("requested_budget", requested_budget)
        require_int("realized_edit_cost", realized_edit_cost)
        if candidate_count != len(enumeration.candidates):
            raise ValueError("candidate_count does not match replayed enumeration")
        if requested_budget <= 0:
            raise ValueError("requested_budget must be positive")
        if not 0 <= realized_edit_cost <= requested_budget:
            raise ValueError("realized_edit_cost must be between zero and requested_budget")
        if realized_edit_cost != len(selected_ids):
            raise ValueError("realized_edit_cost does not match selected candidate count")
        unused_budget = requested_budget - realized_edit_cost
        unselected_candidate_count = candidate_count - realized_edit_cost
        proxy_saturated_before_budget = unused_budget > 0 and unselected_candidate_count > 0

        marginals = diagnose_unselected_exact_marginals(
            source_sample_id=source_id,
            source_text=source_text,
            registry=registry,
            enumeration=enumeration,
            selected_candidate_ids=selected_ids,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
        )
        hidden_rows = tuple(row for row in marginals.rows if row.hidden_exact_gain)
        row_payload = {
            "variant_hash": variant_hash,
            "source_sample_id": source_id,
            "source_text_hash": source_text_hash,
            "enumeration_hash": enumeration.enumeration_hash,
            "selected_candidate_ids": selected_ids,
            "plan_transform_trace_hash": plan_trace_hash,
            "diagnostic_transform_trace_hash": selected_geometry.transform_trace_hash,
            "selected_geometry_hash": selected_geometry.diagnostic_hash,
            "marginal_geometry_hash": marginals.diagnostic_hash,
            "candidate_count": candidate_count,
            "requested_budget": requested_budget,
            "realized_edit_cost": realized_edit_cost,
            "unused_budget": unused_budget,
            "unselected_candidate_count": unselected_candidate_count,
            "proxy_saturated_before_budget": proxy_saturated_before_budget,
            "root_observation_count": selected_geometry.root_observation_count,
            "proxy_covered_observation_count": selected_geometry.proxy_covered_observation_count,
            "exact_destroyed_observation_count": selected_geometry.exact_destroyed_observation_count,
            "exact_surviving_observation_count": selected_geometry.exact_surviving_observation_count,
            "exact_minus_proxy_count": selected_geometry.exact_minus_proxy_count,
            "hidden_exact_gain_count": marginals.hidden_exact_gain_count,
            "actionable_hidden_exact_gain_count": (
                marginals.hidden_exact_gain_count if proxy_saturated_before_budget else 0
            ),
            "maximum_hidden_exact_gain": marginals.maximum_hidden_exact_gain,
            "hidden_exact_gain_candidate_ids": tuple(row.candidate_id for row in hidden_rows),
            "hidden_exact_gain_rows": tuple(
                {**row.payload(), "row_hash": row.row_hash}
                for row in hidden_rows
            ),
            "marginal_row_hashes": tuple(row.row_hash for row in marginals.rows),
        }
        rows.append({**row_payload, "row_hash": sha256_json(row_payload)})

    row_tuple = tuple(rows)
    proxy_total = sum(int(row["proxy_covered_observation_count"]) for row in row_tuple)
    exact_total = sum(int(row["exact_destroyed_observation_count"]) for row in row_tuple)
    hidden_total = sum(int(row["hidden_exact_gain_count"]) for row in row_tuple)
    summary = {
        "variant_count": len(row_tuple),
        "independent_source_count": len({str(row["source_sample_id"]) for row in row_tuple}),
        "root_observation_count": sum(int(row["root_observation_count"]) for row in row_tuple),
        "proxy_covered_observation_count": proxy_total,
        "exact_destroyed_observation_count": exact_total,
        "exact_minus_proxy_count": exact_total - proxy_total,
        "proxy_overstatement_row_count": sum(int(row["exact_minus_proxy_count"]) < 0 for row in row_tuple),
        "proxy_understatement_row_count": sum(int(row["exact_minus_proxy_count"]) > 0 for row in row_tuple),
        "proxy_exact_match_row_count": sum(int(row["exact_minus_proxy_count"]) == 0 for row in row_tuple),
        "early_stop_row_count": sum(int(row["unused_budget"]) > 0 for row in row_tuple),
        "proxy_saturation_row_count": sum(
            bool(row["proxy_saturated_before_budget"]) for row in row_tuple
        ),
        "hidden_exact_gain_candidate_count": hidden_total,
        "hidden_exact_gain_row_count": sum(int(row["hidden_exact_gain_count"]) > 0 for row in row_tuple),
        "actionable_hidden_exact_gain_candidate_count": sum(
            int(row["actionable_hidden_exact_gain_count"]) for row in row_tuple
        ),
        "actionable_hidden_exact_gain_row_count": sum(
            bool(row["proxy_saturated_before_budget"]) and int(row["hidden_exact_gain_count"]) > 0
            for row in row_tuple
        ),
        "maximum_hidden_exact_gain": max(
            (int(row["maximum_hidden_exact_gain"]) for row in row_tuple),
            default=0,
        ),
    }
    summary_with_hash = {**summary, "summary_hash": sha256_json(summary)}
    payload = {
        "algorithm_version": EFFECTIVENESS_EXACT_GEOMETRY_AUDIT_VERSION,
        "scientific_scope": (
            "Detector-blind and key-blind structural replay comparing frozen source-span proxy "
            "coverage with exact post-retokenization root-observation destruction; no detector "
            "effectiveness or watermark-removal claim"
        ),
        "plan_hash": plan_hash,
        "ruleset_hash": registry.ruleset_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "selection_detector_access_observed": False,
        "selection_secret_access_observed": False,
        "rows": row_tuple,
        "summary": summary_with_hash,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
