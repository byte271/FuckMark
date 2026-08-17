from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, WatermarkLabel
from ..detectors import ExactBinomialInterval, exact_binomial_interval
from ..hashing import sha256_json
from .e20_bundle import E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_rows import E20OutcomeRow, ExperimentReasonCode


E22_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION = "e22-transformed-negative-v1"


class E22Estimand(str, Enum):
    POLICY_ALL = "POLICY_ALL"
    ELIGIBLE_ONLY = "ELIGIBLE_ONLY"


class E22CellStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    NO_VALID_OUTCOMES = "NO_VALID_OUTCOMES"
    NO_ELIGIBLE_OUTCOMES = "NO_ELIGIBLE_OUTCOMES"


class E22AnalysisStatus(str, Enum):
    COMPLETE = "COMPLETE"
    NO_ESTIMATE = "NO_ESTIMATE"


def _probability(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


def _finite(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class E22FprEstimate:
    positive_count: int
    trial_count: int
    rate: float
    interval: ExactBinomialInterval

    def __post_init__(self) -> None:
        require_int("positive_count", self.positive_count)
        require_int("trial_count", self.trial_count)
        if self.trial_count <= 0:
            raise ValueError("trial_count must be positive")
        if self.positive_count < 0 or self.positive_count > self.trial_count:
            raise ValueError("positive_count must lie inside trial_count")
        rate = _probability("rate", self.rate)
        if not math.isclose(rate, self.positive_count / self.trial_count, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("rate does not match positive_count and trial_count")
        object.__setattr__(self, "rate", rate)
        if not isinstance(self.interval, ExactBinomialInterval):
            raise TypeError("interval must be an ExactBinomialInterval")
        if self.interval != exact_binomial_interval(self.positive_count, self.trial_count, 0.95):
            raise ValueError("interval must be the exact 95% binomial interval")


@dataclass(frozen=True, slots=True)
class E22NegativeControlCell:
    condition_id: str
    transform_condition_id: str
    estimand: E22Estimand
    calibration_bundle_hash: str
    target_fpr: float
    negative_outcome_count: int
    negative_failure_count: int
    material_change_exclusion_count: int
    no_eligible_transform_count: int
    included_count: int
    pristine_fpr: E22FprEstimate | None
    transformed_fpr: E22FprEstimate | None
    fpr_shift: float | None
    mean_raw_score_shift: float | None
    mean_standardized_margin_shift: float | None
    false_to_true_count: int
    true_to_false_count: int
    status: E22CellStatus
    cell_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("transform_condition_id", self.transform_condition_id)
        if not isinstance(self.estimand, E22Estimand):
            raise TypeError("estimand must be an E22Estimand")
        require_sha256("calibration_bundle_hash", self.calibration_bundle_hash)
        target = _probability("target_fpr", self.target_fpr)
        if target <= 0.0 or target >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        for name, value in (
            ("negative_outcome_count", self.negative_outcome_count),
            ("negative_failure_count", self.negative_failure_count),
            ("material_change_exclusion_count", self.material_change_exclusion_count),
            ("no_eligible_transform_count", self.no_eligible_transform_count),
            ("included_count", self.included_count),
            ("false_to_true_count", self.false_to_true_count),
            ("true_to_false_count", self.true_to_false_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.material_change_exclusion_count > self.negative_outcome_count:
            raise ValueError("material change exclusions cannot exceed negative outcomes")
        if self.no_eligible_transform_count > self.negative_outcome_count:
            raise ValueError("no-eligible count cannot exceed negative outcomes")
        expected_included = self.negative_outcome_count - self.material_change_exclusion_count
        if self.estimand is E22Estimand.ELIGIBLE_ONLY:
            expected_included -= self.no_eligible_transform_count
        if self.included_count != expected_included:
            raise ValueError("included_count does not match the E22 estimand population")
        if self.false_to_true_count + self.true_to_false_count > self.included_count:
            raise ValueError("discordant decision counts cannot exceed included outcomes")
        if not isinstance(self.status, E22CellStatus):
            raise TypeError("status must be an E22CellStatus")
        values = (
            self.fpr_shift,
            self.mean_raw_score_shift,
            self.mean_standardized_margin_shift,
        )
        if self.included_count == 0:
            expected_status = E22CellStatus.NO_ELIGIBLE_OUTCOMES if self.estimand is E22Estimand.ELIGIBLE_ONLY else E22CellStatus.NO_VALID_OUTCOMES
            if self.status is not expected_status:
                raise ValueError("empty E22 cell has the wrong status")
            if self.pristine_fpr is not None or self.transformed_fpr is not None or any(value is not None for value in values):
                raise ValueError("empty E22 cells cannot carry detector estimates")
            if self.false_to_true_count or self.true_to_false_count:
                raise ValueError("empty E22 cells cannot carry discordant decisions")
        else:
            if self.status is not E22CellStatus.ESTIMATED:
                raise ValueError("non-empty E22 cell must be ESTIMATED")
            if not isinstance(self.pristine_fpr, E22FprEstimate) or not isinstance(self.transformed_fpr, E22FprEstimate):
                raise TypeError("estimated E22 cells require pristine and transformed FPR estimates")
            if self.pristine_fpr.trial_count != self.included_count or self.transformed_fpr.trial_count != self.included_count:
                raise ValueError("E22 FPR trial counts must equal included_count")
            if any(value is None for value in values):
                raise ValueError("estimated E22 cells require all detector shift estimates")
            fpr_shift = _finite("fpr_shift", self.fpr_shift)
            raw_shift = _finite("mean_raw_score_shift", self.mean_raw_score_shift)
            margin_shift = _finite("mean_standardized_margin_shift", self.mean_standardized_margin_shift)
            if not math.isclose(fpr_shift, self.transformed_fpr.rate - self.pristine_fpr.rate, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("fpr_shift does not match transformed minus pristine FPR")
            object.__setattr__(self, "fpr_shift", fpr_shift)
            object.__setattr__(self, "mean_raw_score_shift", raw_shift)
            object.__setattr__(self, "mean_standardized_margin_shift", margin_shift)
        require_sha256("cell_hash", self.cell_hash)
        if self.cell_hash != sha256_json(self._payload()):
            raise ValueError("cell_hash does not match E22 negative-control cell")

    def _payload(self) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "transform_condition_id": self.transform_condition_id,
            "estimand": self.estimand.value,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "target_fpr": self.target_fpr,
            "negative_outcome_count": self.negative_outcome_count,
            "negative_failure_count": self.negative_failure_count,
            "material_change_exclusion_count": self.material_change_exclusion_count,
            "no_eligible_transform_count": self.no_eligible_transform_count,
            "included_count": self.included_count,
            "pristine_fpr": self.pristine_fpr,
            "transformed_fpr": self.transformed_fpr,
            "fpr_shift": self.fpr_shift,
            "mean_raw_score_shift": self.mean_raw_score_shift,
            "mean_standardized_margin_shift": self.mean_standardized_margin_shift,
            "false_to_true_count": self.false_to_true_count,
            "true_to_false_count": self.true_to_false_count,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class E22TransformedNegativeReport:
    algorithm_version: str
    result_bundle_hash: str
    corpus_manifest_hash: str
    condition_plan_hash: str
    negative_source_sample_count: int
    negative_row_count: int
    negative_outcome_count: int
    negative_failure_count: int
    cells: tuple[E22NegativeControlCell, ...]
    maximum_positive_fpr_shift: float | None
    status: E22AnalysisStatus
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E22_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION:
            raise ValueError("unsupported E22 transformed-negative algorithm version")
        for name, value in (
            ("result_bundle_hash", self.result_bundle_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("report_hash", self.report_hash),
        ):
            require_sha256(name, value)
        for name, value in (
            ("negative_source_sample_count", self.negative_source_sample_count),
            ("negative_row_count", self.negative_row_count),
            ("negative_outcome_count", self.negative_outcome_count),
            ("negative_failure_count", self.negative_failure_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.negative_row_count != self.negative_outcome_count + self.negative_failure_count:
            raise ValueError("negative_row_count does not close over outcomes and failures")
        if not isinstance(self.cells, tuple):
            raise TypeError("cells must be a tuple")
        if any(not isinstance(value, E22NegativeControlCell) for value in self.cells):
            raise TypeError("cells must contain E22NegativeControlCell values")
        expected = tuple(sorted(self.cells, key=lambda value: (value.condition_id, value.estimand.value, value.cell_hash)))
        if self.cells != expected:
            raise ValueError("E22 cells must be canonically ordered")
        if len({(value.condition_id, value.estimand) for value in self.cells}) != len(self.cells):
            raise ValueError("E22 cells must be unique by condition and estimand")
        policy_cells = tuple(value for value in self.cells if value.estimand is E22Estimand.POLICY_ALL)
        if sum(value.negative_outcome_count for value in policy_cells) != self.negative_outcome_count:
            raise ValueError("E22 policy-all cells do not account for every negative outcome")
        if sum(value.negative_failure_count for value in policy_cells) != self.negative_failure_count:
            raise ValueError("E22 policy-all cells do not account for every negative failure")
        positive_shifts = tuple(value.fpr_shift for value in policy_cells if value.fpr_shift is not None and value.fpr_shift > 0.0)
        expected_maximum = max(positive_shifts) if positive_shifts else None
        if expected_maximum is None:
            if self.maximum_positive_fpr_shift is not None:
                raise ValueError("maximum_positive_fpr_shift must be None when no positive shift exists")
        elif self.maximum_positive_fpr_shift is None or not math.isclose(self.maximum_positive_fpr_shift, expected_maximum, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("maximum_positive_fpr_shift does not match E22 cells")
        if not isinstance(self.status, E22AnalysisStatus):
            raise TypeError("status must be an E22AnalysisStatus")
        expected_status = E22AnalysisStatus.COMPLETE if any(value.status is E22CellStatus.ESTIMATED for value in policy_cells) else E22AnalysisStatus.NO_ESTIMATE
        if self.status is not expected_status:
            raise ValueError("E22 analysis status does not match policy-all estimates")
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match E22 transformed-negative report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "result_bundle_hash": self.result_bundle_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "condition_plan_hash": self.condition_plan_hash,
            "negative_source_sample_count": self.negative_source_sample_count,
            "negative_row_count": self.negative_row_count,
            "negative_outcome_count": self.negative_outcome_count,
            "negative_failure_count": self.negative_failure_count,
            "cells": self.cells,
            "maximum_positive_fpr_shift": self.maximum_positive_fpr_shift,
            "status": self.status.value,
        }


def _estimate(decisions: tuple[bool, ...]) -> E22FprEstimate:
    positives = sum(decisions)
    trials = len(decisions)
    return E22FprEstimate(positives, trials, positives / trials, exact_binomial_interval(positives, trials, 0.95))


def _mean_shift(outcomes: tuple[E20OutcomeRow, ...], transformed_name: str, pristine_name: str) -> float:
    return math.fsum(getattr(row.detector, transformed_name) - getattr(row.detector, pristine_name) for row in outcomes) / len(outcomes)


def _build_cell(condition, outcomes: tuple[E20OutcomeRow, ...], failure_count: int, estimand: E22Estimand) -> E22NegativeControlCell:
    for row in outcomes:
        if row.detector.calibration_bundle_hash != condition.calibration_bundle_hash or row.detector.target_fpr != condition.target_fpr:
            raise ValueError("E22 outcome detector evaluation does not match its condition plan cell")
    material = tuple(row for row in outcomes if row.fidelity.reason_codes[0] is ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE)
    no_eligible = tuple(row for row in outcomes if row.fidelity.reason_codes[0] is ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM)
    valid = tuple(row for row in outcomes if row.fidelity.reason_codes[0] is not ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE)
    if estimand is E22Estimand.ELIGIBLE_ONLY:
        valid = tuple(row for row in valid if row.transform.eligible)
    pristine = _estimate(tuple(row.detector.pristine_decision for row in valid)) if valid else None
    transformed = _estimate(tuple(row.detector.transformed_decision for row in valid)) if valid else None
    shift = transformed.rate - pristine.rate if pristine is not None and transformed is not None else None
    raw_shift = _mean_shift(valid, "transformed_raw_score", "pristine_raw_score") if valid else None
    margin_shift = _mean_shift(valid, "transformed_standardized_margin", "pristine_standardized_margin") if valid else None
    false_to_true = sum(not row.detector.pristine_decision and row.detector.transformed_decision for row in valid)
    true_to_false = sum(row.detector.pristine_decision and not row.detector.transformed_decision for row in valid)
    if valid:
        status = E22CellStatus.ESTIMATED
    elif estimand is E22Estimand.ELIGIBLE_ONLY:
        status = E22CellStatus.NO_ELIGIBLE_OUTCOMES
    else:
        status = E22CellStatus.NO_VALID_OUTCOMES
    payload = {
        "condition_id": condition.condition_id,
        "transform_condition_id": condition.transform_condition_id,
        "estimand": estimand.value,
        "calibration_bundle_hash": condition.calibration_bundle_hash,
        "target_fpr": condition.target_fpr,
        "negative_outcome_count": len(outcomes),
        "negative_failure_count": failure_count,
        "material_change_exclusion_count": len(material),
        "no_eligible_transform_count": len(no_eligible),
        "included_count": len(valid),
        "pristine_fpr": pristine,
        "transformed_fpr": transformed,
        "fpr_shift": shift,
        "mean_raw_score_shift": raw_shift,
        "mean_standardized_margin_shift": margin_shift,
        "false_to_true_count": false_to_true,
        "true_to_false_count": true_to_false,
        "status": status.value,
    }
    return E22NegativeControlCell(
        condition.condition_id,
        condition.transform_condition_id,
        estimand,
        condition.calibration_bundle_hash,
        condition.target_fpr,
        len(outcomes),
        failure_count,
        len(material),
        len(no_eligible),
        len(valid),
        pristine,
        transformed,
        shift,
        raw_shift,
        margin_shift,
        false_to_true,
        true_to_false,
        status,
        sha256_json(payload),
    )


def build_e22_transformed_negative_report(result_bundle: E20ResultBundle, corpus_manifest: CorpusManifest, condition_plan: E20ConditionPlan) -> E22TransformedNegativeReport:
    if not isinstance(result_bundle, E20ResultBundle):
        raise TypeError("result_bundle must be an E20ResultBundle")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if result_bundle.corpus_manifest_hash != corpus_manifest.manifest_hash:
        raise ValueError("E22 corpus manifest does not match the E20 result bundle")
    if result_bundle.condition_plan_hash != condition_plan.plan_hash:
        raise ValueError("E22 condition plan does not match the E20 result bundle")
    label_by_sample = {value.sample_id: value.label for value in corpus_manifest.samples}
    for row in (*result_bundle.outcome_rows, *result_bundle.failure_rows):
        if row.identity.sample_id not in label_by_sample:
            raise ValueError("E22 result row references a sample outside the bound corpus manifest")
    negative_sample_ids = frozenset(value.sample_id for value in corpus_manifest.samples if value.label is WatermarkLabel.UNWATERMARKED)
    outcomes_by_condition: dict[str, list[E20OutcomeRow]] = {}
    failures_by_condition: dict[str, int] = {}
    for row in result_bundle.outcome_rows:
        if row.identity.sample_id in negative_sample_ids:
            outcomes_by_condition.setdefault(row.identity.condition_id, []).append(row)
    for row in result_bundle.failure_rows:
        if row.identity.sample_id in negative_sample_ids:
            failures_by_condition[row.identity.condition_id] = failures_by_condition.get(row.identity.condition_id, 0) + 1
    observed_condition_ids = set(outcomes_by_condition) | set(failures_by_condition)
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    if observed_condition_ids - set(condition_by_id):
        raise ValueError("E22 negative rows reference conditions outside the bound condition plan")
    cells = []
    for condition_id in sorted(observed_condition_ids):
        condition = condition_by_id[condition_id]
        outcomes = tuple(sorted(outcomes_by_condition.get(condition_id, ()), key=lambda value: (value.identity.sample_id, value.row_hash)))
        failure_count = failures_by_condition.get(condition_id, 0)
        cells.append(_build_cell(condition, outcomes, failure_count, E22Estimand.POLICY_ALL))
        cells.append(_build_cell(condition, outcomes, failure_count, E22Estimand.ELIGIBLE_ONLY))
    ordered_cells = tuple(sorted(cells, key=lambda value: (value.condition_id, value.estimand.value, value.cell_hash)))
    negative_outcome_count = sum(len(value) for value in outcomes_by_condition.values())
    negative_failure_count = sum(failures_by_condition.values())
    positive_shifts = tuple(value.fpr_shift for value in ordered_cells if value.estimand is E22Estimand.POLICY_ALL and value.fpr_shift is not None and value.fpr_shift > 0.0)
    maximum_positive_fpr_shift = max(positive_shifts) if positive_shifts else None
    policy_cells = tuple(value for value in ordered_cells if value.estimand is E22Estimand.POLICY_ALL)
    status = E22AnalysisStatus.COMPLETE if any(value.status is E22CellStatus.ESTIMATED for value in policy_cells) else E22AnalysisStatus.NO_ESTIMATE
    payload = {
        "algorithm_version": E22_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION,
        "result_bundle_hash": result_bundle.bundle_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "negative_source_sample_count": len(negative_sample_ids),
        "negative_row_count": negative_outcome_count + negative_failure_count,
        "negative_outcome_count": negative_outcome_count,
        "negative_failure_count": negative_failure_count,
        "cells": ordered_cells,
        "maximum_positive_fpr_shift": maximum_positive_fpr_shift,
        "status": status.value,
    }
    return E22TransformedNegativeReport(
        E22_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION,
        result_bundle.bundle_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        len(negative_sample_ids),
        negative_outcome_count + negative_failure_count,
        negative_outcome_count,
        negative_failure_count,
        ordered_cells,
        maximum_positive_fpr_shift,
        status,
        sha256_json(payload),
    )


def verify_e22_transformed_negative_report(report: E22TransformedNegativeReport, result_bundle: E20ResultBundle, corpus_manifest: CorpusManifest, condition_plan: E20ConditionPlan) -> None:
    if not isinstance(report, E22TransformedNegativeReport):
        raise TypeError("report must be an E22TransformedNegativeReport")
    expected = build_e22_transformed_negative_report(result_bundle, corpus_manifest, condition_plan)
    if report != expected:
        raise ValueError("E22 transformed-negative report does not replay exactly from the bound E20 evidence")
