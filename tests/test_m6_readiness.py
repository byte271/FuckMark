from dataclasses import replace

import pytest

from fuckmark.experiments.m6_readiness import (
    M6EvidencePartition,
    M6ExperimentEvidence,
    M6PowerAnalysisEvidence,
    M6ReadinessStatus,
    build_m6_readiness,
    verify_m6_readiness,
)
from fuckmark.experiments.registry import (
    DevelopmentExperimentId,
    default_development_experiment_registry,
)
from fuckmark.hashing import sha256_text


def _all_evidence():
    registry = default_development_experiment_registry()
    rows = []
    for experiment_id in tuple(DevelopmentExperimentId)[5:]:
        definition = registry.get(experiment_id)
        rows.append(
            M6ExperimentEvidence.create(
                experiment_id,
                definition.definition_hash,
                M6EvidencePartition.VALIDATION,
                sha256_text(f"artifact-{experiment_id.value}"),
            )
        )
    return registry, tuple(rows)


def _power() -> M6PowerAnalysisEvidence:
    return M6PowerAnalysisEvidence.create(
        "group-stratified-power-analysis-v1",
        sha256_text("validation-inputs"),
        sha256_text("power-analysis-artifact"),
        200,
    )


def test_empty_m6_evidence_is_blocked_fail_closed() -> None:
    registry = default_development_experiment_registry()
    report = build_m6_readiness(registry, (), None)
    assert report.ready_for_m7 is False
    assert report.status is M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE_AND_POWER_ANALYSIS
    assert report.missing_experiments == tuple(DevelopmentExperimentId)[5:]


def test_complete_experiment_evidence_without_power_analysis_is_blocked() -> None:
    registry, evidence = _all_evidence()
    report = build_m6_readiness(registry, evidence, None)
    assert report.ready_for_m7 is False
    assert report.status is M6ReadinessStatus.MISSING_POWER_ANALYSIS
    assert report.missing_experiments == ()


def test_power_analysis_without_all_e07_e19_evidence_is_blocked() -> None:
    registry, evidence = _all_evidence()
    report = build_m6_readiness(registry, evidence[:-1], _power())
    assert report.ready_for_m7 is False
    assert report.status is M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE
    assert report.missing_experiments == (DevelopmentExperimentId.E19,)


def test_complete_validation_evidence_and_power_analysis_reaches_m7_gate() -> None:
    registry, evidence = _all_evidence()
    power = _power()
    report = build_m6_readiness(registry, evidence, power)
    assert report.ready_for_m7 is True
    assert report.status is M6ReadinessStatus.READY
    assert report.missing_experiments == ()
    verify_m6_readiness(report, registry, evidence, power)


def test_m6_evidence_cannot_target_pre_m6_experiment() -> None:
    registry = default_development_experiment_registry()
    definition = registry.get(DevelopmentExperimentId.E06)
    with pytest.raises(ValueError, match="E07 through E19"):
        M6ExperimentEvidence.create(
            DevelopmentExperimentId.E06,
            definition.definition_hash,
            M6EvidencePartition.DEV,
            sha256_text("artifact-E06"),
        )


def test_m6_evidence_is_bound_to_registry_definition_hash() -> None:
    registry, evidence = _all_evidence()
    corrupted = M6ExperimentEvidence.create(
        evidence[0].experiment_id,
        "f" * 64,
        evidence[0].partition,
        evidence[0].artifact_hash,
    )
    with pytest.raises(ValueError, match="definition hash"):
        build_m6_readiness(registry, (corrupted,) + evidence[1:], _power())


def test_m6_report_hash_rejects_tampering() -> None:
    registry, evidence = _all_evidence()
    report = build_m6_readiness(registry, evidence, _power())
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, report_hash="f" * 64)
