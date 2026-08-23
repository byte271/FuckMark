from __future__ import annotations

from ..hashing import sha256_json, sha256_text
from .prompt import PromptRecord
from .schema import CorpusDomain, CorpusSplit, KeySplit, MAX_GENERATION_SEED, WatermarkLabel
from .tiny_dev import (
    TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
    TINY_DEV_SPLITS,
    TINY_DEV_TARGET_LENGTH,
    TinyDevCorpusError,
)
from .tiny_dev_generation import (
    TINY_DEV_DEFAULT_MAX_ATTEMPTS,
    TINY_DEV_PAIR_SEED_STRIDE,
    TINY_DEV_PROMPT_LICENSE_ID,
    TINY_DEV_PROMPT_PROVENANCE,
    TINY_DEV_PROMPT_SOURCE_ID,
    TINY_DEV_SEED_POLICY_ID,
    TinyDevGenerationBackend,
    TinyDevGenerationError,
    _TINY_DEV_TEMPLATES,
    _TINY_DEV_TOPICS,
    _build_sample,
)
from .tiny_dev_v3 import (
    TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN,
    TinyDevV3CorpusArtifact,
    build_tiny_dev_v3_corpus,
)


TINY_DEV_V3_GENERATION_ALGORITHM_VERSION = "tiny-dev-v3-generation-v1"
TINY_DEV_V3_PROMPT_SOURCE_ID = "fuckmark-tiny-dev-v3-prompts-v1"
TINY_DEV_V3_DOMAINS = tuple(CorpusDomain)

_TINY_DEV_V3_ATTACK_TOPICS = (
    "research claims",
    "effect size honesty",
    "preregistration discipline",
    "randomization integrity",
    "baseline drift",
    "reporting bias",
    "measurement error",
    "replication crisis",
    "statistical power",
    "selection effects",
    "confound control",
    "outcome switching",
    "sample size planning",
    "analysis robustness",
    "evidence strength",
    "uncertainty reporting",
)


def _v3_topics() -> tuple[str, ...]:
    if _TINY_DEV_TOPICS[25] != _TINY_DEV_V3_ATTACK_TOPICS[0]:
        raise TinyDevCorpusError("v3 attack topic pool must extend the v2 attack topic")
    return (*_TINY_DEV_TOPICS[:25], *_TINY_DEV_V3_ATTACK_TOPICS)


def _v3_prompt_source_hash(attack_pairs_per_domain: int) -> str:
    return sha256_json(
        {
            "algorithm_version": TINY_DEV_V3_GENERATION_ALGORITHM_VERSION,
            "v2_source_id": TINY_DEV_PROMPT_SOURCE_ID,
            "source_id": TINY_DEV_V3_PROMPT_SOURCE_ID,
            "license_id": TINY_DEV_PROMPT_LICENSE_ID,
            "provenance": TINY_DEV_PROMPT_PROVENANCE,
            "attack_pairs_per_domain": attack_pairs_per_domain,
            "calibration_topics": _TINY_DEV_TOPICS[:25],
            "attack_topics": _TINY_DEV_V3_ATTACK_TOPICS,
            "templates": tuple(
                (domain.value, _TINY_DEV_TEMPLATES[domain])
                for domain in TINY_DEV_V3_DOMAINS
            ),
        }
    )


def build_tiny_dev_v3_prompt_records(attack_pairs_per_domain: int) -> tuple[PromptRecord, ...]:
    if type(attack_pairs_per_domain) is not int or attack_pairs_per_domain < 1:
        raise ValueError("attack_pairs_per_domain must be a positive integer")
    if attack_pairs_per_domain > TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN:
        raise TinyDevCorpusError(
            "v3 attack pairs per domain exceeds the frozen maximum of "
            f"{TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN}"
        )
    topics = _v3_topics()
    source_hash = _v3_prompt_source_hash(attack_pairs_per_domain)
    records: list[PromptRecord] = []
    for split in TINY_DEV_SPLITS:
        pair_count = (
            TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
            if split is CorpusSplit.THRESHOLD_CALIBRATION
            else attack_pairs_per_domain
        )
        topic_offset = (
            0
            if split is CorpusSplit.THRESHOLD_CALIBRATION
            else TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
        )
        for domain in TINY_DEV_V3_DOMAINS:
            template = _TINY_DEV_TEMPLATES[domain]
            for local_index in range(pair_count):
                topic_index = topic_offset + local_index
                topic = topics[topic_index]
                prompt_id = f"tiny-dev-{split.value}-{domain.value}-{topic_index:02d}"
                records.append(
                    PromptRecord.create(
                        prompt_id=prompt_id,
                        prompt_family_id=f"tiny-dev-family-{domain.value}-{topic_index:02d}",
                        domain=domain,
                        split=split,
                        source_id=TINY_DEV_V3_PROMPT_SOURCE_ID,
                        source_hash=source_hash,
                        license_id=TINY_DEV_PROMPT_LICENSE_ID,
                        provenance=TINY_DEV_PROMPT_PROVENANCE,
                        text=template.format(topic=topic),
                    )
                )
    return tuple(sorted(records, key=lambda value: value.prompt_id))


def build_real_tiny_dev_v3_corpus(
    backend: TinyDevGenerationBackend,
    *,
    corpus_id: str = "fuckmark-tiny-dev-real-v3",
    seed_base: int = 402000,
    attack_pairs_per_domain: int = 1,
    max_attempts: int = TINY_DEV_DEFAULT_MAX_ATTEMPTS,
) -> TinyDevV3CorpusArtifact:
    if type(seed_base) is not int or seed_base < 0:
        raise ValueError("seed_base must be a non-negative integer")
    if type(max_attempts) is not int or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if type(attack_pairs_per_domain) is not int or attack_pairs_per_domain < 1:
        raise ValueError("attack_pairs_per_domain must be a positive integer")
    if attack_pairs_per_domain > TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN:
        raise ValueError("attack_pairs_per_domain exceeds the frozen v3 maximum")
    prompts = build_tiny_dev_v3_prompt_records(attack_pairs_per_domain)
    if seed_base + len(prompts) * TINY_DEV_PAIR_SEED_STRIDE + max_attempts > MAX_GENERATION_SEED:
        raise ValueError("seed schedule exceeds the 64-bit generation-seed range")

    samples: list[object] = []
    seen_text_hashes: set[str] = set()
    seen_token_hashes: set[str] = set()

    for pair_index, prompt in enumerate(prompts):
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = False
        for attempt in range(max_attempts):
            seed = pair_seed_base + attempt
            try:
                control = backend.generate(prompt.text, seed, watermarked=False)
                watermarked = backend.generate(prompt.text, seed, watermarked=True)
            except RuntimeError:
                continue
            if not control.text.strip() or not watermarked.text.strip():
                continue
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

    artifact = build_tiny_dev_v3_corpus(
        corpus_id,
        prompts,
        samples,
        attack_pairs_per_domain=attack_pairs_per_domain,
    )
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in artifact.manifest.samples):
        raise TinyDevGenerationError("real tiny development v3 generation must use DEV_KEYS")
    for match_id in sorted({sample.match_id for sample in artifact.manifest.samples}):
        pair = tuple(sample for sample in artifact.manifest.samples if sample.match_id == match_id)
        if len({sample.generation.seed for sample in pair}) != 1:
            raise TinyDevGenerationError("real tiny development v3 runner requires one shared seed per on/off pair")
        if any(sample.generation.seed_policy_id != TINY_DEV_SEED_POLICY_ID for sample in pair):
            raise TinyDevGenerationError("real tiny development v3 pair seed policy drifted")
    return artifact
