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
