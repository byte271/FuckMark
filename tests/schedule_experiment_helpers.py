from functools import lru_cache

from fuckmark.corpus import CorpusSplit, KeySplit, WatermarkLabel
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.transform_analysis import DevelopmentTransformRow
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


@lru_cache(maxsize=1)
def threshold_identity():
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    threshold = next(value for value in binding.calibration_bundle.thresholds if value.target_fpr == 0.01)
    return binding.calibration_bundle.detector_identity.identity_hash, threshold.threshold_hash, threshold.value


def attack_sources():
    return tuple(
        sorted(
            (
                sample
                for sample in tiny_dev_artifact().manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
                and sample.label is WatermarkLabel.WATERMARKED
            ),
            key=lambda sample: sample.sample_id,
        )
    )


def schedule_row(
    sample,
    policy: SchedulePolicy,
    *,
    variant: int = 0,
    pool: str | None = None,
    seed: int = 7,
    budget: int = 3,
    realized_cost: int = 1,
    coverage: int = 10,
    replacement_count: int = 10,
    margin_drop: float = 0.10,
    secret_access_observed: bool = False,
):
    detector_identity_hash, threshold_hash, threshold_value = threshold_identity()
    pristine_score = 0.90
    pool_id = pool if pool is not None else f"pool-{sample.sample_id}-{variant}"
    return DevelopmentTransformRow.create(
        source_sample_id=sample.sample_id,
        prompt_family_id=sample.prompt_family_id,
        source_text_hash=sha256_text(sample.text),
        transformed_text_hash=sha256_text(f"{sample.text}|{policy.value}|{variant}|{realized_cost}|{coverage}|{replacement_count}|{margin_drop}|{secret_access_observed}"),
        key_split=KeySplit.DEV,
        detector_identity_hash=detector_identity_hash,
        threshold_hash=threshold_hash,
        threshold_value=threshold_value,
        candidate_pool_hash=sha256_text(pool_id),
        scheduler_input_hash=sha256_text(f"scheduler-input-{pool_id}"),
        schedule_result_hash=sha256_text(f"schedule-result-{sample.sample_id}-{policy.value}-{variant}-{realized_cost}-{coverage}-{replacement_count}-{secret_access_observed}"),
        schedule_policy=policy,
        schedule_seed=seed,
        budget=budget,
        budget_unit="operation",
        realized_edit_cost=realized_cost,
        scheduler_covered_interval_size=coverage,
        word_edit_count=max(1, realized_cost),
        word_count=100,
        observation_replacement_count=replacement_count,
        original_observation_count=100,
        pristine_score=pristine_score,
        transformed_score=pristine_score - margin_drop,
        eligible=True,
        secret_access_observed=secret_access_observed,
    )
