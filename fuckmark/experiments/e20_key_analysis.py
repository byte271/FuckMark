from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, WatermarkLabel
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ResultBundle, verify_e20_result_bundle
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization


E20_KEY_ANALYSIS_ALGORITHM_VERSION = "e20-key-analysis-v1"
E20_KEY_QUANTILE_ALGORITHM_VERSION = "linear-type7-v1"


class E20KeyEffectStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE_FAILURE_ROWS = "INCOMPLETE_FAILURE_ROWS"
    NO_ANALYSABLE_ROWS = "NO_ANALYSABLE_ROWS"


@dataclass(frozen=True, slots=True)
class E20KeyEffect:
    condition_id: str
    key_id: str
    status: E20KeyEffectStatus
    expected_sample_count: int
    outcome_sample_count: int
    failure_sample_count: int
    pristine_tpr: float | None
    transformed_tpr: float | None
    tpr_change: float | None
    mean_standardized_margin_drop: float | None
    effect_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("key_id", self.key_id)
        if not isinstance(self.status, E20KeyEffectStatus):
            raise TypeError("status must be an E20KeyEffectStatus")
        for name, value in (
            ("expected_sample_count", self.expected_sample_count),
            ("outcome_sample_count", self.outcome_sample_count),
            ("failure_sample_count", self.failure_sample_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.outcome_sample_count + self.failure_sample_count != self.expected_sample_count:
            raise ValueError("held-out key sample counts do not close")
        metrics = (
            self.pristine_tpr,
            self.transformed_tpr,
            self.tpr_change,
            self.mean_standardized_margin_drop,
        )
        if self.outcome_sample_count == 0:
            if any(value is not None for value in metrics):
                raise ValueError("key effect with no analysable outcomes cannot contain effect metrics")
            if self.status is not E20KeyEffectStatus.NO_ANALYSABLE_ROWS:
                raise ValueError("key effect with no analysable outcomes requires NO_ANALYSABLE_ROWS")
        else:
            if any(value is None for value in metrics):
                raise ValueError("key effect with outcomes requires all effect metrics")
            for value in metrics:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("key effect metrics must be finite")
            expected_status = (
                E20KeyEffectStatus.COMPLETE
                if self.failure_sample_count == 0
                else E20KeyEffectStatus.INCOMPLETE_FAILURE_ROWS
            )
            if self.status is not expected_status:
                raise ValueError("key effect status does not match failure-row completeness")
            if not (0.0 <= float(self.pristine_tpr) <= 1.0):
                raise ValueError("pristine_tpr must be in [0, 1]")
            if not (0.0 <= float(self.transformed_tpr) <= 1.0):
                raise ValueError("transformed_tpr must be in [0, 1]")
            if not math.isclose(
                float(self.tpr_change),
                float(self.transformed_tpr) - float(self.pristine_tpr),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("tpr_change must equal transformed_tpr minus pristine_tpr")
        require_sha256("effect_hash", self.effect_hash)
        if self.effect_hash != sha256_json(self._payload()):
            raise ValueError("effect_hash does not match E20 key effect")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_KEY_ANALYSIS_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "key_id": self.key_id,
            "status": self.status.value,
            "expected_sample_count": self.expected_sample_count,
            "outcome_sample_count": self.outcome_sample_count,
            "failure_sample_count": self.failure_sample_count,
            "pristine_tpr": self.pristine_tpr,
            "transformed_tpr": self.transformed_tpr,
            "tpr_change": self.tpr_change,
            "mean_standardized_margin_drop": self.mean_standardized_margin_drop,
        }


@dataclass(frozen=True, slots=True)
class E20KeyDistributionSummary:
    condition_id: str
    effects: tuple[E20KeyEffect, ...]
    complete_key_count: int
    incomplete_key_count: int
    tpr_change_mean: float | None
    tpr_change_sd: float | None
    tpr_change_iqr: float | None
    margin_drop_mean: float | None
    margin_drop_sd: float | None
    margin_drop_iqr: float | None
    summary_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        if not isinstance(self.effects, tuple) or not self.effects:
            raise TypeError("effects must be a non-empty tuple")
        if any(not isinstance(value, E20KeyEffect) for value in self.effects):
            raise TypeError("effects must contain E20KeyEffect values")
        expected = tuple(sorted(self.effects, key=lambda value: (value.key_id, value.effect_hash)))
        if self.effects != expected:
            raise ValueError("held-out key effects must be canonically ordered")
        if any(value.condition_id != self.condition_id for value in self.effects):
            raise ValueError("held-out key effect condition IDs must match summary")
        if len({value.key_id for value in self.effects}) != len(self.effects):
            raise ValueError("held-out key IDs must be unique within condition summary")
        for name, value in (
            ("complete_key_count", self.complete_key_count),
            ("incomplete_key_count", self.incomplete_key_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        actual_complete = sum(value.status is E20KeyEffectStatus.COMPLETE for value in self.effects)
        if self.complete_key_count != actual_complete:
            raise ValueError("complete_key_count does not match key effects")
        if self.incomplete_key_count != len(self.effects) - actual_complete:
            raise ValueError("incomplete_key_count does not match key effects")
        metric_fields = (
            self.tpr_change_mean,
            self.tpr_change_sd,
            self.tpr_change_iqr,
            self.margin_drop_mean,
            self.margin_drop_sd,
            self.margin_drop_iqr,
        )
        available = tuple(value for value in self.effects if value.tpr_change is not None)
        if not available:
            if any(value is not None for value in metric_fields):
                raise ValueError("key distribution without analysable keys cannot contain distribution metrics")
        else:
            if any(value is None for value in metric_fields):
                raise ValueError("key distribution with analysable keys requires all distribution metrics")
            for value in metric_fields:
                if not math.isfinite(float(value)):
                    raise ValueError("held-out key distribution metrics must be finite")
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match held-out key distribution")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_KEY_ANALYSIS_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "effects": self.effects,
            "complete_key_count": self.complete_key_count,
            "incomplete_key_count": self.incomplete_key_count,
            "tpr_change_mean": self.tpr_change_mean,
            "tpr_change_sd": self.tpr_change_sd,
            "tpr_change_iqr": self.tpr_change_iqr,
            "margin_drop_mean": self.margin_drop_mean,
            "margin_drop_sd": self.margin_drop_sd,
            "margin_drop_iqr": self.margin_drop_iqr,
        }


@dataclass(frozen=True, slots=True)
class E20KeyAnalysisBundle:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    summaries: tuple[E20KeyDistributionSummary, ...]
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_KEY_ANALYSIS_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 key analysis algorithm version")
        require_sha256("execution_id", self.execution_id)
        require_sha256("result_bundle_hash", self.result_bundle_hash)
        if not isinstance(self.summaries, tuple) or not self.summaries:
            raise TypeError("summaries must be a non-empty tuple")
        if any(not isinstance(value, E20KeyDistributionSummary) for value in self.summaries):
            raise TypeError("summaries must contain E20KeyDistributionSummary values")
        expected = tuple(sorted(self.summaries, key=lambda value: value.condition_id))
        if self.summaries != expected:
            raise ValueError("held-out key summaries must be canonically ordered")
        if len({value.condition_id for value in self.summaries}) != len(self.summaries):
            raise ValueError("held-out key summary condition IDs must be unique")
        require_sha256("bundle_hash", self.bundle_hash)
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E20 key analysis bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "summaries": self.summaries,
        }


def _quantile(values: tuple[float, ...], probability: float) -> float:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("quantile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: tuple[float, ...]) -> tuple[float, float, float]:
    if not values:
        raise ValueError("distribution requires at least one value")
    mean = math.fsum(values) / len(values)
    sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / len(values))
    iqr = _quantile(values, 0.75) - _quantile(values, 0.25)
    return mean, sd, iqr


def build_e20_key_analysis_bundle(
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> E20KeyAnalysisBundle:
    verify_e20_result_bundle(
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    summaries: list[E20KeyDistributionSummary] = []
    for condition in condition_plan.conditions:
        outcomes = tuple(
            value
            for value in result_bundle.outcome_rows
            if value.identity.condition_id == condition.condition_id
            and sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
        )
        failures = tuple(
            value
            for value in result_bundle.failure_rows
            if value.identity.condition_id == condition.condition_id
            and sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
        )
        outcome_by_key: dict[str, list] = defaultdict(list)
        failure_by_key: dict[str, int] = defaultdict(int)
        for row in outcomes:
            outcome_by_key[sample_by_id[row.identity.sample_id].watermark.key_id].append(row)
        for row in failures:
            failure_by_key[sample_by_id[row.identity.sample_id].watermark.key_id] += 1
        key_ids = tuple(sorted(set(outcome_by_key) | set(failure_by_key)))
        if not key_ids:
            continue
        effects: list[E20KeyEffect] = []
        for key_id in key_ids:
            rows = tuple(outcome_by_key[key_id])
            failure_count = failure_by_key[key_id]
            expected_count = len(rows) + failure_count
            if not rows:
                status = E20KeyEffectStatus.NO_ANALYSABLE_ROWS
                metrics = (None, None, None, None)
            else:
                pristine_tpr = sum(row.detector.pristine_decision for row in rows) / len(rows)
                transformed_tpr = sum(row.detector.transformed_decision for row in rows) / len(rows)
                tpr_change = transformed_tpr - pristine_tpr
                margin_drop = math.fsum(
                    row.detector.pristine_standardized_margin - row.detector.transformed_standardized_margin
                    for row in rows
                ) / len(rows)
                status = (
                    E20KeyEffectStatus.COMPLETE
                    if failure_count == 0
                    else E20KeyEffectStatus.INCOMPLETE_FAILURE_ROWS
                )
                metrics = (pristine_tpr, transformed_tpr, tpr_change, margin_drop)
            payload = {
                "algorithm_version": E20_KEY_ANALYSIS_ALGORITHM_VERSION,
                "condition_id": condition.condition_id,
                "key_id": key_id,
                "status": status.value,
                "expected_sample_count": expected_count,
                "outcome_sample_count": len(rows),
                "failure_sample_count": failure_count,
                "pristine_tpr": metrics[0],
                "transformed_tpr": metrics[1],
                "tpr_change": metrics[2],
                "mean_standardized_margin_drop": metrics[3],
            }
            effects.append(
                E20KeyEffect(
                    condition.condition_id,
                    key_id,
                    status,
                    expected_count,
                    len(rows),
                    failure_count,
                    metrics[0],
                    metrics[1],
                    metrics[2],
                    metrics[3],
                    sha256_json(payload),
                )
            )
        ordered_effects = tuple(sorted(effects, key=lambda value: (value.key_id, value.effect_hash)))
        available_tpr = tuple(float(value.tpr_change) for value in ordered_effects if value.tpr_change is not None)
        available_margin = tuple(
            float(value.mean_standardized_margin_drop)
            for value in ordered_effects
            if value.mean_standardized_margin_drop is not None
        )
        if available_tpr:
            tpr_distribution = _distribution(available_tpr)
            margin_distribution = _distribution(available_margin)
        else:
            tpr_distribution = (None, None, None)
            margin_distribution = (None, None, None)
        complete_count = sum(value.status is E20KeyEffectStatus.COMPLETE for value in ordered_effects)
        summary_payload = {
            "algorithm_version": E20_KEY_ANALYSIS_ALGORITHM_VERSION,
            "condition_id": condition.condition_id,
            "effects": ordered_effects,
            "complete_key_count": complete_count,
            "incomplete_key_count": len(ordered_effects) - complete_count,
            "tpr_change_mean": tpr_distribution[0],
            "tpr_change_sd": tpr_distribution[1],
            "tpr_change_iqr": tpr_distribution[2],
            "margin_drop_mean": margin_distribution[0],
            "margin_drop_sd": margin_distribution[1],
            "margin_drop_iqr": margin_distribution[2],
        }
        summaries.append(
            E20KeyDistributionSummary(
                condition.condition_id,
                ordered_effects,
                complete_count,
                len(ordered_effects) - complete_count,
                tpr_distribution[0],
                tpr_distribution[1],
                tpr_distribution[2],
                margin_distribution[0],
                margin_distribution[1],
                margin_distribution[2],
                sha256_json(summary_payload),
            )
        )
    ordered_summaries = tuple(sorted(summaries, key=lambda value: value.condition_id))
    if not ordered_summaries:
        raise ValueError("E20 key analysis requires at least one watermarked held-out key")
    payload = {
        "algorithm_version": E20_KEY_ANALYSIS_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "summaries": ordered_summaries,
    }
    return E20KeyAnalysisBundle(
        E20_KEY_ANALYSIS_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        ordered_summaries,
        sha256_json(payload),
    )


def verify_e20_key_analysis_bundle(
    bundle: E20KeyAnalysisBundle,
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> None:
    if not isinstance(bundle, E20KeyAnalysisBundle):
        raise TypeError("bundle must be an E20KeyAnalysisBundle")
    expected = build_e20_key_analysis_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    if bundle != expected:
        raise ValueError("E20 key analysis bundle does not replay exactly from sealed results")
