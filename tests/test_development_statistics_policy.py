from fuckmark.experiments.e08_dose import E08_ALGORITHM_VERSION, E08_BOOTSTRAP_REPLICATES


def test_e08_development_bootstrap_floor_matches_frozen_spec() -> None:
    assert E08_ALGORITHM_VERSION == "e08-dose-response-v2"
    assert E08_BOOTSTRAP_REPLICATES >= 2000
