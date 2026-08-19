from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..hashing import sha256_json, sha256_text
from .generation import GenerationParameters, WatermarkCondition
from .identity import ModelTokenizerIdentity
from .mid_dev import (
    MidDevAttackArtifact,
    build_mid_dev_attack_artifact,
    build_mid_dev_prompt_records,
    mid_dev_seed_for_prompt,
    mid_dev_target_length_for_prompt,
)
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import KeySplit, WatermarkLabel
from .tokenization import GenerationTokenRecord, TextOnlyTokenRecord


MID_DEV_GENERATION_ALGORITHM_VERSION = "mid-dev-generation-v1"
MID_DEV_SEED_POLICY_ID = "mid-dev-one-seed-per-source-v1"


class MidDevGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MidDevGeneratedContinuation:
    text: str
    input_token_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    continuation_token_ids: tuple[int, ...]
    text_only_token_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("generated continuation text must be non-empty")
        for name, values in (
            ("input_token_ids", self.input_token_ids),
            ("attention_mask", self.attention_mask),
            ("continuation_token_ids", self.continuation_token_ids),
            ("text_only_token_ids", self.text_only_token_ids),
        ):
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{name} must be a non-empty tuple")
        if len(self.attention_mask) != len(self.input_token_ids):
            raise ValueError("attention_mask length must match input_token_ids")
        if any(type(value) is not int or value < 0 for value in self.input_token_ids):
            raise ValueError("input_token_ids must contain non-negative integers")
        if any(type(value) is not int or value not in (0, 1) for value in self.attention_mask):
            raise ValueError("attention_mask must contain binary integers")
        if any(
            type(value) is not int or value < 0
            for value in (*self.continuation_token_ids, *self.text_only_token_ids)
        ):
            raise ValueError("continuation/text-only token IDs must be non-negative integers")


class MidDevGenerationBackend(Protocol):
    @property
    def model_identity(self) -> ModelTokenizerIdentity: ...

    @property
    def watermark_condition(self) -> WatermarkCondition: ...

    def generation_parameters(self, seed: int, target_length: int) -> GenerationParameters: ...

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation: ...


def _sample_id(prompt: PromptRecord, label: WatermarkLabel) -> str:
    return f"{prompt.prompt_id}-{label.value}"


def _match_id(prompt: PromptRecord) -> str:
    return f"match-{prompt.prompt_id}"


def _build_sample(
    *,
    prompt: PromptRecord,
    label: WatermarkLabel,
    generated: MidDevGeneratedContinuation,
    backend: MidDevGenerationBackend,
    seed: int,
    target_length: int,
) -> CorpusSample:
    model = backend.model_identity
    generation = backend.generation_parameters(seed, target_length)
    if generation.seed != seed:
        raise MidDevGenerationError("backend generation parameters do not bind the requested seed")
    if generation.seed_policy_id != MID_DEV_SEED_POLICY_ID:
        raise MidDevGenerationError("backend seed policy does not match the frozen MidDev policy")
    if generation.max_new_tokens != target_length:
        raise MidDevGenerationError("backend generation parameters do not bind the target length")
    generation_tokens = GenerationTokenRecord.create(
        input_token_ids=generated.input_token_ids,
        attention_mask=generated.attention_mask,
        generated_sequence_ids=generated.input_token_ids + generated.continuation_token_ids,
        continuation_start_index=len(generated.input_token_ids),
        continuation_token_ids=generated.continuation_token_ids,
        prompt_length_after_templating=sum(generated.attention_mask),
        model_tokenizer_identity_hash=model.identity_hash,
    )
    text_only = TextOnlyTokenRecord.create(
        source_text_sha256=sha256_text(generated.text),
        token_ids=generated.text_only_token_ids,
        model_tokenizer_identity_hash=model.identity_hash,
    )
    return CorpusSample.create(
        sample_id=_sample_id(prompt, label),
        match_id=_match_id(prompt),
        prompt_id=prompt.prompt_id,
        prompt_family_id=prompt.prompt_family_id,
        domain=prompt.domain,
        split=prompt.split,
        label=label,
        text=generated.text,
        model=model,
        generation=generation,
        watermark=backend.watermark_condition,
        target_length=target_length,
        generation_tokens=generation_tokens,
        text_only_tokens=text_only,
    )


def build_real_mid_dev_corpus(
    backend: MidDevGenerationBackend,
    *,
    corpus_id: str = "fuckmark-mid-dev-real-v1",
) -> MidDevAttackArtifact:
    prompts = build_mid_dev_prompt_records()
    samples: list[CorpusSample] = []
    seen_text_hashes: set[str] = set()
    seen_token_hashes: set[str] = set()

    for prompt in prompts:
        seed = mid_dev_seed_for_prompt(prompt.prompt_id)
        target_length = mid_dev_target_length_for_prompt(prompt.prompt_id)
        control = backend.generate(
            prompt.text,
            seed,
            target_length,
            watermarked=False,
        )
        watermarked = backend.generate(
            prompt.text,
            seed,
            target_length,
            watermarked=True,
        )
        candidates = (
            (WatermarkLabel.UNWATERMARKED, control),
            (WatermarkLabel.WATERMARKED, watermarked),
        )
        if any(
            len(value.continuation_token_ids) != target_length
            for _, value in candidates
        ):
            raise MidDevGenerationError(
                f"exact-length generation failed for {prompt.prompt_id}; seed changes are forbidden"
            )
        text_hashes = tuple(sha256_text(value.text) for _, value in candidates)
        token_hashes = tuple(
            sha256_json(value.continuation_token_ids)
            for _, value in candidates
        )
        if len(set(text_hashes)) != 2 or len(set(token_hashes)) != 2:
            raise MidDevGenerationError(
                f"watermarked/control pair is not distinct for {prompt.prompt_id}"
            )
        if any(value in seen_text_hashes for value in text_hashes):
            raise MidDevGenerationError("MidDev generated text duplicated an earlier source")
        if any(value in seen_token_hashes for value in token_hashes):
            raise MidDevGenerationError("MidDev generated token sequence duplicated an earlier source")

        pair_samples = tuple(
            _build_sample(
                prompt=prompt,
                label=label,
                generated=value,
                backend=backend,
                seed=seed,
                target_length=target_length,
            )
            for label, value in candidates
        )
        if len({sample.generation.matching_signature_hash for sample in pair_samples}) != 1:
            raise MidDevGenerationError("matched MidDev pair generation parameters drifted")
        samples.extend(pair_samples)
        seen_text_hashes.update(text_hashes)
        seen_token_hashes.update(token_hashes)

    artifact = build_mid_dev_attack_artifact(corpus_id, prompts, samples)
    if any(
        sample.watermark.key_split is not KeySplit.DEV
        for sample in artifact.manifest.samples
    ):
        raise MidDevGenerationError("real MidDev generation must use DEV_KEYS")
    for sample in artifact.manifest.samples:
        expected_seed = mid_dev_seed_for_prompt(sample.prompt_id)
        if sample.generation.seed != expected_seed:
            raise MidDevGenerationError("real MidDev source seed drifted")
        if sample.generation.seed_policy_id != MID_DEV_SEED_POLICY_ID:
            raise MidDevGenerationError("real MidDev seed policy drifted")
    return artifact
