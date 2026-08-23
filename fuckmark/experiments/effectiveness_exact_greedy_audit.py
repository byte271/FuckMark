from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .._validation import require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..transforms.registry import TransformRegistry
from .exact_survival_greedy import schedule_exact_survival_greedy
from .general_spacing_exact_geometry import diagnose_selected_candidate_geometry


EFFECTIVENESS_EXACT_GREEDY_AUDIT_VERSION = "effectiveness-exact-greedy-audit-v1"


def build_effectiveness_exact_greedy_audit(
    *,
    plan: Mapping[str, object],
    source_texts: Mapping[str, str],
    registry: TransformRegistry,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> dict[str, object]:
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")
    if not isinstance(source_texts, Mapping):
        raise TypeError("source_texts must be a mapping")
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
        raise ValueError("plan ruleset does not match exact-greedy audit registry")
    if plan.get("detector_access_observed") is not False or plan.get("secret_access_observed") is not False:
        raise ValueError("exact-greedy audit requires detector-blind and key-blind baseline planning")
    raw_variants = plan.get("variants")
    if isinstance(raw_variants, (str, bytes, bytearray)) or not isinstance(raw_variants, Sequence):
        raise TypeError("plan variants must be a sequence")
    if not raw_variants:
        raise ValueError("plan variants must not be empty")

    rows: list[dict[str, object]] = []
    seen_variants: set[str] = set()
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, Mapping):
            raise TypeError("plan variant must be a mapping")
        entry = dict(raw_variant)
        variant_hash = entry.get("variant_hash")
        require_sha256("variant_hash", variant_hash)
        if variant_hash in seen_variants:
            raise ValueError("plan variant hashes must be unique")
        seen_variants.add(variant_hash)
        source_id = entry.get("source_sample_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_sample_id must be a non-empty string")
        source_text = source_texts.get(source_id)
        if not isinstance(source_text, str):
            raise KeyError(f"source_texts does not contain {source_id}")
        source_text_hash = entry.get("source_text_hash")
        require_sha256("source_text_hash", source_text_hash)
        if source_text_hash != sha256_text(source_text):
            raise ValueError("source text hash does not replay")

        enumeration = registry.enumerate(source_text)
        if entry.get("enumeration_hash") != enumeration.enumeration_hash:
            raise ValueError("enumeration hash does not replay")
        candidate_count = entry.get("candidate_count")
        budget = entry.get("budget")
        realized_edit_cost = entry.get("realized_edit_cost")
        require_int("candidate_count", candidate_count)
        require_int("budget", budget)
        require_int("realized_edit_cost", realized_edit_cost)
        if candidate_count != len(enumeration.candidates):
            raise ValueError("candidate_count does not match replayed enumeration")
        if budget < 0 or realized_edit_cost < 0 or realized_edit_cost > budget:
            raise ValueError("baseline budget accounting is invalid")
        raw_selected = entry.get("selected_candidate_ids")
        if isinstance(raw_selected, (str, bytes, bytearray)) or not isinstance(raw_selected, Sequence):
            raise TypeError("selected_candidate_ids must be a sequence")
        baseline_selected = tuple(raw_selected)
        if len(baseline_selected) != realized_edit_cost:
            raise ValueError("baseline realized edit cost does not match selected IDs")

        baseline = diagnose_selected_candidate_geometry(
            source_sample_id=source_id,
            source_text=source_text,
            registry=registry,
            enumeration=enumeration,
            selected_candidate_ids=baseline_selected,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
        )
        if entry.get("transformed_text_hash") != baseline.transformed_text_hash:
            raise ValueError("baseline transformed text does not replay")

        exact = schedule_exact_survival_greedy(
            source_sample_id=source_id,
            source_text=source_text,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
            budget=budget,
        )
        exact_gain = exact.exact_destroyed_observation_count - baseline.exact_destroyed_observation_count
        row_payload = {
            "variant_hash": variant_hash,
            "source_sample_id": source_id,
            "source_label": entry.get("source_label"),
            "domain": entry.get("domain"),
            "source_text_hash": source_text_hash,
            "enumeration_hash": enumeration.enumeration_hash,
            "candidate_count": candidate_count,
            "budget": budget,
            "baseline_selected_candidate_ids": baseline_selected,
            "baseline_selected_candidate_count": len(baseline_selected),
            "baseline_proxy_covered_observation_count": baseline.proxy_covered_observation_count,
            "baseline_exact_destroyed_observation_count": baseline.exact_destroyed_observation_count,
            "baseline_geometry_diagnostic_hash": baseline.diagnostic_hash,
            "exact_greedy_selection_order": exact.selection_order,
            "exact_greedy_selected_candidate_ids": exact.selected_candidate_ids,
            "exact_greedy_selected_candidate_count": exact.selected_candidate_count,
            "exact_greedy_destroyed_observation_count": exact.exact_destroyed_observation_count,
            "exact_greedy_surviving_observation_count": exact.exact_surviving_observation_count,
            "exact_greedy_policy_saturated": exact.policy_saturated,
            "exact_greedy_result_hash": exact.result_hash,
            "exact_destruction_gain": exact_gain,
            "same_selected_set": set(baseline_selected) == set(exact.selected_candidate_ids),
            "detector_access_observed": False,
            "secret_access_observed": False,
        }
        rows.append({**row_payload, "row_hash": sha256_json(row_payload)})

    row_tuple = tuple(rows)
    baseline_total = sum(int(row["baseline_exact_destroyed_observation_count"]) for row in row_tuple)
    exact_total = sum(int(row["exact_greedy_destroyed_observation_count"]) for row in row_tuple)
    summary = {
        "variant_count": len(row_tuple),
        "independent_source_count": len({str(row["source_sample_id"]) for row in row_tuple}),
        "baseline_selected_candidate_count": sum(int(row["baseline_selected_candidate_count"]) for row in row_tuple),
        "exact_greedy_selected_candidate_count": sum(int(row["exact_greedy_selected_candidate_count"]) for row in row_tuple),
        "baseline_exact_destroyed_observation_count": baseline_total,
        "exact_greedy_destroyed_observation_count": exact_total,
        "exact_destruction_gain": exact_total - baseline_total,
        "improved_row_count": sum(int(row["exact_destruction_gain"]) > 0 for row in row_tuple),
        "equal_row_count": sum(int(row["exact_destruction_gain"]) == 0 for row in row_tuple),
        "regressed_row_count": sum(int(row["exact_destruction_gain"]) < 0 for row in row_tuple),
        "changed_selection_row_count": sum(not bool(row["same_selected_set"]) for row in row_tuple),
        "exact_greedy_policy_saturated_row_count": sum(bool(row["exact_greedy_policy_saturated"]) for row in row_tuple),
        "maximum_row_gain": max((int(row["exact_destruction_gain"]) for row in row_tuple), default=0),
        "minimum_row_gain": min((int(row["exact_destruction_gain"]) for row in row_tuple), default=0),
    }
    summary_with_hash = {**summary, "summary_hash": sha256_json(summary)}
    payload = {
        "algorithm_version": EFFECTIVENESS_EXACT_GREEDY_AUDIT_VERSION,
        "scientific_scope": (
            "Detector-blind and key-blind matched-budget structural comparison between the frozen "
            "source-span proxy scheduler and exact post-retokenization root-observation greedy search; "
            "no detector effectiveness or watermark-removal claim"
        ),
        "plan_hash": plan_hash,
        "ruleset_hash": registry.ruleset_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "rows": row_tuple,
        "summary": summary_with_hash,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
