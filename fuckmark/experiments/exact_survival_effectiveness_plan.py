from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusSplit
from ..hashing import sha256_json, sha256_text
from ..transforms import InvariantStatus, content_region_coverage_profile, content_region_coverage_transform_registry, validate_effectiveness_profile_registry
from .exact_survival_greedy import EXACT_SURVIVAL_GREEDY_ALGORITHM_VERSION, EXACT_SURVIVAL_GREEDY_POLICY_ID, schedule_exact_survival_greedy


EXACT_SURVIVAL_EFFECTIVENESS_PLAN_VERSION = "exact-survival-effectiveness-plan-v1"
EXACT_SURVIVAL_CONFIRMATION_CONTRACT_VERSION = "exact-survival-confirmation-contract-v4"
EXACT_SURVIVAL_CONFIRMATION_PROFILE_ID = "content-region-coverage-v1"
EXACT_SURVIVAL_CONFIRMATION_BUDGET = 16
EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT = "fa823ba724fd24ec8c595151f2cff383a3147615"
EXACT_SURVIVAL_FROZEN_SOURCE_BLOB_SHA = "5f2443663d05ac9cb7d0268a747c7616d7c9153c"
EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH = "fb808c4a14b801fff20a6856801a92c3aee1fa71a796a93c9b913ad3d9a1db08"
INHERITED_THRESHOLD_VALUE = 0.5570987654320988
INHERITED_THRESHOLD_FILE_SHA256 = "0b1b9e6ead71caf567e1b21bb3996098298aa207ae86db15c07584faaae09f37"
CONFIRMATION_SEED_BASES = (530000, 540000, 550000)


def _require_git_object_id(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    require_clean_string(name, value)
    if len(value) not in (40, 64) or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase Git object ID")
    return value


def _attack_samples(corpus: Any):
    return tuple(
        sorted(
            (sample for sample in corpus.manifest.samples if sample.split is CorpusSplit.ATTACK_DEVELOPMENT),
            key=lambda sample: sample.sample_id,
        )
    )


def validate_exact_survival_confirmation_contract(contract: Mapping[str, object]) -> str:
    if not isinstance(contract, Mapping):
        raise TypeError("confirmation contract must be a mapping")
    value = dict(contract)
    if value.get("algorithm_version") != EXACT_SURVIVAL_CONFIRMATION_CONTRACT_VERSION:
        raise ValueError("unsupported exact-survival confirmation contract version")
    candidate = value.get("candidate")
    if not isinstance(candidate, Mapping):
        raise TypeError("confirmation contract candidate must be a mapping")
    if candidate.get("profile_id") != EXACT_SURVIVAL_CONFIRMATION_PROFILE_ID:
        raise ValueError("confirmation contract profile id drifted")
    if candidate.get("budget") != EXACT_SURVIVAL_CONFIRMATION_BUDGET:
        raise ValueError("confirmation contract budget drifted")
    if candidate.get("scheduler_algorithm_version") != EXACT_SURVIVAL_GREEDY_ALGORITHM_VERSION:
        raise ValueError("confirmation contract scheduler algorithm drifted")
    if candidate.get("scheduler_policy_id") != EXACT_SURVIVAL_GREEDY_POLICY_ID:
        raise ValueError("confirmation contract scheduler policy drifted")
    if candidate.get("scheduler_source_commit") != EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT:
        raise ValueError("confirmation contract scheduler source commit drifted")
    if candidate.get("scheduler_source_blob_sha") != EXACT_SURVIVAL_FROZEN_SOURCE_BLOB_SHA:
        raise ValueError("confirmation contract scheduler source blob drifted")
    if candidate.get("promotion_artifact_hash") != EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH:
        raise ValueError("confirmation contract promotion artifact drifted")
    measurement = value.get("measurement")
    if not isinstance(measurement, Mapping):
        raise TypeError("confirmation contract measurement must be a mapping")
    if measurement.get("identity") != "open-detector-measurement-stability-v1":
        raise ValueError("confirmation contract measurement identity drifted")
    if measurement.get("threshold") != INHERITED_THRESHOLD_VALUE:
        raise ValueError("confirmation contract threshold drifted")
    if measurement.get("comparison") != ">=":
        raise ValueError("confirmation contract comparison drifted")
    if measurement.get("target_fpr") != 0.01:
        raise ValueError("confirmation contract target FPR drifted")
    if measurement.get("prior_fixed_threshold_file_sha256") != INHERITED_THRESHOLD_FILE_SHA256:
        raise ValueError("confirmation contract prior threshold file hash drifted")
    if measurement.get("prior_threshold_replay") is not True:
        raise ValueError("confirmation contract must preserve prior threshold replay attestation")
    if measurement.get("prior_audit_exceedances") != 0 or measurement.get("prior_audit_count") != 256:
        raise ValueError("confirmation contract prior audit binding drifted")
    confirmation = value.get("confirmation")
    if not isinstance(confirmation, Mapping):
        raise TypeError("confirmation contract confirmation block must be a mapping")
    seeds = confirmation.get("seed_bases")
    if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes, bytearray)):
        raise TypeError("confirmation seed_bases must be a sequence")
    if tuple(seeds) != CONFIRMATION_SEED_BASES:
        raise ValueError("confirmation seed ledger drifted")
    if confirmation.get("attack_pairs_per_domain") != 16:
        raise ValueError("confirmation attack-pair count drifted")
    if confirmation.get("freeze_before_score") is not True:
        raise ValueError("confirmation must freeze corpora and plans before scoring")
    claim = value.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise TypeError("confirmation contract claim_boundary must be a mapping")
    if claim.get("release_authorized") is not False or claim.get("watermark_removal_claim") is not False or claim.get("undetectability_claim") is not False:
        raise ValueError("confirmation contract claim boundary drifted")
    return sha256_json(value)


def build_exact_survival_effectiveness_plan(
    corpus: Any,
    tokenizer: Any,
    *,
    source_code_commit: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    _require_git_object_id("source_code_commit", source_code_commit)
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    profile = content_region_coverage_profile((EXACT_SURVIVAL_CONFIRMATION_BUDGET,))
    registry = content_region_coverage_transform_registry()
    validate_effectiveness_profile_registry(profile, registry)
    sources = _attack_samples(corpus)
    if not sources:
        raise ValueError("exact-survival effectiveness planning requires attack-development samples")
    variants: list[dict[str, object]] = []
    for source_index, source in enumerate(sources):
        enumeration = registry.enumerate(source.text)
        result = schedule_exact_survival_greedy(
            source_sample_id=source.sample_id,
            source_text=source.text,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=profile.ngram_len,
            budget=EXACT_SURVIVAL_CONFIRMATION_BUDGET,
        )
        transformed = registry.apply(enumeration, result.selected_candidate_ids)
        if sha256_text(transformed.output_text) != result.transformed_text_hash:
            raise ValueError("exact-survival result transformed text hash does not replay")
        if transformed.trace.trace_hash != result.transform_trace_hash:
            raise ValueError("exact-survival result trace hash does not replay")
        if transformed.trace.invariant_report.status is not InvariantStatus.PASS:
            raise ValueError("exact-survival effectiveness plan accepted a hard-invariant violation")
        row = {
            "source_sample_id": source.sample_id,
            "source_index": source_index,
            "source_label": source.label.value,
            "prompt_family_id": source.prompt_family_id,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "candidate_count": len(enumeration.candidates),
            "enumeration_hash": enumeration.enumeration_hash,
            "requested_budget": EXACT_SURVIVAL_CONFIRMATION_BUDGET,
            "budget_unit": "operation",
            "scheduler_algorithm_version": result.algorithm_version,
            "scheduler_policy_id": EXACT_SURVIVAL_GREEDY_POLICY_ID,
            "exact_result_hash": result.result_hash,
            "selection_order": result.selection_order,
            "selected_candidate_ids": result.selected_candidate_ids,
            "realized_edit_cost": result.selected_candidate_count,
            "policy_saturated": result.policy_saturated,
            "root_observation_count": result.root_observation_count,
            "exact_destroyed_observation_count": result.exact_destroyed_observation_count,
            "exact_surviving_observation_count": result.exact_surviving_observation_count,
            "transformed_text": transformed.output_text,
            "transformed_text_hash": result.transformed_text_hash,
            "transform_trace_hash": result.transform_trace_hash,
            "hard_invariant_status": transformed.trace.invariant_report.status.value,
            "detector_access_observed": False,
            "secret_access_observed": False,
        }
        variants.append({**row, "variant_hash": sha256_json(row)})
    payload = {
        "algorithm_version": EXACT_SURVIVAL_EFFECTIVENESS_PLAN_VERSION,
        "scientific_scope": "Frozen exact-retokenization structural selection for fresh fixed-open-detector confirmation; no release or watermark-removal claim",
        "source_code_commit": source_code_commit,
        "contract_hash": contract_hash,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "tokenizer_identity_hash": corpus.model_identity_hash,
        "profile_id": profile.profile_id,
        "profile_hash": profile.profile_hash,
        "ruleset_hash": registry.ruleset_hash,
        "ngram_len": profile.ngram_len,
        "requested_budget": EXACT_SURVIVAL_CONFIRMATION_BUDGET,
        "budget_unit": "operation",
        "scheduler_algorithm_version": EXACT_SURVIVAL_GREEDY_ALGORITHM_VERSION,
        "scheduler_policy_id": EXACT_SURVIVAL_GREEDY_POLICY_ID,
        "scheduler_source_commit": EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT,
        "scheduler_source_blob_sha": EXACT_SURVIVAL_FROZEN_SOURCE_BLOB_SHA,
        "promotion_artifact_hash": EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "variants": tuple(variants),
    }
    return {**payload, "plan_hash": sha256_json(payload)}


def validate_exact_survival_effectiveness_plan(
    plan: Mapping[str, object],
    corpus: Any,
    *,
    contract: Mapping[str, object],
) -> None:
    if not isinstance(plan, Mapping):
        raise TypeError("exact-survival plan must be a mapping")
    value = dict(plan)
    if value.get("algorithm_version") != EXACT_SURVIVAL_EFFECTIVENESS_PLAN_VERSION:
        raise ValueError("unsupported exact-survival effectiveness plan version")
    _require_git_object_id("source_code_commit", value.get("source_code_commit"))
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    if value.get("contract_hash") != contract_hash:
        raise ValueError("exact-survival plan contract binding does not match")
    profile = content_region_coverage_profile((EXACT_SURVIVAL_CONFIRMATION_BUDGET,))
    registry = content_region_coverage_transform_registry()
    validate_effectiveness_profile_registry(profile, registry)
    expected_top = {
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "tokenizer_identity_hash": corpus.model_identity_hash,
        "profile_id": profile.profile_id,
        "profile_hash": profile.profile_hash,
        "ruleset_hash": registry.ruleset_hash,
        "ngram_len": profile.ngram_len,
        "requested_budget": EXACT_SURVIVAL_CONFIRMATION_BUDGET,
        "budget_unit": "operation",
        "scheduler_algorithm_version": EXACT_SURVIVAL_GREEDY_ALGORITHM_VERSION,
        "scheduler_policy_id": EXACT_SURVIVAL_GREEDY_POLICY_ID,
        "scheduler_source_commit": EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT,
        "scheduler_source_blob_sha": EXACT_SURVIVAL_FROZEN_SOURCE_BLOB_SHA,
        "promotion_artifact_hash": EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH,
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    for key, expected in expected_top.items():
        if value.get(key) != expected:
            raise ValueError(f"exact-survival plan {key} binding does not match")
    variants = value.get("variants")
    if not isinstance(variants, Sequence) or isinstance(variants, (str, bytes, bytearray)):
        raise TypeError("exact-survival plan variants must be a sequence")
    sources = _attack_samples(corpus)
    if len(variants) != len(sources):
        raise ValueError("exact-survival plan variant count does not match attack corpus")
    by_source = {source.sample_id: source for source in sources}
    seen: set[str] = set()
    for raw in variants:
        if not isinstance(raw, Mapping):
            raise TypeError("exact-survival plan variant must be a mapping")
        entry = dict(raw)
        source_id = entry.get("source_sample_id")
        if not isinstance(source_id, str) or source_id not in by_source or source_id in seen:
            raise ValueError("exact-survival plan contains an unknown or duplicate source")
        seen.add(source_id)
        source = by_source[source_id]
        if entry.get("source_text_hash") != source.text_sha256:
            raise ValueError("exact-survival plan source text binding does not match")
        enumeration = registry.enumerate(source.text)
        if entry.get("enumeration_hash") != enumeration.enumeration_hash:
            raise ValueError("exact-survival plan enumeration does not replay")
        if entry.get("candidate_count") != len(enumeration.candidates):
            raise ValueError("exact-survival plan candidate count does not replay")
        selected = entry.get("selected_candidate_ids")
        if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes, bytearray)):
            raise TypeError("selected_candidate_ids must be a sequence")
        selected_ids = tuple(selected)
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("selected_candidate_ids must be unique")
        if entry.get("realized_edit_cost") != len(selected_ids) or len(selected_ids) > EXACT_SURVIVAL_CONFIRMATION_BUDGET:
            raise ValueError("exact-survival plan realized edit cost is invalid")
        for candidate_id in selected_ids:
            require_sha256("selected_candidate_id", candidate_id)
        if not set(selected_ids) <= {candidate.candidate_id for candidate in enumeration.candidates}:
            raise ValueError("exact-survival plan selected an unknown candidate")
        transformed = registry.apply(enumeration, selected_ids)
        if entry.get("transformed_text") != transformed.output_text:
            raise ValueError("exact-survival plan transformed text does not replay")
        if entry.get("transformed_text_hash") != sha256_text(transformed.output_text):
            raise ValueError("exact-survival plan transformed text hash does not replay")
        if entry.get("transform_trace_hash") != transformed.trace.trace_hash:
            raise ValueError("exact-survival plan trace hash does not replay")
        if entry.get("hard_invariant_status") != InvariantStatus.PASS.value:
            raise ValueError("exact-survival plan hard invariant status is not PASS")
        if entry.get("detector_access_observed") is not False or entry.get("secret_access_observed") is not False:
            raise ValueError("exact-survival plan variant must remain detector-blind and key-blind")
        root_count = entry.get("root_observation_count")
        destroyed = entry.get("exact_destroyed_observation_count")
        surviving = entry.get("exact_surviving_observation_count")
        require_int("root_observation_count", root_count)
        require_int("exact_destroyed_observation_count", destroyed)
        require_int("exact_surviving_observation_count", surviving)
        if destroyed < 0 or surviving < 0 or destroyed + surviving != root_count:
            raise ValueError("exact-survival plan exact observation counts are invalid")
        require_sha256("exact_result_hash", entry.get("exact_result_hash"))
        variant_hash = entry.get("variant_hash")
        require_sha256("variant_hash", variant_hash)
        row_payload = {key: item for key, item in entry.items() if key != "variant_hash"}
        if variant_hash != sha256_json(row_payload):
            raise ValueError("exact-survival plan variant hash does not replay")
    if seen != set(by_source):
        raise ValueError("exact-survival plan does not cover every attack source exactly once")
    plan_hash = value.get("plan_hash")
    require_sha256("plan_hash", plan_hash)
    payload = {key: item for key, item in value.items() if key != "plan_hash"}
    if plan_hash != sha256_json(payload):
        raise ValueError("exact-survival plan hash does not replay")
