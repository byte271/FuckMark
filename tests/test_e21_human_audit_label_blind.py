from dataclasses import fields, replace

import fuckmark.experiments.e21_human_audit as canonical_human_audit
from test_e21_bundle import _fixture
from fuckmark.experiments._e21_human_audit_legacy import (
    build_e21_human_audit_selection as build_legacy_e21_human_audit_selection,
)
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_human_audit_v2 import (
    E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
    E21HumanAuditSelection,
    _from_legacy,
)
from fuckmark.hashing import sha256_json, sha256_text


def test_e21_human_audit_selection_v2_does_not_bind_mutable_result_bundle_hash() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (),
        failures,
    )
    legacy = build_legacy_e21_human_audit_selection(
        bundle,
        preregistration,
        manifest,
        condition_plan,
    )
    changed_result_bundle_hash = sha256_text("post-human-label-result-bundle")
    changed_payload = legacy._payload()
    changed_payload["result_bundle_hash"] = changed_result_bundle_hash
    rebound = replace(
        legacy,
        result_bundle_hash=changed_result_bundle_hash,
        selection_hash=sha256_json(changed_payload),
    )
    before = _from_legacy(legacy)
    after = _from_legacy(rebound)
    assert E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION == "e21-human-audit-selection-v2"
    assert "result_bundle_hash" not in tuple(value.name for value in fields(E21HumanAuditSelection))
    assert legacy.result_bundle_hash != rebound.result_bundle_hash
    assert before == after
    assert before.selection_hash == after.selection_hash


def test_canonical_e21_human_audit_does_not_expose_legacy_fidelity_summary() -> None:
    assert not hasattr(canonical_human_audit, "E21HumanFidelitySummary")
    assert not hasattr(canonical_human_audit, "build_e21_human_fidelity_summary")
