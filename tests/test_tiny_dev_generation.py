from __future__ import annotations

from collections import defaultdict

import pytest

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
from fuckmark.corpus.tiny_dev_generation import (
    TINY_DEV_GENERATION_ALGORITHM_VERSION,
    TINY_DEV_PROMPT_LICENSE_ID,
    TINY_DEV_PROMPT_SOURCE_ID,
    TINY_DEV_SEED_POLICY_ID,
    TinyDevGeneratedContinuation,
    TinyDevGenerationError,
    build_real_tiny_dev_corpus,
    build_tiny_dev_prompt_records,
)
from fuckmark.hashing import sha256_json, sha256_text


class FakeTinyDevBackend:
    def __init__(self, *, short_first_attempt: bool = False, always_short: bool = False) -> None:
        self._model = ModelTokenizerIdentity.create(
            model_id="example/tiny-dev-model",
            model_revision="a" * 40,
            tokenizer_id="example/tiny-dev-tokenizer",
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
        self._short_first_attempt = short_first_attempt
        self._always_short = always_short
        self.calls: defaultdict[tuple[str, bool], list[int]] = defaultdict(list)

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
            backend_id="fake-tiny-dev",
            backend_version="1",
        )

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> TinyDevGeneratedContinuation:
        self.calls[(prompt, watermarked)].append(seed)
        first_seed = self.calls[(prompt, watermarked)][0]
        short = self._always_short or (
            self._short_first_attempt and seed == first_seed
        )
        continuation_length = 63 if short else 64
        prompt_token = 10 + (sum(prompt.encode("utf-8")) % 1000)
        label_offset = 100_000 if watermarked else 200_000
        continuation = tuple(
            label_offset + ((seed * 131 + index) % 90_000)
            for index in range(continuation_length)
        )
        text = (
            f"{'watermarked' if watermarked else 'control'} output for "
            f"{sha256_text(prompt)[:12]} seed {seed}"
        )
        text_only = tuple(300_000 + ((seed * 17 + index) % 80_000) for index in range(16))
        return TinyDevGeneratedContinuation(
            text=text,
            input_token_ids=(prompt_token, prompt_token + 1),
            attention_mask=(1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=text_only,
        )


def test_prompt_suite_matches_frozen_tiny_dev_matrix() -> None:
    prompts = build_tiny_dev_prompt_records()
    assert len(prompts) == 104
    assert len({prompt.prompt_id for prompt in prompts}) == 104
    assert len({prompt.prompt_family_id for prompt in prompts}) == 104
    assert {prompt.source_id for prompt in prompts} == {TINY_DEV_PROMPT_SOURCE_ID}
    assert {prompt.license_id for prompt in prompts} == {TINY_DEV_PROMPT_LICENSE_ID}
    assert len({prompt.source_hash for prompt in prompts}) == 1
    counts = defaultdict(int)
    for prompt in prompts:
        counts[(prompt.split, prompt.domain)] += 1
    for domain in CorpusDomain:
        assert counts[(CorpusSplit.THRESHOLD_CALIBRATION, domain)] == 25
        assert counts[(CorpusSplit.ATTACK_DEVELOPMENT, domain)] == 1


def test_real_tiny_dev_runner_builds_exact_paired_corpus() -> None:
    backend = FakeTinyDevBackend()
    artifact = build_real_tiny_dev_corpus(backend, seed_base=5000)
    assert artifact.algorithm_version == "tiny-dev-corpus-v2"
    assert len(artifact.manifest.prompts) == 104
    assert len(artifact.manifest.samples) == 208
    assert all(sample.generation_realized_length == 64 for sample in artifact.manifest.samples)
    assert all(sample.watermark.key_split is KeySplit.DEV for sample in artifact.manifest.samples)
    assert all(
        sample.generation.seed_policy_id == TINY_DEV_SEED_POLICY_ID
        for sample in artifact.manifest.samples
    )
    by_match = defaultdict(list)
    for sample in artifact.manifest.samples:
        by_match[sample.match_id].append(sample)
    assert len(by_match) == 104
    for pair in by_match.values():
        assert {sample.label for sample in pair} == {
            WatermarkLabel.UNWATERMARKED,
            WatermarkLabel.WATERMARKED,
        }
        assert len({sample.generation.seed for sample in pair}) == 1
        assert len({sample.generation.matching_signature_hash for sample in pair}) == 1
        assert all(sample.text_only_tokens is not None for sample in pair)


def test_real_tiny_dev_runner_retries_whole_pair_after_early_eos() -> None:
    backend = FakeTinyDevBackend(short_first_attempt=True)
    artifact = build_real_tiny_dev_corpus(backend, seed_base=7000, max_attempts=2)
    first_prompt = build_tiny_dev_prompt_records()[0]
    first_pair = tuple(
        sample for sample in artifact.manifest.samples
        if sample.prompt_id == first_prompt.prompt_id
    )
    assert len(first_pair) == 2
    assert {sample.generation.seed for sample in first_pair} == {7001}
    assert backend.calls[(first_prompt.text, False)] == [7000, 7001]
    assert backend.calls[(first_prompt.text, True)] == [7000, 7001]


def test_real_tiny_dev_runner_fails_closed_when_exact_length_cannot_be_reached() -> None:
    backend = FakeTinyDevBackend(always_short=True)
    with pytest.raises(TinyDevGenerationError, match="within 2 deterministic attempts"):
        build_real_tiny_dev_corpus(backend, seed_base=9000, max_attempts=2)


def test_generation_contract_rejects_invalid_continuation_shapes() -> None:
    with pytest.raises(ValueError, match="attention_mask length"):
        TinyDevGeneratedContinuation(
            text="output",
            input_token_ids=(1, 2),
            attention_mask=(1,),
            continuation_token_ids=(3,),
            text_only_token_ids=(3,),
        )
    assert TINY_DEV_GENERATION_ALGORITHM_VERSION == "tiny-dev-generation-v1"
