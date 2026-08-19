from __future__ import annotations

import pytest

from fuckmark.corpus.generation import GenerationParameters, WatermarkCondition
from fuckmark.corpus.identity import ModelTokenizerIdentity, PaddingSide
from fuckmark.corpus.mid_dev import (
    MID_DEV_SEED_BASE,
    MID_DEV_SOURCE_COUNT,
    mid_dev_seed_for_prompt,
    mid_dev_target_length_for_prompt,
)
from fuckmark.corpus.mid_dev_generation import (
    MID_DEV_SEED_POLICY_ID,
    MidDevGeneratedContinuation,
    MidDevGenerationError,
    build_real_mid_dev_corpus,
)
from fuckmark.corpus.schema import KeySplit, WatermarkLabel
from fuckmark.hashing import sha256_json, sha256_text


class _FakeBackend:
    def __init__(self, *, wrong_length: bool = False) -> None:
        revision = "a" * 40
        self._identity = ModelTokenizerIdentity.create(
            model_id="fake-middev-model",
            model_revision=revision,
            tokenizer_id="fake-middev-model",
            tokenizer_revision=revision,
            chat_template_present=False,
            chat_template_hash=sha256_text(""),
            special_token_map_hash=sha256_json({}),
            padding_side=PaddingSide.LEFT,
            bos_token_id=1,
            eos_token_id=2,
            pad_token_id=2,
            add_bos_token=False,
            add_eos_token=False,
        )
        self._watermark = WatermarkCondition.create(
            sha256_text("fake-watermark-config"),
            KeySplit.DEV,
            "fake-middev-dev-key",
        )
        self._wrong_length = wrong_length

    @property
    def model_identity(self) -> ModelTokenizerIdentity:
        return self._identity

    @property
    def watermark_condition(self) -> WatermarkCondition:
        return self._watermark

    def generation_parameters(self, seed: int, target_length: int) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id=MID_DEV_SEED_POLICY_ID,
            temperature=0.8,
            top_k=50,
            top_p=0.95,
            max_new_tokens=target_length,
            do_sample=True,
            dtype="float32",
            device="cpu",
            backend_id="fake-middev-exact-length",
            backend_version="v1",
        )

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation:
        realized = target_length
        if self._wrong_length and seed == MID_DEV_SEED_BASE and not watermarked:
            realized -= 1
        label_offset = 1_000_000 if watermarked else 2_000_000
        base = label_offset + seed * 1000
        continuation = tuple(base + index for index in range(realized))
        text = f"fake generated continuation seed={seed} target={target_length} wm={watermarked}"
        return MidDevGeneratedContinuation(
            text=text,
            input_token_ids=(11, 12, 13),
            attention_mask=(1, 1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=continuation,
        )


def test_real_middev_builder_uses_one_frozen_seed_and_exact_length_per_source() -> None:
    artifact = build_real_mid_dev_corpus(_FakeBackend())
    assert artifact.source_count == MID_DEV_SOURCE_COUNT == 36
    assert len(artifact.manifest.samples) == 72
    assert len({value.match_id for value in artifact.manifest.samples}) == 36

    for sample in artifact.manifest.samples:
        assert sample.generation.seed == mid_dev_seed_for_prompt(sample.prompt_id)
        assert sample.generation.seed_policy_id == MID_DEV_SEED_POLICY_ID
        assert sample.target_length == mid_dev_target_length_for_prompt(sample.prompt_id)
        assert len(sample.generation_tokens.continuation_token_ids) == sample.target_length

    for match_id in {value.match_id for value in artifact.manifest.samples}:
        pair = tuple(
            value for value in artifact.manifest.samples if value.match_id == match_id
        )
        assert {value.label for value in pair} == {
            WatermarkLabel.WATERMARKED,
            WatermarkLabel.UNWATERMARKED,
        }
        assert len({value.generation.seed for value in pair}) == 1
        assert len({value.generation.matching_signature_hash for value in pair}) == 1


def test_middev_builder_fails_instead_of_searching_a_replacement_seed() -> None:
    with pytest.raises(MidDevGenerationError, match="seed changes are forbidden"):
        build_real_mid_dev_corpus(_FakeBackend(wrong_length=True))
