from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .alignment import align_tokens
from .config import canonical_json_text
from .corpus import CorpusSample, CorpusSplit, WatermarkLabel, load_tiny_dev_corpus_json
from .detectors import (
    CalibrationScope,
    ComparisonOperator,
    DetectorFamily,
    calibrate_detector,
    weighted_mean_evidence,
)
from .experiments import (
    DevelopmentTransformRow,
    run_e07_predictor_comparison,
    run_e08_dose_response,
    run_e09_random_baseline,
    run_e10_spacing_comparison,
    run_e11_greedy_comparison,
)
from .hashing import sha256_json, sha256_text
from .native_observations import build_native_observations
from .observations import structural_observation_diff, summarize_structural_observations
from .tiny_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_detector_hf import default_watermark_config_hash, default_watermark_payload
from .transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    build_candidate_tokenizer_geometry,
    development_transform_registry,
)


TINY_DEV_TRANSFORM_PILOT_VERSION = "real-tiny-dev-transform-pilot-v1"
TINY_DEV_TRANSFORM_PLAN_VERSION = "real-tiny-dev-transform-plan-v1"
TEXT_ONLY_CALIBRATION_POPULATION_ID = "tiny-dev-threshold-calibration-unwatermarked-text-only-v1"
TEXT_ONLY_LENGTH_POLICY_ID = "target-64-text-only-unpadded-v1"
TEXT_ONLY_TOKEN_TRACK = "text_only"
TEXT_ONLY_PROMPT_BOUNDARY_MODE = "continuation_only"
OBSERVATION_DAMAGE_POLICY_ID = "original-nonpreserved-replaced-plus-unmapped-v1"
PRIMARY_TARGET_FPR = 0.01
DEFAULT_BUDGETS = (1, 2, 4)
DEFAULT_RANDOM_SEED_COUNT = 8
DEFAULT_SCHEDULE_SEED_BASE = 61000
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z0-9]+)?")


class TinyDevTransformPilotError(ValueError):
    pass


def _word_units(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return tuple(match.group(0) for match in _WORD_RE.finditer(text))


def _word_edit_distance(original: str, transformed: str) -> int:
    left = _word_units(original)
    right = _word_units(transformed)
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for row, source in enumerate(left, start=1):
        current = [row]
        for column, target in enumerate(right, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (source != target),
                )
            )
        previous = current
    return previous[-1]


def _attack_samples(corpus) -> tuple[CorpusSample, ...]:
    return tuple(
        sorted(
            (
                sample
                for sample in corpus.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
            ),
            key=lambda value: value.sample_id,
        )
    )


def _calibration_negatives(corpus) -> tuple[CorpusSample, ...]:
    values = tuple(
        sorted(
            (
                sample
                for sample in corpus.manifest.samples
                if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
                and sample.label is WatermarkLabel.UNWATERMARKED
            ),
            key=lambda value: value.sample_id,
        )
    )
    if len(values) != 100:
        raise TinyDevTransformPilotError("TinyDev text-only calibration requires exactly 100 negative samples")
    return values


def _encode_text(tokenizer, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        if len(ids) != 1:
            raise TinyDevTransformPilotError("unexpected batched tokenizer output")
        ids = ids[0]
    output = tuple(int(value) for value in ids)
    if not output:
        raise TinyDevTransformPilotError("tokenizer produced an empty transformed token sequence")
    return output


def _encode_with_offsets(tokenizer, sample: CorpusSample) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    if sample.text_only_tokens is None:
        raise TinyDevTransformPilotError(f"sample {sample.sample_id} has no text-only token track")
    encoded = tokenizer(sample.text, add_special_tokens=False, return_offsets_mapping=True)
    ids = tuple(int(value) for value in encoded["input_ids"])
    offsets = tuple((int(start), int(end)) for start, end in encoded["offset_mapping"])
    if ids != sample.text_only_tokens.token_ids:
        raise TinyDevTransformPilotError(
            f"public tokenizer replay does not match recorded text-only track for {sample.sample_id}"
        )
    return ids, offsets


def _schedule_seed(source_index: int, budget_index: int, replicate: int) -> int:
    if source_index < 0 or budget_index < 0 or replicate < 0:
        raise ValueError("schedule seed coordinates must be non-negative")
    return DEFAULT_SCHEDULE_SEED_BASE + source_index * 1000 + budget_index * 100 + replicate


def _plan_variant(
    *,
    registry,
    scheduler: CandidateScheduler,
    enumeration,
    scheduler_input: KeyBlindScheduleInput,
    candidate_pool_hash: str,
    source: CorpusSample,
    policy: SchedulePolicy,
    budget: int,
    seed: int,
) -> dict[str, object]:
    schedule = scheduler.schedule(scheduler_input, policy, budget, seed)
    result = registry.apply(enumeration, schedule.selected_candidate_ids, seed=seed)
    return {
        "source_sample_id": source.sample_id,
        "source_label": source.label.value,
        "prompt_family_id": source.prompt_family_id,
        "domain": source.domain.value,
        "source_text_hash": source.text_sha256,
        "candidate_pool_hash": candidate_pool_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "scheduler_input_hash": scheduler_input.input_artifact_hash,
        "schedule_policy": policy.value,
        "schedule_seed": seed,
        "budget": budget,
        "budget_unit": schedule.budget_unit,
        "schedule_result_hash": schedule.result_hash,
        "selected_candidate_ids": schedule.selected_candidate_ids,
        "realized_edit_cost": schedule.total_cost,
        "scheduler_covered_interval_size": schedule.covered_interval_size,
        "transformed_text": result.output_text,
        "transformed_text_hash": sha256_text(result.output_text),
        "transform_trace_hash": result.trace.trace_hash,
        "hard_invariant_status": result.trace.invariant_report.status.value,
    }


def build_transform_plan(corpus, tokenizer, *, budgets: Sequence[int], random_seed_count: int) -> dict[str, object]:
    if isinstance(random_seed_count, bool) or not isinstance(random_seed_count, int) or random_seed_count <= 0:
        raise ValueError("random_seed_count must be a positive integer")
    budget_tuple = tuple(int(value) for value in budgets)
    if not budget_tuple or any(value <= 0 for value in budget_tuple) or len(set(budget_tuple)) != len(budget_tuple):
        raise ValueError("budgets must be unique positive integers")
    registry = development_transform_registry()
    scheduler = CandidateScheduler()
    sources = _attack_samples(corpus)
    if len(sources) != 8:
        raise TinyDevTransformPilotError("TinyDev transform plan requires all eight attack-development samples")
    entries: list[dict[str, object]] = []
    source_diagnostics: list[dict[str, object]] = []
    for source_index, source in enumerate(sources):
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        enumeration = registry.enumerate(source.text)
        geometry = build_candidate_tokenizer_geometry(
            source.text,
            enumeration,
            token_ids,
            offsets,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=5,
        )
        scheduler_input = KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=geometry.coverage_mapping(),
            budget_unit="operation",
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
                "candidate_count": len(enumeration.candidates),
                "enumeration_hash": enumeration.enumeration_hash,
                "geometry_hash": geometry.geometry_hash,
                "scheduler_input_hash": scheduler_input.input_artifact_hash,
                "candidate_pool_hash": candidate_pool_hash,
                "text_only_generation_roundtrip_exact": (
                    source.text_only_tokens is not None
                    and source.text_only_tokens.token_ids == source.generation_tokens.continuation_token_ids
                ),
            }
        )
        if source.label is WatermarkLabel.WATERMARKED and not enumeration.candidates:
            raise TinyDevTransformPilotError(
                f"watermarked attack source {source.sample_id} has no transform candidates"
            )
        for budget_index, budget in enumerate(budget_tuple):
            for replicate in range(random_seed_count):
                seed = _schedule_seed(source_index, budget_index, replicate)
                for policy in (SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND):
                    entries.append(
                        _plan_variant(
                            registry=registry,
                            scheduler=scheduler,
                            enumeration=enumeration,
                            scheduler_input=scheduler_input,
                            candidate_pool_hash=candidate_pool_hash,
                            source=source,
                            policy=policy,
                            budget=budget,
                            seed=seed,
                        )
                    )
            spacing_seed = _schedule_seed(source_index, budget_index, random_seed_count)
            for policy in (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING):
                entries.append(
                    _plan_variant(
                        registry=registry,
                        scheduler=scheduler,
                        enumeration=enumeration,
                        scheduler_input=scheduler_input,
                        candidate_pool_hash=candidate_pool_hash,
                        source=source,
                        policy=policy,
                        budget=budget,
                        seed=spacing_seed,
                    )
                )
    payload = {
        "algorithm_version": TINY_DEV_TRANSFORM_PLAN_VERSION,
        "scientific_scope": "DEV_KEYS TinyDev key-blind transform selection plan; detector-free selection artifact",
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "tokenizer_identity_hash": corpus.model_identity_hash,
        "ruleset_hash": registry.ruleset_hash,
        "geometry_mode": ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC.value,
        "budget_unit": "operation",
        "budgets": budget_tuple,
        "random_seed_count": random_seed_count,
        "schedule_seed_base": DEFAULT_SCHEDULE_SEED_BASE,
        "source_diagnostics": tuple(source_diagnostics),
        "variants": tuple(entries),
    }
    return {**payload, "plan_hash": sha256_json(payload)}


def _text_only_weighted_evidence(sample: CorpusSample, adapter: HuggingFaceSynthIDAdapter):
    if sample.text_only_tokens is None:
        raise TinyDevTransformPilotError(f"sample {sample.sample_id} lacks text-only tokens")
    eos = sample.model.eos_token_id
    if eos is None:
        raise TinyDevTransformPilotError("TinyDev tokenizer must define eos_token_id")
    batch = build_native_observations(sample.sample_id, sample.text_only_tokens.token_ids, eos, adapter)
    return weighted_mean_evidence(batch)


def _text_only_calibration(corpus, adapter: HuggingFaceSynthIDAdapter):
    negatives = _calibration_negatives(corpus)
    evidence = tuple(_text_only_weighted_evidence(sample, adapter) for sample in negatives)
    scope = CalibrationScope.create(
        corpus_id=corpus.manifest.corpus_id,
        population_id=TEXT_ONLY_CALIBRATION_POPULATION_ID,
        length_policy_id=TEXT_ONLY_LENGTH_POLICY_ID,
        token_track=TEXT_ONLY_TOKEN_TRACK,
        prompt_boundary_mode=TEXT_ONLY_PROMPT_BOUNDARY_MODE,
    )
    return calibrate_detector(
        evidence,
        scope,
        target_fprs=(0.05, 0.01),
        comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        confidence_level=0.95,
    )


def _threshold(bundle, target_fpr: float):
    return next(value for value in bundle.thresholds if value.target_fpr == target_fpr)


def _score_plan(corpus, tokenizer, plan: dict[str, object], adapter: HuggingFaceSynthIDAdapter) -> dict[str, object]:
    if plan.get("tiny_dev_artifact_hash") != corpus.artifact_hash:
        raise TinyDevTransformPilotError("transform plan does not bind the supplied TinyDev corpus")
    calibration = _text_only_calibration(corpus, adapter)
    threshold = _threshold(calibration, PRIMARY_TARGET_FPR)
    if calibration.detector_identity.detector_family is not DetectorFamily.WEIGHTED_MEAN:
        raise TinyDevTransformPilotError("pilot calibration must use Weighted Mean")
    attack_by_id = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    pristine_evidence = {
        sample_id: _text_only_weighted_evidence(sample, adapter)
        for sample_id, sample in attack_by_id.items()
    }
    positive_ids = tuple(
        sorted(sample.sample_id for sample in attack_by_id.values() if sample.label is WatermarkLabel.WATERMARKED)
    )
    negative_ids = tuple(
        sorted(sample.sample_id for sample in attack_by_id.values() if sample.label is WatermarkLabel.UNWATERMARKED)
    )
    pristine_positive_detected = sum(pristine_evidence[value].raw_score >= threshold.value for value in positive_ids)
    pristine_negative_detected = sum(pristine_evidence[value].raw_score >= threshold.value for value in negative_ids)

    transform_rows: list[DevelopmentTransformRow] = []
    row_diagnostics: list[dict[str, object]] = []
    control_rows: list[dict[str, object]] = []
    for entry in plan["variants"]:
        source = attack_by_id[entry["source_sample_id"]]
        source_tokens = source.text_only_tokens.token_ids if source.text_only_tokens is not None else ()
        transformed_text = entry["transformed_text"]
        transformed_tokens = _encode_text(tokenizer, transformed_text)
        eos = source.model.eos_token_id
        if eos is None:
            raise TinyDevTransformPilotError("TinyDev tokenizer must define eos_token_id")
        transformed_batch = build_native_observations(
            f"{source.sample_id}-transformed-{entry['schedule_result_hash'][:12]}",
            transformed_tokens,
            eos,
            adapter,
        )
        transformed_evidence = weighted_mean_evidence(transformed_batch)
        original_evidence = pristine_evidence[source.sample_id]
        alignment = align_tokens(source_tokens, transformed_tokens)
        diffs = structural_observation_diff(source_tokens, transformed_tokens, adapter.ngram_len, alignment)
        summary = summarize_structural_observations(source_tokens, transformed_tokens, adapter.ngram_len, diffs)
        damaged_count = summary.replaced_count + summary.unmapped_count
        word_count = len(_word_units(source.text))
        if word_count <= 0:
            raise TinyDevTransformPilotError("word-edit denominator is empty")
        word_edits = _word_edit_distance(source.text, transformed_text)
        eligible = entry["realized_edit_cost"] > 0
        if source.label is WatermarkLabel.WATERMARKED:
            if not eligible:
                raise TinyDevTransformPilotError(
                    f"watermarked planned variant unexpectedly realized zero edits for {source.sample_id}"
                )
            transform_rows.append(
                DevelopmentTransformRow.create(
                    source_sample_id=source.sample_id,
                    prompt_family_id=source.prompt_family_id,
                    source_text_hash=source.text_sha256,
                    transformed_text_hash=entry["transformed_text_hash"],
                    key_split=source.watermark.key_split,
                    detector_identity_hash=calibration.detector_identity.identity_hash,
                    threshold_hash=threshold.threshold_hash,
                    threshold_value=threshold.value,
                    candidate_pool_hash=entry["candidate_pool_hash"],
                    scheduler_input_hash=entry["scheduler_input_hash"],
                    schedule_result_hash=entry["schedule_result_hash"],
                    schedule_policy=SchedulePolicy(entry["schedule_policy"]),
                    schedule_seed=entry["schedule_seed"],
                    budget=entry["budget"],
                    budget_unit=entry["budget_unit"],
                    realized_edit_cost=entry["realized_edit_cost"],
                    scheduler_covered_interval_size=entry["scheduler_covered_interval_size"],
                    word_edit_count=word_edits,
                    word_count=word_count,
                    observation_replacement_count=damaged_count,
                    original_observation_count=summary.original_count,
                    pristine_score=original_evidence.raw_score,
                    transformed_score=transformed_evidence.raw_score,
                    eligible=True,
                    secret_access_observed=False,
                )
            )
        else:
            control_rows.append(
                {
                    "source_sample_id": source.sample_id,
                    "domain": source.domain.value,
                    "schedule_policy": entry["schedule_policy"],
                    "schedule_seed": entry["schedule_seed"],
                    "budget": entry["budget"],
                    "realized_edit_cost": entry["realized_edit_cost"],
                    "eligible": eligible,
                    "pristine_score": original_evidence.raw_score,
                    "transformed_score": transformed_evidence.raw_score,
                    "score_shift_transformed_minus_pristine": transformed_evidence.raw_score - original_evidence.raw_score,
                    "pristine_detected": original_evidence.raw_score >= threshold.value,
                    "transformed_detected": transformed_evidence.raw_score >= threshold.value,
                    "observation_damage_count": damaged_count,
                    "original_observation_count": summary.original_count,
                    "row_hash": sha256_json(
                        {
                            "source_sample_id": source.sample_id,
                            "schedule_result_hash": entry["schedule_result_hash"],
                            "pristine_score": original_evidence.raw_score,
                            "transformed_score": transformed_evidence.raw_score,
                            "observation_damage_count": damaged_count,
                        }
                    ),
                }
            )
        row_diagnostics.append(
            {
                "source_sample_id": source.sample_id,
                "source_label": source.label.value,
                "schedule_result_hash": entry["schedule_result_hash"],
                "schedule_policy": entry["schedule_policy"],
                "schedule_seed": entry["schedule_seed"],
                "budget": entry["budget"],
                "realized_edit_cost": entry["realized_edit_cost"],
                "source_token_count": len(source_tokens),
                "transformed_token_count": len(transformed_tokens),
                "alignment_distance": alignment.distance,
                "alignment_ambiguous_ties": alignment.ambiguous_ties,
                "preserved_observation_count": summary.preserved_count,
                "replaced_observation_count": summary.replaced_count,
                "unmapped_observation_count": summary.unmapped_count,
                "observation_damage_count": damaged_count,
                "word_edit_count": word_edits,
                "hard_invariant_status": entry["hard_invariant_status"],
            }
        )
    rows = tuple(transform_rows)
    e07 = run_e07_predictor_comparison(corpus, rows)
    e08 = run_e08_dose_response(corpus, rows)
    random_rows = tuple(value for value in rows if value.schedule_policy is SchedulePolicy.RANDOM_VALID)
    spacing_rows = tuple(
        value for value in rows
        if value.schedule_policy in (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING)
    )
    greedy_rows = tuple(
        value for value in rows
        if value.schedule_policy in (SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND)
    )
    e09 = run_e09_random_baseline(corpus, random_rows)
    e10 = run_e10_spacing_comparison(corpus, spacing_rows)
    e11 = run_e11_greedy_comparison(corpus, greedy_rows)

    policy_summaries: list[dict[str, object]] = []
    for policy in SchedulePolicy:
        selected = tuple(value for value in rows if value.schedule_policy is policy)
        if not selected:
            continue
        policy_summaries.append(
            {
                "policy": policy.value,
                "row_count": len(selected),
                "mean_observation_damage_ratio": sum(value.observation_replacement_ratio for value in selected) / len(selected),
                "mean_replacement_per_edit": sum(value.replacement_per_edit for value in selected) / len(selected),
                "mean_score_drop": sum(value.margin_drop for value in selected) / len(selected),
                "transformed_detected_count": sum(value.transformed_detected for value in selected),
                "pristine_detected_count": sum(value.pristine_detected for value in selected),
            }
        )
    control_eligible = tuple(value for value in control_rows if value["eligible"])
    payload = {
        "algorithm_version": TINY_DEV_TRANSFORM_PILOT_VERSION,
        "scientific_scope": "DEV_KEYS-only real TinyDev text-only transform pilot; exploratory development evidence, not M6 readiness and not confirmatory evidence",
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "plan_hash": plan["plan_hash"],
        "watermark_config_hash": default_watermark_config_hash(),
        "adapter_id": adapter.adapter_id,
        "adapter_config_hash": adapter.configuration_fingerprint(),
        "sampling_table_hash": adapter.sampling_table_hash,
        "token_track": TEXT_ONLY_TOKEN_TRACK,
        "prompt_boundary_mode": TEXT_ONLY_PROMPT_BOUNDARY_MODE,
        "observation_damage_policy": OBSERVATION_DAMAGE_POLICY_ID,
        "detector_family": DetectorFamily.WEIGHTED_MEAN.value,
        "calibration_bundle_hash": calibration.bundle_hash,
        "calibration_negative_count": calibration.negative_count,
        "primary_target_fpr": PRIMARY_TARGET_FPR,
        "primary_threshold_hash": threshold.threshold_hash,
        "primary_threshold_value": threshold.value,
        "achieved_calibration_fpr": threshold.achieved_fpr,
        "calibration_fpr_interval": threshold.fpr_interval,
        "pristine_positive_detected_count": pristine_positive_detected,
        "pristine_positive_count": len(positive_ids),
        "pristine_negative_detected_count": pristine_negative_detected,
        "pristine_negative_count": len(negative_ids),
        "development_rows": rows,
        "row_diagnostics": tuple(row_diagnostics),
        "control_rows": tuple(control_rows),
        "control_eligible_count": len(control_eligible),
        "control_mean_score_shift": (
            sum(value["score_shift_transformed_minus_pristine"] for value in control_eligible) / len(control_eligible)
            if control_eligible else None
        ),
        "control_false_to_true_count": sum(
            (not value["pristine_detected"]) and value["transformed_detected"] for value in control_eligible
        ),
        "policy_summaries": tuple(policy_summaries),
        "e07": e07,
        "e08": e08,
        "e09": e09,
        "e10": e10,
        "e11": e11,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _write_fsynced(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_text(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-transform-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--random-seeds", type=int, default=DEFAULT_RANDOM_SEED_COUNT)
    parser.add_argument("--plan-json", type=Path, default=Path("artifacts/tiny-dev-transform-plan.json"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/tiny-dev-transform-evidence.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("TinyDev transform geometry requires a fast tokenizer with offset mappings")
    if tokenizer.eos_token_id != next(iter(corpus.manifest.samples)).model.eos_token_id:
        raise RuntimeError("runtime tokenizer EOS identity does not match TinyDev corpus")

    plan = build_transform_plan(
        corpus,
        tokenizer,
        budgets=DEFAULT_BUDGETS,
        random_seed_count=args.random_seeds,
    )
    _write_fsynced(args.plan_json, plan)

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
    evidence = _score_plan(corpus, tokenizer, plan, adapter)
    _write_fsynced(args.json, evidence)

    sys.stdout.write(f"plan_hash={plan['plan_hash']}\n")
    sys.stdout.write(f"artifact_hash={evidence['artifact_hash']}\n")
    sys.stdout.write(f"calibration_bundle_hash={evidence['calibration_bundle_hash']}\n")
    sys.stdout.write(
        f"pristine_positive={evidence['pristine_positive_detected_count']}/{evidence['pristine_positive_count']}\n"
    )
    sys.stdout.write(
        f"pristine_negative={evidence['pristine_negative_detected_count']}/{evidence['pristine_negative_count']}\n"
    )
    sys.stdout.write(f"control_mean_score_shift={evidence['control_mean_score_shift']}\n")
    sys.stdout.write(f"control_false_to_true_count={evidence['control_false_to_true_count']}\n")
    for summary in evidence["policy_summaries"]:
        sys.stdout.write(
            f"policy={summary['policy']} rows={summary['row_count']} "
            f"mean_damage={summary['mean_observation_damage_ratio']:.8f} "
            f"replacement_per_edit={summary['mean_replacement_per_edit']:.8f} "
            f"mean_score_drop={summary['mean_score_drop']:.8f} "
            f"detected={summary['transformed_detected_count']}/{summary['row_count']}\n"
        )
    sys.stdout.write(
        f"e07_lower_error_metric={evidence['e07'].lower_error_metric.value} "
        f"word_rmse={evidence['e07'].word_edit_rmse:.8f} "
        f"observation_rmse={evidence['e07'].observation_replacement_rmse:.8f}\n"
    )
    sys.stdout.write(
        f"e11_mean_improvement={evidence['e11'].mean_improvement_greedy_minus_random} "
        f"status={evidence['e11'].status.value}\n"
    )
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
