from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN
from ..hashing import sha256_json
from .synthid_smoke import SynthIDSmokePromptResult, SynthIDSmokeReport


E26_OPEN_ADAPTER_TRANSFER_ALGORITHM_VERSION = "e26-open-adapter-transfer-v1"
DEEPMIND_BACKEND_ID = "deepmind-synthid-text-reference-generation"
HUGGINGFACE_BACKEND_ID = "huggingface-transformers-synthid-generation"
TRANSFER_INTERPRETATION_POLICY = "descriptive-native-adapter-transfer-v1"
_DIRECTION_TOLERANCE = 1e-15


def _finite(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


def _direction(value: float) -> int:
    if value > _DIRECTION_TOLERANCE:
        return 1
    if value < -_DIRECTION_TOLERANCE:
        return -1
    return 0


def _pearson(xs: tuple[float, ...], ys: tuple[float, ...]) -> float | None:
    if len(xs) != len(ys):
        raise ValueError("correlation vectors must have the same length")
    if len(xs) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    centered_x = tuple(value - mean_x for value in xs)
    centered_y = tuple(value - mean_y for value in ys)
    sum_x2 = math.fsum(value * value for value in centered_x)
    sum_y2 = math.fsum(value * value for value in centered_y)
    if sum_x2 <= 0.0 or sum_y2 <= 0.0:
        return None
    return math.fsum(x * y for x, y in zip(centered_x, centered_y)) / math.sqrt(sum_x2 * sum_y2)


@dataclass(frozen=True, slots=True)
class E26AdapterTransferPair:
    prompt_id: str
    seed: int
    prompt_hash: str
    deepmind_result_hash: str
    huggingface_result_hash: str
    deepmind_control_changed: bool
    huggingface_control_changed: bool
    deepmind_watermark_changed: bool
    huggingface_watermark_changed: bool
    deepmind_control_score_shift: float
    huggingface_control_score_shift: float
    deepmind_watermark_score_drop: float
    huggingface_watermark_score_drop: float
    deepmind_watermark_drop_direction: int
    huggingface_watermark_drop_direction: int
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("prompt_id", self.prompt_id)
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must fit in 64 bits")
        for name in ("prompt_hash", "deepmind_result_hash", "huggingface_result_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        for name in (
            "deepmind_control_changed",
            "huggingface_control_changed",
            "deepmind_watermark_changed",
            "huggingface_watermark_changed",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")
        for name in (
            "deepmind_control_score_shift",
            "huggingface_control_score_shift",
            "deepmind_watermark_score_drop",
            "huggingface_watermark_score_drop",
        ):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))
        for name in ("deepmind_watermark_drop_direction", "huggingface_watermark_drop_direction"):
            value = getattr(self, name)
            require_int(name, value)
            if value not in (-1, 0, 1):
                raise ValueError(f"{name} must be -1, 0, or 1")
        if self.deepmind_watermark_drop_direction != _direction(self.deepmind_watermark_score_drop):
            raise ValueError("deepmind watermark direction does not match score drop")
        if self.huggingface_watermark_drop_direction != _direction(self.huggingface_watermark_score_drop):
            raise ValueError("huggingface watermark direction does not match score drop")
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E26 adapter transfer pair")

    @property
    def both_watermark_changed(self) -> bool:
        return self.deepmind_watermark_changed and self.huggingface_watermark_changed

    @property
    def same_watermark_drop_direction(self) -> bool:
        return self.deepmind_watermark_drop_direction == self.huggingface_watermark_drop_direction

    def _payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "seed": self.seed,
            "prompt_hash": self.prompt_hash,
            "deepmind_result_hash": self.deepmind_result_hash,
            "huggingface_result_hash": self.huggingface_result_hash,
            "deepmind_control_changed": self.deepmind_control_changed,
            "huggingface_control_changed": self.huggingface_control_changed,
            "deepmind_watermark_changed": self.deepmind_watermark_changed,
            "huggingface_watermark_changed": self.huggingface_watermark_changed,
            "deepmind_control_score_shift": self.deepmind_control_score_shift,
            "huggingface_control_score_shift": self.huggingface_control_score_shift,
            "deepmind_watermark_score_drop": self.deepmind_watermark_score_drop,
            "huggingface_watermark_score_drop": self.huggingface_watermark_score_drop,
            "deepmind_watermark_drop_direction": self.deepmind_watermark_drop_direction,
            "huggingface_watermark_drop_direction": self.huggingface_watermark_drop_direction,
        }


@dataclass(frozen=True, slots=True)
class E26OpenAdapterTransferSummary:
    prompt_count: int
    both_watermark_changed_count: int
    either_watermark_changed_count: int
    both_control_changed_count: int
    same_watermark_drop_direction_count: int
    positive_drop_both_count: int
    positive_drop_deepmind_only_count: int
    positive_drop_huggingface_only_count: int
    nonpositive_drop_both_count: int
    mean_deepmind_watermark_score_drop: float
    mean_huggingface_watermark_score_drop: float
    median_deepmind_watermark_score_drop: float
    median_huggingface_watermark_score_drop: float
    mean_absolute_watermark_drop_difference: float
    watermark_drop_pearson: float | None
    deepmind_pristine_detection_rate: float
    deepmind_transformed_detection_rate: float
    huggingface_pristine_detection_rate: float
    huggingface_transformed_detection_rate: float

    def __post_init__(self) -> None:
        for name in (
            "prompt_count",
            "both_watermark_changed_count",
            "either_watermark_changed_count",
            "both_control_changed_count",
            "same_watermark_drop_direction_count",
            "positive_drop_both_count",
            "positive_drop_deepmind_only_count",
            "positive_drop_huggingface_only_count",
            "nonpositive_drop_both_count",
        ):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.prompt_count <= 0:
            raise ValueError("prompt_count must be positive")
        for name in (
            "both_watermark_changed_count",
            "either_watermark_changed_count",
            "both_control_changed_count",
            "same_watermark_drop_direction_count",
            "positive_drop_both_count",
            "positive_drop_deepmind_only_count",
            "positive_drop_huggingface_only_count",
            "nonpositive_drop_both_count",
        ):
            if getattr(self, name) > self.prompt_count:
                raise ValueError(f"{name} cannot exceed prompt_count")
        for name in (
            "mean_deepmind_watermark_score_drop",
            "mean_huggingface_watermark_score_drop",
            "median_deepmind_watermark_score_drop",
            "median_huggingface_watermark_score_drop",
            "mean_absolute_watermark_drop_difference",
            "deepmind_pristine_detection_rate",
            "deepmind_transformed_detection_rate",
            "huggingface_pristine_detection_rate",
            "huggingface_transformed_detection_rate",
        ):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))
        for name in (
            "deepmind_pristine_detection_rate",
            "deepmind_transformed_detection_rate",
            "huggingface_pristine_detection_rate",
            "huggingface_transformed_detection_rate",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.mean_absolute_watermark_drop_difference < 0.0:
            raise ValueError("mean_absolute_watermark_drop_difference must be non-negative")
        if self.watermark_drop_pearson is not None:
            object.__setattr__(self, "watermark_drop_pearson", _finite("watermark_drop_pearson", self.watermark_drop_pearson))
            if not -1.0 - 1e-12 <= self.watermark_drop_pearson <= 1.0 + 1e-12:
                raise ValueError("watermark_drop_pearson must lie in [-1, 1]")

    @property
    def direction_concordance_rate(self) -> float:
        return self.same_watermark_drop_direction_count / self.prompt_count


@dataclass(frozen=True, slots=True)
class E26OpenAdapterTransferReport:
    algorithm_version: str
    interpretation_policy: str
    deepmind_source_commit: str
    huggingface_source_commit: str
    deepmind_report_hash: str
    huggingface_report_hash: str
    model_id: str
    target_fpr: float
    pairs: tuple[E26AdapterTransferPair, ...]
    summary: E26OpenAdapterTransferSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E26_OPEN_ADAPTER_TRANSFER_ALGORITHM_VERSION:
            raise ValueError("unsupported E26 adapter transfer algorithm version")
        if self.interpretation_policy != TRANSFER_INTERPRETATION_POLICY:
            raise ValueError("unsupported E26 interpretation policy")
        if self.deepmind_source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit:
            raise ValueError("deepmind source commit does not match the pinned reference implementation")
        if self.huggingface_source_commit != HUGGINGFACE_SYNTHID_SOURCE_PIN.commit:
            raise ValueError("huggingface source commit does not match the pinned maintained implementation")
        require_sha256("deepmind_report_hash", self.deepmind_report_hash)
        require_sha256("huggingface_report_hash", self.huggingface_report_hash)
        require_clean_string("model_id", self.model_id)
        object.__setattr__(self, "target_fpr", _finite("target_fpr", self.target_fpr))
        if not 0.0 < self.target_fpr < 1.0:
            raise ValueError("target_fpr must lie in (0, 1)")
        if not isinstance(self.pairs, tuple) or not self.pairs:
            raise ValueError("pairs must be a non-empty tuple")
        if any(not isinstance(row, E26AdapterTransferPair) for row in self.pairs):
            raise TypeError("pairs must contain E26AdapterTransferPair values")
        if tuple(row.prompt_id for row in self.pairs) != tuple(sorted(row.prompt_id for row in self.pairs)):
            raise ValueError("pairs must be canonically ordered by prompt_id")
        if len({row.prompt_id for row in self.pairs}) != len(self.pairs):
            raise ValueError("pairs must contain unique prompt IDs")
        if not isinstance(self.summary, E26OpenAdapterTransferSummary):
            raise TypeError("summary must be an E26OpenAdapterTransferSummary")
        if self.summary.prompt_count != len(self.pairs):
            raise ValueError("summary prompt_count does not match pairs")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match E26 open adapter transfer report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "interpretation_policy": self.interpretation_policy,
            "deepmind_source_commit": self.deepmind_source_commit,
            "huggingface_source_commit": self.huggingface_source_commit,
            "deepmind_report_hash": self.deepmind_report_hash,
            "huggingface_report_hash": self.huggingface_report_hash,
            "model_id": self.model_id,
            "target_fpr": self.target_fpr,
            "pairs": self.pairs,
            "summary": self.summary,
        }


def _pair(deepmind: SynthIDSmokePromptResult, huggingface: SynthIDSmokePromptResult) -> E26AdapterTransferPair:
    if deepmind.prompt_id != huggingface.prompt_id:
        raise ValueError("adapter result prompt IDs do not match")
    if deepmind.seed != huggingface.seed:
        raise ValueError("adapter result seeds do not match")
    if deepmind.prompt_hash != huggingface.prompt_hash:
        raise ValueError("adapter result prompt hashes do not match")
    payload = {
        "prompt_id": deepmind.prompt_id,
        "seed": deepmind.seed,
        "prompt_hash": deepmind.prompt_hash,
        "deepmind_result_hash": deepmind.result_hash,
        "huggingface_result_hash": huggingface.result_hash,
        "deepmind_control_changed": deepmind.control_changed,
        "huggingface_control_changed": huggingface.control_changed,
        "deepmind_watermark_changed": deepmind.watermark_changed,
        "huggingface_watermark_changed": huggingface.watermark_changed,
        "deepmind_control_score_shift": deepmind.control_score_shift,
        "huggingface_control_score_shift": huggingface.control_score_shift,
        "deepmind_watermark_score_drop": deepmind.watermark_score_drop,
        "huggingface_watermark_score_drop": huggingface.watermark_score_drop,
        "deepmind_watermark_drop_direction": _direction(deepmind.watermark_score_drop),
        "huggingface_watermark_drop_direction": _direction(huggingface.watermark_score_drop),
    }
    return E26AdapterTransferPair(
        deepmind.prompt_id,
        deepmind.seed,
        deepmind.prompt_hash,
        deepmind.result_hash,
        huggingface.result_hash,
        deepmind.control_changed,
        huggingface.control_changed,
        deepmind.watermark_changed,
        huggingface.watermark_changed,
        deepmind.control_score_shift,
        huggingface.control_score_shift,
        deepmind.watermark_score_drop,
        huggingface.watermark_score_drop,
        payload["deepmind_watermark_drop_direction"],
        payload["huggingface_watermark_drop_direction"],
        sha256_json(payload),
    )


def build_e26_open_adapter_transfer(
    deepmind_report: SynthIDSmokeReport,
    huggingface_report: SynthIDSmokeReport,
) -> E26OpenAdapterTransferReport:
    if not isinstance(deepmind_report, SynthIDSmokeReport) or not isinstance(huggingface_report, SynthIDSmokeReport):
        raise TypeError("E26 requires two SynthIDSmokeReport values")
    if deepmind_report.backend_id != DEEPMIND_BACKEND_ID:
        raise ValueError("deepmind report does not come from the pinned DeepMind reference generation backend")
    if huggingface_report.backend_id != HUGGINGFACE_BACKEND_ID:
        raise ValueError("huggingface report does not come from the pinned maintained Transformers generation backend")
    if deepmind_report.model_id != huggingface_report.model_id:
        raise ValueError("adapter transfer reports must use the same model_id")
    if not math.isclose(
        deepmind_report.summary.target_fpr,
        huggingface_report.summary.target_fpr,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ValueError("adapter transfer reports must use the same target_fpr")
    deepmind_by_id = {row.prompt_id: row for row in deepmind_report.results}
    huggingface_by_id = {row.prompt_id: row for row in huggingface_report.results}
    if set(deepmind_by_id) != set(huggingface_by_id):
        raise ValueError("adapter transfer reports must contain the same prompt IDs")
    pairs = tuple(
        _pair(deepmind_by_id[prompt_id], huggingface_by_id[prompt_id])
        for prompt_id in sorted(deepmind_by_id)
    )
    deepmind_drops = tuple(row.deepmind_watermark_score_drop for row in pairs)
    huggingface_drops = tuple(row.huggingface_watermark_score_drop for row in pairs)
    summary = E26OpenAdapterTransferSummary(
        prompt_count=len(pairs),
        both_watermark_changed_count=sum(row.both_watermark_changed for row in pairs),
        either_watermark_changed_count=sum(row.deepmind_watermark_changed or row.huggingface_watermark_changed for row in pairs),
        both_control_changed_count=sum(row.deepmind_control_changed and row.huggingface_control_changed for row in pairs),
        same_watermark_drop_direction_count=sum(row.same_watermark_drop_direction for row in pairs),
        positive_drop_both_count=sum(
            row.deepmind_watermark_drop_direction > 0 and row.huggingface_watermark_drop_direction > 0
            for row in pairs
        ),
        positive_drop_deepmind_only_count=sum(
            row.deepmind_watermark_drop_direction > 0 and row.huggingface_watermark_drop_direction <= 0
            for row in pairs
        ),
        positive_drop_huggingface_only_count=sum(
            row.deepmind_watermark_drop_direction <= 0 and row.huggingface_watermark_drop_direction > 0
            for row in pairs
        ),
        nonpositive_drop_both_count=sum(
            row.deepmind_watermark_drop_direction <= 0 and row.huggingface_watermark_drop_direction <= 0
            for row in pairs
        ),
        mean_deepmind_watermark_score_drop=statistics.fmean(deepmind_drops),
        mean_huggingface_watermark_score_drop=statistics.fmean(huggingface_drops),
        median_deepmind_watermark_score_drop=statistics.median(deepmind_drops),
        median_huggingface_watermark_score_drop=statistics.median(huggingface_drops),
        mean_absolute_watermark_drop_difference=statistics.fmean(
            abs(left - right) for left, right in zip(deepmind_drops, huggingface_drops)
        ),
        watermark_drop_pearson=_pearson(deepmind_drops, huggingface_drops),
        deepmind_pristine_detection_rate=deepmind_report.summary.pristine_watermark_detection_rate,
        deepmind_transformed_detection_rate=deepmind_report.summary.transformed_watermark_detection_rate,
        huggingface_pristine_detection_rate=huggingface_report.summary.pristine_watermark_detection_rate,
        huggingface_transformed_detection_rate=huggingface_report.summary.transformed_watermark_detection_rate,
    )
    payload = {
        "algorithm_version": E26_OPEN_ADAPTER_TRANSFER_ALGORITHM_VERSION,
        "interpretation_policy": TRANSFER_INTERPRETATION_POLICY,
        "deepmind_source_commit": DEEPMIND_REFERENCE_SOURCE_PIN.commit,
        "huggingface_source_commit": HUGGINGFACE_SYNTHID_SOURCE_PIN.commit,
        "deepmind_report_hash": deepmind_report.report_hash,
        "huggingface_report_hash": huggingface_report.report_hash,
        "model_id": deepmind_report.model_id,
        "target_fpr": deepmind_report.summary.target_fpr,
        "pairs": pairs,
        "summary": summary,
    }
    return E26OpenAdapterTransferReport(
        E26_OPEN_ADAPTER_TRANSFER_ALGORITHM_VERSION,
        TRANSFER_INTERPRETATION_POLICY,
        DEEPMIND_REFERENCE_SOURCE_PIN.commit,
        HUGGINGFACE_SYNTHID_SOURCE_PIN.commit,
        deepmind_report.report_hash,
        huggingface_report.report_hash,
        deepmind_report.model_id,
        deepmind_report.summary.target_fpr,
        pairs,
        summary,
        sha256_json(payload),
    )
