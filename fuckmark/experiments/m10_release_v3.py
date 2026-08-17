from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from .m10_release_v2 import (
    M10ReleaseError,
    M10ReleaseStatus,
    build_m10_release_manifest as _build_m10_release_manifest_v2,
)


M10_RELEASE_ALGORITHM_VERSION = "m10-release-readiness-v3"


@dataclass(frozen=True, slots=True)
class M10ReleaseManifest:
    algorithm_version: str
    release_code_commit: str
    preregistration_hash: str
    m6_readiness_hash: str
    detector_readiness_hash: str
    test_key_manifest_hash: str
    e20_corpus_manifest_hash: str
    e20_authorization_hash: str
    e20_result_bundle_hash: str
    e20_aggregate_hash: str
    e20_inference_hash: str
    e20_report_hash: str
    e20_fidelity_summary_hash: str
    e21_corpus_manifest_hash: str
    e21_rerun_seal_hash: str
    e21_authorization_hash: str
    e21_result_bundle_hash: str
    e21_analysis_hash: str
    e21_inference_hash: str
    e21_fidelity_summary_hash: str
    e21_replication_hash: str
    limitations: tuple[str, ...]
    status: M10ReleaseStatus
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != M10_RELEASE_ALGORITHM_VERSION:
            raise ValueError("unsupported M10 release manifest algorithm version")
        require_clean_string("release_code_commit", self.release_code_commit)
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("m6_readiness_hash", self.m6_readiness_hash),
            ("detector_readiness_hash", self.detector_readiness_hash),
            ("test_key_manifest_hash", self.test_key_manifest_hash),
            ("e20_corpus_manifest_hash", self.e20_corpus_manifest_hash),
            ("e20_authorization_hash", self.e20_authorization_hash),
            ("e20_result_bundle_hash", self.e20_result_bundle_hash),
            ("e20_aggregate_hash", self.e20_aggregate_hash),
            ("e20_inference_hash", self.e20_inference_hash),
            ("e20_report_hash", self.e20_report_hash),
            ("e20_fidelity_summary_hash", self.e20_fidelity_summary_hash),
            ("e21_corpus_manifest_hash", self.e21_corpus_manifest_hash),
            ("e21_rerun_seal_hash", self.e21_rerun_seal_hash),
            ("e21_authorization_hash", self.e21_authorization_hash),
            ("e21_result_bundle_hash", self.e21_result_bundle_hash),
            ("e21_analysis_hash", self.e21_analysis_hash),
            ("e21_inference_hash", self.e21_inference_hash),
            ("e21_fidelity_summary_hash", self.e21_fidelity_summary_hash),
            ("e21_replication_hash", self.e21_replication_hash),
            ("manifest_hash", self.manifest_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be a tuple")
        for value in self.limitations:
            require_clean_string("limitation", value)
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("limitations must be unique and canonically ordered")
        if not isinstance(self.status, M10ReleaseStatus):
            raise TypeError("status must be an M10ReleaseStatus")
        if self.status is M10ReleaseStatus.READY_COMPLETE and self.limitations:
            raise ValueError("complete M10 release cannot carry limitations")
        if self.status is M10ReleaseStatus.READY_WITH_LIMITATIONS and not self.limitations:
            raise ValueError("limited M10 release requires explicit limitations")
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match M10 release manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "release_code_commit": self.release_code_commit,
            "preregistration_hash": self.preregistration_hash,
            "m6_readiness_hash": self.m6_readiness_hash,
            "detector_readiness_hash": self.detector_readiness_hash,
            "test_key_manifest_hash": self.test_key_manifest_hash,
            "e20_corpus_manifest_hash": self.e20_corpus_manifest_hash,
            "e20_authorization_hash": self.e20_authorization_hash,
            "e20_result_bundle_hash": self.e20_result_bundle_hash,
            "e20_aggregate_hash": self.e20_aggregate_hash,
            "e20_inference_hash": self.e20_inference_hash,
            "e20_report_hash": self.e20_report_hash,
            "e20_fidelity_summary_hash": self.e20_fidelity_summary_hash,
            "e21_corpus_manifest_hash": self.e21_corpus_manifest_hash,
            "e21_rerun_seal_hash": self.e21_rerun_seal_hash,
            "e21_authorization_hash": self.e21_authorization_hash,
            "e21_result_bundle_hash": self.e21_result_bundle_hash,
            "e21_analysis_hash": self.e21_analysis_hash,
            "e21_inference_hash": self.e21_inference_hash,
            "e21_fidelity_summary_hash": self.e21_fidelity_summary_hash,
            "e21_replication_hash": self.e21_replication_hash,
            "limitations": self.limitations,
            "status": self.status.value,
        }


def build_m10_release_manifest(*args, **kwargs) -> M10ReleaseManifest:
    verified = _build_m10_release_manifest_v2(*args, **kwargs)
    payload = {
        "algorithm_version": M10_RELEASE_ALGORITHM_VERSION,
        "release_code_commit": verified.release_code_commit,
        "preregistration_hash": verified.preregistration_hash,
        "m6_readiness_hash": verified.m6_readiness_hash,
        "detector_readiness_hash": verified.detector_readiness_hash,
        "test_key_manifest_hash": verified.test_key_manifest_hash,
        "e20_corpus_manifest_hash": verified.e20_corpus_manifest_hash,
        "e20_authorization_hash": verified.e20_authorization_hash,
        "e20_result_bundle_hash": verified.e20_result_bundle_hash,
        "e20_aggregate_hash": verified.e20_aggregate_hash,
        "e20_inference_hash": verified.e20_inference_hash,
        "e20_report_hash": verified.e20_report_hash,
        "e20_fidelity_summary_hash": verified.e20_fidelity_summary_hash,
        "e21_corpus_manifest_hash": verified.e21_corpus_manifest_hash,
        "e21_rerun_seal_hash": verified.e21_rerun_seal_hash,
        "e21_authorization_hash": verified.e21_authorization_hash,
        "e21_result_bundle_hash": verified.e21_result_bundle_hash,
        "e21_analysis_hash": verified.e21_analysis_hash,
        "e21_inference_hash": verified.e21_inference_hash,
        "e21_fidelity_summary_hash": verified.e21_fidelity_summary_hash,
        "e21_replication_hash": verified.e21_replication_hash,
        "limitations": verified.limitations,
        "status": verified.status.value,
    }
    return M10ReleaseManifest(
        M10_RELEASE_ALGORITHM_VERSION,
        verified.release_code_commit,
        verified.preregistration_hash,
        verified.m6_readiness_hash,
        verified.detector_readiness_hash,
        verified.test_key_manifest_hash,
        verified.e20_corpus_manifest_hash,
        verified.e20_authorization_hash,
        verified.e20_result_bundle_hash,
        verified.e20_aggregate_hash,
        verified.e20_inference_hash,
        verified.e20_report_hash,
        verified.e20_fidelity_summary_hash,
        verified.e21_corpus_manifest_hash,
        verified.e21_rerun_seal_hash,
        verified.e21_authorization_hash,
        verified.e21_result_bundle_hash,
        verified.e21_analysis_hash,
        verified.e21_inference_hash,
        verified.e21_fidelity_summary_hash,
        verified.e21_replication_hash,
        verified.limitations,
        verified.status,
        sha256_json(payload),
    )
