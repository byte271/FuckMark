import pytest

from fuckmark.detectors import exact_binomial_interval


def test_exact_binomial_interval_edges() -> None:
    zero = exact_binomial_interval(0, 100, 0.95)
    full = exact_binomial_interval(100, 100, 0.95)
    assert zero.lower == 0.0
    assert 0.0 < zero.upper < 0.1
    assert 0.9 < full.lower < 1.0
    assert full.upper == 1.0


def test_exact_binomial_interval_matches_scipy_beta_quantiles() -> None:
    scipy_stats = pytest.importorskip("scipy.stats")
    beta = scipy_stats.beta
    for successes, trials in ((1, 100), (5, 100), (50, 100), (95, 100), (10, 1000), (800, 1000)):
        interval = exact_binomial_interval(successes, trials, 0.95)
        expected_lower = beta.ppf(0.025, successes, trials - successes + 1) if successes else 0.0
        expected_upper = beta.ppf(0.975, successes + 1, trials - successes) if successes < trials else 1.0
        assert interval.lower == pytest.approx(expected_lower, rel=1e-10, abs=1e-12)
        assert interval.upper == pytest.approx(expected_upper, rel=1e-10, abs=1e-12)
