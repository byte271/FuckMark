from __future__ import annotations

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSplit,
    GenerationParameters,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    WatermarkCondition,
    WatermarkLabel,
)
from fuckmark.corpus.measurement_calibration import (
    MEASUREMENT_CALIBRATION_AUDIT_COUNT,
    MEASUREMENT_CALIBRATION_NEGATIVE_COUNT,
    MEASUREMENT_CALIBRATION_SAMPLE_COUNT,
    build_measurement_calibration_corpus,
)
from fuckmark.corpus.tiny_dev_generation import (
    TINY_DEV_SEED_POLICY_ID,
    TinyDevGeneratedContinuation,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.tiny_dev_measurement_calibration_hf import (
    build_measurement_calibration_prompt_records,
    build_real_measurement_calibration_corpus,
)


class FakeCalibrationBackend:
    def __init__(self) -> None:
        self._model = ModelTokenizerIdentity.create(
            model_id="example/calibration-model",
            model_revision="a" * 40,
            tokenizer_id="example/calibration-tokenizer",
            tokenizer_revision="b" * 40,
            chat_template_present=False,
            chat_template_hash=sha256_text(""),
            special_token_map_hash=sha256_json({"eos_token": "<eos>", "pad_token": "<pad>"}),
            padding_side=PaddingSide.LEFT,
            bos_token_id=None,
            eos_token_id=2,
            pad_token_id=0,
            add_bos_token=False,
            add_eos_token=False,
        )
        self._watermark = WatermarkCondition.create(
            sha256_json({"ngram_len": 5, "keys": (1, 2, 3)}),
            KeySplit.DEV,
            "dev-test-key",
        )

    @property
    def model_identity(self) -> ModelTokenizerIdentity:
        return self._model

    @property
    def watermark_condition(self) -> WatermarkCondition:
        return self._watermark

    def generation_parameters(self, seed: int) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id=TINY_DEV_SEED_POLICY_ID,
            temperature=0.8,
            top_k=50,
            top_p=0.95,
            max_new_tokens=64,
            do_sample=True,
            dtype="float32",
            device="cpu",
            backend_id="fake-calibration",
            backend_version="1",
        )

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> TinyDevGeneratedContinuation:
        assert watermarked is False
        prompt_token = 10 + (sum(prompt.encode("utf-8")) % 1000)
        continuation = tuple(
            200_000 + ((seed * 977 + index) % 90_000)
            for index in range(64)
        )
        text = f"calibration negative for {sha256_text(prompt)[:12]} seed {seed}"
        text_only = tuple(300_000 + ((seed * 31 + index) % 80_000) for index in range(16))
        return TinyDevGeneratedContinuation(
            text=text,
            input_token_ids=(prompt_token, prompt_token + 1),
            attention_mask=(1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=text_only,
        )


def test_measurement_calibration_prompt_records_are_frozen_and_disjoint() -> None:
    prompts = build_measurement_calibration_prompt_records()
    assert len(prompts) == 160
    assert len({prompt.prompt_id for prompt in prompts}) == 160
    counts: dict[CorpusDomain, int] = {}
    for prompt in prompts:
        counts[prompt.domain] = counts.get(prompt.domain, 0) + 1
    assert set(counts.values()) == {40}
    from fuckmark.corpus.tiny_dev_v3_generation import build_tiny_dev_v3_prompt_records

    prior_texts = {
        prompt.text
        for prompt in build_tiny_dev_v3_prompt_records(16)
    }
    assert not any(prompt.text in prior_texts for prompt in prompts)


def test_measurement_calibration_corpus_builds_with_frozen_split() -> None:
    backend = FakeCalibrationBackend()
    artifact = build_real_measurement_calibration_corpus(backend, seed_base=6000)
    assert len(artifact.manifest.samples) == MEASUREMENT_CALIBRATION_SAMPLE_COUNT == 1280
    assert artifact.negative_count == MEASUREMENT_CALIBRATION_NEGATIVE_COUNT == 1024
    assert artifact.audit_count == MEASUREMENT_CALIBRATION_AUDIT_COUNT == 256
    calibration = artifact.calibration_samples()
    audit = artifact.audit_samples()
    assert len(calibration) == 1024
    assert len(audit) == 256
    assert not {sample.sample_id for sample in calibration} & {sample.sample_id for sample in audit}
    assert all(sample.split is CorpusSplit.THRESHOLD_CALIBRATION for sample in artifact.manifest.samples)
    assert all(sample.label is WatermarkLabel.UNWATERMARKED for sample in artifact.manifest.samples)
    text = canonical_json_text(artifact) + "\n"
    assert len(text) > 0


def test_measurement_calibration_builder_return_type_is_importable() -> None:
    from typing import get_type_hints

    hints = get_type_hints(build_real_measurement_calibration_corpus)
    assert hints["return"].__name__ == "MeasurementCalibrationCorpus"


def test_measurement_calibration_rejects_wrong_sample_count() -> None:
    backend = FakeCalibrationBackend()
    prompts = build_measurement_calibration_prompt_records()
    with pytest.raises(Exception):
        build_measurement_calibration_corpus("bad-corpus", prompts, ())
