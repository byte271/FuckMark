from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import WatermarkLabel
from .corpus.measurement_calibration import (
    MEASUREMENT_CALIBRATION_PROMPT_SOURCE_ID,
    MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT,
    MEASUREMENT_CALIBRATION_SAMPLE_COUNT,
    MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN,
    build_measurement_calibration_corpus,
    measurement_calibration_topics,
)
from .corpus.prompt import PromptRecord
from .corpus.sample import CorpusSample
from .corpus.schema import CorpusSplit, MAX_GENERATION_SEED
from .corpus.tokenization import GenerationTokenRecord, TextOnlyTokenRecord
from .corpus.tiny_dev import TINY_DEV_TARGET_LENGTH
from .corpus.tiny_dev_generation import (
    TINY_DEV_PROMPT_LICENSE_ID,
    TINY_DEV_PROMPT_PROVENANCE,
    TINY_DEV_SEED_POLICY_ID,
    TinyDevGenerationError,
    _TINY_DEV_TEMPLATES,
)
from .hashing import sha256_json, sha256_text
from .tiny_dev_corpus_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION, HuggingFaceTinyDevBackend


MEASUREMENT_CALIBRATION_GENERATION_VERSION = "measurement-calibration-generation-v1"
MEASUREMENT_CALIBRATION_SEED_STRIDE = 16
MEASUREMENT_CALIBRATION_MAX_ATTEMPTS = 16
MEASUREMENT_CALIBRATION_TOPIC_OFFSET = 100


def build_measurement_calibration_prompt_records() -> tuple[PromptRecord, ...]:
    topics = measurement_calibration_topics()
    if len(topics) != MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN:
        raise ValueError("measurement calibration topic pool must contain 40 topics")
    source_hash = sha256_json(
        {
            "algorithm_version": MEASUREMENT_CALIBRATION_GENERATION_VERSION,
            "source_id": MEASUREMENT_CALIBRATION_PROMPT_SOURCE_ID,
            "license_id": TINY_DEV_PROMPT_LICENSE_ID,
            "provenance": TINY_DEV_PROMPT_PROVENANCE,
            "topics": topics,
            "templates": tuple(
                (domain.value, _TINY_DEV_TEMPLATES[domain])
                for domain in _TINY_DEV_TEMPLATES
            ),
        }
    )
    records: list[PromptRecord] = []
    for domain in _TINY_DEV_TEMPLATES:
        template = _TINY_DEV_TEMPLATES[domain]
        for local_index, topic in enumerate(topics):
            topic_index = MEASUREMENT_CALIBRATION_TOPIC_OFFSET + local_index
            prompt_id = f"measurement-calibration-{domain.value}-{topic_index:02d}"
            records.append(
                PromptRecord.create(
                    prompt_id=prompt_id,
                    prompt_family_id=f"measurement-calibration-family-{domain.value}-{topic_index:02d}",
                    domain=domain,
                    split=CorpusSplit.THRESHOLD_CALIBRATION,
                    source_id=MEASUREMENT_CALIBRATION_PROMPT_SOURCE_ID,
                    source_hash=source_hash,
                    license_id=TINY_DEV_PROMPT_LICENSE_ID,
                    provenance=TINY_DEV_PROMPT_PROVENANCE,
                    text=template.format(topic=topic),
                )
            )
    return tuple(sorted(records, key=lambda value: value.prompt_id))


def _build_slot_sample(
    *,
    prompt,
    slot: int,
    generated,
    backend,
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
    sample_id = f"{prompt.prompt_id}-s{slot:02d}-{WatermarkLabel.UNWATERMARKED.value}"
    return CorpusSample.create(
        sample_id=sample_id,
        match_id=f"match-{sample_id}",
        prompt_id=prompt.prompt_id,
        prompt_family_id=prompt.prompt_family_id,
        domain=prompt.domain,
        split=prompt.split,
        label=WatermarkLabel.UNWATERMARKED,
        text=generated.text,
        model=model,
        generation=generation,
        watermark=backend.watermark_condition,
        target_length=TINY_DEV_TARGET_LENGTH,
        generation_tokens=generation_tokens,
        text_only_tokens=text_only,
    )


def build_real_measurement_calibration_corpus(
    backend: HuggingFaceTinyDevBackend,
    *,
    corpus_id: str = "fuckmark-measurement-calibration-v1",
    seed_base: int = 500000,
) -> MeasurementCalibrationCorpus:
    if type(seed_base) is not int or seed_base < 0:
        raise ValueError("seed_base must be a non-negative integer")
    prompts = build_measurement_calibration_prompt_records()
    slot_count = len(prompts) * MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT
    if seed_base + slot_count * MEASUREMENT_CALIBRATION_SEED_STRIDE + MEASUREMENT_CALIBRATION_MAX_ATTEMPTS > MAX_GENERATION_SEED:
        raise ValueError("measurement calibration seed schedule exceeds the 64-bit range")

    samples: list[object] = []
    seen_text_hashes: set[str] = set()
    seen_token_hashes: set[str] = set()
    slot_index = 0
    for prompt in prompts:
        for slot in range(MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT):
            slot_seed_base = seed_base + slot_index * MEASUREMENT_CALIBRATION_SEED_STRIDE
            slot_index += 1
            accepted = False
            for attempt in range(MEASUREMENT_CALIBRATION_MAX_ATTEMPTS):
                seed = slot_seed_base + attempt
                try:
                    generated = backend.generate(prompt.text, seed, watermarked=False)
                except RuntimeError:
                    continue
                if len(generated.continuation_token_ids) != TINY_DEV_TARGET_LENGTH:
                    continue
                if not generated.text.strip():
                    continue
                text_hash = sha256_text(generated.text)
                token_hash = sha256_json(generated.continuation_token_ids)
                if text_hash in seen_text_hashes or token_hash in seen_token_hashes:
                    continue
                samples.append(
                    _build_slot_sample(
                        prompt=prompt,
                        slot=slot,
                        generated=generated,
                        backend=backend,
                        seed=seed,
                    )
                )
                seen_text_hashes.add(text_hash)
                seen_token_hashes.add(token_hash)
                accepted = True
                break
            if not accepted:
                raise RuntimeError(
                    f"could not produce an exact unique 64-token negative for {prompt.prompt_id} slot {slot}"
                )
    if len(samples) != MEASUREMENT_CALIBRATION_SAMPLE_COUNT:
        raise RuntimeError("measurement calibration sample count does not match the frozen profile")
    return build_measurement_calibration_corpus(corpus_id, prompts, samples)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-measurement-calibration-hf")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--seed-base", type=int, default=500000)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    backend = HuggingFaceTinyDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    artifact = build_real_measurement_calibration_corpus(backend, seed_base=args.seed_base)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"manifest_hash={artifact.manifest.manifest_hash}\n")
    sys.stdout.write(f"sample_count={len(artifact.manifest.samples)}\n")
    sys.stdout.write(f"model_identity_hash={artifact.model_identity_hash}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
