from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_detector_readiness import (
    ConfirmatoryDetectorReadinessReport,
    verify_confirmatory_detector_readiness,
)
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_aggregate import E20AggregateBundle
from .e20_bundle import E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    E20RunState,
    verify_e20_run_ledger,
)
from .e20_human_audit import E20HumanAuditSelection
from .e20_inference import E20InferenceBundle
from .e20_key_analysis import E20KeyAnalysisBundle
from .e20_report import (
    E20ConfirmatoryReport,
    E20ReportStatus,
    verify_e20_confirmatory_report,
)
from .e21_analysis import E21PrimaryAnalysis, verify_e21_primary_analysis
from .e21_bundle import E21ResultBundle, verify_e21_result_bundle
from .e21_execution import E21RunLedger, E21RunState, verify_e21_run_ledger
from .e21_fidelity_summary import build_verified_e21_fidelity_summary
from .e21_human_audit import E21HumanAuditSelection
from .e21_inference import E21PrimaryInference, verify_e21_primary_inference
from .e21_replication import E21ReplicationStatus
from .e21_replication_verified import (
    E21VerifiedReplicationBundle,
    verify_verified_e21_replication_bundle,
)
from .e21_rerun import E21ExecutionAuthorization, E21RerunSeal, verify_e21_rerun_seal
from .m6_readiness import M6ReadinessReport, verify_m6_readiness
from .registry import default_development_experiment_registry


M10_RELEASE_ALGORITHM_VERSION = "m10-release-readiness-v2"


class M10ReleaseStatus(str, Enum):
    READY_COMPLETE = "READY_COMPLETE"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"


class M10ReleaseError(ValueError):
    pass


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


def build_m10_release_manifest(
    preregistration: ConfirmatoryPreregistration,
    m6_readiness: M6ReadinessReport,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    condition_plan: E20ConditionPlan,
    e20_authorization: E20ExecutionAuthorization,
    e20_completed_ledger: E20RunLedger,
    e20_corpus_manifest: CorpusManifest,
    e20_result_bundle: E20ResultBundle,
    e20_aggregate: E20AggregateBundle,
    e20_key_analysis: E20KeyAnalysisBundle,
    e20_inference: E20InferenceBundle,
    e20_report: E20ConfirmatoryReport,
    e21_rerun_seal: E21RerunSeal,
    e21_authorization: E21ExecutionAuthorization,
    e21_started_ledger: E21RunLedger,
    e21_completed_ledger: E21RunLedger,
    e21_corpus_manifest: CorpusManifest,
    e21_result_bundle: E21ResultBundle,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_replication: E21VerifiedReplicationBundle,
    *,
    release_code_commit: str,
    limitations: tuple[str, ...] = (),
    human_audit_selection: E20HumanAuditSelection | None = None,
    human_audit_evidence: BlindHumanFidelityAudit | None = None,
    e21_human_audit_selection: E21HumanAuditSelection | None = None,
    e21_human_audit_evidence: BlindHumanFidelityAudit | None = None,
) -> M10ReleaseManifest:
    if not isinstance(m6_readiness, M6ReadinessReport):
        raise TypeError("m6_readiness must be an M6ReadinessReport")
    registry = default_development_experiment_registry()
    verify_m6_readiness(
        m6_readiness,
        registry,
        m6_readiness.evidence,
        m6_readiness.power_analysis,
    )
    if not m6_readiness.ready_for_m7:
        raise M10ReleaseError("M10 release is blocked until M6 validation and power analysis are READY")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    verify_confirmatory_detector_readiness(detector_readiness, preregistration)
    if not detector_readiness.ready_for_e20:
        raise M10ReleaseError("M10 release is blocked until confirmatory detector readiness is complete")
    require_clean_string("release_code_commit", release_code_commit)
    if release_code_commit != preregistration.code_commit:
        raise M10ReleaseError("M10 release code commit must equal the frozen preregistration code commit")
    if e20_authorization.code_commit != release_code_commit:
        raise M10ReleaseError("E20 authorization code commit differs from the M10 release commit")
    if e21_authorization.code_commit != release_code_commit:
        raise M10ReleaseError("E21 authorization code commit differs from the M10 release commit")
    verify_e20_run_ledger(e20_completed_ledger, e20_authorization)
    if e20_completed_ledger.state is not E20RunState.COMPLETED:
        raise M10ReleaseError("M10 release requires a completed non-invalidated E20 run")
    if e20_completed_ledger.events[-1].artifact_hash != e20_result_bundle.bundle_hash:
        raise M10ReleaseError("completed E20 ledger does not bind the supplied result bundle")
    verify_e20_confirmatory_report(
        e20_report,
        e20_result_bundle,
        e20_aggregate,
        e20_key_analysis,
        e20_inference,
        detector_readiness,
        preregistration,
        e20_corpus_manifest,
        condition_plan,
        e20_authorization,
        human_audit_selection,
        human_audit_evidence,
    )
    if not e20_report.human_fidelity.audit_verified:
        raise M10ReleaseError("M10 release requires replay-verified E20 blind human fidelity evidence")
    verify_e21_rerun_seal(
        e21_rerun_seal,
        preregistration,
        e20_authorization,
        e20_completed_ledger,
        e20_corpus_manifest,
        e21_corpus_manifest,
        test_key_manifest,
    )
    verify_e21_run_ledger(e21_started_ledger, e21_authorization)
    if e21_started_ledger.state is not E21RunState.STARTED:
        raise M10ReleaseError("E21 source analysis requires the frozen STARTED ledger")
    verify_e21_result_bundle(
        e21_result_bundle,
        e21_authorization,
        e21_started_ledger,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
    )
    verify_e21_run_ledger(e21_completed_ledger, e21_authorization)
    if e21_completed_ledger.state is not E21RunState.COMPLETED:
        raise M10ReleaseError("M10 release requires a completed non-invalidated E21 run")
    if e21_completed_ledger.events[-1].artifact_hash != e21_result_bundle.bundle_hash:
        raise M10ReleaseError("completed E21 ledger does not bind the supplied result bundle")
    verify_e21_primary_analysis(
        e21_analysis,
        e21_result_bundle,
        e21_authorization,
        e21_started_ledger,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
    )
    verify_e21_primary_inference(
        e21_inference,
        e21_result_bundle,
        e21_analysis,
        e21_authorization,
        e21_started_ledger,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
    )
    if e21_human_audit_selection is None or e21_human_audit_evidence is None:
        raise M10ReleaseError("M10 release requires replay-verified E21 blind human fidelity evidence")
    e21_fidelity = build_verified_e21_fidelity_summary(
        e21_human_audit_selection,
        e21_human_audit_evidence,
        e21_result_bundle,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
    )
    verify_verified_e21_replication_bundle(
        e21_replication,
        e20_report,
        e21_authorization,
        e21_rerun_seal,
        e21_completed_ledger,
        e21_analysis,
        e21_inference,
        e21_result_bundle,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
        e21_human_audit_selection,
        e21_human_audit_evidence,
    )
    if e21_replication.e21_fidelity_summary_hash != e21_fidelity.summary_hash:
        raise M10ReleaseError("E21 verified replication does not bind the release fidelity summary")
    ordered_limitations = tuple(sorted(set(limitations)))
    for value in ordered_limitations:
        require_clean_string("limitation", value)
    complete = (
        e20_report.status is E20ReportStatus.CONFIRMATORY_EVALUABLE
        and e20_report.human_fidelity.gate_passed
        and e21_fidelity.gate_passed
        and e21_replication.comparison.status is E21ReplicationStatus.DESCRIPTIVE_COMPLETE
    )
    if complete:
        if ordered_limitations:
            raise M10ReleaseError("complete M10 release cannot add post hoc limitations")
        status = M10ReleaseStatus.READY_COMPLETE
    else:
        if not ordered_limitations:
            raise M10ReleaseError(
                "scientifically incomplete M10 release requires explicit frozen limitations"
            )
        status = M10ReleaseStatus.READY_WITH_LIMITATIONS
    payload = {
        "algorithm_version": M10_RELEASE_ALGORITHM_VERSION,
        "release_code_commit": release_code_commit,
        "preregistration_hash": preregistration.preregistration_hash,
        "m6_readiness_hash": m6_readiness.report_hash,
        "detector_readiness_hash": detector_readiness.report_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "e20_corpus_manifest_hash": e20_corpus_manifest.manifest_hash,
        "e20_authorization_hash": e20_authorization.authorization_hash,
        "e20_result_bundle_hash": e20_result_bundle.bundle_hash,
        "e20_aggregate_hash": e20_aggregate.aggregate_hash,
        "e20_inference_hash": e20_inference.bundle_hash,
        "e20_report_hash": e20_report.report_hash,
        "e20_fidelity_summary_hash": e20_report.human_fidelity.summary_hash,
        "e21_corpus_manifest_hash": e21_corpus_manifest.manifest_hash,
        "e21_rerun_seal_hash": e21_rerun_seal.seal_hash,
        "e21_authorization_hash": e21_authorization.authorization_hash,
        "e21_result_bundle_hash": e21_result_bundle.bundle_hash,
        "e21_analysis_hash": e21_analysis.analysis_hash,
        "e21_inference_hash": e21_inference.inference_hash,
        "e21_fidelity_summary_hash": e21_fidelity.summary_hash,
        "e21_replication_hash": e21_replication.bundle_hash,
        "limitations": ordered_limitations,
        "status": status.value,
    }
    return M10ReleaseManifest(
        M10_RELEASE_ALGORITHM_VERSION,
        release_code_commit,
        preregistration.preregistration_hash,
        m6_readiness.report_hash,
        detector_readiness.report_hash,
        test_key_manifest.manifest_hash,
        e20_corpus_manifest.manifest_hash,
        e20_authorization.authorization_hash,
        e20_result_bundle.bundle_hash,
        e20_aggregate.aggregate_hash,
        e20_inference.bundle_hash,
        e20_report.report_hash,
        e20_report.human_fidelity.summary_hash,
        e21_corpus_manifest.manifest_hash,
        e21_rerun_seal.seal_hash,
        e21_authorization.authorization_hash,
        e21_result_bundle.bundle_hash,
        e21_analysis.analysis_hash,
        e21_inference.inference_hash,
        e21_fidelity.summary_hash,
        e21_replication.bundle_hash,
        ordered_limitations,
        status,
        sha256_json(payload),
    )
