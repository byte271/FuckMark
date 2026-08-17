import fuckmark.experiments as experiments


def test_e21_protocol_is_publicly_exported() -> None:
    expected = (
        "E21_EXPERIMENT_ID",
        "E21_RERUN_SEAL_ALGORITHM_VERSION",
        "E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION",
        "E21_RUN_LEDGER_ALGORITHM_VERSION",
        "E21_SEED_DERIVATION_ALGORITHM_VERSION",
        "E21_OUTCOME_ROW_ALGORITHM_VERSION",
        "E21_FAILURE_ROW_ALGORITHM_VERSION",
        "E21_RESULT_BUNDLE_ALGORITHM_VERSION",
        "E21_PRIMARY_ANALYSIS_ALGORITHM_VERSION",
        "E21_PRIMARY_INFERENCE_ALGORITHM_VERSION",
        "E21_REPLICATION_ALGORITHM_VERSION",
        "E21RerunSeal",
        "E21ExecutionAuthorization",
        "E21RunLedger",
        "E21IdentityFields",
        "E21OutcomeRow",
        "E21FailureRow",
        "E21ResultBundle",
        "E21PrimaryAnalysis",
        "E21PrimaryInference",
        "E21ReplicationComparison",
        "E21HeadlineEvidence",
        "E21ConditionComparison",
        "build_e21_rerun_seal",
        "verify_e21_rerun_seal",
        "authorize_e21_execution",
        "verify_e21_execution_authorization",
        "create_e21_run_ledger",
        "start_e21_run",
        "complete_e21_run",
        "invalidate_e21_run",
        "verify_e21_run_ledger",
        "e21_sample_shard",
        "derive_e21_condition_seed",
        "build_e21_result_bundle",
        "verify_e21_result_bundle",
        "build_e21_primary_analysis",
        "verify_e21_primary_analysis",
        "build_e21_primary_inference",
        "verify_e21_primary_inference",
        "build_e21_headline_evidence",
        "build_verified_e21_replication_comparison",
        "verify_verified_e21_replication_comparison",
    )
    for name in expected:
        assert hasattr(experiments, name)
        assert name in experiments.__all__
    assert not hasattr(experiments, "build_e21_replication_comparison")
    assert not hasattr(experiments, "verify_e21_replication_comparison")
