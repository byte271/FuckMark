from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusSample, CorpusSplit
from ..hashing import sha256_json, sha256_text
from ..transforms import (
    CandidateScheduler,
    EffectivenessTransformProfile,
    InvariantStatus,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    build_candidate_tokenizer_geometry,
    key_blind_coverage_completion_transform_registry,
    key_blind_high_coverage_transform_registry,
    validate_effectiveness_profile_registry,
    validate_hard_invariants,
    KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
)


KEY_BLIND_HIGH_COVERAGE_PLAN_VERSION = "key-blind-high-coverage-plan-v1"
KEY_BLIND_HIGH_COVERAGE_SEED_VERSION = "b16-sorted-source-index-seed-v1"
_PLAN_KEYS = frozenset(
    (
        "algorithm_version",
        "scientific_scope",
        "source_code_commit",
        "tiny_dev_artifact_hash",
        "corpus_manifest_hash",
        "tokenizer_identity_hash",
        "profile_id",
        "profile_hash",
        "ruleset_hash",
        "geometry_mode",
        "ngram_len",
        "schedule_policy",
        "budget_unit",
        "budgets",
        "replicate_count",
        "seed_derivation_version",
        "detector_access_observed",
        "secret_access_observed",
        "source_diagnostics",
        "variants",
        "plan_hash",
    )
)
_VARIANT_KEYS = frozenset(
    (
        "source_sample_id",
        "source_index",
        "replicate",
        "source_label",
        "prompt_family_id",
        "domain",
        "source_text_hash",
        "candidate_count",
        "candidate_pool_hash",
        "enumeration_hash",
        "geometry_hash",
        "scheduler_input_hash",
        "schedule_policy",
        "schedule_seed",
        "requested_budget",
        "budget",
        "budget_unit",
        "schedule_result_hash",
        "selected_candidate_ids",
        "realized_edit_cost",
        "scheduler_covered_interval_size",
        "transformed_text",
        "transformed_text_hash",
        "transform_trace_hash",
        "hard_invariant_status",
        "detector_access_observed",
        "secret_access_observed",
        "variant_hash",
    )
)
_SOURCE_DIAGNOSTIC_KEYS = frozenset(
    (
        "sample_id",
        "label",
        "domain",
        "source_text_hash",
        "candidate_count",
        "rejection_count",
        "enumeration_hash",
        "geometry_hash",
        "scheduler_input_hash",
        "candidate_pool_hash",
    )
)


def _require_git_object_id(name: str, value: str) -> None:
    require_clean_string(name, value)
    if len(value) not in (40, 64) or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase Git object ID")


def _attack_samples(corpus: Any) -> tuple[CorpusSample, ...]:
    samples = tuple(
        sorted(
            (
                sample
                for sample in corpus.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
            ),
            key=lambda value: value.sample_id,
        )
    )
    if not samples:
        raise ValueError("effectiveness planning requires attack-development samples")
    return samples


def _encode_with_offsets(tokenizer: Any, sample: CorpusSample) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    if sample.text_only_tokens is None:
        raise ValueError(f"sample {sample.sample_id} has no text-only token track")
    encoded = tokenizer(
        sample.text,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    ids = tuple(int(value) for value in encoded["input_ids"])
    offsets = tuple((int(start), int(end)) for start, end in encoded["offset_mapping"])
    if ids != sample.text_only_tokens.token_ids:
        raise ValueError(
            f"public tokenizer replay does not match recorded text-only track for {sample.sample_id}"
        )
    return ids, offsets


def _schedule_seed(
    profile: EffectivenessTransformProfile,
    source_index: int,
    replicate: int,
) -> int:
    if isinstance(source_index, bool) or not isinstance(source_index, int) or source_index < 0:
        raise ValueError("source_index must be a non-negative integer")
    if isinstance(replicate, bool) or not isinstance(replicate, int) or replicate < 0:
        raise ValueError("replicate must be a non-negative integer")
    if profile.replicate_count != 1 or replicate != 0:
        raise ValueError("the frozen B16 profile requires exactly one replicate")
    seed = profile.schedule_seed_base + source_index
    if seed >= 1 << 64:
        raise ValueError("derived schedule seed exceeds the uint64 range")
    return seed


def _registry_for_profile(profile: EffectivenessTransformProfile):
    if profile.profile_id == KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID:
        return key_blind_coverage_completion_transform_registry()
    return key_blind_high_coverage_transform_registry()


def build_key_blind_high_coverage_plan(
    corpus: Any,
    tokenizer: Any,
    *,
    profile: EffectivenessTransformProfile,
    source_code_commit: str,
) -> dict[str, object]:
    _require_git_object_id("source_code_commit", source_code_commit)
    registry = _registry_for_profile(profile)
    validate_effectiveness_profile_registry(profile, registry)
    policy = SchedulePolicy(profile.schedule_policy_id)
    if policy is not SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND:
        raise ValueError("effectiveness profile must use key-blind coverage scheduling")
    scheduler = CandidateScheduler()
    source_diagnostics: list[dict[str, object]] = []
    variants: list[dict[str, object]] = []
    sources = _attack_samples(corpus)
    for source_index, source in enumerate(sources):
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        enumeration = registry.enumerate(source.text)
        geometry = build_candidate_tokenizer_geometry(
            source.text,
            enumeration,
            token_ids,
            offsets,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=profile.ngram_len,
        )
        scheduler_input = KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=geometry.coverage_mapping(),
            budget_unit=profile.budget_unit,
            geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        )
        candidate_pool_hash = sha256_json(
            {
                "enumeration_hash": enumeration.enumeration_hash,
                "geometry_hash": geometry.geometry_hash,
                "ruleset_hash": registry.ruleset_hash,
            }
        )
        source_diagnostics.append(
            {
                "sample_id": source.sample_id,
                "label": source.label.value,
                "domain": source.domain.value,
                "source_text_hash": source.text_sha256,
                "candidate_count": len(enumeration.candidates),
                "rejection_count": len(enumeration.rejections),
                "enumeration_hash": enumeration.enumeration_hash,
                "geometry_hash": geometry.geometry_hash,
                "scheduler_input_hash": scheduler_input.input_artifact_hash,
                "candidate_pool_hash": candidate_pool_hash,
            }
        )
        for requested_budget in profile.budgets:
            budget = min(requested_budget, len(enumeration.candidates))
            for replicate in range(profile.replicate_count):
                seed = _schedule_seed(profile, source_index, replicate)
                schedule = scheduler.schedule(scheduler_input, policy, budget, seed)
                result = registry.apply(enumeration, schedule.selected_candidate_ids, seed=seed)
                if result.trace.invariant_report.status is not InvariantStatus.PASS:
                    raise ValueError("effectiveness plan accepted a hard-invariant violation")
                row = {
                    "source_sample_id": source.sample_id,
                    "source_index": source_index,
                    "replicate": replicate,
                    "source_label": source.label.value,
                    "prompt_family_id": source.prompt_family_id,
                    "domain": source.domain.value,
                    "source_text_hash": source.text_sha256,
                    "candidate_count": len(enumeration.candidates),
                    "candidate_pool_hash": candidate_pool_hash,
                    "enumeration_hash": enumeration.enumeration_hash,
                    "geometry_hash": geometry.geometry_hash,
                    "scheduler_input_hash": scheduler_input.input_artifact_hash,
                    "schedule_policy": policy.value,
                    "schedule_seed": seed,
                    "requested_budget": requested_budget,
                    "budget": budget,
                    "budget_unit": profile.budget_unit,
                    "schedule_result_hash": schedule.result_hash,
                    "selected_candidate_ids": schedule.selected_candidate_ids,
                    "realized_edit_cost": schedule.total_cost,
                    "scheduler_covered_interval_size": schedule.covered_interval_size,
                    "transformed_text": result.output_text,
                    "transformed_text_hash": sha256_text(result.output_text),
                    "transform_trace_hash": result.trace.trace_hash,
                    "hard_invariant_status": result.trace.invariant_report.status.value,
                    "detector_access_observed": False,
                    "secret_access_observed": False,
                }
                variants.append({**row, "variant_hash": sha256_json(row)})
    payload = {
        "algorithm_version": KEY_BLIND_HIGH_COVERAGE_PLAN_VERSION,
        "scientific_scope": profile.scientific_scope,
        "source_code_commit": source_code_commit,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "tokenizer_identity_hash": corpus.model_identity_hash,
        "profile_id": profile.profile_id,
        "profile_hash": profile.profile_hash,
        "ruleset_hash": registry.ruleset_hash,
        "geometry_mode": ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC.value,
        "ngram_len": profile.ngram_len,
        "schedule_policy": policy.value,
        "budget_unit": profile.budget_unit,
        "budgets": profile.budgets,
        "replicate_count": profile.replicate_count,
        "seed_derivation_version": KEY_BLIND_HIGH_COVERAGE_SEED_VERSION,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "source_diagnostics": tuple(source_diagnostics),
        "variants": tuple(variants),
    }
    return {**payload, "plan_hash": sha256_json(payload)}


def validate_key_blind_high_coverage_plan(
    plan: Mapping[str, object],
    corpus: Any,
    profile: EffectivenessTransformProfile,
) -> None:
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")
    value = dict(plan)
    if frozenset(value) != _PLAN_KEYS:
        raise ValueError("effectiveness plan keys do not match the frozen schema")
    if value["algorithm_version"] != KEY_BLIND_HIGH_COVERAGE_PLAN_VERSION:
        raise ValueError("unsupported effectiveness plan algorithm version")
    _require_git_object_id("source_code_commit", value["source_code_commit"])
    if value["scientific_scope"] != profile.scientific_scope:
        raise ValueError("effectiveness plan scientific scope does not match the frozen profile")
    if value["profile_id"] != profile.profile_id or value["profile_hash"] != profile.profile_hash:
        raise ValueError("effectiveness plan profile binding does not match")
    if value["ruleset_hash"] != profile.ruleset_hash:
        raise ValueError("effectiveness plan ruleset binding does not match")
    if tuple(value["budgets"]) != profile.budgets:
        raise ValueError("effectiveness plan budgets do not match the frozen profile")
    if value["ngram_len"] != profile.ngram_len:
        raise ValueError("effectiveness plan ngram length does not match the frozen profile")
    if value["schedule_policy"] != profile.schedule_policy_id:
        raise ValueError("effectiveness plan scheduling policy does not match the frozen profile")
    if value["budget_unit"] != profile.budget_unit:
        raise ValueError("effectiveness plan budget unit does not match the frozen profile")
    if value["geometry_mode"] != ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC.value:
        raise ValueError("effectiveness plan geometry mode is not the frozen public mode")
    if value["seed_derivation_version"] != KEY_BLIND_HIGH_COVERAGE_SEED_VERSION:
        raise ValueError("effectiveness plan seed derivation does not match the frozen profile")
    if value["tiny_dev_artifact_hash"] != corpus.artifact_hash:
        raise ValueError("effectiveness plan does not bind the supplied TinyDev corpus")
    if value["corpus_manifest_hash"] != corpus.manifest.manifest_hash:
        raise ValueError("effectiveness plan manifest hash does not match the supplied corpus")
    if value["tokenizer_identity_hash"] != corpus.model_identity_hash:
        raise ValueError("effectiveness plan tokenizer identity does not match the supplied corpus")
    if value["detector_access_observed"] is not False or value["secret_access_observed"] is not False:
        raise ValueError("effectiveness plan reports forbidden planning access")
    expected_plan_hash = sha256_json({key: item for key, item in value.items() if key != "plan_hash"})
    if value["plan_hash"] != expected_plan_hash:
        raise ValueError("effectiveness plan hash does not replay")
    sources = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    replicate_count = value["replicate_count"]
    if replicate_count != profile.replicate_count:
        raise ValueError("effectiveness plan replicate count does not match the frozen profile")
    ordered_sources = tuple(sources)
    source_indices = {sample_id: index for index, sample_id in enumerate(ordered_sources)}
    diagnostic_values = value["source_diagnostics"]
    if not isinstance(diagnostic_values, (tuple, list)):
        raise TypeError("effectiveness plan source diagnostics must be a sequence")
    if len(diagnostic_values) != len(sources):
        raise ValueError("effectiveness plan source diagnostics do not preserve the denominator")
    diagnostics: dict[str, dict[str, object]] = {}
    for source_index, diagnostic_value in enumerate(diagnostic_values):
        if not isinstance(diagnostic_value, Mapping):
            raise TypeError("effectiveness plan source diagnostics must be mappings")
        diagnostic = dict(diagnostic_value)
        if frozenset(diagnostic) != _SOURCE_DIAGNOSTIC_KEYS:
            raise ValueError("effectiveness plan source diagnostic keys do not match the frozen schema")
        sample_id = diagnostic["sample_id"]
        if sample_id not in sources or sample_id in diagnostics:
            raise ValueError("effectiveness plan source diagnostics contain an unknown or duplicate source")
        if source_indices[sample_id] != source_index:
            raise ValueError("effectiveness plan source diagnostics are not in frozen source order")
        source = sources[sample_id]
        if (
            diagnostic["label"] != source.label.value
            or diagnostic["domain"] != source.domain.value
            or diagnostic["source_text_hash"] != source.text_sha256
        ):
            raise ValueError("effectiveness plan source diagnostic binding does not match")
        for name in ("candidate_count", "rejection_count"):
            require_int(name, diagnostic[name])
            if diagnostic[name] < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in (
            "source_text_hash",
            "enumeration_hash",
            "geometry_hash",
            "scheduler_input_hash",
            "candidate_pool_hash",
        ):
            require_sha256(name, diagnostic[name])
        diagnostics[sample_id] = diagnostic
    expected_coordinates = {
        (sample_id, requested_budget, replicate)
        for sample_id in sources
        for requested_budget in profile.budgets
        for replicate in range(profile.replicate_count)
    }
    observed_coordinates: set[tuple[str, int, int]] = set()
    variant_values = value["variants"]
    if not isinstance(variant_values, (tuple, list)):
        raise TypeError("effectiveness plan variants must be a sequence")
    for row_value in variant_values:
        if not isinstance(row_value, Mapping):
            raise TypeError("effectiveness plan variants must be mappings")
        row = dict(row_value)
        if frozenset(row) != _VARIANT_KEYS:
            raise ValueError("effectiveness plan variant keys do not match the frozen schema")
        expected_variant_hash = sha256_json({key: item for key, item in row.items() if key != "variant_hash"})
        if row["variant_hash"] != expected_variant_hash:
            raise ValueError("effectiveness plan variant hash does not replay")
        sample_id = row["source_sample_id"]
        if sample_id not in sources:
            raise ValueError("effectiveness plan variant references an unknown source")
        source = sources[sample_id]
        if (
            row["source_text_hash"] != source.text_sha256
            or row["source_label"] != source.label.value
            or row["prompt_family_id"] != source.prompt_family_id
            or row["domain"] != source.domain.value
        ):
            raise ValueError("effectiveness plan variant source binding does not match")
        diagnostic = diagnostics[sample_id]
        for name in (
            "candidate_count",
            "candidate_pool_hash",
            "enumeration_hash",
            "geometry_hash",
            "scheduler_input_hash",
        ):
            if row[name] != diagnostic[name]:
                raise ValueError("effectiveness plan variant does not match its source diagnostic")
        source_index = source_indices[sample_id]
        if row["source_index"] != source_index:
            raise ValueError("effectiveness plan variant source index does not replay")
        replicate = row["replicate"]
        if replicate != 0:
            raise ValueError("effectiveness plan variant replicate does not match the frozen profile")
        requested_budget = row["requested_budget"]
        if requested_budget not in profile.budgets:
            raise ValueError("effectiveness plan variant uses an unknown requested budget")
        require_int("candidate_count", row["candidate_count"])
        budget = row["budget"]
        require_int("budget", budget)
        expected_budget = min(requested_budget, row["candidate_count"])
        if budget != expected_budget:
            raise ValueError("effectiveness plan variant budget does not replay candidate truncation")
        if row["schedule_seed"] != _schedule_seed(profile, source_index, replicate):
            raise ValueError("effectiveness plan variant schedule seed does not replay")
        coordinate = (sample_id, requested_budget, replicate)
        if coordinate in observed_coordinates:
            raise ValueError("effectiveness plan contains a duplicate source-budget-replicate row")
        observed_coordinates.add(coordinate)
        selected_ids = tuple(row["selected_candidate_ids"])
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("effectiveness plan variant contains duplicate candidate IDs")
        for candidate_id in selected_ids:
            require_sha256("selected_candidate_id", candidate_id)
        if len(selected_ids) > row["candidate_count"]:
            raise ValueError("effectiveness plan selects more candidates than its candidate pool")
        if row["schedule_policy"] != profile.schedule_policy_id:
            raise ValueError("effectiveness plan variant scheduling policy does not match")
        if row["budget_unit"] != profile.budget_unit:
            raise ValueError("effectiveness plan variant budget unit does not match")
        require_int("realized_edit_cost", row["realized_edit_cost"])
        require_int("scheduler_covered_interval_size", row["scheduler_covered_interval_size"])
        if row["realized_edit_cost"] != len(selected_ids) or row["realized_edit_cost"] > budget:
            raise ValueError("effectiveness plan realized edit cost is invalid")
        if (row["realized_edit_cost"] > 0) == (row["transformed_text"] == source.text):
            raise ValueError("effectiveness plan edit cost does not match transformed text change")
        if row["scheduler_covered_interval_size"] < 0:
            raise ValueError("effectiveness plan covered interval size is invalid")
        for name in (
            "source_text_hash",
            "candidate_pool_hash",
            "enumeration_hash",
            "geometry_hash",
            "scheduler_input_hash",
            "schedule_result_hash",
            "transformed_text_hash",
            "transform_trace_hash",
            "variant_hash",
        ):
            require_sha256(name, row[name])
        if not isinstance(row["transformed_text"], str):
            raise TypeError("transformed_text must be a string")
        if row["transformed_text_hash"] != sha256_text(row["transformed_text"]):
            raise ValueError("effectiveness plan transformed text hash does not replay")
        if row["hard_invariant_status"] != InvariantStatus.PASS.value:
            raise ValueError("effectiveness plan variant failed hard invariants")
        if validate_hard_invariants(source.text, row["transformed_text"]).status is not InvariantStatus.PASS:
            raise ValueError("effectiveness plan transformed text does not replay hard invariants")
        if row["detector_access_observed"] is not False or row["secret_access_observed"] is not False:
            raise ValueError("effectiveness plan variant reports forbidden planning access")
    if observed_coordinates != expected_coordinates:
        raise ValueError("effectiveness plan does not preserve the complete source denominator")
