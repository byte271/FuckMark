import fuckmark.experiments as experiments


def test_real_e20_readiness_gate_is_public_without_replacing_infrastructure_authorization() -> None:
    assert experiments.authorize_ready_e20_execution.__module__ == "fuckmark.experiments.e20_readiness_gate"
    assert experiments.authorize_e20_execution.__module__ == "fuckmark.experiments.e20_authorization"
    assert experiments.E20ReadinessGateError.__module__ == "fuckmark.experiments.e20_readiness_gate"


def test_e20_analysis_chain_is_public_and_versioned() -> None:
    assert experiments.E20_AGGREGATOR_ALGORITHM_VERSION == "e20-aggregator-v1"
    assert experiments.E20_KEY_ANALYSIS_ALGORITHM_VERSION == "e20-key-analysis-v1"
    assert experiments.E20_INFERENCE_ALGORITHM_VERSION == "e20-inference-v1"
    assert experiments.E20_REPORT_ALGORITHM_VERSION == "e20-report-v2"
    assert callable(experiments.build_e20_aggregate_bundle)
    assert callable(experiments.verify_e20_aggregate_bundle)
    assert callable(experiments.build_e20_key_analysis_bundle)
    assert callable(experiments.verify_e20_key_analysis_bundle)
    assert callable(experiments.build_e20_inference_bundle)
    assert callable(experiments.verify_e20_inference_bundle)
    assert callable(experiments.build_e20_confirmatory_report)
    assert callable(experiments.verify_e20_confirmatory_report)


def test_confirmatory_detector_readiness_is_public_and_fail_closed() -> None:
    assert experiments.CONFIRMATORY_DETECTOR_READINESS_ALGORITHM_VERSION == "confirmatory-detector-readiness-v1"
    assert callable(experiments.build_confirmatory_detector_readiness)
    assert callable(experiments.verify_confirmatory_detector_readiness)
