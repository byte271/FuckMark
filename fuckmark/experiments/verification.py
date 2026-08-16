from __future__ import annotations

from collections.abc import Sequence

from ..adapters import WatermarkAdapter
from ..corpus import TinyDevCorpusArtifact
from ..detectors import UncalibratedDetectorEvidence
from .development_calibration import (
    DevelopmentCalibrationBinding,
    calibrate_tiny_dev_detector,
)
from .e02_pristine import (
    E02PristineDetectabilityResult,
    run_e02_pristine_detectability,
)
from .e08_dose import E08DoseResponseResult, run_e08_dose_response
from .mechanisms import (
    E03RepetitionFixture,
    E03RepetitionResult,
    ObservationMechanismResult,
    run_e03_repetition_fixture,
    run_observation_mechanism,
)
from .schedule_analysis import (
    E09RandomBaselineResult,
    E10SpacingComparisonResult,
    E11GreedyComparisonResult,
    run_e09_random_baseline,
    run_e10_spacing_comparison,
    run_e11_greedy_comparison,
)
from .transform_analysis import (
    DevelopmentTransformRow,
    E07PredictorComparisonResult,
    run_e07_predictor_comparison,
)


class ExperimentArtifactVerificationError(ValueError):
    pass


def _require_equal(name: str, actual, expected) -> None:
    if actual != expected:
        raise ExperimentArtifactVerificationError(f"{name} does not replay exactly from supplied source artifacts")


def verify_development_calibration_binding(
    artifact: TinyDevCorpusArtifact,
    evidence: Sequence[UncalibratedDetectorEvidence],
    binding: DevelopmentCalibrationBinding,
) -> None:
    if not isinstance(binding, DevelopmentCalibrationBinding):
        raise TypeError("binding must be a DevelopmentCalibrationBinding")
    expected = calibrate_tiny_dev_detector(artifact, evidence)
    _require_equal("development calibration binding", binding, expected)


def verify_e02_result(
    artifact: TinyDevCorpusArtifact,
    calibration: DevelopmentCalibrationBinding,
    evidence: Sequence[UncalibratedDetectorEvidence],
    result: E02PristineDetectabilityResult,
) -> None:
    if not isinstance(result, E02PristineDetectabilityResult):
        raise TypeError("result must be an E02PristineDetectabilityResult")
    expected = run_e02_pristine_detectability(artifact, calibration, evidence)
    _require_equal("E02 result", result, expected)


def verify_e03_result(
    fixture: E03RepetitionFixture,
    adapter: WatermarkAdapter,
    result: E03RepetitionResult,
) -> None:
    if not isinstance(result, E03RepetitionResult):
        raise TypeError("result must be an E03RepetitionResult")
    expected = run_e03_repetition_fixture(fixture, adapter)
    _require_equal("E03 result", result, expected)


def verify_observation_mechanism_result(result: ObservationMechanismResult) -> None:
    if not isinstance(result, ObservationMechanismResult):
        raise TypeError("result must be an ObservationMechanismResult")
    expected = run_observation_mechanism(
        result.experiment_id,
        result.original_tokens,
        result.transformed_tokens,
        result.ngram_len,
    )
    _require_equal(result.experiment_id.value, result, expected)


def verify_e07_result(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    result: E07PredictorComparisonResult,
) -> None:
    if not isinstance(result, E07PredictorComparisonResult):
        raise TypeError("result must be an E07PredictorComparisonResult")
    expected = run_e07_predictor_comparison(artifact, rows)
    _require_equal("E07 result", result, expected)


def verify_e08_result(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    result: E08DoseResponseResult,
) -> None:
    if not isinstance(result, E08DoseResponseResult):
        raise TypeError("result must be an E08DoseResponseResult")
    expected = run_e08_dose_response(artifact, rows)
    _require_equal("E08 result", result, expected)


def verify_e09_result(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    result: E09RandomBaselineResult,
) -> None:
    if not isinstance(result, E09RandomBaselineResult):
        raise TypeError("result must be an E09RandomBaselineResult")
    expected = run_e09_random_baseline(artifact, rows)
    _require_equal("E09 result", result, expected)


def verify_e10_result(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    result: E10SpacingComparisonResult,
) -> None:
    if not isinstance(result, E10SpacingComparisonResult):
        raise TypeError("result must be an E10SpacingComparisonResult")
    expected = run_e10_spacing_comparison(artifact, rows)
    _require_equal("E10 result", result, expected)


def verify_e11_result(
    artifact: TinyDevCorpusArtifact,
    rows: tuple[DevelopmentTransformRow, ...],
    result: E11GreedyComparisonResult,
) -> None:
    if not isinstance(result, E11GreedyComparisonResult):
        raise TypeError("result must be an E11GreedyComparisonResult")
    expected = run_e11_greedy_comparison(artifact, rows)
    _require_equal("E11 result", result, expected)
