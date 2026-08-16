from __future__ import annotations

import unicodedata
from enum import Enum


TARGET_LENGTHS = (64, 128, 256, 512, 1024)
MAX_GENERATION_SEED = (1 << 64) - 1


class CorpusDomain(str, Enum):
    GENERAL_EXPLANATORY = "general_explanatory"
    TECHNICAL_EXPLANATION = "technical_explanation"
    CONVERSATIONAL_PROSE = "conversational_prose"
    STRUCTURED_INSTRUCTIONAL = "structured_instructional"


class CorpusSplit(str, Enum):
    DETECTOR_TRAIN = "detector_train"
    DETECTOR_VALIDATION = "detector_validation"
    THRESHOLD_CALIBRATION = "threshold_calibration"
    ATTACK_DEVELOPMENT = "attack_development"
    FINAL_TEST = "final_test"


class WatermarkLabel(str, Enum):
    WATERMARKED = "watermarked"
    UNWATERMARKED = "unwatermarked"


class KeySplit(str, Enum):
    DEV = "DEV_KEYS"
    VALIDATION = "VALIDATION_KEYS"
    TEST = "TEST_KEYS"


class PromptBoundaryMode(str, Enum):
    CONTINUATION_ONLY = "continuation_only"
    PROMPT_INCLUDED_DIAGNOSTIC = "prompt_included_diagnostic"


class DeduplicationPolicy(str, Enum):
    EXACT_UTF8 = "exact_utf8_v1"


def require_exact_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if value == "":
        raise ValueError(f"{name} must not be empty")
    if any(unicodedata.category(character) == "Cs" for character in value):
        raise ValueError(f"{name} must not contain surrogate code points")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8 text") from error


def float_for_hash(name: str, value: float | int) -> float | bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be representable as a finite float") from error
