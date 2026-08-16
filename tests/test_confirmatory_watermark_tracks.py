from dataclasses import replace

import pytest

from confirmatory_helpers import confirmatory_watermark_tracks, preregistration_inputs
from fuckmark.adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from fuckmark.experiments.confirmatory_tracks import (
    ConfirmatoryWatermarkTrack,
    ConfirmatoryWatermarkTrackError,
    build_confirmatory_watermark_track_manifest,
    verify_confirmatory_watermark_track_manifest,
)
from fuckmark.hashing import sha256_text


def _identities(inputs):
    return tuple(value.detector_identity for value in inputs.calibration_bundles)


def test_confirmatory_watermark_tracks_replay_against_preregistered_sources_and_detectors() -> None:
    inputs = preregistration_inputs()
    manifest = confirmatory_watermark_tracks()
    verify_confirmatory_watermark_track_manifest(
        manifest,
        inputs.source_pins,
        _identities(inputs),
    )


def test_confirmatory_watermark_track_rejects_source_pin_outside_preregistration() -> None:
    inputs = preregistration_inputs()
    manifest = confirmatory_watermark_tracks()
    first = manifest.tracks[0]
    outside_pin = replace(DEEPMIND_REFERENCE_SOURCE_PIN, commit="f" * 40)
    forged = ConfirmatoryWatermarkTrack.create(
        first.watermark_config_hash,
        first.adapter_id,
        first.adapter_algorithm_version,
        first.adapter_config_hash,
        outside_pin,
    )
    changed = build_confirmatory_watermark_track_manifest((forged, *manifest.tracks[1:]))
    with pytest.raises(ConfirmatoryWatermarkTrackError, match="source pin outside"):
        verify_confirmatory_watermark_track_manifest(
            changed,
            inputs.source_pins,
            _identities(inputs),
        )


def test_confirmatory_watermark_track_rejects_adapter_config_without_calibrated_identity() -> None:
    inputs = preregistration_inputs()
    manifest = confirmatory_watermark_tracks()
    first = manifest.tracks[0]
    forged = ConfirmatoryWatermarkTrack.create(
        first.watermark_config_hash,
        first.adapter_id,
        first.adapter_algorithm_version,
        sha256_text("different-adapter-configuration"),
        first.source_pin,
    )
    changed = build_confirmatory_watermark_track_manifest((forged, *manifest.tracks[1:]))
    with pytest.raises(ConfirmatoryWatermarkTrackError, match="no source-compatible calibrated detector"):
        verify_confirmatory_watermark_track_manifest(
            changed,
            inputs.source_pins,
            _identities(inputs),
        )
