import fuckmark.experiments as experiments


def test_confirmatory_sealing_api_is_public_from_experiments_package() -> None:
    expected = {
        "CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION",
        "CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION",
        "CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION",
        "CONFIRMATORY_HUMAN_AUDIT_PLAN_ALGORITHM_VERSION",
        "E20_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION",
        "PRIMARY_OUTCOMES",
        "ConfirmatoryBootstrapPlan",
        "ConfirmatoryCorpusSeal",
        "ConfirmatoryCorpusSealError",
        "ConfirmatoryFidelityGate",
        "ConfirmatoryHumanAuditPlan",
        "ConfirmatoryHypothesis",
        "ConfirmatoryPreflightVerificationError",
        "ConfirmatoryPreregistration",
        "ConfirmatoryPreregistrationError",
        "ConfirmatoryPreregistrationInputs",
        "ConfirmatoryPrimaryOutcome",
        "ConfirmatoryStratumCount",
        "ConfirmatoryTestKeyEntry",
        "ConfirmatoryTestKeyManifest",
        "ConfirmatoryTestKeyVerificationError",
        "E20HumanAuditSelection",
        "MultipleTestingMethod",
        "build_confirmatory_corpus_seal",
        "build_confirmatory_test_key_manifest",
        "build_e20_human_audit_selection",
        "create_confirmatory_preregistration",
        "verify_confirmatory_corpus_seal",
        "verify_confirmatory_preregistration",
        "verify_confirmatory_test_key_material",
        "verify_e20_human_audit_evidence",
        "verify_e20_human_audit_selection",
    }
    assert expected <= set(experiments.__all__)
    for name in expected:
        assert getattr(experiments, name) is not None


def test_m6_extended_analysis_power_and_sealed_authorization_are_public() -> None:
    expected = {
        "M6_READINESS_ALGORITHM_VERSION",
        "M6EvidencePartition",
        "M6ExperimentEvidence",
        "M6PowerAnalysisEvidence",
        "M6ReadinessReport",
        "M6ReadinessStatus",
        "build_m6_readiness",
        "verify_m6_readiness",
        "EXTENDED_ANALYSIS_ALGORITHM_VERSION",
        "ExtendedAnalysisInputError",
        "ExtendedAnalysisResult",
        "ExtendedAnalysisRow",
        "ExtendedStratumSummary",
        "run_e12_surface_battery",
        "run_e13_contraction_battery",
        "run_e14_length_scaling",
        "run_e15_domain_transfer",
        "run_e16_validation_key_transfer",
        "run_e17_tokenizer_transfer",
        "run_e18_detector_disagreement",
        "run_e19_per_depth_drift",
        "verify_extended_analysis_result",
        "POWER_ANALYSIS_ALGORITHM_VERSION",
        "PowerAnalysisDirection",
        "PowerAnalysisInput",
        "PowerAnalysisResult",
        "PowerAnalysisStatus",
        "PowerEstimate",
        "m6_power_evidence_from_result",
        "run_power_analysis",
        "verify_power_analysis",
        "authorize_sealed_e20_execution",
        "verify_sealed_e20_execution_authorization",
    }
    assert expected <= set(experiments.__all__)
    for name in expected:
        assert getattr(experiments, name) is not None
