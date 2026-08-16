import fuckmark


def test_task29_readiness_api_is_exported_and_defaults_to_blocked() -> None:
    expected = {
        "TASK29_FIDELITY_READINESS_ALGORITHM_VERSION",
        "FidelityReadinessStatus",
        "FidelityRuleReadiness",
        "Task29FidelityReadinessReport",
        "build_task29_fidelity_readiness",
    }
    assert expected <= set(fuckmark.__all__)
    for name in expected:
        assert getattr(fuckmark, name) is not None
    report = fuckmark.build_task29_fidelity_readiness()
    assert report.has_missing_evidence
    assert not report.confirmatory_scale_ready
