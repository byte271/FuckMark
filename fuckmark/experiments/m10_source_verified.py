from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .m10_release_v3 import M10ReleaseManifest, build_m10_release_manifest as _build_m10_release_manifest
from .m6_source_verified import (
    M6ExperimentReplayInput,
    M6SourceVerifiedReadiness,
    verify_source_verified_m6_readiness,
)
from .power_analysis import PowerAnalysisInput, PowerAnalysisResult
from .registry import DevelopmentExperimentRegistry


M10_SOURCE_VERIFIED_ALGORITHM_VERSION = "m10-source-verified-m6-v1"


@dataclass(frozen=True, slots=True)
class M10SourceVerifiedReleaseManifest:
    algorithm_version: str
    m6_source_verified_bundle_hash: str
    m6_readiness_hash: str
    release_manifest: M10ReleaseManifest
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != M10_SOURCE_VERIFIED_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified M10 algorithm version")
        require_sha256("m6_source_verified_bundle_hash", self.m6_source_verified_bundle_hash)
        require_sha256("m6_readiness_hash", self.m6_readiness_hash)
        if not isinstance(self.release_manifest, M10ReleaseManifest):
            raise TypeError("release_manifest must be an M10ReleaseManifest")
        if self.release_manifest.m6_readiness_hash != self.m6_readiness_hash:
            raise ValueError("M10 release manifest does not bind the verified M6 readiness report")
        require_sha256("manifest_hash", self.manifest_hash)
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match source-verified M10 release manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "m6_source_verified_bundle_hash": self.m6_source_verified_bundle_hash,
            "m6_readiness_hash": self.m6_readiness_hash,
            "release_manifest": self.release_manifest,
        }


def build_source_verified_m10_release_manifest(
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
    preregistration: ConfirmatoryPreregistration,
    *release_args,
    **release_kwargs,
) -> M10SourceVerifiedReleaseManifest:
    if not isinstance(source_verified_m6, M6SourceVerifiedReadiness):
        raise TypeError("source_verified_m6 must be an M6SourceVerifiedReadiness")
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(m6_experiments, tuple):
        raise TypeError("m6_experiments must be a tuple")
    if any(not isinstance(value, M6ExperimentReplayInput) for value in m6_experiments):
        raise TypeError("m6_experiments must contain M6ExperimentReplayInput values")
    if not isinstance(power_input, PowerAnalysisInput):
        raise TypeError("power_input must be a PowerAnalysisInput")
    if not isinstance(power_result, PowerAnalysisResult):
        raise TypeError("power_result must be a PowerAnalysisResult")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")

    verify_source_verified_m6_readiness(
        source_verified_m6,
        registry,
        m6_experiments,
        power_input,
        power_result,
    )

    release_manifest = _build_m10_release_manifest(
        preregistration,
        source_verified_m6.readiness,
        *release_args,
        **release_kwargs,
    )
    if release_manifest.m6_readiness_hash != source_verified_m6.readiness.readiness_hash:
        raise ValueError("M10 release builder returned a manifest outside the source-verified M6 chain")

    payload = {
        "algorithm_version": M10_SOURCE_VERIFIED_ALGORITHM_VERSION,
        "m6_source_verified_bundle_hash": source_verified_m6.bundle_hash,
        "m6_readiness_hash": source_verified_m6.readiness.readiness_hash,
        "release_manifest": release_manifest,
    }
    return M10SourceVerifiedReleaseManifest(
        M10_SOURCE_VERIFIED_ALGORITHM_VERSION,
        source_verified_m6.bundle_hash,
        source_verified_m6.readiness.readiness_hash,
        release_manifest,
        sha256_json(payload),
    )


def verify_source_verified_m10_release_manifest(
    manifest: M10SourceVerifiedReleaseManifest,
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
    preregistration: ConfirmatoryPreregistration,
    *release_args,
    **release_kwargs,
) -> None:
    if not isinstance(manifest, M10SourceVerifiedReleaseManifest):
        raise TypeError("manifest must be an M10SourceVerifiedReleaseManifest")
    expected = build_source_verified_m10_release_manifest(
        source_verified_m6,
        registry,
        m6_experiments,
        power_input,
        power_result,
        preregistration,
        *release_args,
        **release_kwargs,
    )
    if manifest != expected:
        raise ValueError("source-verified M10 release manifest does not replay exactly from M6 and release evidence")
