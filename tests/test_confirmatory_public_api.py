import fuckmark.experiments as experiments


def test_confirmatory_sealing_api_is_public_from_experiments_package() -> None:
    expected = {
        "CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION",
        "CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION",
        "CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION",
        "PRIMARY_OUTCOMES",
        "ConfirmatoryBootstrapPlan",
        "ConfirmatoryCorpusSeal",
        "ConfirmatoryCorpusSealError",
        "ConfirmatoryFidelityGate",
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
        "MultipleTestingMethod",
        "build_confirmatory_corpus_seal",
        "build_confirmatory_test_key_manifest",
        "create_confirmatory_preregistration",
        "verify_confirmatory_corpus_seal",
        "verify_confirmatory_preregistration",
        "verify_confirmatory_test_key_material",
    }
    assert expected <= set(experiments.__all__)
    for name in expected:
        assert getattr(experiments, name) is not None
