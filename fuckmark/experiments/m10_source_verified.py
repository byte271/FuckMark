from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_source_verified_authorization import E20SourceVerifiedAuthorization
from .e21_source_verified_rerun import E21SourceVerifiedAuthorization, E21SourceVerifiedRerunSeal
from .m10_release_v3 import M10ReleaseManifest, build_m10_release_manifest as _build_m10_release_manifest
from .m6_source_verified import M6ExperimentReplayInput, M6SourceVerifiedReadiness, verify_source_verified_m6_readiness
from .power_analysis import PowerAnalysisInput, PowerAnalysisResult
from .registry import DevelopmentExperimentRegistry


M10_SOURCE_VERIFIED_ALGORITHM_VERSION = "m10-source-verified-chain-v3"


@dataclass(frozen=True, slots=True)
class M10SourceVerifiedReleaseManifest:
    algorithm_version: str
    m6_source_verified_bundle_hash: str
    m6_readiness_hash: str
    e20_source_verified_authorization_hash: str
    e20_authorization_hash: str
    e21_source_verified_rerun_seal_hash: str
    e21_rerun_seal_hash: str
    e21_source_verified_authorization_hash: str
    e21_authorization_hash: str
    release_manifest: M10ReleaseManifest
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != M10_SOURCE_VERIFIED_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified M10 algorithm version")
        for name, value in (
            ("m6_source_verified_bundle_hash", self.m6_source_verified_bundle_hash),
            ("m6_readiness_hash", self.m6_readiness_hash),
            ("e20_source_verified_authorization_hash", self.e20_source_verified_authorization_hash),
            ("e20_authorization_hash", self.e20_authorization_hash),
            ("e21_source_verified_rerun_seal_hash", self.e21_source_verified_rerun_seal_hash),
            ("e21_rerun_seal_hash", self.e21_rerun_seal_hash),
            ("e21_source_verified_authorization_hash", self.e21_source_verified_authorization_hash),
            ("e21_authorization_hash", self.e21_authorization_hash),
            ("manifest_hash", self.manifest_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.release_manifest, M10ReleaseManifest):
            raise TypeError("release_manifest must be an M10ReleaseManifest")
        if self.release_manifest.m6_readiness_hash != self.m6_readiness_hash:
            raise ValueError("M10 release manifest does not bind the verified M6 readiness report")
        if self.release_manifest.e20_authorization_hash != self.e20_authorization_hash:
            raise ValueError("M10 release manifest does not bind the source-verified E20 authorization")
        if self.release_manifest.e21_rerun_seal_hash != self.e21_rerun_seal_hash:
            raise ValueError("M10 release manifest does not bind the source-verified E21 rerun seal")
        if self.release_manifest.e21_authorization_hash != self.e21_authorization_hash:
            raise ValueError("M10 release manifest does not bind the source-verified E21 authorization")
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match source-verified M10 release manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "m6_source_verified_bundle_hash": self.m6_source_verified_bundle_hash,
            "m6_readiness_hash": self.m6_readiness_hash,
            "e20_source_verified_authorization_hash": self.e20_source_verified_authorization_hash,
            "e20_authorization_hash": self.e20_authorization_hash,
            "e21_source_verified_rerun_seal_hash": self.e21_source_verified_rerun_seal_hash,
            "e21_rerun_seal_hash": self.e21_rerun_seal_hash,
            "e21_source_verified_authorization_hash": self.e21_source_verified_authorization_hash,
            "e21_authorization_hash": self.e21_authorization_hash,
            "release_manifest": self.release_manifest,
        }


def _verify_e20_chain(e20: E20SourceVerifiedAuthorization, m6: M6SourceVerifiedReadiness, preregistration: ConfirmatoryPreregistration) -> None:
    if not isinstance(e20, E20SourceVerifiedAuthorization):
        raise TypeError("e20_source_verified_authorization must be an E20SourceVerifiedAuthorization")
    if e20.preregistration_hash != preregistration.preregistration_hash:
        raise ValueError("source-verified E20 authorization does not bind the release preregistration")
    if e20.m6_source_verified_bundle_hash != m6.bundle_hash:
        raise ValueError("source-verified E20 authorization does not bind the verified M6 bundle")
    if e20.m6_readiness_hash != m6.readiness.report_hash:
        raise ValueError("source-verified E20 authorization does not bind the verified M6 readiness report")
    if e20.power_evidence_hash != m6.power_evidence.evidence_hash:
        raise ValueError("source-verified E20 authorization does not bind the verified power evidence")


def _verify_e21_chain(e20: E20SourceVerifiedAuthorization, rerun: E21SourceVerifiedRerunSeal, authorization: E21SourceVerifiedAuthorization, preregistration: ConfirmatoryPreregistration) -> None:
    if not isinstance(rerun, E21SourceVerifiedRerunSeal):
        raise TypeError("e21_source_verified_rerun_seal must be an E21SourceVerifiedRerunSeal")
    if not isinstance(authorization, E21SourceVerifiedAuthorization):
        raise TypeError("e21_source_verified_authorization must be an E21SourceVerifiedAuthorization")
    if rerun.preregistration_hash != preregistration.preregistration_hash or authorization.preregistration_hash != preregistration.preregistration_hash:
        raise ValueError("source-verified E21 chain does not bind the release preregistration")
    if rerun.e20_source_verified_authorization_hash != e20.envelope_hash or authorization.e20_source_verified_authorization_hash != e20.envelope_hash:
        raise ValueError("source-verified E21 chain does not bind the verified E20 envelope")
    if rerun.e20_authorization_hash != e20.authorization.authorization_hash:
        raise ValueError("source-verified E21 rerun does not bind the verified raw E20 authorization")
    if authorization.source_verified_rerun_seal_hash != rerun.envelope_hash:
        raise ValueError("source-verified E21 authorization does not bind the verified rerun envelope")
    if authorization.rerun_seal_hash != rerun.rerun_seal.seal_hash:
        raise ValueError("source-verified E21 authorization does not bind the verified raw rerun seal")


def build_source_verified_m10_release_manifest(
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
    e21_source_verified_rerun_seal: E21SourceVerifiedRerunSeal,
    e21_source_verified_authorization: E21SourceVerifiedAuthorization,
    *release_args,
    **release_kwargs,
) -> M10SourceVerifiedReleaseManifest:
    if not isinstance(source_verified_m6, M6SourceVerifiedReadiness):
        raise TypeError("source_verified_m6 must be an M6SourceVerifiedReadiness")
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(m6_experiments, tuple) or any(not isinstance(value, M6ExperimentReplayInput) for value in m6_experiments):
        raise TypeError("m6_experiments must be a tuple of M6ExperimentReplayInput values")
    if not isinstance(power_input, PowerAnalysisInput):
        raise TypeError("power_input must be a PowerAnalysisInput")
    if not isinstance(power_result, PowerAnalysisResult):
        raise TypeError("power_result must be a PowerAnalysisResult")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")

    verify_source_verified_m6_readiness(source_verified_m6, registry, m6_experiments, power_input, power_result)
    if preregistration.power_analysis_hash != source_verified_m6.power_evidence.evidence_hash:
        raise ValueError("confirmatory preregistration does not bind the source-verified power analysis evidence")
    if preregistration.final_n_per_core_cell != source_verified_m6.power_evidence.final_n_per_core_cell:
        raise ValueError("confirmatory preregistration final N does not match source-verified power analysis")
    _verify_e20_chain(e20_source_verified_authorization, source_verified_m6, preregistration)
    _verify_e21_chain(e20_source_verified_authorization, e21_source_verified_rerun_seal, e21_source_verified_authorization, preregistration)

    release_manifest = _build_m10_release_manifest(preregistration, source_verified_m6.readiness, *release_args, **release_kwargs)
    if release_manifest.m6_readiness_hash != source_verified_m6.readiness.report_hash:
        raise ValueError("M10 release builder returned a manifest outside the source-verified M6 chain")
    if release_manifest.e20_authorization_hash != e20_source_verified_authorization.authorization.authorization_hash:
        raise ValueError("M10 release builder returned a manifest outside the source-verified E20 authorization chain")
    if release_manifest.e21_rerun_seal_hash != e21_source_verified_rerun_seal.rerun_seal.seal_hash:
        raise ValueError("M10 release builder returned a manifest outside the source-verified E21 rerun chain")
    if release_manifest.e21_authorization_hash != e21_source_verified_authorization.authorization.authorization_hash:
        raise ValueError("M10 release builder returned a manifest outside the source-verified E21 authorization chain")

    payload = {
        "algorithm_version": M10_SOURCE_VERIFIED_ALGORITHM_VERSION,
        "m6_source_verified_bundle_hash": source_verified_m6.bundle_hash,
        "m6_readiness_hash": source_verified_m6.readiness.report_hash,
        "e20_source_verified_authorization_hash": e20_source_verified_authorization.envelope_hash,
        "e20_authorization_hash": e20_source_verified_authorization.authorization.authorization_hash,
        "e21_source_verified_rerun_seal_hash": e21_source_verified_rerun_seal.envelope_hash,
        "e21_rerun_seal_hash": e21_source_verified_rerun_seal.rerun_seal.seal_hash,
        "e21_source_verified_authorization_hash": e21_source_verified_authorization.envelope_hash,
        "e21_authorization_hash": e21_source_verified_authorization.authorization.authorization_hash,
        "release_manifest": release_manifest,
    }
    return M10SourceVerifiedReleaseManifest(
        M10_SOURCE_VERIFIED_ALGORITHM_VERSION,
        source_verified_m6.bundle_hash,
        source_verified_m6.readiness.report_hash,
        e20_source_verified_authorization.envelope_hash,
        e20_source_verified_authorization.authorization.authorization_hash,
        e21_source_verified_rerun_seal.envelope_hash,
        e21_source_verified_rerun_seal.rerun_seal.seal_hash,
        e21_source_verified_authorization.envelope_hash,
        e21_source_verified_authorization.authorization.authorization_hash,
        release_manifest,
        sha256_json(payload),
    )


def verify_source_verified_m10_release_manifest(manifest: M10SourceVerifiedReleaseManifest, *args, **kwargs) -> None:
    if not isinstance(manifest, M10SourceVerifiedReleaseManifest):
        raise TypeError("manifest must be an M10SourceVerifiedReleaseManifest")
    expected = build_source_verified_m10_release_manifest(*args, **kwargs)
    if manifest != expected:
        raise ValueError("source-verified M10 release manifest does not replay exactly from M6, E20, E21, and release evidence")
