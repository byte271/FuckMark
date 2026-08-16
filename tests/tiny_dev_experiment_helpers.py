from dataclasses import replace
from functools import lru_cache

from calibration_helpers import _base_evidence
from corpus_helpers import SOURCE_HASH, generation, generation_tokens, model_identity, watermark
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    KeySplit,
    PromptRecord,
    WatermarkLabel,
    build_tiny_dev_corpus,
)
from fuckmark.corpus.tiny_dev import (
    TINY_DEV_ATTACK_PAIRS_PER_DOMAIN,
    TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
    TINY_DEV_DOMAINS,
    TINY_DEV_SPLITS,
)
from fuckmark.hashing import sha256_text


def _pairs_for_split(split: CorpusSplit) -> int:
    if split is CorpusSplit.THRESHOLD_CALIBRATION:
        return TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
    return TINY_DEV_ATTACK_PAIRS_PER_DOMAIN


@lru_cache(maxsize=1)
def tiny_dev_artifact():
    model = model_identity()
    prompts = []
    samples = []
    seed = 1
    for split in TINY_DEV_SPLITS:
        for domain in TINY_DEV_DOMAINS:
            for pair_index in range(_pairs_for_split(split)):
                cell = f"{split.value}-{domain.value}-{pair_index:02d}"
                prompt = PromptRecord.create(
                    prompt_id=f"prompt-{cell}",
                    prompt_family_id=f"family-{cell}",
                    domain=domain,
                    split=split,
                    source_id="tiny-dev-experiment-test-prompts",
                    source_hash=SOURCE_HASH,
                    license_id="CC0-1.0",
                    provenance="tests/tiny_dev_experiment_helpers.py",
                    text=f"Write a short English response for experiment fixture {cell}.",
                )
                prompts.append(prompt)
                match_id = f"match-{cell}"
                for label in (WatermarkLabel.UNWATERMARKED, WatermarkLabel.WATERMARKED):
                    tokens = generation_tokens((17, 18, 19, seed + 300), model)
                    samples.append(
                        CorpusSample.create(
                            sample_id=f"sample-{cell}-{label.value}",
                            match_id=match_id,
                            prompt_id=prompt.prompt_id,
                            prompt_family_id=prompt.prompt_family_id,
                            domain=domain,
                            split=split,
                            label=label,
                            text=f"Experiment fixture output {cell} {label.value} seed {seed}.",
                            model=model,
                            generation=generation(seed),
                            watermark=watermark(KeySplit.DEV),
                            target_length=64,
                            generation_tokens=tokens,
                        )
                    )
                    seed += 1
    return build_tiny_dev_corpus("tiny-dev-experiment-test", prompts, samples)


def calibration_evidence():
    artifact = tiny_dev_artifact()
    sample_ids = tuple(
        sorted(
            sample.sample_id
            for sample in artifact.manifest.samples
            if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
            and sample.label is WatermarkLabel.UNWATERMARKED
        )
    )
    base = _base_evidence()
    return tuple(
        replace(
            base,
            sample_id=sample_id,
            observation_batch_hash=sha256_text(f"calibration-observation-{sample_id}"),
            raw_score=index / 1000.0,
        )
        for index, sample_id in enumerate(sample_ids)
    )


def attack_evidence(underpowered: bool = False):
    artifact = tiny_dev_artifact()
    samples = tuple(
        sorted(
            (
                sample
                for sample in artifact.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
            ),
            key=lambda sample: sample.sample_id,
        )
    )
    base = _base_evidence()
    positive_index = 0
    negative_index = 0
    output = []
    for sample in samples:
        if sample.label is WatermarkLabel.WATERMARKED:
            score = 0.02 + positive_index * 0.005 if underpowered else 0.80 + positive_index * 0.02
            positive_index += 1
        else:
            score = 0.01 + negative_index * 0.01
            negative_index += 1
        output.append(
            replace(
                base,
                sample_id=sample.sample_id,
                observation_batch_hash=sha256_text(f"attack-observation-{sample.sample_id}-{underpowered}"),
                raw_score=score,
            )
        )
    return tuple(output)
