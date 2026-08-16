import math

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors import (
    CompatibilityStatus,
    DetectorCompatibilityError,
    DetectorFamily,
    ZeroValidObservationsError,
    evaluate_detector_compatibility,
    mean_evidence,
    mean_score,
    require_supported_detector,
    weighted_mean_evidence,
    weighted_mean_score,
)
from fuckmark.native_observations import NativeObservationBatch, build_native_observations


def _adapter() -> DeepMindReferenceAdapter:
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)
    )


def test_t076_all_zero_g() -> None:
    assert mean_score(((0, 0), (0, 0)), (1, 1)) == 0.0
    assert weighted_mean_score(((0, 0), (0, 0)), (1, 1)) == 0.0


def test_t077_all_one_g() -> None:
    assert mean_score(((1, 1), (1, 1)), (1, 1)) == 1.0
    assert weighted_mean_score(((1, 1), (1, 1)), (1, 1)) == 1.0


def test_t078_alternating_g() -> None:
    values = ((0, 1), (1, 0), (0, 1), (1, 0))
    assert mean_score(values, (1, 1, 1, 1)) == 0.5
    assert weighted_mean_score(values, (1, 1, 1, 1)) == 0.5


def test_t079_mixed_depth_vectors() -> None:
    values = ((1, 0, 1), (0, 1, 1), (1, 1, 0))
    assert mean_score(values, (1, 0, 1)) == pytest.approx(4 / 6)
    assert weighted_mean_score(values, (1, 0, 1), (3, 2, 1)) == pytest.approx(0.75)


def test_t080_depth_one() -> None:
    values = ((1,), (0,), (1,))
    assert mean_score(values, (1, 1, 1)) == pytest.approx(2 / 3)
    assert weighted_mean_score(values, (1, 1, 1)) == pytest.approx(2 / 3)


def test_t081_depth_two() -> None:
    values = ((1, 0), (1, 1))
    assert mean_score(values, (1, 1)) == 0.75
    assert weighted_mean_score(values, (1, 1), (1, 1)) == 0.75


def test_t082_depth_thirty() -> None:
    row = tuple(index % 2 for index in range(30))
    assert mean_score((row,), (1,)) == 0.5
    score = weighted_mean_score((row,), (1,))
    assert 0.0 <= score <= 1.0


def test_t083_single_valid_mask() -> None:
    values = ((0, 0, 0), (1, 0, 1), (0, 0, 0))
    assert mean_score(values, (0, 1, 0)) == pytest.approx(2 / 3)


def test_t084_mixed_mask() -> None:
    values = ((1, 1), (0, 0), (1, 0), (0, 1))
    assert mean_score(values, (1, 0, 1, 0)) == 0.75


def test_t085_zero_mask_error() -> None:
    with pytest.raises(ZeroValidObservationsError):
        mean_score(((1, 0), (0, 1)), (0, 0))
    with pytest.raises(ZeroValidObservationsError):
        weighted_mean_score(((1, 0), (0, 1)), (False, False))


def test_t086_long_repetition_mask() -> None:
    values = tuple((1, 0) for _ in range(2000))
    mask = tuple(index % 7 != 0 for index in range(2000))
    assert mean_score(values, mask) == 0.5


def test_t087_eos_mask_is_consumed_from_native_batch() -> None:
    batch = build_native_observations(
        "eos",
        [10, 20, 30, 40, 20, 30, 50],
        40,
        _adapter(),
    )
    evidence = mean_evidence(batch)
    assert batch.valid_mask == (True, False, False, False, False)
    assert evidence.valid_observation_count == 1
    assert evidence.raw_score == pytest.approx(2 / 3)


def test_weighted_mean_matches_pinned_source_default_weights_golden() -> None:
    values = ((0, 1, 1), (1, 0, 1), (1, 1, 1), (0, 0, 1), (0, 1, 0))
    mask = (1, 1, 1, 1, 0)
    assert mean_score(values, mask) == pytest.approx(2 / 3)
    assert weighted_mean_score(values, mask) == pytest.approx(35 / 66)


def test_weighted_mean_normalizes_proportional_weights_to_same_behavior() -> None:
    values = ((1, 0), (0, 1), (1, 1))
    mask = (1, 1, 1)
    first = weighted_mean_score(values, mask, (2, 1))
    second = weighted_mean_score(values, mask, (20, 10))
    assert first == pytest.approx(second)


def test_weight_validation_rejects_invalid_values() -> None:
    values = ((1, 0),)
    with pytest.raises(ValueError):
        weighted_mean_score(values, (1,), (0, 0))
    with pytest.raises(ValueError):
        weighted_mean_score(values, (1,), (-1, 2))
    with pytest.raises(ValueError):
        weighted_mean_score(values, (1,), (math.nan, 1))
    with pytest.raises(ValueError):
        weighted_mean_score(values, (1,), (1,))
    with pytest.raises(TypeError):
        weighted_mean_score(values, (1,), (True, 1))


def test_detector_inputs_are_snapshotted_without_mutation() -> None:
    values = [[1, 0], [0, 1]]
    mask = [1, 1]
    weights = [10.0, 1.0]
    before_values = [row[:] for row in values]
    before_mask = mask[:]
    before_weights = weights[:]
    weighted_mean_score(values, mask, weights)
    assert values == before_values
    assert mask == before_mask
    assert weights == before_weights


def test_mean_and_weighted_evidence_bind_adapter_and_detector_identity() -> None:
    batch = build_native_observations(
        "sample",
        [10, 20, 30, 40, 20, 30, 50],
        999,
        _adapter(),
    )
    mean = mean_evidence(batch)
    weighted = weighted_mean_evidence(batch)
    assert mean.raw_score == pytest.approx(2 / 3)
    assert weighted.raw_score == pytest.approx(35 / 66)
    assert mean.detector_config_hash != weighted.detector_config_hash
    assert mean.adapter_config_hash == batch.adapter_config_hash
    assert mean.valid_observation_count == 4
    assert mean.total_observation_count == 5
    assert mean.compatibility.status is CompatibilityStatus.SUPPORTED


def test_mean_evidence_rejects_zero_valid_native_batch() -> None:
    batch = build_native_observations("short", [1, 2], 99, _adapter())
    with pytest.raises(ZeroValidObservationsError):
        mean_evidence(batch)


def test_mean_and_weighted_compatibility_are_supported_for_pinned_adapter() -> None:
    batch = build_native_observations("sample", [1, 2, 3, 4], 99, _adapter())
    assert evaluate_detector_compatibility(batch, DetectorFamily.MEAN).status is CompatibilityStatus.SUPPORTED
    assert evaluate_detector_compatibility(batch, DetectorFamily.WEIGHTED_MEAN).status is CompatibilityStatus.SUPPORTED


def test_bayesian_compatibility_fails_closed_until_required_metadata_exists() -> None:
    batch = build_native_observations("sample", [1, 2, 3, 4], 99, _adapter())
    compatibility = evaluate_detector_compatibility(batch, DetectorFamily.BAYESIAN)
    assert compatibility.status is CompatibilityStatus.UNVERIFIED
    with pytest.raises(DetectorCompatibilityError):
        require_supported_detector(batch, DetectorFamily.BAYESIAN)


def test_source_revision_mismatch_is_unverified() -> None:
    batch = build_native_observations("short", [1, 2], 99, _adapter())
    mismatched = NativeObservationBatch(
        sample_id=batch.sample_id,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        adapter_config_hash=batch.adapter_config_hash,
        source_id=batch.source_id,
        source_commit="f" * 40,
        ngram_len=batch.ngram_len,
        depth=batch.depth,
        token_ids=batch.token_ids,
        eos_token_id=batch.eos_token_id,
        records=(),
    )
    compatibility = evaluate_detector_compatibility(mismatched, DetectorFamily.MEAN)
    assert compatibility.status is CompatibilityStatus.UNVERIFIED


def test_generic_mean_rejects_malformed_shapes_and_values() -> None:
    with pytest.raises(ValueError):
        mean_score(((1, 0), (1,)), (1, 1))
    with pytest.raises(ValueError):
        mean_score(((1, 2),), (1,))
    with pytest.raises(ValueError):
        mean_score(((1, 0),), (1, 0))
    with pytest.raises(TypeError):
        mean_score(((1, 0),), (0.5,))


def test_mean_and_weighted_compatibility_are_supported_for_pinned_huggingface_adapter() -> None:
    from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig

    adapter = HuggingFaceSynthIDAdapter(
        HuggingFaceSynthIDConfig(
            ngram_len=3,
            keys=(7, 11),
            context_history_size=4,
            sampling_table_size=8,
        ),
        bytes((0, 1, 0, 1, 1, 0, 1, 0)),
        "fixture",
    )
    batch = build_native_observations("hf", [1, 2, 3, 4], 99, adapter)
    assert evaluate_detector_compatibility(batch, DetectorFamily.MEAN).status is CompatibilityStatus.SUPPORTED
    assert evaluate_detector_compatibility(batch, DetectorFamily.WEIGHTED_MEAN).status is CompatibilityStatus.SUPPORTED


def test_proportional_weight_configs_share_behavioral_evidence_hash() -> None:
    batch = build_native_observations("sample", [10, 20, 30, 40, 50], 999, _adapter())
    first = weighted_mean_evidence(batch, (2, 1, 1))
    second = weighted_mean_evidence(batch, (20, 10, 10))
    assert first.raw_score == pytest.approx(second.raw_score)
    assert first.detector_config_hash == second.detector_config_hash


def test_weight_normalization_is_stable_across_extreme_finite_scales() -> None:
    values = ((1, 0), (0, 1), (1, 1))
    mask = (1, 1, 1)
    reference = weighted_mean_score(values, mask, (2.0, 1.0))
    huge = weighted_mean_score(values, mask, (1e308, 5e307))
    tiny = weighted_mean_score(values, mask, (1e-300, 5e-301))
    assert huge == pytest.approx(reference)
    assert tiny == pytest.approx(reference)
