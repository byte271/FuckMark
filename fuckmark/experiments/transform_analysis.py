from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusSplit, KeySplit, TinyDevCorpusArtifact, WatermarkLabel
from ..hashing import sha256_json, sha256_text
from ..transforms import SchedulePolicy
from .registry import DevelopmentExperimentId, TransformSelectionAccess, default_development_experiment_registry


DEVELOPMENT_TRANSFORM_ROW_VERSION = "development-transform-row-v1"
E07_ALGORITHM_VERSION = "e07-predictor-comparison-v1"


class PredictorMetric(str, Enum):
    WORD_EDIT_RATE = "WORD_EDIT_RATE"
    OBSERVATION_REPLACEMENT = "OBSERVATION_REPLACEMENT"
    TIE = "TIE"


class DevelopmentClaimStatus(str, Enum):
    WITHHELD_DEV_ONLY = "WITHHELD_DEV_ONLY"


class TransformAnalysisInputError(ValueError):
    pass


def _require_probability(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


@dataclass(frozen=True, slots=True)
class DevelopmentTransformRow:
    algorithm_version: str
    source_sample_id: str
    prompt_family_id: str
    source_text_hash: str
    transformed_text_hash: str
    key_split: KeySplit
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    candidate_pool_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    schedule_policy: SchedulePolicy
    schedule_seed: int
    budget: int
    budget_unit: str
    realized_edit_cost: int
    scheduler_covered_interval_size: int
    word_edit_count: int
    word_count: int
    observation_replacement_count: int
    original_observation_count: int
    pristine_score: float
    transformed_score: float
    eligible: bool
    selection_access: TransformSelectionAccess
    secret_access_observed: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != DEVELOPMENT_TRANSFORM_ROW_VERSION:
            raise ValueError("unsupported development transform row version")
        require_clean_string("source_sample_id", self.source_sample_id)
        require_clean_string("prompt_family_id", self.prompt_family_id)
        for name, value in (
            ("source_text_hash", self.source_text_hash),
            ("transformed_text_hash", self.transformed_text_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("threshold_hash", self.threshold_hash),
            ("candidate_pool_hash", self.candidate_pool_hash),
            ("scheduler_input_hash", self.scheduler_input_hash),
            ("schedule_result_hash", self.schedule_result_hash),
            ("row_hash", self.row_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.key_split, KeySplit):
            raise TypeError("key_split must be a KeySplit")
        if not isinstance(self.schedule_policy, SchedulePolicy):
            raise TypeError("schedule_policy must be a SchedulePolicy")
        require_int("schedule_seed", self.schedule_seed)
        if self.schedule_seed < 0 or self.schedule_seed >= 1 << 64:
            raise ValueError("schedule_seed must be between 0 and 2^64-1")
        require_int("budget", self.budget)
        require_int("realized_edit_cost", self.realized_edit_cost)
        require_int("scheduler_covered_interval_size", self.scheduler_covered_interval_size)
        require_int("word_edit_count", self.word_edit_count)
        require_int("word_count", self.word_count)
        require_int("observation_replacement_count", self.observation_replacement_count)
        require_int("original_observation_count", self.original_observation_count)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        if self.realized_edit_cost < 0 or self.realized_edit_cost > self.budget:
            raise ValueError("realized_edit_cost must lie inside the requested budget")
        if self.scheduler_covered_interval_size < 0:
            raise ValueError("scheduler_covered_interval_size must be non-negative")
        if self.word_edit_count < 0 or self.word_count <= 0:
            raise ValueError("word edit geometry must have non-negative edits and positive denominator")
        if self.original_observation_count <= 0:
            raise ValueError("original_observation_count must be positive")
        if not 0 <= self.observation_replacement_count <= self.original_observation_count:
            raise ValueError("observation_replacement_count is outside the original observation range")
        object.__setattr__(self, "threshold_value", _require_probability("threshold_value", self.threshold_value))
        object.__setattr__(self, "pristine_score", _require_probability("pristine_score", self.pristine_score))
        object.__setattr__(self, "transformed_score", _require_probability("transformed_score", self.transformed_score))
        require_clean_string("budget_unit", self.budget_unit)
        require_bool("eligible", self.eligible)
        if not isinstance(self.selection_access, TransformSelectionAccess):
            raise TypeError("selection_access must be a TransformSelectionAccess")
        if self.selection_access is not TransformSelectionAccess.KEY_BLIND:
            raise ValueError("development transform rows for E07-E11 must use key-blind selection")
        require_bool("secret_access_observed", self.secret_access_observed)
        if not self.eligible:
            if self.realized_edit_cost != 0 or self.word_edit_count != 0 or self.observation_replacement_count != 0:
                raise ValueError("ineligible policy rows must have zero realized edit and replacement counts")
            if self.scheduler_covered_interval_size != 0:
                raise ValueError("ineligible policy rows must have zero scheduler coverage")
            if self.source_text_hash != self.transformed_text_hash or self.pristine_score != self.transformed_score:
                raise ValueError("ineligible policy rows must preserve text and detector score")
        else:
            if self.realized_edit_cost <= 0:
                raise ValueError("eligible policy rows must realize a positive edit cost")
            if self.source_text_hash == self.transformed_text_hash:
                raise ValueError("eligible policy rows must change the text")
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match development transform row")

    @property
    def word_edit_rate(self) -> float:
        return self.word_edit_count / self.word_count

    @property
    def observation_replacement_ratio(self) -> float:
        return self.observation_replacement_count / self.original_observation_count

    @property
    def margin_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    @property
    def pristine_detected(self) -> bool:
        return self.pristine_score >= self.threshold_value

    @property
    def transformed_detected(self) -> bool:
        return self.transformed_score >= self.threshold_value

    @property
    def replacement_per_edit(self) -> float:
        if self.realized_edit_cost == 0:
            return 0.0
        return self.observation_replacement_count / self.realized_edit_cost

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "prompt_family_id": self.prompt_family_id,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "key_split": self.key_split.value,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "candidate_pool_hash": self.candidate_pool_hash,
            "scheduler_input_hash": self.scheduler_input_hash,
            "schedule_result_hash": self.schedule_result_hash,
            "schedule_policy": self.schedule_policy.value,
            "schedule_seed": self.schedule_seed,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "realized_edit_cost": self.realized_edit_cost,
            "scheduler_covered_interval_size": self.scheduler_covered_interval_size,
            "word_edit_count": self.word_edit_count,
            "word_count": self.word_count,
            "observation_replacement_count": self.observation_replacement_count,
            "original_observation_count": self.original_observation_count,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "eligible": self.eligible,
            "selection_access": self.selection_access.value,
            "secret_access_observed": self.secret_access_observed,
        }

    @classmethod
    def create(
        cls,
        source_sample_id: str,
        prompt_family_id: str,
        source_text_hash: str,
        transformed_text_hash: str,
        key_split: KeySplit,
        detector_identity_hash: str,
        threshold_hash: str,
        threshold_value: float,
        candidate_pool_hash: str,
        scheduler_input_hash: str,
        schedule_result_hash: str,
        schedule_policy: SchedulePolicy,
        schedule_seed: int,
        budget: int,
        budget_unit: str,
        realized_edit_cost: int,
        scheduler_covered_interval_size: int,
        word_edit_count: int,
        word_count: int,
        observation_replacement_count: int,
        original_observation_count: int,
        pristine_score: float,
        transformed_score: float,
        eligible: bool,
        secret_access_observed: bool = False,
    ) -> DevelopmentTransformRow:
        payload = {
            "algorithm_version": DEVELOPMENT_TRANSFORM_ROW_VERSION,
            "source_sample_id": source_sample_id,
            "prompt_family_id": prompt_family_id,
            "source_text_hash": source_text_hash,
            "transformed_text_hash": transformed_text_hash,
            "key_split": key_split.value,
            "detector_identity_hash": detector_identity_hash,
            "threshold_hash": threshold_hash,
            "threshold_value": float(threshold_value),
            "candidate_pool_hash": candidate_pool_hash,
            "scheduler_input_hash": scheduler_input_hash,
            "schedule_result_hash": schedule_result_hash,
            "schedule_policy": schedule_policy.value,
            "schedule_seed": schedule_seed,
            "budget": budget,
            "budget_unit": budget_unit,
            "realized_edit_cost": realized_edit_cost,
            "scheduler_covered_interval_size": scheduler_covered_interval_size,
            "word_edit_count": word_edit_count,
            "word_count": word_count,
            "observation_replacement_count": observation_replacement_count,
            "original_observation_count": original_observation_count,
            "pristine_score": float(pristine_score),
            "transformed_score": float(transformed_score),
            "eligible": eligible,
            "selection_access": TransformSelectionAccess.KEY_BLIND.value,
            "secret_access_observed": secret_access_observed,
        }
        return cls(
            DEVELOPMENT_TRANSFORM_ROW_VERSION,
            source_sample_id,
            prompt_family_id,
            source_text_hash,
            transformed_text_hash,
            key_split,
            detector_identity_hash,
            threshold_hash,
            float(threshold_value),
            candidate_pool_hash,
            scheduler_input_hash,
            schedule_result_hash,
            schedule_policy,
            schedule_seed,
            budget,
            budget_unit,
            realized_edit_cost,
            scheduler_covered_interval_size,
            word_edit_count,
            word_count,
            observation_replacement_count,
            original_observation_count,
            float(pristine_score),
            float(transformed_score),
            eligible,
            TransformSelectionAccess.KEY_BLIND,
            secret_access_observed,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E07PredictorComparisonResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    row_hashes: tuple[str, ...]
    source_count: int
    variant_count: int
    word_edit_rmse: float
    observation_replacement_rmse: float
    lower_error_metric: PredictorMetric
    claim_status: DevelopmentClaimStatus
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != E07_ALGORITHM_VERSION:
            raise ValueError("unsupported E07 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("threshold_hash", self.threshold_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if self.row_hashes != tuple(sorted(set(self.row_hashes))):
            raise ValueError("row_hashes must be unique and canonically ordered")
        for value in self.row_hashes:
            require_sha256("row_hash", value)
        require_int("source_count", self.source_count)
        require_int("variant_count", self.variant_count)
        if self.source_count < 2:
            raise ValueError("E07 requires at least two source clusters")
        if self.variant_count != len(self.row_hashes) or self.variant_count < self.source_count:
            raise ValueError("variant_count does not match row hashes")
        for name, value in (
            ("word_edit_rmse", self.word_edit_rmse),
            ("observation_replacement_rmse", self.observation_replacement_rmse),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not isinstance(self.lower_error_metric, PredictorMetric):
            raise TypeError("lower_error_metric must be a PredictorMetric")
        expected_metric = _lower_error_metric(self.word_edit_rmse, self.observation_replacement_rmse)
        if self.lower_error_metric is not expected_metric:
            raise ValueError("lower_error_metric does not match held-out RMSE values")
        if self.claim_status is not DevelopmentClaimStatus.WITHHELD_DEV_ONLY:
            raise ValueError("E07 development result must withhold predictor superiority claims")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E07 predictor result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "row_hashes": self.row_hashes,
            "source_count": self.source_count,
            "variant_count": self.variant_count,
            "word_edit_rmse": self.word_edit_rmse,
            "observation_replacement_rmse": self.observation_replacement_rmse,
            "lower_error_metric": self.lower_error_metric.value,
            "claim_status": self.claim_status.value,
        }


def _fit_linear(rows: tuple[DevelopmentTransformRow, ...], predictor: PredictorMetric) -> tuple[float, float]:
    if not rows:
        raise TransformAnalysisInputError("linear predictor fit requires training rows")
    if predictor is PredictorMetric.WORD_EDIT_RATE:
        xs = tuple(row.word_edit_rate for row in rows)
    elif predictor is PredictorMetric.OBSERVATION_REPLACEMENT:
        xs = tuple(row.observation_replacement_ratio for row in rows)
    else:
        raise ValueError("predictor must be a concrete metric")
    ys = tuple(row.margin_drop for row in rows)
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0.0:
        return mean_y, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    intercept = mean_y - slope * mean_x
    return intercept, slope


def _held_out_rmse(rows: tuple[DevelopmentTransformRow, ...], predictor: PredictorMetric) -> float:
    source_ids = tuple(sorted({row.source_sample_id for row in rows}))
    squared_errors: list[float] = []
    for held_out in source_ids:
        training = tuple(row for row in rows if row.source_sample_id != held_out)
        testing = tuple(row for row in rows if row.source_sample_id == held_out)
        intercept, slope = _fit_linear(training, predictor)
        for row in testing:
            x = row.word_edit_rate if predictor is PredictorMetric.WORD_EDIT_RATE else row.observation_replacement_ratio
            error = row.margin_drop - (intercept + slope * x)
            squared_errors.append(error * error)
    return math.sqrt(sum(squared_errors) / len(squared_errors))


def _lower_error_metric(word_rmse: float, observation_rmse: float) -> PredictorMetric:
    if observation_rmse < word_rmse:
        return PredictorMetric.OBSERVATION_REPLACEMENT
    if word_rmse < observation_rmse:
        return PredictorMetric.WORD_EDIT_RATE
    return PredictorMetric.TIE


def _validate_tiny_attack_rows(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> tuple[str, str, tuple[str, ...]]:
    if any(row.secret_access_observed for row in rows):
        raise TransformAnalysisInputError("secret access contaminates E07/E08 key-blind analysis")
    expected_samples = tuple(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT and sample.label is WatermarkLabel.WATERMARKED
    )
    sample_by_id = {sample.sample_id: sample for sample in expected_samples}
    expected_ids = tuple(sorted(sample_by_id))
    actual_ids = tuple(sorted({row.source_sample_id for row in rows}))
    if actual_ids != expected_ids:
        missing = tuple(sorted(set(expected_ids) - set(actual_ids)))
        unexpected = tuple(sorted(set(actual_ids) - set(expected_ids)))
        raise TransformAnalysisInputError(
            f"transform rows must cover every tiny-dev watermarked attack source; missing={missing}, unexpected={unexpected}"
        )
    for row in rows:
        sample = sample_by_id[row.source_sample_id]
        if row.prompt_family_id != sample.prompt_family_id:
            raise TransformAnalysisInputError("transform row prompt family does not match corpus source")
        if row.source_text_hash != sha256_text(sample.text):
            raise TransformAnalysisInputError("transform row source text hash does not match corpus source")
        if row.key_split is not KeySplit.DEV:
            raise TransformAnalysisInputError("tiny-dev transform rows must use DEV_KEYS")
    detector_ids = {row.detector_identity_hash for row in rows}
    threshold_hashes = {row.threshold_hash for row in rows}
    threshold_values = {row.threshold_value for row in rows}
    if len(detector_ids) != 1 or len(threshold_hashes) != 1 or len(threshold_values) != 1:
        raise TransformAnalysisInputError("transform rows must use one frozen detector and threshold identity")
    for source_id in expected_ids:
        source_rows = tuple(row for row in rows if row.source_sample_id == source_id)
        pristine_scores = {row.pristine_score for row in source_rows}
        source_hashes = {row.source_text_hash for row in source_rows}
        if len(pristine_scores) != 1 or len(source_hashes) != 1:
            raise TransformAnalysisInputError("variants from one source must share pristine score and source identity")
    return next(iter(detector_ids)), next(iter(threshold_hashes)), expected_ids


def run_e07_predictor_comparison(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
) -> E07PredictorComparisonResult:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(rows, tuple) or not rows:
        raise TypeError("rows must be a non-empty tuple")
    if any(not isinstance(row, DevelopmentTransformRow) for row in rows):
        raise TypeError("rows must contain DevelopmentTransformRow values")
    if len({row.row_hash for row in rows}) != len(rows):
        raise TransformAnalysisInputError("E07 rows must not contain duplicate artifacts")
    detector_identity_hash, threshold_hash, source_ids = _validate_tiny_attack_rows(artifact, rows)
    word_rmse = _held_out_rmse(rows, PredictorMetric.WORD_EDIT_RATE)
    observation_rmse = _held_out_rmse(rows, PredictorMetric.OBSERVATION_REPLACEMENT)
    metric = _lower_error_metric(word_rmse, observation_rmse)
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E07)
    row_hashes = tuple(sorted(row.row_hash for row in rows))
    payload = {
        "algorithm_version": E07_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "row_hashes": row_hashes,
        "source_count": len(source_ids),
        "variant_count": len(rows),
        "word_edit_rmse": word_rmse,
        "observation_replacement_rmse": observation_rmse,
        "lower_error_metric": metric.value,
        "claim_status": DevelopmentClaimStatus.WITHHELD_DEV_ONLY.value,
    }
    return E07PredictorComparisonResult(
        E07_ALGORITHM_VERSION,
        definition.definition_hash,
        artifact.artifact_hash,
        detector_identity_hash,
        threshold_hash,
        row_hashes,
        len(source_ids),
        len(rows),
        word_rmse,
        observation_rmse,
        metric,
        DevelopmentClaimStatus.WITHHELD_DEV_ONLY,
        sha256_json(payload),
    )
