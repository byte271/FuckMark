from __future__ import annotations

from collections import Counter

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus.mid_dev_calibration import (
    MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
    build_mid_dev_calibration_prompt_records,
)
from fuckmark.corpus.mid_dev_calibration_generation import build_real_mid_dev_calibration
from fuckmark.corpus.mid_dev_calibration_io import (
    MidDevCalibrationJsonError,
    parse_mid_dev_calibration_json,
)
from fuckmark.corpus.schema import CorpusSplit, KeySplit, WatermarkLabel
from tests.test_mid_dev_generation import _FakeBackend


def test_middev_length_calibration_contains_100_independent_negatives_per_length() -> None:
    artifact = build_real_mid_dev_calibration(_FakeBackend())
    assert len(artifact.manifest.prompts) == 200
    assert len(artifact.manifest.samples) == 200
    assert artifact.negatives_per_length == MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH == 100
    assert Counter(sample.target_length for sample in artifact.manifest.samples) == Counter(
        {128: 100, 256: 100}
    )
    assert all(sample.split is CorpusSplit.THRESHOLD_CALIBRATION for sample in artifact.manifest.samples)
    assert all(sample.label is WatermarkLabel.UNWATERMARKED for sample in artifact.manifest.samples)
    assert all(sample.watermark.key_split is KeySplit.DEV for sample in artifact.manifest.samples)
    assert len({sample.text_sha256 for sample in artifact.manifest.samples}) == 200
    assert len({sample.generation.seed for sample in artifact.manifest.samples}) == 200


def test_middev_length_calibration_prompt_matrix_is_disjoint_and_balanced() -> None:
    prompts = build_mid_dev_calibration_prompt_records()
    assert len(prompts) == 200
    assert len({prompt.prompt_id for prompt in prompts}) == 200
    assert len({prompt.text_sha256 for prompt in prompts}) == 200
    assert all(prompt.prompt_id.startswith("middev-cal-") for prompt in prompts)
    assert Counter(
        128 if prompt.prompt_id.startswith("middev-cal-128-") else 256
        for prompt in prompts
    ) == Counter({128: 100, 256: 100})


def test_middev_length_calibration_json_round_trip_is_canonical() -> None:
    artifact = build_real_mid_dev_calibration(_FakeBackend())
    text = canonical_json_text(artifact) + "\n"
    loaded = parse_mid_dev_calibration_json(text)
    assert loaded.artifact_hash == artifact.artifact_hash
    assert loaded.source_profile_hash == artifact.source_profile_hash


def test_middev_length_calibration_json_rejects_noncanonical_form() -> None:
    artifact = build_real_mid_dev_calibration(_FakeBackend())
    text = "\n" + canonical_json_text(artifact)
    with pytest.raises(MidDevCalibrationJsonError, match="not canonical"):
        parse_mid_dev_calibration_json(text)
