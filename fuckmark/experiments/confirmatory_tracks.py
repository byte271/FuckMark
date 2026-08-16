from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..detectors import DetectorCalibrationIdentity
from ..hashing import sha256_json
from ..types import SourcePin


CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION = "confirmatory-watermark-track-manifest-v1"


class ConfirmatoryWatermarkTrackError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfirmatoryWatermarkTrack:
    watermark_config_hash: str
    adapter_id: str
    adapter_algorithm_version: str
    adapter_config_hash: str
    source_pin: SourcePin
    track_hash: str

    def __post_init__(self) -> None:
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        if not isinstance(self.source_pin, SourcePin):
            raise TypeError("source_pin must be a SourcePin")
        require_sha256("track_hash", self.track_hash)
        if self.track_hash != sha256_json(self._payload()):
            raise ValueError("track_hash does not match confirmatory watermark track")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION,
            "watermark_config_hash": self.watermark_config_hash,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "adapter_config_hash": self.adapter_config_hash,
            "source_pin": self.source_pin,
        }

    @classmethod
    def create(
        cls,
        watermark_config_hash: str,
        adapter_id: str,
        adapter_algorithm_version: str,
        adapter_config_hash: str,
        source_pin: SourcePin,
    ) -> ConfirmatoryWatermarkTrack:
        payload = {
            "algorithm_version": CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION,
            "watermark_config_hash": watermark_config_hash,
            "adapter_id": adapter_id,
            "adapter_algorithm_version": adapter_algorithm_version,
            "adapter_config_hash": adapter_config_hash,
            "source_pin": source_pin,
        }
        return cls(
            watermark_config_hash,
            adapter_id,
            adapter_algorithm_version,
            adapter_config_hash,
            source_pin,
            sha256_json(payload),
        )

    def matches_detector_identity(self, identity: DetectorCalibrationIdentity) -> bool:
        if not isinstance(identity, DetectorCalibrationIdentity):
            raise TypeError("identity must be a DetectorCalibrationIdentity")
        return (
            identity.adapter_id == self.adapter_id
            and identity.adapter_algorithm_version == self.adapter_algorithm_version
            and identity.adapter_config_hash == self.adapter_config_hash
            and identity.source_id == self.source_pin.source_id
            and identity.source_commit == self.source_pin.commit
        )


@dataclass(frozen=True, slots=True)
class ConfirmatoryWatermarkTrackManifest:
    algorithm_version: str
    tracks: tuple[ConfirmatoryWatermarkTrack, ...]
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory watermark track manifest algorithm version")
        if not isinstance(self.tracks, tuple) or not self.tracks:
            raise TypeError("tracks must be a non-empty tuple")
        if any(not isinstance(value, ConfirmatoryWatermarkTrack) for value in self.tracks):
            raise TypeError("tracks must contain ConfirmatoryWatermarkTrack values")
        expected = tuple(sorted(self.tracks, key=lambda value: (value.watermark_config_hash, value.track_hash)))
        if self.tracks != expected:
            raise ValueError("confirmatory watermark tracks must be canonically ordered")
        config_hashes = tuple(value.watermark_config_hash for value in self.tracks)
        if len(set(config_hashes)) != len(config_hashes):
            raise ValueError("watermark_config_hash values must be unique across confirmatory tracks")
        track_hashes = tuple(value.track_hash for value in self.tracks)
        if len(set(track_hashes)) != len(track_hashes):
            raise ValueError("confirmatory watermark track hashes must be unique")
        require_sha256("manifest_hash", self.manifest_hash)
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match confirmatory watermark track manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "tracks": self.tracks,
        }

    def track_for(self, watermark_config_hash: str) -> ConfirmatoryWatermarkTrack:
        require_sha256("watermark_config_hash", watermark_config_hash)
        for value in self.tracks:
            if value.watermark_config_hash == watermark_config_hash:
                return value
        raise KeyError(watermark_config_hash)


def build_confirmatory_watermark_track_manifest(
    tracks: Sequence[ConfirmatoryWatermarkTrack],
) -> ConfirmatoryWatermarkTrackManifest:
    if not isinstance(tracks, Sequence) or isinstance(tracks, (str, bytes, bytearray)):
        raise TypeError("tracks must be a sequence")
    values = tuple(tracks)
    if not values:
        raise ValueError("tracks must not be empty")
    if any(not isinstance(value, ConfirmatoryWatermarkTrack) for value in values):
        raise TypeError("tracks must contain ConfirmatoryWatermarkTrack values")
    ordered = tuple(sorted(values, key=lambda value: (value.watermark_config_hash, value.track_hash)))
    payload = {
        "algorithm_version": CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION,
        "tracks": ordered,
    }
    return ConfirmatoryWatermarkTrackManifest(
        CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION,
        ordered,
        sha256_json(payload),
    )


def verify_confirmatory_watermark_track_manifest(
    manifest: ConfirmatoryWatermarkTrackManifest,
    source_pins: Sequence[SourcePin],
    detector_identities: Sequence[DetectorCalibrationIdentity],
) -> None:
    if not isinstance(manifest, ConfirmatoryWatermarkTrackManifest):
        raise TypeError("manifest must be a ConfirmatoryWatermarkTrackManifest")
    pins = tuple(source_pins)
    identities = tuple(detector_identities)
    if any(not isinstance(value, SourcePin) for value in pins):
        raise TypeError("source_pins must contain SourcePin values")
    if any(not isinstance(value, DetectorCalibrationIdentity) for value in identities):
        raise TypeError("detector_identities must contain DetectorCalibrationIdentity values")
    for track in manifest.tracks:
        if track.source_pin not in pins:
            raise ConfirmatoryWatermarkTrackError(
                "confirmatory watermark track uses a source pin outside the preregistration"
            )
        if not any(track.matches_detector_identity(identity) for identity in identities):
            raise ConfirmatoryWatermarkTrackError(
                "confirmatory watermark track has no source-compatible calibrated detector identity"
            )
    for identity in identities:
        if not any(track.matches_detector_identity(identity) for track in manifest.tracks):
            raise ConfirmatoryWatermarkTrackError(
                "confirmatory detector identity has no compatible sealed watermark track"
            )
