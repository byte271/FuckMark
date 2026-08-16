from __future__ import annotations

import math
import statistics

from .calibration_types import CalibrationResolutionError, ExactBinomialInterval


BINOMIAL_INTERVAL_METHOD = "clopper-pearson-equal-tailed"
NULL_QUANTILE_METHOD = "empirical-inverse-cdf-no-interpolation"
ROBUST_SCALE_METHOD = "normal-consistent-mad-with-iqr-fallback"
_MAD_NORMAL_SCALE = 1.482602218505602
_IQR_NORMAL_SCALE = 1.3489795003921634


def _validate_probability(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number <= 0.0 or number >= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _empirical_quantile(sorted_values: tuple[float, ...], probability: float) -> float:
    if not sorted_values:
        raise ValueError("sorted_values must not be empty")
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        raise TypeError("probability must be a real number")
    q = float(probability)
    if not math.isfinite(q) or q < 0.0 or q > 1.0:
        raise ValueError("probability must be between 0 and 1")
    if q <= 0.0:
        return sorted_values[0]
    rank = math.ceil(q * len(sorted_values))
    return sorted_values[min(len(sorted_values) - 1, rank - 1)]


def _binomial_pmf(n: int, k: int, p: float) -> float:
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    log_value = (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
    )
    return math.exp(log_value)


def _binomial_range_probability(n: int, lower: int, upper: int, p: float) -> float:
    if lower > upper:
        return 0.0
    if p <= 0.0:
        return 1.0 if lower <= 0 <= upper else 0.0
    if p >= 1.0:
        return 1.0 if lower <= n <= upper else 0.0
    mode = min(n, math.floor((n + 1) * p))
    anchor = min(upper, max(lower, mode))
    anchor_probability = _binomial_pmf(n, anchor, p)
    if anchor_probability == 0.0:
        return 0.0
    relative_terms = [1.0]
    term = 1.0
    x = anchor
    while x > lower:
        term *= x * (1.0 - p) / ((n - x + 1) * p)
        relative_terms.append(term)
        x -= 1
    term = 1.0
    x = anchor
    while x < upper:
        term *= (n - x) * p / ((x + 1) * (1.0 - p))
        relative_terms.append(term)
        x += 1
    probability = anchor_probability * math.fsum(relative_terms)
    return min(1.0, max(0.0, probability))


def _binomial_cdf(n: int, k: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return _binomial_range_probability(n, 0, k, p)


def _binomial_survival(n: int, k: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return _binomial_range_probability(n, k, n, p)


def _bisect_increasing(function, target: float) -> float:
    low = 0.0
    high = 1.0
    for _ in range(80):
        middle = (low + high) / 2.0
        if function(middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _bisect_decreasing(function, target: float) -> float:
    low = 0.0
    high = 1.0
    for _ in range(80):
        middle = (low + high) / 2.0
        if function(middle) > target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def exact_binomial_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ExactBinomialInterval:
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise TypeError("successes must be an integer")
    if isinstance(trials, bool) or not isinstance(trials, int):
        raise TypeError("trials must be an integer")
    if trials <= 0:
        raise ValueError("trials must be positive")
    if successes < 0 or successes > trials:
        raise ValueError("successes must be between zero and trials")
    level = _validate_probability("confidence_level", confidence_level)
    tail = (1.0 - level) / 2.0
    lower = 0.0 if successes == 0 else _bisect_increasing(
        lambda p: _binomial_survival(trials, successes, p),
        tail,
    )
    upper = 1.0 if successes == trials else _bisect_decreasing(
        lambda p: _binomial_cdf(trials, successes, p),
        tail,
    )
    return ExactBinomialInterval(BINOMIAL_INTERVAL_METHOD, level, lower, upper)



def _robust_location_scale(sorted_scores: tuple[float, ...]) -> tuple[float, float]:
    center = float(statistics.median(sorted_scores))
    deviations = tuple(sorted(abs(value - center) for value in sorted_scores))
    mad = float(statistics.median(deviations))
    if mad > 0.0:
        return center, mad * _MAD_NORMAL_SCALE
    q25 = _empirical_quantile(sorted_scores, 0.25)
    q75 = _empirical_quantile(sorted_scores, 0.75)
    iqr = q75 - q25
    if iqr > 0.0:
        return center, iqr / _IQR_NORMAL_SCALE
    raise CalibrationResolutionError("negative calibration scores have zero robust scale")


