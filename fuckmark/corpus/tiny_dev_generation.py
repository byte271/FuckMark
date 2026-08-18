from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..hashing import sha256_json, sha256_text
from .generation import GenerationParameters, WatermarkCondition
from .identity import ModelTokenizerIdentity
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusDomain, CorpusSplit, KeySplit, MAX_GENERATION_SEED, WatermarkLabel
from .tiny_dev import (
    TINY_DEV_ATTACK_PAIRS_PER_DOMAIN,
    TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
    TINY_DEV_DOMAINS,
    TINY_DEV_SPLITS,
    TINY_DEV_TARGET_LENGTH,
    TinyDevCorpusArtifact,
    build_tiny_dev_corpus,
)
from .tokenization import GenerationTokenRecord, TextOnlyTokenRecord


TINY_DEV_GENERATION_ALGORITHM_VERSION = "tiny-dev-generation-v1"
TINY_DEV_SEED_POLICY_ID = "tiny-dev-paired-seed-v1"
TINY_DEV_PROMPT_SOURCE_ID = "fuckmark-tiny-dev-prompts-v1"
TINY_DEV_PROMPT_LICENSE_ID = "LicenseRef-FuckMark-Unspecified"
TINY_DEV_PROMPT_PROVENANCE = "fuckmark/corpus/tiny_dev_generation.py"
TINY_DEV_DEFAULT_MAX_ATTEMPTS = 16
TINY_DEV_PAIR_SEED_STRIDE = 32

_TINY_DEV_TOPICS = (
    "reproducibility",
    "control groups",
    "measurement uncertainty",
    "data provenance",
    "source licensing",
    "fixed thresholds",
    "held-out evaluation",
    "random baselines",
    "failure logging",
    "tokenization changes",
    "prompt boundaries",
    "calibration drift",
    "independent replication",
    "protected spans",
    "semantic fidelity",
    "edit budgets",
    "deterministic replay",
    "multiple testing",
    "confidence intervals",
    "model revision pinning",
    "key separation",
    "negative controls",
    "ablation studies",
    "domain shift",
    "null results",
    "research claims",
)

_TINY_DEV_TEMPLATES = {
    CorpusDomain.GENERAL_EXPLANATORY: (
        "Explain in plain English why {topic} matters in careful scientific work. "
        "Write one coherent paragraph without a list."
    ),
    CorpusDomain.TECHNICAL_EXPLANATION: (
        "Give a technical explanation of {topic} in software experiments. "
        "Define the main idea, one failure mode, and one validation check."
    ),
    CorpusDomain.CONVERSATIONAL_PROSE: (
        "Answer a colleague who asks why {topic} matters. "
        "Use natural conversational prose while keeping the explanation precise."
    ),
    CorpusDomain.STRUCTURED_INSTRUCTIONAL: (
        "Write a short three-step instruction for applying {topic} in an experiment. "
        "Use complete sentences and keep each step concrete."
    ),
}


class TinyDevGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TinyDevGeneratedContinuation:
    text: str
    input_token_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    continuation_token_ids: tuple[int, ...]
    text_only_token_ids: tuple[int, ...] | None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("generated continuation text must be a non-empty string")
        for name, value in (
            ("input_token_ids", self.input_token_ids),
            ("attention_mask", self.attention_mask),
            ("continuation_token_ids", self.continuation_token_ids),
        ):
            if not isinstance(value, tuple):
                raise TypeError(f"{name} must be a tuple")
        if not self.input_token_ids:
            raise ValueError("input_token_ids must not be empty")
        if len(self.attention_mask) != len(self.input_token_ids):
            raise ValueError("attention_mask length must match input_token_ids")
        if any(type(value) is not int or value < 0 for value in self.input_token_ids):
            raise ValueError("input_token_ids must contain non-negative integers")
        if any(type(value) is not int or value not in (0, 1) for value in self.attention_mask):
            raise ValueError("attention_mask must contain binary integers")
        if not self.continuation_token_ids:
            raise ValueError("continuation_token_ids must not be empty")
        if any(type(value) is not int or value < 0 for value in self.continuation_token_ids):
            raise ValueError("continuation_token_ids must contain non-negative integers")
        if self.text_only_token_ids is not None:
            if not isinstance(self.text_only_token_ids, tuple):
                raise TypeError("text_only_token_ids must be a tuple or None")
            if not self.text_only_token_ids:
                raise ValueError("text_only_token_ids must not be empty when present")
            if any(type(value) is not int or value < 0 for value in self.text_only_token_ids):
                raise ValueError("text_only_token_ids must contain non-negative integers")


class TinyDevGenerationBackend(Protocol):
    @property
    def model_identity(self) -> ModelTokenizerIdentity: ...

    @property
    def watermark_condition(self) -> WatermarkCondition: ...

    def generation_parameters(self, seed: int) -> GenerationParameters: ...

    def generate(
        self,
        prompt: str,
        seed: int,
        *,
        watermarked: bool,
    ) -> TinyDevGeneratedContinuation: ...


def _pairs_for_split(split: CorpusSplit) -> int:
    if split is CorpusSplit.THRESHOLD_CALIBRATION:
        return TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
    if split is CorpusSplit.ATTACK_DEVELOPMENT:
        return TINY_DEV_ATTACK_PAIRS_PER_DOMAIN
    raise ValueError("split is outside the frozen tiny development profile")


def _prompt_source_hash() -> str:
    return sha256_json(
        {
            "algorithm_version": TINY_DEV_GENERATION_ALGORITHM_VERSION,
            "source_id": TINY_DEV_PROMPT_SOURCE_ID,
            "license_id": TINY_DEV_PROMPT_LICENSE_ID,
            "provenance": TINY_DEV_PROMPT_PROVENANCE,
            "topics": _TINY_DEV_TOPICS,
            "templates": tuple(
                (domain.value, _TINY_DEV_TEMPLATES[domain])
                for domain in TINY_DEV_DOMAINS
            ),
        }
    )


def build_tiny_dev_prompt_records() -> tuple[PromptRecord, ...]:
    if len(_TINY_DEV_TOPICS) != (
        TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN + TINY_DEV_ATTACK_PAIRS_PER_DOMAIN
    ):
        raise RuntimeError("tiny development prompt topics do not match the frozen pair profile")
    source_hash = _prompt_source_hash()
    records: list[PromptRecord] = []
    for split in TINY_DEV_SPLITS:
        pair_count = _pairs_for_split(split)
        topic_offset = (
            0
            if split is CorpusSplit.THRESHOLD_CALIBRATION
            else TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
        )
        for domain in TINY_DEV_DOMAINS:
            template = _TINY_DEV_TEMPLATES[domain]
            for local_index in range(pair_count):
                topic_index = topic_offset + local_index
                topic = _TINY_DEV_TOPICS[topic_index]
                prompt_id = f"tiny-dev-{split.value}-{domain.value}-{topic_index:02d}"
                records.append(
                    PromptRecord.create(
                        prompt_id=prompt_id,
                        prompt_family_id=f"tiny-dev-family-{domain.value}-{topic_index:02d}",
                        domain=domain,
                        split=split,
                        source_id=TINY_DEV_PROMPT_SOURCE_ID,
                        source_hash=source_hash,
                        license_id=TINY_DEV_PROMPT_LICENSE_ID,
                        provenance=TINY_DEV_PROMPT_PROVENANCE,
                        text=template.format(topic=topic),
                    )
                )
    return tuple(sorted(records, key=lambda value: value.prompt_id))


def _sample_id(prompt: PromptRecord, label: WatermarkLabel) -> str:
    return f"{prompt.prompt_id}-{label.value}"


def _match_id(prompt: PromptRecord) -> str:
    return f"match-{prompt.prompt_id}"


def _build_sample(
    *,
    prompt: PromptRecord,
    label: WatermarkLabel,
    generated: TinyDevGeneratedContinuation,
    backend: TinyDevGenerationBackend,
    seed: int,
) -> CorpusSample:
    model = backend.model_identity
    generation = backend.generation_parameters(seed)
    if generation.seed != seed:
        raise TinyDevGenerationError("backend generation parameters do not bind the requested seed")
    if generation.seed_policy_id != TINY_DEV_SEED_POLICY_ID:
        raise TinyDevGenerationError("backend seed policy does not match the frozen tiny development policy")
    generation_tokens = GenerationTokenRecord.create(
        input_token_ids=generated.input_token_ids,
        attention_mask=generated.attention_mask,
        generated_sequence_ids=generated.input_token_ids + generated.continuation_token_ids,
        continuation_start_index=len(generated.input_token_ids),
        continuation_token_ids=generated.continuation_token_ids,
        prompt_length_after_templating=sum(generated.attention_mask),
        model_tokenizer_identity_hash=model.identity_hash,
    )
    text_only = None
    if generated.text_only_token_ids is not None:
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
        target_length=TINY_DEV_TARGET_LENGTH,
        generation_tokens=generation_tokens,
        text_only_tokens=text_only,
    )


def build_real_tiny_dev_corpus(
    backend: TinyDevGenerationBackend,
    *,
    corpus_id: str = "fuckmark-tiny-dev-real-v1",
    seed_base: int = 401000,
    max_attempts: int = TINY_DEV_DEFAULT_MAX_ATTEMPTS,
) -> TinyDevCorpusArtifact:
    if type(seed_base) is not int or seed_base < 0:
        raise ValueError("seed_base must be a non-negative integer")
    if type(max_attempts) is not int or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    prompts = build_tiny_dev_prompt_records()
    if seed_base + len(prompts) * TINY_DEV_PAIR_SEED_STRIDE + max_attempts > MAX_GENERATION_SEED:
        raise ValueError("seed schedule exceeds the 64-bit generation-seed range")

    samples: list[CorpusSample] = []
    seen_text_hashes: set[str] = set()
    seen_token_hashes: set[str] = set()

    for pair_index, prompt in enumerate(prompts):
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = False
        for attempt in range(max_attempts):
            seed = pair_seed_base + attempt
            control = backend.generate(prompt.text, seed, watermarked=False)
            watermarked = backend.generate(prompt.text, seed, watermarked=True)
            candidates = (
                (WatermarkLabel.UNWATERMARKED, control),
                (WatermarkLabel.WATERMARKED, watermarked),
            )
            if any(
                len(value.continuation_token_ids) != TINY_DEV_TARGET_LENGTH
                for _, value in candidates
            ):
                continue
            text_hashes = tuple(sha256_text(value.text) for _, value in candidates)
            token_hashes = tuple(
                sha256_json(value.continuation_token_ids)
                for _, value in candidates
            )
            if len(set(text_hashes)) != len(text_hashes) or len(set(token_hashes)) != len(token_hashes):
                continue
            if any(value in seen_text_hashes for value in text_hashes):
                continue
            if any(value in seen_token_hashes for value in token_hashes):
                continue

            pair_samples = tuple(
                _build_sample(
                    prompt=prompt,
                    label=label,
                    generated=value,
                    backend=backend,
                    seed=seed,
                )
                for label, value in candidates
            )
            samples.extend(pair_samples)
            seen_text_hashes.update(text_hashes)
            seen_token_hashes.update(token_hashes)
            accepted = True
            break
        if not accepted:
            raise TinyDevGenerationError(
                f"could not produce an exact, unique 64-token pair for {prompt.prompt_id} "
                f"within {max_attempts} deterministic attempts"
            )

    artifact = build_tiny_dev_corpus(corpus_id, prompts, samples)
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in artifact.manifest.samples):
        raise TinyDevGenerationError("real tiny development generation must use DEV_KEYS")
    for match_id in sorted({sample.match_id for sample in artifact.manifest.samples}):
        pair = tuple(sample for sample in artifact.manifest.samples if sample.match_id == match_id)
        if len({sample.generation.seed for sample in pair}) != 1:
            raise TinyDevGenerationError("real tiny development runner requires one shared seed per on/off pair")
        if any(sample.generation.seed_policy_id != TINY_DEV_SEED_POLICY_ID for sample in pair):
            raise TinyDevGenerationError("real tiny development pair seed policy drifted")
    return artifact
