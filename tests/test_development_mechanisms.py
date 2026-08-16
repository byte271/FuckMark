from dataclasses import replace

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.experiments.mechanisms import (
    E03_ALGORITHM_VERSION,
    OBSERVATION_MECHANISM_ALGORITHM_VERSION,
    E03RepetitionFixture,
    MechanismInputError,
    MechanismStatus,
    run_e03_repetition_fixture,
    run_observation_mechanism,
)
from fuckmark.experiments.registry import DevelopmentExperimentId
from fuckmark.hashing import sha256_json


TOKENS = (10, 20, 30, 40, 20, 30, 50)
CONFIG = DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)


def _adapter():
    return DeepMindReferenceAdapter(CONFIG)


def test_e03_wraps_pinned_repetition_golden_as_content_addressed_result() -> None:
    adapter = _adapter()
    fixture = E03RepetitionFixture.create(
        "deepmind-context-repetition-golden",
        adapter,
        TOKENS,
        (True, True, True, True, False),
    )
    result = run_e03_repetition_fixture(fixture, adapter)
    assert result.algorithm_version == E03_ALGORITHM_VERSION
    assert result.status is MechanismStatus.PASS
    assert result.observation_count == 5
    assert result.masked_repetition_count == 1
    assert result.masked_repetition_ratio == 0.2
    assert result.actual_context_mask == fixture.expected_context_mask


def test_e03_records_source_compatible_mask_mismatch_instead_of_hiding_it() -> None:
    adapter = _adapter()
    fixture = E03RepetitionFixture.create(
        "deliberately-wrong-expected-mask",
        adapter,
        TOKENS,
        (True, True, True, True, True),
    )
    result = run_e03_repetition_fixture(fixture, adapter)
    assert result.status is MechanismStatus.MISMATCH
    assert result.actual_context_mask == (True, True, True, True, False)


def test_e03_rejects_adapter_configuration_drift() -> None:
    adapter = _adapter()
    fixture = E03RepetitionFixture.create(
        "deepmind-context-repetition-golden",
        adapter,
        TOKENS,
        (True, True, True, True, False),
    )
    changed = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=2)
    )
    with pytest.raises(MechanismInputError, match="identity or configuration"):
        run_e03_repetition_fixture(fixture, changed)


def test_e03_fixture_and_result_reject_rehashed_identity_tampering() -> None:
    adapter = _adapter()
    fixture = E03RepetitionFixture.create(
        "deepmind-context-repetition-golden",
        adapter,
        TOKENS,
        (True, True, True, True, False),
    )
    with pytest.raises(ValueError, match="40-character Git revision"):
        replace(fixture, source_commit="f" * 64, fixture_hash="0" * 64)
    result = run_e03_repetition_fixture(fixture, adapter)
    with pytest.raises(ValueError, match="result_hash"):
        replace(result, result_hash="f" * 64)


def test_e04_single_substitution_matches_exact_theoretical_observation_interval() -> None:
    result = run_observation_mechanism(
        DevelopmentExperimentId.E04,
        (10, 20, 30, 40, 50, 60),
        (10, 20, 99, 40, 50, 60),
        3,
    )
    assert result.algorithm_version == OBSERVATION_MECHANISM_ALGORITHM_VERSION
    assert result.status is MechanismStatus.PASS
    assert result.edit_original_index == 2
    assert result.edit_transformed_index == 2
    assert result.expected_non_preserved_indices == (0, 1, 2)
    assert result.actual_non_preserved_indices == (0, 1, 2)
    assert result.observation_summary.preserved_count == 1
    assert result.observation_summary.replaced_count == 3


def test_e05_insertion_recovers_all_full_suffix_ngrams_after_resynchronization() -> None:
    result = run_observation_mechanism(
        DevelopmentExperimentId.E05,
        (10, 20, 30, 40, 50, 60),
        (10, 20, 99, 30, 40, 50, 60),
        3,
    )
    assert result.status is MechanismStatus.PASS
    assert result.edit_original_index is None
    assert result.edit_transformed_index == 2
    assert result.suffix_expected_observation_count == 2
    assert result.suffix_preserved_observation_count == 2
    assert (2, 6, 3, 7) in result.conserved_token_runs


def test_e06_deletion_recovers_all_full_suffix_ngrams_after_resynchronization() -> None:
    result = run_observation_mechanism(
        DevelopmentExperimentId.E06,
        (10, 20, 99, 30, 40, 50, 60),
        (10, 20, 30, 40, 50, 60),
        3,
    )
    assert result.status is MechanismStatus.PASS
    assert result.edit_original_index == 2
    assert result.edit_transformed_index is None
    assert result.suffix_expected_observation_count == 2
    assert result.suffix_preserved_observation_count == 2
    assert (3, 7, 2, 6) in result.conserved_token_runs


def test_e04_e05_e06_reject_wrong_edit_shapes_and_non_evidentiary_suffixes() -> None:
    with pytest.raises(MechanismInputError, match="one substitute"):
        run_observation_mechanism(
            DevelopmentExperimentId.E04,
            (1, 2, 3, 4),
            (1, 9, 8, 4),
            2,
        )
    with pytest.raises(MechanismInputError, match="one inserted"):
        run_observation_mechanism(
            DevelopmentExperimentId.E05,
            (1, 2, 3, 4),
            (1, 9, 8, 2, 3, 4),
            2,
        )
    with pytest.raises(MechanismInputError, match="full suffix n-gram"):
        run_observation_mechanism(
            DevelopmentExperimentId.E06,
            (1, 2, 3, 9),
            (1, 2, 3),
            3,
        )


def test_observation_mechanism_rejects_rehashed_geometry_tampering() -> None:
    result = run_observation_mechanism(
        DevelopmentExperimentId.E05,
        (10, 20, 30, 40, 50, 60),
        (10, 20, 99, 30, 40, 50, 60),
        3,
    )
    forged_payload = result._payload()
    forged_payload["suffix_preserved_observation_count"] = 1
    forged_payload["status"] = MechanismStatus.MISMATCH.value
    with pytest.raises(ValueError, match="declared mechanism geometry"):
        replace(
            result,
            suffix_preserved_observation_count=1,
            status=MechanismStatus.MISMATCH,
            result_hash=sha256_json(forged_payload),
        )
