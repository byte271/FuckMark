from dataclasses import replace

import pytest

import fuckmark.experiments as experiments
import fuckmark.experiments.e21_human_audit as canonical_e21_human_audit
import fuckmark.experiments.m10_release_v2 as m10_release_v2
from test_e21_bundle import _fixture
from fuckmark.experiments._e21_human_audit_legacy import (
    E21HumanAuditSelection as LegacyE21HumanAuditSelection,
    build_e21_human_audit_selection as build_legacy_e21_human_audit_selection,
)
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_fidelity_summary import build_verified_e21_fidelity_summary
from fuckmark.experiments.e21_human_audit_v2 import (
    E21HumanAuditSelection as CurrentE21HumanAuditSelection,
)
from fuckmark.experiments.m10_release import (
    M10_RELEASE_ALGORITHM_VERSION,
    M10ReleaseManifest,
    M10ReleaseStatus,
)
from fuckmark.hashing import sha256_json, sha256_text


M10_EVIDENCE_HASH_FIELDS = (
    "preregistration_hash",
    "m6_readiness_hash",
    "detector_readiness_hash",
    "test_key_manifest_hash",
    "e20_corpus_manifest_hash",
    "e20_authorization_hash",
    "e20_result_bundle_hash",
    "e20_aggregate_hash",
    "e20_inference_hash",
    "e20_report_hash",
    "e20_fidelity_summary_hash",
    "e21_corpus_manifest_hash",
    "e21_rerun_seal_hash",
    "e21_authorization_hash",
    "e21_result_bundle_hash",
    "e21_analysis_hash",
    "e21_inference_hash",
    "e21_fidelity_summary_hash",
    "e21_replication_hash",
)


def _synthetic_m10_manifest() -> M10ReleaseManifest:
    evidence = {
        name: sha256_text(f"m10-contract:{name}")
        for name in M10_EVIDENCE_HASH_FIELDS
    }
    payload = {
        "algorithm_version": M10_RELEASE_ALGORITHM_VERSION,
        "release_code_commit": "a" * 40,
        **evidence,
        "limitations": (),
        "status": M10ReleaseStatus.READY_COMPLETE.value,
    }
    return M10ReleaseManifest(
        algorithm_version=M10_RELEASE_ALGORITHM_VERSION,
        release_code_commit=payload["release_code_commit"],
        limitations=(),
        status=M10ReleaseStatus.READY_COMPLETE,
        manifest_hash=sha256_json(payload),
        **evidence,
    )


def test_canonical_e21_audit_and_m10_use_the_current_selection_contract() -> None:
    assert canonical_e21_human_audit.E21HumanAuditSelection is CurrentE21HumanAuditSelection
    assert experiments.E21HumanAuditSelection is CurrentE21HumanAuditSelection
    assert m10_release_v2.E21HumanAuditSelection is CurrentE21HumanAuditSelection
    assert LegacyE21HumanAuditSelection is not CurrentE21HumanAuditSelection


def test_current_e21_fidelity_rejects_legacy_v1_selection_explicitly() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    result_bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (),
        failures,
    )
    legacy_selection = build_legacy_e21_human_audit_selection(
        result_bundle,
        preregistration,
        manifest,
        condition_plan,
    )

    with pytest.raises(TypeError, match="legacy v1 selections are not accepted"):
        build_verified_e21_fidelity_summary(
            legacy_selection,
            None,
            result_bundle,
            preregistration,
            manifest,
            condition_plan,
        )


@pytest.mark.parametrize("field_name", M10_EVIDENCE_HASH_FIELDS)
def test_m10_manifest_hash_binds_every_release_evidence_hash(field_name: str) -> None:
    manifest = _synthetic_m10_manifest()
    with pytest.raises(ValueError, match="manifest_hash"):
        replace(
            manifest,
            **{field_name: sha256_text(f"tampered:{field_name}")},
        )
