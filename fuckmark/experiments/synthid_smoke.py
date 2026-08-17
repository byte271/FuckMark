from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .._validation import require_clean_string, require_int, require_sha256
from ..cli import process_text
from ..hashing import sha256_json, sha256_text


SYNTHID_SMOKE_ALGORITHM_VERSION = "synthid-open-smoke-v1"


@runtime_checkable
class SynthIDSmokeBackend(Protocol):
    @property
    def backend_id(self) -> str: ...

    @property
    def backend_version(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    @property
    def detector_id(self) -> str: ...

    @property
    def detector_config_hash(self) -> str: ...

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str: ...

    def score(self, text: str) -> float: ...


@dataclass(frozen=True, slots=True)
class SynthIDSmokePrompt:
    prompt_id: str
    text: str
    seed: int

    def __post_init__(self) -> None:
        require_clean_string("prompt_id", self.prompt_id)
        require_clean_string("text", self.text)
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed > 2**64 - 1:
            raise ValueError("seed must be between 0 and 2^64-1")


@dataclass(frozen=True, slots=True)
class SynthIDSmokePromptResult:
    prompt_id: str
    seed: int
    prompt_hash: str
    control_pristine_text: str
    control_transformed_text: str
    watermark_pristine_text: str
    watermark_transformed_text: str
    control_pristine_score: float
    control_transformed_score: float
    watermark_pristine_score: float
    watermark_transformed_score: float
    control_score_shift: float
    watermark_score_drop: float
    control_changed: bool
    watermark_changed: bool
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("prompt_id", self.prompt_id)
        require_int("seed", self.seed)
        require_sha256("prompt_hash", self.prompt_hash)
        for name, value in (
            ("control_pristine_text", self.control_pristine_text),
            ("control_transformed_text", self.control_transformed_text),
            ("watermark_pristine_text", self.watermark_pristine_text),
            ("watermark_transformed_text", self.watermark_transformed_text),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        for name, value in (
            ("control_pristine_score", self.control_pristine_score),
            ("control_transformed_score", self.control_transformed_score),
            ("watermark_pristine_score", self.watermark_pristine_score),
            ("watermark_transformed_score", self.watermark_transformed_score),
            ("control_score_shift", self.control_score_shift),
            ("watermark_score_drop", self.watermark_score_drop),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        for name, value in (("control_changed", self.control_changed), ("watermark_changed", self.watermark_changed)):
            if type(value) is not bool:
                raise TypeError(f"{name} must be a bool")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match smoke prompt result")

    def _payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "seed": self.seed,
            "prompt_hash": self.prompt_hash,
            "control_pristine_text": self.control_pristine_text,
            "control_transformed_text": self.control_transformed_text,
            "watermark_pristine_text": self.watermark_pristine_text,
            "watermark_transformed_text": self.watermark_transformed_text,
            "control_pristine_score": self.control_pristine_score,
            "control_transformed_score": self.control_transformed_score,
            "watermark_pristine_score": self.watermark_pristine_score,
            "watermark_transformed_score": self.watermark_transformed_score,
            "control_score_shift": self.control_score_shift,
            "watermark_score_drop": self.watermark_score_drop,
            "control_changed": self.control_changed,
            "watermark_changed": self.watermark_changed,
        }


@dataclass(frozen=True, slots=True)
class SynthIDSmokeSummary:
    prompt_count: int
    target_fpr: float
    threshold: float
    threshold_comparator: str
    pristine_control_detection_rate: float
    transformed_control_detection_rate: float
    pristine_watermark_detection_rate: float
    transformed_watermark_detection_rate: float
    watermark_detection_rate_drop: float
    mean_control_pristine_score: float
    mean_control_transformed_score: float
    mean_control_score_shift: float
    mean_watermark_pristine_score: float
    mean_watermark_transformed_score: float
    mean_watermark_score_drop: float
    median_watermark_score_drop: float
    control_transform_rate: float
    watermark_transform_rate: float

    def __post_init__(self) -> None:
        require_int("prompt_count", self.prompt_count)
        if self.prompt_count <= 0:
            raise ValueError("prompt_count must be positive")
        if self.threshold_comparator != ">":
            raise ValueError("smoke threshold comparator must be >")
        for name, value in (
            ("target_fpr", self.target_fpr),
            ("threshold", self.threshold),
            ("pristine_control_detection_rate", self.pristine_control_detection_rate),
            ("transformed_control_detection_rate", self.transformed_control_detection_rate),
            ("pristine_watermark_detection_rate", self.pristine_watermark_detection_rate),
            ("transformed_watermark_detection_rate", self.transformed_watermark_detection_rate),
            ("watermark_detection_rate_drop", self.watermark_detection_rate_drop),
            ("mean_control_pristine_score", self.mean_control_pristine_score),
            ("mean_control_transformed_score", self.mean_control_transformed_score),
            ("mean_control_score_shift", self.mean_control_score_shift),
            ("mean_watermark_pristine_score", self.mean_watermark_pristine_score),
            ("mean_watermark_transformed_score", self.mean_watermark_transformed_score),
            ("mean_watermark_score_drop", self.mean_watermark_score_drop),
            ("median_watermark_score_drop", self.median_watermark_score_drop),
            ("control_transform_rate", self.control_transform_rate),
            ("watermark_transform_rate", self.watermark_transform_rate),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not 0.0 < self.target_fpr < 1.0:
            raise ValueError("target_fpr must be in (0, 1)")
        for name in (
            "pristine_control_detection_rate",
            "transformed_control_detection_rate",
            "pristine_watermark_detection_rate",
            "transformed_watermark_detection_rate",
            "control_transform_rate",
            "watermark_transform_rate",
        ):
            value = float(getattr(self, name))
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class SynthIDSmokeReport:
    algorithm_version: str
    backend_id: str
    backend_version: str
    model_id: str
    detector_id: str
    detector_config_hash: str
    results: tuple[SynthIDSmokePromptResult, ...]
    summary: SynthIDSmokeSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_SMOKE_ALGORITHM_VERSION:
            raise ValueError("unsupported SynthID smoke algorithm version")
        for name, value in (
            ("backend_id", self.backend_id),
            ("backend_version", self.backend_version),
            ("model_id", self.model_id),
            ("detector_id", self.detector_id),
        ):
            require_clean_string(name, value)
        require_sha256("detector_config_hash", self.detector_config_hash)
        if not isinstance(self.results, tuple) or not self.results:
            raise ValueError("results must be a non-empty tuple")
        if any(not isinstance(value, SynthIDSmokePromptResult) for value in self.results):
            raise TypeError("results must contain SynthIDSmokePromptResult values")
        if len({value.prompt_id for value in self.results}) != len(self.results):
            raise ValueError("smoke results must have unique prompt IDs")
        if not isinstance(self.summary, SynthIDSmokeSummary):
            raise TypeError("summary must be a SynthIDSmokeSummary")
        if self.summary.prompt_count != len(self.results):
            raise ValueError("summary prompt count does not match results")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match SynthID smoke report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "detector_id": self.detector_id,
            "detector_config_hash": self.detector_config_hash,
            "results": self.results,
            "summary": self.summary,
        }


def _validate_score(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


def _descriptive_threshold(control_scores: Sequence[float], target_fpr: float) -> float:
    if isinstance(target_fpr, bool) or not isinstance(target_fpr, (int, float)):
        raise TypeError("target_fpr must be a real number")
    target = float(target_fpr)
    if not 0.0 < target < 1.0:
        raise ValueError("target_fpr must be in (0, 1)")
    if not isinstance(control_scores, Sequence) or isinstance(control_scores, (str, bytes, bytearray)):
        raise TypeError("control_scores must be a sequence")
    normalized = tuple(_validate_score("control score", value) for value in control_scores)
    if not normalized:
        raise ValueError("control_scores must not be empty")
    allowed_false_positives = int(math.floor(target * len(normalized)))
    ordered = tuple(sorted(normalized, reverse=True))
    return ordered[min(allowed_false_positives, len(ordered) - 1)]


def _rate(values: Sequence[bool]) -> float:
    return sum(values) / len(values)


def _result(
    prompt: SynthIDSmokePrompt,
    control_pristine: str,
    control_transformed: str,
    watermark_pristine: str,
    watermark_transformed: str,
    control_pristine_score: float,
    control_transformed_score: float,
    watermark_pristine_score: float,
    watermark_transformed_score: float,
) -> SynthIDSmokePromptResult:
    payload = {
        "prompt_id": prompt.prompt_id,
        "seed": prompt.seed,
        "prompt_hash": sha256_text(prompt.text),
        "control_pristine_text": control_pristine,
        "control_transformed_text": control_transformed,
        "watermark_pristine_text": watermark_pristine,
        "watermark_transformed_text": watermark_transformed,
        "control_pristine_score": control_pristine_score,
        "control_transformed_score": control_transformed_score,
        "watermark_pristine_score": watermark_pristine_score,
        "watermark_transformed_score": watermark_transformed_score,
        "control_score_shift": control_transformed_score - control_pristine_score,
        "watermark_score_drop": watermark_pristine_score - watermark_transformed_score,
        "control_changed": control_pristine != control_transformed,
        "watermark_changed": watermark_pristine != watermark_transformed,
    }
    return SynthIDSmokePromptResult(
        prompt.prompt_id,
        prompt.seed,
        payload["prompt_hash"],
        control_pristine,
        control_transformed,
        watermark_pristine,
        watermark_transformed,
        control_pristine_score,
        control_transformed_score,
        watermark_pristine_score,
        watermark_transformed_score,
        payload["control_score_shift"],
        payload["watermark_score_drop"],
        payload["control_changed"],
        payload["watermark_changed"],
        sha256_json(payload),
    )


def run_synthid_smoke(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: SynthIDSmokeBackend,
    *,
    transform: Callable[[str], str] = process_text,
    target_fpr: float = 0.05,
) -> SynthIDSmokeReport:
    if not isinstance(prompts, Sequence) or isinstance(prompts, (str, bytes, bytearray)):
        raise TypeError("prompts must be a sequence")
    prompt_values = tuple(prompts)
    if not prompt_values:
        raise ValueError("prompts must not be empty")
    if any(not isinstance(value, SynthIDSmokePrompt) for value in prompt_values):
        raise TypeError("prompts must contain SynthIDSmokePrompt values")
    if len({value.prompt_id for value in prompt_values}) != len(prompt_values):
        raise ValueError("prompt IDs must be unique")
    if not isinstance(backend, SynthIDSmokeBackend):
        raise TypeError("backend must satisfy SynthIDSmokeBackend")
    if not callable(transform):
        raise TypeError("transform must be callable")
    backend_id = backend.backend_id
    backend_version = backend.backend_version
    model_id = backend.model_id
    detector_id = backend.detector_id
    detector_config_hash = backend.detector_config_hash
    for name, value in (
        ("backend_id", backend_id),
        ("backend_version", backend_version),
        ("model_id", model_id),
        ("detector_id", detector_id),
    ):
        require_clean_string(name, value)
    require_sha256("detector_config_hash", detector_config_hash)

    generated: list[tuple[SynthIDSmokePrompt, str, str, str, str]] = []
    for prompt in prompt_values:
        control_pristine = backend.generate(prompt.text, prompt.seed, watermarked=False)
        watermark_pristine = backend.generate(prompt.text, prompt.seed, watermarked=True)
        if not isinstance(control_pristine, str) or not isinstance(watermark_pristine, str):
            raise TypeError("backend generate must return strings")
        control_transformed = transform(control_pristine)
        watermark_transformed = transform(watermark_pristine)
        if not isinstance(control_transformed, str) or not isinstance(watermark_transformed, str):
            raise TypeError("transform must return strings")
        generated.append(
            (
                prompt,
                control_pristine,
                control_transformed,
                watermark_pristine,
                watermark_transformed,
            )
        )

    results: list[SynthIDSmokePromptResult] = []
    for prompt, control_pristine, control_transformed, watermark_pristine, watermark_transformed in generated:
        control_pristine_score = _validate_score("control pristine score", backend.score(control_pristine))
        control_transformed_score = _validate_score("control transformed score", backend.score(control_transformed))
        watermark_pristine_score = _validate_score("watermark pristine score", backend.score(watermark_pristine))
        watermark_transformed_score = _validate_score("watermark transformed score", backend.score(watermark_transformed))
        results.append(
            _result(
                prompt,
                control_pristine,
                control_transformed,
                watermark_pristine,
                watermark_transformed,
                control_pristine_score,
                control_transformed_score,
                watermark_pristine_score,
                watermark_transformed_score,
            )
        )

    result_values = tuple(results)
    threshold = _descriptive_threshold(tuple(value.control_pristine_score for value in result_values), target_fpr)
    control_pristine_decisions = tuple(value.control_pristine_score > threshold for value in result_values)
    control_transformed_decisions = tuple(value.control_transformed_score > threshold for value in result_values)
    watermark_pristine_decisions = tuple(value.watermark_pristine_score > threshold for value in result_values)
    watermark_transformed_decisions = tuple(value.watermark_transformed_score > threshold for value in result_values)
    watermark_drops = tuple(value.watermark_score_drop for value in result_values)
    summary = SynthIDSmokeSummary(
        prompt_count=len(result_values),
        target_fpr=float(target_fpr),
        threshold=threshold,
        threshold_comparator=">",
        pristine_control_detection_rate=_rate(control_pristine_decisions),
        transformed_control_detection_rate=_rate(control_transformed_decisions),
        pristine_watermark_detection_rate=_rate(watermark_pristine_decisions),
        transformed_watermark_detection_rate=_rate(watermark_transformed_decisions),
        watermark_detection_rate_drop=_rate(watermark_pristine_decisions) - _rate(watermark_transformed_decisions),
        mean_control_pristine_score=statistics.fmean(value.control_pristine_score for value in result_values),
        mean_control_transformed_score=statistics.fmean(value.control_transformed_score for value in result_values),
        mean_control_score_shift=statistics.fmean(value.control_score_shift for value in result_values),
        mean_watermark_pristine_score=statistics.fmean(value.watermark_pristine_score for value in result_values),
        mean_watermark_transformed_score=statistics.fmean(value.watermark_transformed_score for value in result_values),
        mean_watermark_score_drop=statistics.fmean(watermark_drops),
        median_watermark_score_drop=statistics.median(watermark_drops),
        control_transform_rate=_rate(tuple(value.control_changed for value in result_values)),
        watermark_transform_rate=_rate(tuple(value.watermark_changed for value in result_values)),
    )
    payload = {
        "algorithm_version": SYNTHID_SMOKE_ALGORITHM_VERSION,
        "backend_id": backend_id,
        "backend_version": backend_version,
        "model_id": model_id,
        "detector_id": detector_id,
        "detector_config_hash": detector_config_hash,
        "results": result_values,
        "summary": summary,
    }
    return SynthIDSmokeReport(
        SYNTHID_SMOKE_ALGORITHM_VERSION,
        backend_id,
        backend_version,
        model_id,
        detector_id,
        detector_config_hash,
        result_values,
        summary,
        sha256_json(payload),
    )
