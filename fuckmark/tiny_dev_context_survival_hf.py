from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .alignment import align_tokens
from .corpus import WatermarkLabel, load_tiny_dev_corpus_json
from .detectors import DetectorFamily, weighted_mean_evidence
from .experiments.context_survival_plan import (
    BEAM_B4_POLICY,
    BEAM_B6_POLICY,
    COVERAGE_POLICY,
    EVEN_SPACING_POLICY,
    EXACT_B1_POLICY,
    EXACT_B2_POLICY,
    GREEDY_POLICY,
    STATEFUL_RANDOM_POLICY,
    SUCCESS,
)
from .hashing import sha256_json
from .native_observations import build_native_observations
from .observations import structural_observation_diff, summarize_structural_observations
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .tiny_dev_detector_hf import default_watermark_config_hash, default_watermark_payload
from .tiny_dev_transform_hf import (
    PRIMARY_TARGET_FPR,
    _attack_samples,
    _encode_text,
    _text_only_calibration,
    _text_only_weighted_evidence,
    _threshold,
    _word_edit_distance,
    _word_units,
    _write_fsynced,
)


TINY_DEV_CONTEXT_SURVIVAL_EVIDENCE_VERSION = "tiny-dev-context-survival-evidence-v1"
TINY_DEV_CONTEXT_SURVIVAL_PROVENANCE_VERSION = "tiny-dev-context-survival-provenance-v2"
PAIR_STATUS_MATCHED = "MATCHED"
PAIR_STATUS_UNMATCHED_COST = "UNMATCHED_COST"
ECS1_STATUS = "WITHHELD_TINYDEV_ENGINEERING_ONLY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _mean(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _validate_plan(plan: dict[str, object], corpus: Any) -> None:
    if plan.get("tiny_dev_artifact_hash") != corpus.artifact_hash:
        raise ValueError("context-survival plan does not bind the supplied TinyDev corpus")
    if plan.get("tokenizer_identity_hash") != corpus.model_identity_hash:
        raise ValueError("context-survival plan tokenizer identity does not match TinyDev corpus")
    if plan.get("detector_access_observed") is not False:
        raise ValueError("context-survival plan reports detector access")
    if plan.get("secret_access_observed") is not False:
        raise ValueError("context-survival plan reports secret access")
    expected = sha256_json({key: value for key, value in plan.items() if key != "plan_hash"})
    if plan.get("plan_hash") != expected:
        raise ValueError("context-survival plan hash does not replay")
    for entry in plan["variants"]:
        expected_variant = sha256_json({key: value for key, value in entry.items() if key != "variant_hash"})
        if entry.get("variant_hash") != expected_variant:
            raise ValueError("context-survival variant hash does not replay")


def _score_transformed_text(
    *,
    source: Any,
    transformed_text: str,
    transformed_text_hash: str,
    tokenizer: Any,
    adapter: HuggingFaceSynthIDAdapter,
) -> tuple[Any, tuple[int, ...], Any, int, int, int, int]:
    transformed_tokens = _encode_text(tokenizer, transformed_text)
    eos = source.model.eos_token_id
    if eos is None:
        raise ValueError("TinyDev tokenizer must define eos_token_id")
    batch = build_native_observations(
        f"{source.sample_id}-context-survival-{transformed_text_hash[:12]}",
        transformed_tokens,
        eos,
        adapter,
    )
    evidence = weighted_mean_evidence(batch)
    source_tokens = source.text_only_tokens.token_ids if source.text_only_tokens is not None else ()
    alignment = align_tokens(source_tokens, transformed_tokens)
    diffs = structural_observation_diff(source_tokens, transformed_tokens, adapter.ngram_len, alignment)
    summary = summarize_structural_observations(source_tokens, transformed_tokens, adapter.ngram_len, diffs)
    word_edits = _word_edit_distance(source.text, transformed_text)
    return (
        evidence,
        transformed_tokens,
        alignment,
        summary.preserved_count,
        summary.replaced_count,
        summary.unmapped_count,
        word_edits,
    )


def _policy_summaries(rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    keys = tuple(sorted({(row["source_label"], row["schedule_policy"]) for row in rows}))
    output: list[dict[str, object]] = []
    for label, policy in keys:
        selected = tuple(row for row in rows if row["source_label"] == label and row["schedule_policy"] == policy)
        scored = tuple(row for row in selected if row["realized_edit_cost"] > 0)
        successful = tuple(row for row in scored if row["status"] == SUCCESS)
        payload = {
            "source_label": label,
            "schedule_policy": policy,
            "row_count": len(selected),
            "positive_cost_count": len(scored),
            "success_count": len(successful),
            "independent_source_count": len({row["source_sample_id"] for row in selected}),
            "mean_exact_destruction_ratio": _mean(
                tuple(float(row["exact_destruction_ratio"]) for row in successful)
            ),
            "mean_margin_drop": _mean(tuple(float(row["margin_drop"]) for row in successful)),
            "mean_newly_masked_count": _mean(tuple(float(row["newly_masked_count"]) for row in successful)),
            "transformed_detected_count": sum(bool(row["transformed_detected"]) for row in successful),
        }
        output.append({**payload, "summary_hash": sha256_json(payload)})
    return tuple(output)


def _paired_random_comparisons(rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    deterministic = {
        COVERAGE_POLICY,
        EVEN_SPACING_POLICY,
        GREEDY_POLICY,
        EXACT_B1_POLICY,
        EXACT_B2_POLICY,
        BEAM_B4_POLICY,
        BEAM_B6_POLICY,
    }
    output: list[dict[str, object]] = []
    for row in rows:
        if row["source_label"] != WatermarkLabel.WATERMARKED.value:
            continue
        if row["schedule_policy"] not in deterministic:
            continue
        if row["status"] != SUCCESS or row["realized_edit_cost"] <= 0:
            continue
        random_rows = tuple(
            value
            for value in rows
            if value["source_label"] == WatermarkLabel.WATERMARKED.value
            and value["source_sample_id"] == row["source_sample_id"]
            and value["schedule_policy"] == STATEFUL_RANDOM_POLICY
            and value["budget"] == row["budget"]
            and value["realized_edit_cost"] == row["realized_edit_cost"]
            and value["status"] == SUCCESS
        )
        if not random_rows:
            payload = {
                "source_sample_id": row["source_sample_id"],
                "schedule_policy": row["schedule_policy"],
                "budget": row["budget"],
                "realized_edit_cost": row["realized_edit_cost"],
                "status": PAIR_STATUS_UNMATCHED_COST,
                "matched_random_count": 0,
                "delta_survival": None,
                "delta_margin": None,
                "delta_destruction_per_edit": None,
            }
        else:
            random_survival = sum(float(value["exact_survival_ratio"]) for value in random_rows) / len(random_rows)
            random_margin = sum(float(value["margin_drop"]) for value in random_rows) / len(random_rows)
            random_efficiency = sum(
                float(value["destroyed_root_observation_count"]) / int(value["realized_edit_cost"])
                for value in random_rows
            ) / len(random_rows)
            deterministic_efficiency = (
                float(row["destroyed_root_observation_count"]) / int(row["realized_edit_cost"])
            )
            payload = {
                "source_sample_id": row["source_sample_id"],
                "schedule_policy": row["schedule_policy"],
                "budget": row["budget"],
                "realized_edit_cost": row["realized_edit_cost"],
                "status": PAIR_STATUS_MATCHED,
                "matched_random_count": len(random_rows),
                "delta_survival": random_survival - float(row["exact_survival_ratio"]),
                "delta_margin": float(row["margin_drop"]) - random_margin,
                "delta_destruction_per_edit": deterministic_efficiency - random_efficiency,
            }
        output.append({**payload, "pair_hash": sha256_json(payload)})
    return tuple(output)


def _interaction_headroom(rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    targets = {
        2: EXACT_B2_POLICY,
        4: BEAM_B4_POLICY,
        6: BEAM_B6_POLICY,
    }
    output: list[dict[str, object]] = []
    for budget, target_policy in targets.items():
        target_rows = tuple(
            row
            for row in rows
            if row["source_label"] == WatermarkLabel.WATERMARKED.value
            and row["schedule_policy"] == target_policy
            and row["budget"] == budget
            and row["status"] == SUCCESS
        )
        for target in target_rows:
            greedy = next(
                (
                    row
                    for row in rows
                    if row["source_sample_id"] == target["source_sample_id"]
                    and row["source_label"] == WatermarkLabel.WATERMARKED.value
                    and row["schedule_policy"] == GREEDY_POLICY
                    and row["budget"] == budget
                    and row["status"] == SUCCESS
                    and row["realized_edit_cost"] == target["realized_edit_cost"]
                ),
                None,
            )
            if greedy is None:
                continue
            payload = {
                "source_sample_id": target["source_sample_id"],
                "budget": budget,
                "target_policy": target_policy,
                "realized_edit_cost": target["realized_edit_cost"],
                "extra_destroyed_root_observations": (
                    int(target["destroyed_root_observation_count"])
                    - int(greedy["destroyed_root_observation_count"])
                ),
                "extra_margin_drop": float(target["margin_drop"]) - float(greedy["margin_drop"]),
            }
            output.append({**payload, "headroom_hash": sha256_json(payload)})
    return tuple(output)


def score_context_survival_plan(
    corpus: Any,
    tokenizer: Any,
    plan: dict[str, object],
    adapter: HuggingFaceSynthIDAdapter,
) -> dict[str, object]:
    _validate_plan(plan, corpus)
    calibration = _text_only_calibration(corpus, adapter)
    threshold = _threshold(calibration, PRIMARY_TARGET_FPR)
    if calibration.detector_identity.detector_family is not DetectorFamily.WEIGHTED_MEAN:
        raise ValueError("TinyDev context-survival pilot requires Weighted Mean calibration")
    attack_by_id = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    pristine = {
        sample_id: _text_only_weighted_evidence(sample, adapter)
        for sample_id, sample in attack_by_id.items()
    }
    cache: dict[tuple[str, str], tuple[Any, tuple[int, ...], Any, int, int, int, int]] = {}
    rows: list[dict[str, object]] = []

    for entry in plan["variants"]:
        source = attack_by_id[entry["source_sample_id"]]
        key = (source.sample_id, entry["transformed_text_hash"])
        scored = cache.get(key)
        if scored is None:
            scored = _score_transformed_text(
                source=source,
                transformed_text=entry["transformed_text"],
                transformed_text_hash=entry["transformed_text_hash"],
                tokenizer=tokenizer,
                adapter=adapter,
            )
            cache[key] = scored
        transformed_evidence, transformed_tokens, alignment, preserved, replaced, unmapped, word_edits = scored
        original_evidence = pristine[source.sample_id]
        old_damage = replaced + unmapped
        original_count = preserved + replaced + unmapped
        word_count = len(_word_units(source.text))
        if word_count <= 0:
            raise ValueError("TinyDev context-survival source has no word units")
        payload = {
            "source_sample_id": source.sample_id,
            "source_label": source.label.value,
            "prompt_family_id": source.prompt_family_id,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "variant_hash": entry["variant_hash"],
            "schedule_policy": entry["schedule_policy"],
            "schedule_seed": entry["schedule_seed"],
            "budget": entry["budget"],
            "realized_edit_cost": entry["realized_edit_cost"],
            "status": entry["status"],
            "transformed_text_hash": entry["transformed_text_hash"],
            "candidate_pool_hash": entry["candidate_pool_hash"],
            "scheduler_input_hash": entry["scheduler_input_hash"],
            "schedule_result_hash": entry["schedule_result_hash"],
            "search_state_hash": entry["search_state_hash"],
            "survival_report_hash": entry["survival_report_hash"],
            "root_eligible_observation_count": entry["root_eligible_observation_count"],
            "surviving_root_observation_count": entry["surviving_root_observation_count"],
            "destroyed_root_observation_count": entry["destroyed_root_observation_count"],
            "exact_survival_ratio": entry["exact_survival_ratio"],
            "exact_destruction_ratio": entry["exact_destruction_ratio"],
            "newly_masked_count": entry["newly_masked_count"],
            "source_token_count": len(source.text_only_tokens.token_ids) if source.text_only_tokens is not None else 0,
            "transformed_token_count": len(transformed_tokens),
            "alignment_distance": alignment.distance,
            "alignment_ambiguous_ties": alignment.ambiguous_ties,
            "old_preserved_observation_count": preserved,
            "old_replaced_observation_count": replaced,
            "old_unmapped_observation_count": unmapped,
            "old_observation_damage_count": old_damage,
            "old_observation_damage_ratio": 0.0 if original_count == 0 else old_damage / original_count,
            "word_edit_count": word_edits,
            "word_count": word_count,
            "word_edit_rate": word_edits / word_count,
            "pristine_score": original_evidence.raw_score,
            "transformed_score": transformed_evidence.raw_score,
            "margin_drop": original_evidence.raw_score - transformed_evidence.raw_score,
            "pristine_detected": original_evidence.raw_score >= threshold.value,
            "transformed_detected": transformed_evidence.raw_score >= threshold.value,
            "hard_invariant_status": entry["hard_invariant_status"],
        }
        rows.append({**payload, "row_hash": sha256_json(payload)})

    row_tuple = tuple(rows)
    positive_ids = tuple(
        sorted(
            sample.sample_id
            for sample in attack_by_id.values()
            if sample.label is WatermarkLabel.WATERMARKED
        )
    )
    negative_ids = tuple(
        sorted(
            sample.sample_id
            for sample in attack_by_id.values()
            if sample.label is WatermarkLabel.UNWATERMARKED
        )
    )
    policy_summaries = _policy_summaries(row_tuple)
    pairs = _paired_random_comparisons(row_tuple)
    headroom = _interaction_headroom(row_tuple)
    matched_pairs = tuple(value for value in pairs if value["status"] == PAIR_STATUS_MATCHED)
    control_success = tuple(
        row
        for row in row_tuple
        if row["source_label"] == WatermarkLabel.UNWATERMARKED.value
        and row["status"] == SUCCESS
        and row["realized_edit_cost"] > 0
    )
    payload = {
        "algorithm_version": TINY_DEV_CONTEXT_SURVIVAL_EVIDENCE_VERSION,
        "scientific_scope": "DEV_KEYS TinyDev context-survival mechanism pilot; descriptive engineering evidence only",
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "source_code_commit": plan["source_code_commit"],
        "plan_hash": plan["plan_hash"],
        "watermark_config_hash": default_watermark_config_hash(),
        "adapter_id": adapter.adapter_id,
        "adapter_config_hash": adapter.configuration_fingerprint(),
        "sampling_table_hash": adapter.sampling_table_hash,
        "detector_family": DetectorFamily.WEIGHTED_MEAN.value,
        "calibration_bundle_hash": calibration.bundle_hash,
        "calibration_negative_count": calibration.negative_count,
        "primary_target_fpr": PRIMARY_TARGET_FPR,
        "primary_threshold_hash": threshold.threshold_hash,
        "primary_threshold_value": threshold.value,
        "achieved_calibration_fpr": threshold.achieved_fpr,
        "calibration_fpr_interval": threshold.fpr_interval,
        "independent_watermarked_source_count": len(positive_ids),
        "independent_control_source_count": len(negative_ids),
        "pristine_positive_detected_count": sum(
            pristine[sample_id].raw_score >= threshold.value for sample_id in positive_ids
        ),
        "pristine_positive_count": len(positive_ids),
        "pristine_negative_detected_count": sum(
            pristine[sample_id].raw_score >= threshold.value for sample_id in negative_ids
        ),
        "pristine_negative_count": len(negative_ids),
        "rows": row_tuple,
        "policy_summaries": policy_summaries,
        "random_matched_comparisons": pairs,
        "matched_comparison_count": len(matched_pairs),
        "interaction_headroom": headroom,
        "e_cs1": {
            "status": ECS1_STATUS,
            "independent_watermarked_source_count": len(positive_ids),
            "reason": "Grouped source holdout is deferred to MidDev; TinyDev retains raw predictor fields without inferential fitting",
        },
        "control_success_count": len(control_success),
        "control_mean_margin_drop": _mean(tuple(float(row["margin_drop"]) for row in control_success)),
        "control_false_to_true_count": sum(
            (not bool(row["pristine_detected"])) and bool(row["transformed_detected"])
            for row in control_success
        ),
        "detector_access_during_selection_observed": plan["detector_access_observed"],
        "secret_access_during_selection_observed": plan["secret_access_observed"],
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _validate_plan_provenance(
    plan_provenance: dict[str, object],
    plan: dict[str, object],
) -> None:
    expected = sha256_json(
        {key: value for key, value in plan_provenance.items() if key != "provenance_hash"}
    )
    if plan_provenance.get("provenance_hash") != expected:
        raise ValueError("plan provenance hash does not replay")
    if plan_provenance.get("plan_hash") != plan.get("plan_hash"):
        raise ValueError("plan provenance does not bind the frozen plan")
    if plan_provenance.get("source_code_commit") != plan.get("source_code_commit"):
        raise ValueError("plan provenance source commit does not match the frozen plan")
    if plan_provenance.get("plan_fsync_success") is not True:
        raise ValueError("plan provenance does not record successful fsync")


def _final_provenance(
    *,
    plan: dict[str, object],
    plan_provenance: dict[str, object],
    evidence_hash: str,
    scoring_process_started_at: str,
    scoring_finished_at: str,
) -> dict[str, object]:
    source_code_commit = str(plan["source_code_commit"])
    github_sha = os.environ.get("GITHUB_SHA")
    payload = {
        "algorithm_version": TINY_DEV_CONTEXT_SURVIVAL_PROVENANCE_VERSION,
        "source_code_commit": source_code_commit,
        "plan_hash": plan["plan_hash"],
        "plan_provenance_hash": plan_provenance["provenance_hash"],
        "evidence_hash": evidence_hash,
        "plan_started_at_utc": plan_provenance["plan_started_at_utc"],
        "plan_fsynced_at_utc": plan_provenance["plan_fsynced_at_utc"],
        "plan_fsync_success": plan_provenance["plan_fsync_success"],
        "scoring_process_started_at_utc": scoring_process_started_at,
        "scoring_finished_at_utc": scoring_finished_at,
        "separate_scoring_process": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": github_sha,
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_base_ref": os.environ.get("GITHUB_BASE_REF"),
        "synthetic_pr_merge_checkout": bool(
            os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
            and github_sha
            and source_code_commit != "UNKNOWN"
            and github_sha != source_code_commit
        ),
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-context-survival-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--plan-provenance-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-context-survival-evidence.json"),
    )
    parser.add_argument(
        "--provenance-json",
        type=Path,
        default=Path("artifacts/tiny-dev-context-survival-provenance.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scoring_process_started_at = _now()
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    plan = _load_json(args.plan_json)
    plan_provenance = _load_json(args.plan_provenance_json)
    _validate_plan(plan, corpus)
    _validate_plan_provenance(plan_provenance, plan)

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("TinyDev context-survival scoring requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen TinyDev corpus")

    watermark_payload = default_watermark_payload()
    if int(plan["ngram_len"]) != int(watermark_payload["ngram_len"]):
        raise RuntimeError("frozen plan ngram_len does not match scoring watermark configuration")
    if int(plan["context_history_size"]) != int(watermark_payload["context_history_size"]):
        raise RuntimeError("frozen plan context history does not match scoring watermark configuration")

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
    evidence = score_context_survival_plan(corpus, tokenizer, plan, adapter)
    _write_fsynced(args.json, evidence)
    scoring_finished_at = _now()
    provenance = _final_provenance(
        plan=plan,
        plan_provenance=plan_provenance,
        evidence_hash=evidence["artifact_hash"],
        scoring_process_started_at=scoring_process_started_at,
        scoring_finished_at=scoring_finished_at,
    )
    _write_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    sys.stdout.write(
        f"independent_watermarked_sources={evidence['independent_watermarked_source_count']}\n"
    )
    sys.stdout.write(f"matched_comparisons={evidence['matched_comparison_count']}\n")
    for summary in evidence["policy_summaries"]:
        sys.stdout.write(
            f"label={summary['source_label']} policy={summary['schedule_policy']} "
            f"success={summary['success_count']}/{summary['row_count']} "
            f"mean_exact_destruction={summary['mean_exact_destruction_ratio']} "
            f"mean_margin_drop={summary['mean_margin_drop']}\n"
        )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"provenance_json={args.provenance_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())