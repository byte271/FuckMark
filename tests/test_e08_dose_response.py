from dataclasses import replace

import pytest

from fuckmark.corpus import CorpusSplit, KeySplit, WatermarkLabel
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.e08_dose import (
    E08_ALGORITHM_VERSION,
    E08_BIN_EDGES,
    E08_BOOTSTRAP_REPLICATES,
    run_e08_dose_response,
)
from fuckmark.experiments.transform_analysis import DevelopmentClaimStatus, DevelopmentTransformRow, TransformAnalysisInputError
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


def _threshold_identity():
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    threshold = next(value for value in binding.calibration_bundle.thresholds if value.target_fpr == 0.01)
    return binding.calibration_bundle.detector_identity.identity_hash, threshold.threshold_hash, threshold.value


def _dose_rows(nonmonotonic: bool = False):
    artifact = tiny_dev_artifact()
    detector_identity_hash, threshold_hash, threshold_value = _threshold_identity()
    sources = tuple(
        sorted(
            (
                sample
                for sample in artifact.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
                and sample.label is WatermarkLabel.WATERMARKED
            ),
            key=lambda sample: sample.sample_id,
        )
    )
    ratios = (0.05, 0.20, 0.40, 0.80)
    output = []
    for source_index, sample in enumerate(sources):
        pristine = 0.9 - source_index * 0.01
        pool_hash = sha256_text(f"dose-pool-{sample.sample_id}")
        for variant_index, ratio in enumerate(ratios):
            replacement_count = int(ratio * 100)
            margin = ratio * 0.5
            if nonmonotonic and ratio == 0.80:
                margin = 0.05
            output.append(
                DevelopmentTransformRow.create(
                    source_sample_id=sample.sample_id,
                    prompt_family_id=sample.prompt_family_id,
                    source_text_hash=sha256_text(sample.text),
                    transformed_text_hash=sha256_text(f"{sample.text}|dose-{variant_index}-{nonmonotonic}"),
                    key_split=KeySplit.DEV,
                    detector_identity_hash=detector_identity_hash,
                    threshold_hash=threshold_hash,
                    threshold_value=threshold_value,
                    candidate_pool_hash=pool_hash,
                    scheduler_input_hash=sha256_text(f"dose-input-{sample.sample_id}-{variant_index}"),
                    schedule_result_hash=sha256_text(f"dose-result-{sample.sample_id}-{variant_index}-{nonmonotonic}"),
                    schedule_policy=SchedulePolicy.LEFT_TO_RIGHT,
                    schedule_seed=variant_index,
                    budget=4,
                    budget_unit="operation",
                    realized_edit_cost=1,
                    scheduler_covered_interval_size=replacement_count,
                    word_edit_count=variant_index + 1,
                    word_count=100,
                    observation_replacement_count=replacement_count,
                    original_observation_count=100,
                    pristine_score=pristine,
                    transformed_score=pristine - margin,
                    eligible=True,
                )
            )
    return tuple(output)


def test_e08_freezes_bins_preserves_empty_bin_and_cluster_bootstrap_uncertainty() -> None:
    result = run_e08_dose_response(tiny_dev_artifact(), _dose_rows())
    assert result.algorithm_version == E08_ALGORITHM_VERSION
    assert tuple((dose_bin.lower, dose_bin.upper) for dose_bin in result.bins) == tuple(zip(E08_BIN_EDGES, E08_BIN_EDGES[1:]))
    assert result.nonempty_bin_count == 4
    assert result.bins[3].row_count == 0
    assert result.bins[3].source_count == 0
    assert result.bins[3].mean_margin_drop is None
    assert result.bins[3].bootstrap_lower is None
    assert result.bins[3].bootstrap_upper is None
    assert result.bootstrap_replicates == E08_BOOTSTRAP_REPLICATES
    assert result.monotonic_violation_count == 0
    assert result.monotonic_non_decreasing
    assert result.claim_status is DevelopmentClaimStatus.WITHHELD_DEV_ONLY
    for index in (0, 1, 2, 4):
        dose_bin = result.bins[index]
        assert dose_bin.row_count == 4
        assert dose_bin.source_count == 4
        assert dose_bin.bootstrap_lower == pytest.approx(dose_bin.mean_margin_drop)
        assert dose_bin.bootstrap_upper == pytest.approx(dose_bin.mean_margin_drop)


def test_e08_keeps_nonmonotonic_result_visible() -> None:
    result = run_e08_dose_response(tiny_dev_artifact(), _dose_rows(nonmonotonic=True))
    assert result.monotonic_violation_count == 1
    assert not result.monotonic_non_decreasing
    nonempty_means = tuple(value.mean_margin_drop for value in result.bins if value.mean_margin_drop is not None)
    assert nonempty_means[-1] < nonempty_means[-2]


def test_e08_is_deterministic_and_rejects_duplicate_rows() -> None:
    rows = _dose_rows()
    first = run_e08_dose_response(tiny_dev_artifact(), rows)
    second = run_e08_dose_response(tiny_dev_artifact(), tuple(reversed(rows)))
    assert second == first
    with pytest.raises(TransformAnalysisInputError, match="duplicate"):
        run_e08_dose_response(tiny_dev_artifact(), (*rows, rows[0]))


def test_e08_result_rejects_tampering() -> None:
    result = run_e08_dose_response(tiny_dev_artifact(), _dose_rows())
    with pytest.raises(ValueError, match="result_hash|monotonic"):
        replace(result, monotonic_violation_count=1, result_hash="f" * 64)
