from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._validation import require_clean_string, require_int, require_sha256
from .hashing import sha256_json


SANITIZER_ROBUSTNESS_REPORT_VERSION = "sanitizer-robustness-report-v1"
SANITIZER_VARIANT_IDS = ("raw", "nfkc", "cf_strip", "nfkc_cf_strip")


def nfkc_normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def strip_unicode_format_characters(text: str) -> str:
    return "".join(character for character in text if unicodedata.category(character) != "Cf")


def sanitize_variant(variant_id: str, text: str) -> str:
    require_clean_string("variant_id", variant_id)
    if variant_id == "raw":
        return text
    if variant_id == "nfkc":
        return nfkc_normalize(text)
    if variant_id == "cf_strip":
        return strip_unicode_format_characters(text)
    if variant_id == "nfkc_cf_strip":
        return strip_unicode_format_characters(nfkc_normalize(text))
    raise ValueError(f"unknown sanitizer variant id: {variant_id}")


def introduced_invisible_codepoint_count(original: str, transformed: str) -> int:
    forbidden = {
        ord(character)
        for character in transformed
        if unicodedata.category(character) in ("Cc", "Cf") or unicodedata.category(character) == "Mn"
    }
    baseline = {
        ord(character)
        for character in original
        if unicodedata.category(character) in ("Cc", "Cf") or unicodedata.category(character) == "Mn"
    }
    return len(forbidden - baseline)


@dataclass(frozen=True, slots=True)
class SanitizerVariantScore:
    variant_id: str
    score: float | None
    detected: bool
    error: str | None

    def __post_init__(self) -> None:
        require_clean_string("variant_id", self.variant_id)
        if self.variant_id not in SANITIZER_VARIANT_IDS:
            raise ValueError("sanitizer variant id is unknown")
        if self.error is not None:
            require_clean_string("error", self.error)
            if self.score is not None or self.detected:
                raise ValueError("a failed variant must not carry a score or detection")
        else:
            if self.score is None:
                raise ValueError("a scored variant must carry a score")

    def payload(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "score": self.score,
            "detected": self.detected,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class SanitizerRobustnessRow:
    source_sample_id: str
    condition_id: str
    arm: str
    transformed_text: str
    transformed_text_hash: str
    variants: tuple[SanitizerVariantScore, ...]
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("arm", self.arm)
        if not isinstance(self.transformed_text, str):
            raise TypeError("transformed_text must be a string")
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.transformed_text_hash != sha256_json(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        if not isinstance(self.variants, tuple) or tuple(v.variant_id for v in self.variants) != SANITIZER_VARIANT_IDS:
            raise ValueError("variants must contain every sanitizer variant exactly once")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match sanitizer robustness row")

    def payload(self) -> dict[str, object]:
        return {
            "source_sample_id": self.source_sample_id,
            "condition_id": self.condition_id,
            "arm": self.arm,
            "transformed_text_hash": self.transformed_text_hash,
            "variants": tuple(v.payload() for v in self.variants),
        }

    @property
    def raw_detected(self) -> bool:
        return self.variants[0].detected

    @property
    def durable_detected(self) -> bool:
        return self.variants[-1].detected


@dataclass(frozen=True, slots=True)
class SanitizerRobustnessSummary:
    condition_id: str
    arm: str
    row_count: int
    detected_per_variant: tuple[int, ...]
    error_per_variant: tuple[int, ...]
    mean_score_per_variant: tuple[float | None, ...]
    summary_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("arm", self.arm)
        require_int("row_count", self.row_count)
        if self.row_count <= 0:
            raise ValueError("summary row_count must be positive")
        for name, values in (("detected_per_variant", self.detected_per_variant), ("error_per_variant", self.error_per_variant)):
            if not isinstance(values, tuple) or len(values) != len(SANITIZER_VARIANT_IDS):
                raise ValueError(f"{name} must cover every sanitizer variant")
            for value in values:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} counts must be non-negative")
        if not isinstance(self.mean_score_per_variant, tuple) or len(self.mean_score_per_variant) != len(SANITIZER_VARIANT_IDS):
            raise ValueError("mean_score_per_variant must cover every sanitizer variant")
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("summary_hash does not match sanitizer robustness summary")

    def payload(self) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "arm": self.arm,
            "row_count": self.row_count,
            "detected_per_variant": self.detected_per_variant,
            "error_per_variant": self.error_per_variant,
            "mean_score_per_variant": self.mean_score_per_variant,
        }


@dataclass(frozen=True, slots=True)
class SanitizerRobustnessReport:
    algorithm_version: str
    threshold: float
    rows: tuple[SanitizerRobustnessRow, ...]
    summaries: tuple[SanitizerRobustnessSummary, ...]
    invisible_introduction_rows: tuple[Mapping[str, object], ...]
    detector_access_observed: bool
    secret_access_observed: bool
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SANITIZER_ROBUSTNESS_REPORT_VERSION:
            raise ValueError("unsupported sanitizer robustness report version")
        if not isinstance(self.threshold, float) or not 0.0 < self.threshold < 1.0:
            raise ValueError("threshold must be a probability in (0, 1)")
        if not self.rows:
            raise ValueError("sanitizer robustness report requires rows")
        for value in (
            self.detector_access_observed,
            self.secret_access_observed,
        ):
            if value is not False:
                raise ValueError("sanitizer robustness reporting must remain observation-only")
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match sanitizer robustness report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "threshold": self.threshold,
            "rows": tuple(row.payload() for row in self.rows),
            "summaries": tuple(summary.payload() for summary in self.summaries),
            "invisible_introduction_rows": tuple(dict(row) for row in self.invisible_introduction_rows),
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def evaluate_sanitizer_robustness(
    *,
    condition_id: str,
    arm: str,
    entries: Sequence[Mapping[str, Any]],
    scorer: Any,
    threshold: float,
) -> SanitizerRobustnessReport:
    require_clean_string("condition_id", condition_id)
    require_clean_string("arm", arm)
    if not callable(scorer):
        raise TypeError("scorer must be callable")
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be a probability in (0, 1)")
    rows: list[SanitizerRobustnessRow] = []
    invisible_rows: list[dict[str, object]] = []
    for entry in entries:
        sample_id = str(entry["source_sample_id"])
        text = str(entry["text"])
        invisible = int(entry.get("invisible_introduced", 0))
        if invisible:
            invisible_rows.append(
                {
                    "source_sample_id": sample_id,
                    "condition_id": condition_id,
                    "arm": arm,
                    "introduced_invisible_codepoints": invisible,
                }
            )
        scores: list[SanitizerVariantScore] = []
        for variant_id in SANITIZER_VARIANT_IDS:
            cleaned = sanitize_variant(variant_id, text)
            try:
                value = float(scorer(cleaned))
                scores.append(SanitizerVariantScore(variant_id, value, value >= threshold, None))
            except Exception as error:
                scores.append(SanitizerVariantScore(variant_id, None, False, type(error).__name__))
        row_payload = {
            "source_sample_id": sample_id,
            "condition_id": condition_id,
            "arm": arm,
            "transformed_text_hash": sha256_json(text),
            "variants": tuple(v.payload() for v in scores),
        }
        rows.append(SanitizerRobustnessRow(sample_id, condition_id, arm, text, sha256_json(text), tuple(scores), sha256_json(row_payload)))
    summaries = [_summarize(rows, condition_id, arm)]
    payload = {
        "algorithm_version": SANITIZER_ROBUSTNESS_REPORT_VERSION,
        "threshold": threshold,
        "rows": tuple(row.payload() for row in rows),
        "summaries": tuple(summary.payload() for summary in summaries),
        "invisible_introduction_rows": tuple(invisible_rows),
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return SanitizerRobustnessReport(
        SANITIZER_ROBUSTNESS_REPORT_VERSION,
        threshold,
        tuple(rows),
        tuple(summaries),
        tuple(invisible_rows),
        False,
        False,
        sha256_json(payload),
    )


def _summarize(rows: Sequence[SanitizerRobustnessRow], condition_id: str, arm: str) -> SanitizerRobustnessSummary:
    row_count = len(rows)
    detected = tuple(sum(1 for row in rows if row.variants[index].detected) for index in range(len(SANITIZER_VARIANT_IDS)))
    errors = tuple(sum(1 for row in rows if row.variants[index].error is not None) for index in range(len(SANITIZER_VARIANT_IDS)))
    means: list[float | None] = []
    for index in range(len(SANITIZER_VARIANT_IDS)):
        values = [row.variants[index].score for row in rows if row.variants[index].score is not None]
        means.append(sum(values) / len(values) if values else None)
    payload = {
        "condition_id": condition_id,
        "arm": arm,
        "row_count": row_count,
        "detected_per_variant": detected,
        "error_per_variant": errors,
        "mean_score_per_variant": tuple(means),
    }
    return SanitizerRobustnessSummary(condition_id, arm, row_count, detected, errors, tuple(means), sha256_json(payload))
