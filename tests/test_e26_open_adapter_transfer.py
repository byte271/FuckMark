from __future__ import annotations

import json
from dataclasses import replace

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.e26_open_adapter_transfer import synthid_smoke_report_from_mapping
from fuckmark.experiments.e26_open_adapter_transfer import (
    DEEPMIND_BACKEND_ID,
    HUGGINGFACE_BACKEND_ID,
    build_e26_open_adapter_transfer,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt, run_synthid_smoke
from fuckmark.hashing import sha256_text


class _Backend:
    backend_version = "test-v1"
    model_id = "openai-community/gpt2"
    detector_id = "weighted-mean"

    def __init__(self, backend_id: str, detector_tag: str, watermark_drop: float) -> None:
        self.backend_id = backend_id
        self.detector_config_hash = sha256_text(detector_tag)
        self._watermark_drop = watermark_drop

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        prefix = "WATERMARKED" if watermarked else "CONTROL"
        return f"{prefix} {prompt} I do not stay and I cannot wait."

    def score(self, text: str) -> float:
        transformed = "don't" in text and "can't" in text
        if text.startswith("WATERMARKED"):
            return 0.80 - self._watermark_drop if transformed else 0.80
        return 0.21 if transformed else 0.20


def _prompts() -> tuple[SynthIDSmokePrompt, ...]:
    return tuple(
        SynthIDSmokePrompt(f"p{index}", f"Prompt {index}.", 5000 + index)
        for index in range(5)
    )


def _reports(deepmind_drop: float = 0.30, huggingface_drop: float = 0.20):
    deepmind = run_synthid_smoke(
        _prompts(),
        _Backend(DEEPMIND_BACKEND_ID, "deepmind", deepmind_drop),
        transform=lambda text: text.replace("do not", "don't").replace("cannot", "can't"),
    )
    huggingface = run_synthid_smoke(
        _prompts(),
        _Backend(HUGGINGFACE_BACKEND_ID, "huggingface", huggingface_drop),
        transform=lambda text: text.replace("do not", "don't").replace("cannot", "can't"),
    )
    return deepmind, huggingface


def test_e26_builds_content_addressed_native_adapter_transfer_report() -> None:
    deepmind, huggingface = _reports()
    report = build_e26_open_adapter_transfer(deepmind, huggingface)

    assert report.deepmind_report_hash == deepmind.report_hash
    assert report.huggingface_report_hash == huggingface.report_hash
    assert report.summary.prompt_count == 5
    assert report.summary.both_watermark_changed_count == 5
    assert report.summary.both_control_changed_count == 5
    assert report.summary.same_watermark_drop_direction_count == 5
    assert report.summary.positive_drop_both_count == 5
    assert report.summary.positive_drop_deepmind_only_count == 0
    assert report.summary.positive_drop_huggingface_only_count == 0
    assert report.summary.nonpositive_drop_both_count == 0
    assert report.summary.mean_deepmind_watermark_score_drop == pytest.approx(0.30)
    assert report.summary.mean_huggingface_watermark_score_drop == pytest.approx(0.20)
    assert report.summary.mean_absolute_watermark_drop_difference == pytest.approx(0.10)
    assert report.summary.direction_concordance_rate == 1.0
    assert report.summary.watermark_drop_pearson is None


def test_e26_reports_direction_disagreement_without_promoting_a_claim() -> None:
    deepmind, huggingface = _reports(deepmind_drop=0.25, huggingface_drop=-0.05)
    report = build_e26_open_adapter_transfer(deepmind, huggingface)

    assert report.summary.same_watermark_drop_direction_count == 0
    assert report.summary.positive_drop_deepmind_only_count == 5
    assert report.summary.direction_concordance_rate == 0.0
    assert report.interpretation_policy.startswith("descriptive-")


def test_e26_rejects_wrong_backend_identity_and_prompt_mismatch() -> None:
    deepmind, huggingface = _reports()
    wrong_backend = run_synthid_smoke(
        _prompts(),
        _Backend("not-deepmind", "deepmind", 0.3),
        transform=lambda text: text.replace("do not", "don't").replace("cannot", "can't"),
    )
    with pytest.raises(ValueError, match="DeepMind"):
        build_e26_open_adapter_transfer(wrong_backend, huggingface)

    changed_prompts = tuple(
        SynthIDSmokePrompt(f"q{index}", f"Prompt {index}.", 5000 + index)
        for index in range(5)
    )
    mismatch = run_synthid_smoke(
        changed_prompts,
        _Backend(HUGGINGFACE_BACKEND_ID, "huggingface", 0.2),
        transform=lambda text: text.replace("do not", "don't").replace("cannot", "can't"),
    )
    with pytest.raises(ValueError, match="same prompt IDs"):
        build_e26_open_adapter_transfer(deepmind, mismatch)


def test_e26_smoke_json_roundtrip_is_hash_preserving_and_fail_closed() -> None:
    deepmind, _ = _reports()
    mapping = json.loads(canonical_json_text(deepmind))
    loaded = synthid_smoke_report_from_mapping(mapping)
    assert loaded == deepmind
    assert loaded.report_hash == deepmind.report_hash

    tampered = json.loads(canonical_json_text(deepmind))
    tampered["results"][0]["watermark_score_drop"] = 123.0
    with pytest.raises(ValueError, match="result_hash"):
        synthid_smoke_report_from_mapping(tampered)

    extra = json.loads(canonical_json_text(deepmind))
    extra["unexpected"] = True
    with pytest.raises(ValueError, match="fields do not match schema"):
        synthid_smoke_report_from_mapping(extra)


def test_e26_report_rejects_tampering() -> None:
    report = build_e26_open_adapter_transfer(*_reports())
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, model_id="tampered-model")
    with pytest.raises(ValueError, match="row_hash"):
        replace(report.pairs[0], deepmind_watermark_score_drop=0.123)
