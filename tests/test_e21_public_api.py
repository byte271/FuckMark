import fuckmark.experiments as experiments


def test_e21_protocol_is_publicly_exported() -> None:
    expected = (
        "E21_EXPERIMENT_ID",
        "E21_RERUN_SEAL_ALGORITHM_VERSION",
        "E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION",
        "E21_RUN_LEDGER_ALGORITHM_VERSION",
        "E21RerunSeal",
        "E21ExecutionAuthorization",
        "E21RunLedger",
        "build_e21_rerun_seal",
        "verify_e21_rerun_seal",
        "authorize_e21_execution",
        "verify_e21_execution_authorization",
        "create_e21_run_ledger",
        "start_e21_run",
        "complete_e21_run",
        "invalidate_e21_run",
        "verify_e21_run_ledger",
    )
    for name in expected:
        assert hasattr(experiments, name)
        assert name in experiments.__all__
