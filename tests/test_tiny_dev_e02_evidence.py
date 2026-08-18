from dataclasses import replace

import pytest

from fuckmark.detectors import DetectorFamily
from fuckmark.experiments.e02_pristine import E02Status
from fuckmark.experiments.tiny_dev_detector_evidence import build_tiny_dev_detector_evidence
from fuckmark.experiments.tiny_dev_e02_evidence import (
    TINY_DEV_E02_SCIENTIFIC_STATUS,
    build_tiny_dev_e02_evidence,
)

from test_tiny_dev_detector_evidence import _WATERMARK_HASH, _adapter, _artifact


def _e02():
    corpus = _artifact()
    detector = build_tiny_dev_detector_evidence(
        corpus,
        _adapter(),
        expected_watermark_config_hash=_WATERMARK_HASH,
    )
    return corpus, detector, build_tiny_dev_e02_evidence(corpus, detector)


def test_tiny_dev_e02_replays_detector_rows_through_canonical_e02_gate() -> None:
    corpus, detector, evidence = _e02()
    assert evidence.tiny_dev_artifact_hash == corpus.artifact_hash
    assert evidence.corpus_manifest_hash == corpus.manifest.manifest_hash
    assert evidence.detector_artifact_hash == detector.artifact_hash
    assert evidence.scientific_status == TINY_DEV_E02_SCIENTIFIC_STATUS
    assert tuple(value.detector_family for value in evidence.families) == (
        DetectorFamily.MEAN,
        DetectorFamily.WEIGHTED_MEAN,
    )
    for source, family in zip(detector.family_evidence, evidence.families):
        assert family.detector_source_family_hash == source.family_hash
        assert family.calibration_binding.tiny_dev_artifact_hash == corpus.artifact_hash
        assert family.calibration_binding.calibration_bundle.negative_count == 100
        assert family.calibration_binding.calibration_bundle.scope.token_track == "generation"
        assert family.calibration_binding.calibration_bundle.scope.prompt_boundary_mode == "continuation_only"
        assert family.result.calibration_binding_hash == family.calibration_binding.binding_hash
        assert family.result.status in (E02Status.PASS, E02Status.UNDERPOWERED)
        assert tuple(value.target_fpr for value in family.result.operating_points) == (0.05, 0.01)
        assert family.result.result_hash


def test_tiny_dev_e02_is_tamper_evident() -> None:
    _, _, evidence = _e02()
    with pytest.raises(ValueError, match="artifact_hash"):
        replace(evidence, artifact_hash="0" * 64)
    with pytest.raises(ValueError, match="family_hash"):
        replace(evidence.families[0], family_hash="0" * 64)


def test_tiny_dev_e02_keeps_source_detector_artifact_immutable() -> None:
    _, detector, evidence = _e02()
    for source, family in zip(detector.family_evidence, evidence.families):
        assert family.detector_source_family_hash == source.family_hash
        assert family.calibration_binding.calibration_bundle.bundle_hash != source.calibration_bundle.bundle_hash
        assert tuple(value.value for value in (source.detector_family, family.detector_family)) == (
            source.detector_family.value,
            source.detector_family.value,
        )
