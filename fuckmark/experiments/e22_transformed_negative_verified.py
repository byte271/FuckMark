from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ResultBundle, verify_e20_result_bundle
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import E20ExecutionAuthorization
from .e22_transformed_negative import E22TransformedNegativeReport, build_e22_transformed_negative_report


E22_VERIFIED_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION = "e22-verified-transformed-negative-v1"


@dataclass(frozen=True, slots=True)
class E22VerifiedTransformedNegativeReport:
    algorithm_version: str
    authorization_hash: str
    preregistration_hash: str
    report: E22TransformedNegativeReport
    verified_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E22_VERIFIED_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION:
            raise ValueError("unsupported verified E22 transformed-negative algorithm version")
        require_sha256("authorization_hash", self.authorization_hash)
        require_sha256("preregistration_hash", self.preregistration_hash)
        if not isinstance(self.report, E22TransformedNegativeReport):
            raise TypeError("report must be an E22TransformedNegativeReport")
        require_sha256("verified_hash", self.verified_hash)
        if self.verified_hash != sha256_json(self._payload()):
            raise ValueError("verified_hash does not match verified E22 report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "authorization_hash": self.authorization_hash,
            "preregistration_hash": self.preregistration_hash,
            "report": self.report,
        }


def build_verified_e22_transformed_negative_report(
    result_bundle: E20ResultBundle,
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E22VerifiedTransformedNegativeReport:
    if not isinstance(result_bundle, E20ResultBundle):
        raise TypeError("result_bundle must be an E20ResultBundle")
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    verify_e20_condition_plan(condition_plan, preregistration)
    verify_e20_result_bundle(result_bundle, authorization, preregistration, corpus_manifest, condition_plan)
    report = build_e22_transformed_negative_report(result_bundle, corpus_manifest, condition_plan)
    payload = {
        "algorithm_version": E22_VERIFIED_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION,
        "authorization_hash": authorization.authorization_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "report": report,
    }
    return E22VerifiedTransformedNegativeReport(
        E22_VERIFIED_TRANSFORMED_NEGATIVE_ALGORITHM_VERSION,
        authorization.authorization_hash,
        preregistration.preregistration_hash,
        report,
        sha256_json(payload),
    )


def verify_verified_e22_transformed_negative_report(
    verified: E22VerifiedTransformedNegativeReport,
    result_bundle: E20ResultBundle,
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(verified, E22VerifiedTransformedNegativeReport):
        raise TypeError("verified must be an E22VerifiedTransformedNegativeReport")
    expected = build_verified_e22_transformed_negative_report(
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if verified != expected:
        raise ValueError("verified E22 report does not replay exactly from sealed E20 evidence")
