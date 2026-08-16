from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_sha256
from ..detectors import DetectorFamily
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration


CONFIRMATORY_DETECTOR_READINESS_ALGORITHM_VERSION = "confirmatory-detector-readiness-v1"
_REQUIRED_BASELINE_FAMILIES = (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN)
_REQUIRED_GLOBAL_FAMILIES = (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN, DetectorFamily.BAYESIAN)


class ConfirmatoryDetectorReadinessStatus(str, Enum):
    READY = "READY"
    MISSING_REQUIRED_DETECTORS = "MISSING_REQUIRED_DETECTORS"


@dataclass(frozen=True, slots=True)
class ConfirmatoryTrackDetectorReadiness:
    watermark_config_hash: str
    available_families: tuple[DetectorFamily, ...]
    missing_baseline_families: tuple[DetectorFamily, ...]

    def __post_init__(self) -> None:
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        if not isinstance(self.available_families, tuple):
            raise TypeError("available_families must be a tuple")
        if not isinstance(self.missing_baseline_families, tuple):
            raise TypeError("missing_baseline_families must be a tuple")
        expected_available = tuple(sorted(self.available_families, key=lambda value: value.value))
        expected_missing = tuple(sorted(self.missing_baseline_families, key=lambda value: value.value))
        if self.available_families != expected_available:
            raise ValueError("available detector families must be canonically ordered")
        if self.missing_baseline_families != expected_missing:
            raise ValueError("missing detector families must be canonically ordered")
        if any(not isinstance(value, DetectorFamily) for value in self.available_families):
            raise TypeError("available_families must contain DetectorFamily values")
        if any(not isinstance(value, DetectorFamily) for value in self.missing_baseline_families):
            raise TypeError("missing_baseline_families must contain DetectorFamily values")
        if len(set(self.available_families)) != len(self.available_families):
            raise ValueError("available detector families must be unique")
        if len(set(self.missing_baseline_families)) != len(self.missing_baseline_families):
            raise ValueError("missing detector families must be unique")


@dataclass(frozen=True, slots=True)
class ConfirmatoryDetectorReadinessReport:
    algorithm_version: str
    preregistration_hash: str
    tracks: tuple[ConfirmatoryTrackDetectorReadiness, ...]
    global_available_families: tuple[DetectorFamily, ...]
    global_missing_families: tuple[DetectorFamily, ...]
    status: ConfirmatoryDetectorReadinessStatus
    ready_for_e20: bool
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CONFIRMATORY_DETECTOR_READINESS_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory detector readiness algorithm version")
        require_sha256("preregistration_hash", self.preregistration_hash)
        if not isinstance(self.tracks, tuple) or not self.tracks:
            raise TypeError("tracks must be a non-empty tuple")
        if any(not isinstance(value, ConfirmatoryTrackDetectorReadiness) for value in self.tracks):
            raise TypeError("tracks must contain ConfirmatoryTrackDetectorReadiness values")
        expected_tracks = tuple(sorted(self.tracks, key=lambda value: value.watermark_config_hash))
        if self.tracks != expected_tracks:
            raise ValueError("track detector readiness rows must be canonically ordered")
        if len({value.watermark_config_hash for value in self.tracks}) != len(self.tracks):
            raise ValueError("track detector readiness rows must be unique")
        for name, values in (
            ("global_available_families", self.global_available_families),
            ("global_missing_families", self.global_missing_families),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if values != tuple(sorted(values, key=lambda value: value.value)):
                raise ValueError(f"{name} must be canonically ordered")
            if any(not isinstance(value, DetectorFamily) for value in values):
                raise TypeError(f"{name} must contain DetectorFamily values")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must contain unique detector families")
        if not isinstance(self.status, ConfirmatoryDetectorReadinessStatus):
            raise TypeError("status must be a ConfirmatoryDetectorReadinessStatus")
        require_bool("ready_for_e20", self.ready_for_e20)
        expected_ready = (
            not self.global_missing_families
            and all(not value.missing_baseline_families for value in self.tracks)
        )
        if self.ready_for_e20 != expected_ready:
            raise ValueError("ready_for_e20 does not match detector coverage")
        expected_status = (
            ConfirmatoryDetectorReadinessStatus.READY
            if expected_ready
            else ConfirmatoryDetectorReadinessStatus.MISSING_REQUIRED_DETECTORS
        )
        if self.status is not expected_status:
            raise ValueError("detector readiness status does not match detector coverage")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match confirmatory detector readiness")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "tracks": self.tracks,
            "global_available_families": tuple(value.value for value in self.global_available_families),
            "global_missing_families": tuple(value.value for value in self.global_missing_families),
            "status": self.status.value,
            "ready_for_e20": self.ready_for_e20,
        }


def build_confirmatory_detector_readiness(
    preregistration: ConfirmatoryPreregistration,
) -> ConfirmatoryDetectorReadinessReport:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    rows: list[ConfirmatoryTrackDetectorReadiness] = []
    global_available: set[DetectorFamily] = set()
    for track in preregistration.watermark_tracks.tracks:
        available = {
            bundle.detector_identity.detector_family
            for bundle in preregistration.calibration_bundles
            if track.matches_detector_identity(bundle.detector_identity)
        }
        global_available.update(available)
        missing = set(_REQUIRED_BASELINE_FAMILIES) - available
        rows.append(
            ConfirmatoryTrackDetectorReadiness(
                track.watermark_config_hash,
                tuple(sorted(available, key=lambda value: value.value)),
                tuple(sorted(missing, key=lambda value: value.value)),
            )
        )
    global_missing = set(_REQUIRED_GLOBAL_FAMILIES) - global_available
    ordered_rows = tuple(sorted(rows, key=lambda value: value.watermark_config_hash))
    available_tuple = tuple(sorted(global_available, key=lambda value: value.value))
    missing_tuple = tuple(sorted(global_missing, key=lambda value: value.value))
    ready = not missing_tuple and all(not value.missing_baseline_families for value in ordered_rows)
    status = (
        ConfirmatoryDetectorReadinessStatus.READY
        if ready
        else ConfirmatoryDetectorReadinessStatus.MISSING_REQUIRED_DETECTORS
    )
    payload = {
        "algorithm_version": CONFIRMATORY_DETECTOR_READINESS_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "tracks": ordered_rows,
        "global_available_families": tuple(value.value for value in available_tuple),
        "global_missing_families": tuple(value.value for value in missing_tuple),
        "status": status.value,
        "ready_for_e20": ready,
    }
    return ConfirmatoryDetectorReadinessReport(
        CONFIRMATORY_DETECTOR_READINESS_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        ordered_rows,
        available_tuple,
        missing_tuple,
        status,
        ready,
        sha256_json(payload),
    )


def verify_confirmatory_detector_readiness(
    report: ConfirmatoryDetectorReadinessReport,
    preregistration: ConfirmatoryPreregistration,
) -> None:
    if not isinstance(report, ConfirmatoryDetectorReadinessReport):
        raise TypeError("report must be a ConfirmatoryDetectorReadinessReport")
    expected = build_confirmatory_detector_readiness(preregistration)
    if report != expected:
        raise ValueError("confirmatory detector readiness does not replay exactly from preregistration")
