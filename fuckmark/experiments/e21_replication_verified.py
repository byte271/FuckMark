from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from ..transforms import BlindHumanFidelityAudit
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e20_report import E20ConfirmatoryReport
from .e21_analysis import E21PrimaryAnalysis
from .e21_bundle import E21ResultBundle
from .e21_execution import E21RunLedger, E21RunState, verify_e21_run_ledger
from .e21_fidelity_summary import E21VerifiedFidelitySummary, build_verified_e21_fidelity_summary
from .e21_fidelity_verified import build_fidelity_bound_e21_headline_evidence
from .e21_human_audit import E21HumanAuditSelection
from .e21_inference import E21PrimaryInference
from .e21_replication import (
    E21ReplicationComparison,
    E21ReplicationError,
    build_e21_replication_comparison as _build_from_evidence,
)
from .e21_rerun import E21ExecutionAuthorization, E21RerunSeal


E21_VERIFIED_REPLICATION_ALGORITHM_VERSION = "e21-verified-replication-v1"


@dataclass(frozen=True, slots=True)
class E21VerifiedReplicationBundle:
    algorithm_version: str
    e20_report_hash: str
    e21_execution_id: str
    e21_result_bundle_hash: str
    e21_analysis_hash: str
    e21_inference_hash: str
    e21_fidelity_summary_hash: str
    comparison: E21ReplicationComparison
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_VERIFIED_REPLICATION_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 verified replication algorithm version")
        for name, value in (
            ("e20_report_hash", self.e20_report_hash),
            ("e21_execution_id", self.e21_execution_id),
            ("e21_result_bundle_hash", self.e21_result_bundle_hash),
            ("e21_analysis_hash", self.e21_analysis_hash),
            ("e21_inference_hash", self.e21_inference_hash),
            ("e21_fidelity_summary_hash", self.e21_fidelity_summary_hash),
            ("bundle_hash", self.bundle_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.comparison, E21ReplicationComparison):
            raise TypeError("comparison must be an E21ReplicationComparison")
        if self.comparison.e20_report_hash != self.e20_report_hash:
            raise ValueError("verified E21 replication E20 report hash does not match comparison")
        if self.comparison.e21_execution_id != self.e21_execution_id:
            raise ValueError("verified E21 replication execution ID does not match comparison")
        if self.comparison.e21_result_bundle_hash != self.e21_result_bundle_hash:
            raise ValueError("verified E21 replication result bundle hash does not match comparison")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match verified E21 replication bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "e20_report_hash": self.e20_report_hash,
            "e21_execution_id": self.e21_execution_id,
            "e21_result_bundle_hash": self.e21_result_bundle_hash,
            "e21_analysis_hash": self.e21_analysis_hash,
            "e21_inference_hash": self.e21_inference_hash,
            "e21_fidelity_summary_hash": self.e21_fidelity_summary_hash,
            "comparison": self.comparison,
        }


def _verified_components(
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_completed_ledger: E21RunLedger,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    e21_corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    human_audit_selection: E21HumanAuditSelection,
    human_audit_evidence: BlindHumanFidelityAudit,
) -> tuple[E21VerifiedFidelitySummary, E21ReplicationComparison]:
    if not isinstance(e21_analysis, E21PrimaryAnalysis):
        raise TypeError("e21_analysis must be an E21PrimaryAnalysis")
    if not isinstance(e21_inference, E21PrimaryInference):
        raise TypeError("e21_inference must be an E21PrimaryInference")
    verify_e21_run_ledger(e21_completed_ledger, e21_authorization)
    if e21_completed_ledger.state is not E21RunState.COMPLETED:
        raise E21ReplicationError("verified E21 replication requires a completed non-invalidated E21 run")
    completed_result_hash = e21_completed_ledger.events[-1].artifact_hash
    if completed_result_hash is None:
        raise E21ReplicationError("completed E21 run is missing its result bundle hash")
    if e21_result_bundle.bundle_hash != completed_result_hash:
        raise E21ReplicationError("E21 fidelity evidence does not bind the completed result bundle")
    if e21_analysis.execution_id != e21_authorization.execution_id:
        raise E21ReplicationError("E21 analysis belongs to a different execution")
    if e21_analysis.result_bundle_hash != completed_result_hash:
        raise E21ReplicationError("E21 analysis does not bind the completed result bundle")
    if e21_inference.execution_id != e21_authorization.execution_id:
        raise E21ReplicationError("E21 inference belongs to a different execution")
    if e21_inference.result_bundle_hash != completed_result_hash:
        raise E21ReplicationError("E21 inference does not bind the completed result bundle")
    if e21_inference.analysis_hash != e21_analysis.analysis_hash:
        raise E21ReplicationError("E21 inference does not bind the supplied analysis")
    fidelity_summary = build_verified_e21_fidelity_summary(
        human_audit_selection,
        human_audit_evidence,
        e21_result_bundle,
        preregistration,
        e21_corpus_manifest,
        condition_plan,
    )
    evidence = build_fidelity_bound_e21_headline_evidence(
        e21_analysis,
        e21_inference,
        fidelity_summary,
    )
    comparison = _build_from_evidence(
        e20_report,
        e21_authorization,
        e21_rerun_seal,
        e21_completed_ledger,
        evidence,
    )
    return fidelity_summary, comparison


def build_verified_e21_replication_comparison(
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_completed_ledger: E21RunLedger,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    e21_corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    human_audit_selection: E21HumanAuditSelection,
    human_audit_evidence: BlindHumanFidelityAudit,
) -> E21ReplicationComparison:
    _, comparison = _verified_components(
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
        human_audit_selection,
        human_audit_evidence,
    )
    return comparison


def verify_verified_e21_replication_comparison(
    comparison: E21ReplicationComparison,
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_completed_ledger: E21RunLedger,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    e21_corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    human_audit_selection: E21HumanAuditSelection,
    human_audit_evidence: BlindHumanFidelityAudit,
) -> None:
    if not isinstance(comparison, E21ReplicationComparison):
        raise TypeError("comparison must be an E21ReplicationComparison")
    expected = build_verified_e21_replication_comparison(
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
        human_audit_selection,
        human_audit_evidence,
    )
    if comparison != expected:
        raise E21ReplicationError(
            "verified E21 replication comparison does not replay from analysis, inference, and blind fidelity artifacts"
        )


def build_verified_e21_replication_bundle(
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_completed_ledger: E21RunLedger,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    e21_corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    human_audit_selection: E21HumanAuditSelection,
    human_audit_evidence: BlindHumanFidelityAudit,
) -> E21VerifiedReplicationBundle:
    fidelity_summary, comparison = _verified_components(
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
        human_audit_selection,
        human_audit_evidence,
    )
    payload = {
        "algorithm_version": E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
        "e20_report_hash": e20_report.report_hash,
        "e21_execution_id": e21_authorization.execution_id,
        "e21_result_bundle_hash": e21_result_bundle.bundle_hash,
        "e21_analysis_hash": e21_analysis.analysis_hash,
        "e21_inference_hash": e21_inference.inference_hash,
        "e21_fidelity_summary_hash": fidelity_summary.summary_hash,
        "comparison": comparison,
    }
    return E21VerifiedReplicationBundle(
        E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
        e20_report.report_hash,
        e21_authorization.execution_id,
        e21_result_bundle.bundle_hash,
        e21_analysis.analysis_hash,
        e21_inference.inference_hash,
        fidelity_summary.summary_hash,
        comparison,
        sha256_json(payload),
    )


def verify_verified_e21_replication_bundle(
    bundle: E21VerifiedReplicationBundle,
    e20_report: E20ConfirmatoryReport,
    e21_authorization: E21ExecutionAuthorization,
    e21_rerun_seal: E21RerunSeal,
    e21_completed_ledger: E21RunLedger,
    e21_analysis: E21PrimaryAnalysis,
    e21_inference: E21PrimaryInference,
    e21_result_bundle: E21ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    e21_corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    human_audit_selection: E21HumanAuditSelection,
    human_audit_evidence: BlindHumanFidelityAudit,
) -> None:
    if not isinstance(bundle, E21VerifiedReplicationBundle):
        raise TypeError("bundle must be an E21VerifiedReplicationBundle")
    expected = build_verified_e21_replication_bundle(
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
        human_audit_selection,
        human_audit_evidence,
    )
    if bundle != expected:
        raise E21ReplicationError(
            "verified E21 replication bundle does not replay from analysis, inference, blind fidelity, and comparison artifacts"
        )
