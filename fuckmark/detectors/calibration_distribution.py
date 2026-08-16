from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string


@dataclass(frozen=True, slots=True)
class NullQuantile:
    probability: float
    value: float

    def __post_init__(self) -> None:
        for name, value in (("probability", self.probability), ("value", self.value)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.probability < 0.0 or self.probability > 1.0:
            raise ValueError("probability must be between 0 and 1")
        if self.value < 0.0 or self.value > 1.0:
            raise ValueError("value must be between 0 and 1")

@dataclass(frozen=True, slots=True)
class ExactBinomialInterval:
    method: str
    confidence_level: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        require_clean_string("method", self.method)
        for name, value in (
            ("confidence_level", self.confidence_level),
            ("lower", self.lower),
            ("upper", self.upper),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.confidence_level <= 0.0 or self.confidence_level >= 1.0:
            raise ValueError("confidence_level must be between 0 and 1")
        if self.lower < 0.0 or self.upper > 1.0 or self.lower > self.upper:
            raise ValueError("binomial interval bounds are invalid")
