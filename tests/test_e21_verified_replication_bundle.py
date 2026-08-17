from dataclasses import replace

import pytest

from test_e21_replication import _fixture
from fuckmark.experiments.e21_replication import build_e21_replication_comparison
from fuckmark.experiments.e21_replication_verified import (
    E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
    E21VerifiedReplicationBundle,
)
from fuckmark.hashing import sha256_json, sha256_text


def _bundle():
    e20_report, authorization, seal, ledger, evidence = _fixture()
    comparison = build_e21_replication_comparison(
        e20_report,
        authorization,
        seal,
        ledger,
        evidence,
    )
    analysis_hash = sha256_text("e21-verified-analysis")
    inference_hash = sha256_text("e21-verified-inference")
    fidelity_hash = sha256_text("e21-verified-fidelity")
    payload = {
        "algorithm_version": E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
        "e20_report_hash": e20_report.report_hash,
        "e21_execution_id": authorization.execution_id,
        "e21_result_bundle_hash": comparison.e21_result_bundle_hash,
        "e21_analysis_hash": analysis_hash,
        "e21_inference_hash": inference_hash,
        "e21_fidelity_summary_hash": fidelity_hash,
        "comparison": comparison,
    }
    return E21VerifiedReplicationBundle(
        E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
        e20_report.report_hash,
        authorization.execution_id,
        comparison.e21_result_bundle_hash,
        analysis_hash,
        inference_hash,
        fidelity_hash,
        comparison,
        sha256_json(payload),
    )


def test_verified_e21_replication_hash_binds_fidelity_summary() -> None:
    bundle = _bundle()
    assert bundle.e21_fidelity_summary_hash == sha256_text("e21-verified-fidelity")
    with pytest.raises(ValueError, match="bundle_hash"):
        replace(
            bundle,
            e21_fidelity_summary_hash=sha256_text("different-e21-fidelity"),
        )
