import pytest

from test_e20_row_verification import _fixture
from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from fuckmark.experiments import E20RowVerificationError, build_e20_outcome_row


def _hf_adapter():
    config = HuggingFaceSynthIDConfig(
        ngram_len=3,
        keys=(11, 22, 33),
        context_history_size=8,
        sampling_table_seed=7,
        sampling_table_size=64,
    )
    return HuggingFaceSynthIDAdapter(
        config,
        bytes(index % 2 for index in range(64)),
        "test-fixture-table-v1",
    )


def test_public_e20_outcome_rejects_wrong_observation_adapter_for_sample_generation_track() -> None:
    artifacts = _fixture()
    changed = dict(artifacts)
    changed["adapter"] = _hf_adapter()
    with pytest.raises(E20RowVerificationError, match="observation adapter does not match"):
        build_e20_outcome_row(**changed)


def test_public_e20_outcome_rejects_detector_bundle_from_other_generation_track() -> None:
    artifacts = _fixture()
    current = artifacts["condition_plan"].condition(artifacts["condition_id"])
    wrong_condition = next(
        value
        for value in artifacts["condition_plan"].conditions
        if value.transform_condition_id == current.transform_condition_id
        and value.calibration_bundle_hash != current.calibration_bundle_hash
    )
    wrong_bundle = next(
        value
        for value in artifacts["preregistration"].calibration_bundles
        if value.bundle_hash == wrong_condition.calibration_bundle_hash
    )
    changed = dict(artifacts)
    changed["condition_id"] = wrong_condition.condition_id
    changed["calibration_bundle"] = wrong_bundle
    with pytest.raises(E20RowVerificationError, match="not source/config compatible"):
        build_e20_outcome_row(**changed)
