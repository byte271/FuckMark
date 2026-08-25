from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_smoke import (
    SYNTHID_SMOKE_ALGORITHM_VERSION,
    SynthIDSmokePrompt,
    SynthIDSmokeReport,
    run_synthid_smoke,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms.registry import historical_visible_edit_transform_registry


def _historical_visible_edit(text: str) -> str:
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(text)
    selected = []
    occupied_until = 0
    for candidate in enumeration.candidates:
        if candidate.start < occupied_until:
            continue
        selected.append(candidate.candidate_id)
        occupied_until = candidate.end
    if not selected:
        return text
    return registry.apply(enumeration, tuple(selected)).output_text


class _FakeBackend:
    backend_id = "fake-synthid"
    backend_version = "1"
    model_id = "fake-model"
    detector_id = "fake-weighted-mean"
    detector_config_hash = sha256_text("fake-detector-config")

    def __init__(self, score_guard=None) -> None:
        self.score_guard = score_guard

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        label = "WATERMARKED" if watermarked else "CONTROL"
        return f"{label} {prompt} I do not agree and I cannot stay."

    def score(self, text: str) -> float:
        if self.score_guard is not None:
            self.score_guard()
        transformed = "don't" in text and "can't" in text
        if text.startswith("WATERMARKED"):
            return 0.15 if transformed else 0.90
        return 0.18 if transformed else 0.20


def _prompts() -> tuple[SynthIDSmokePrompt, ...]:
    return tuple(
        SynthIDSmokePrompt(f"p{index}", f"Prompt {index}.", 1000 + index)
        for index in range(4)
    )


def test_synthid_smoke_measures_paired_watermark_degradation_and_control_shift() -> None:
    report = run_synthid_smoke(_prompts(), _FakeBackend())

    assert isinstance(report, SynthIDSmokeReport)
    assert report.algorithm_version == SYNTHID_SMOKE_ALGORITHM_VERSION
    assert report.summary.prompt_count == 4
    assert report.summary.pristine_control_detection_rate == 0.0
    assert report.summary.transformed_control_detection_rate == 0.0
    assert report.summary.pristine_watermark_detection_rate == 1.0
    assert report.summary.transformed_watermark_detection_rate == 1.0
    assert report.summary.watermark_detection_rate_drop == 0.0
    assert report.summary.mean_watermark_score_drop == pytest.approx(0.0)
    assert report.summary.median_watermark_score_drop == pytest.approx(0.0)
    assert report.summary.mean_control_score_shift == pytest.approx(0.0)
    assert report.summary.control_transform_rate == 0.0
    assert report.summary.watermark_transform_rate == 0.0
    assert not any(value.watermark_changed for value in report.results)
    assert not any(value.control_changed for value in report.results)


def test_historical_visible_edit_smoke_still_contracts_when_requested_explicitly() -> None:
    report = run_synthid_smoke(_prompts(), _FakeBackend(), transform=_historical_visible_edit)
    assert report.summary.transformed_watermark_detection_rate == 0.0
    assert report.summary.watermark_transform_rate == 1.0
    assert report.summary.control_transform_rate == 1.0
    assert report.summary.mean_watermark_score_drop == pytest.approx(0.75)


def test_synthid_smoke_finishes_all_key_blind_transforms_before_detector_scoring() -> None:
    transformed = {"count": 0}
    expected = len(_prompts()) * 2

    def transform(text: str) -> str:
        transformed["count"] += 1
        return text.replace("do not", "don't").replace("cannot", "can't")

    def guard() -> None:
        assert transformed["count"] == expected

    report = run_synthid_smoke(_prompts(), _FakeBackend(guard), transform=transform)

    assert report.summary.mean_watermark_score_drop > 0.0


def test_synthid_smoke_report_hash_rejects_tampering() -> None:
    report = run_synthid_smoke(_prompts(), _FakeBackend())

    with pytest.raises(ValueError, match="report_hash"):
        replace(report, backend_version="tampered")


def test_synthid_smoke_rejects_duplicate_prompt_ids() -> None:
    prompts = (
        SynthIDSmokePrompt("same", "One.", 1),
        SynthIDSmokePrompt("same", "Two.", 2),
    )

    with pytest.raises(ValueError, match="prompt IDs"):
        run_synthid_smoke(prompts, _FakeBackend())


def test_synthid_smoke_threshold_is_descriptive_and_uses_pristine_controls_only() -> None:
    class Backend(_FakeBackend):
        def score(self, text: str) -> float:
            transformed = "don't" in text and "can't" in text
            if text.startswith("WATERMARKED"):
                return 0.30 if transformed else 0.80
            return 0.95 if transformed else 0.20

    report = run_synthid_smoke(_prompts(), Backend(), target_fpr=0.05, transform=_historical_visible_edit)

    assert report.summary.threshold == pytest.approx(0.20)
    assert report.summary.pristine_control_detection_rate == 0.0
    assert report.summary.transformed_control_detection_rate == 1.0
