from dataclasses import replace

import pytest

from corpus_helpers import SOURCE_HASH, generation, generation_tokens, model_identity, watermark
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    KeySplit,
    PromptRecord,
    WatermarkLabel,
)
from fuckmark.corpus.tiny_dev import (
    TINY_DEV_CORPUS_ALGORITHM_VERSION,
    TINY_DEV_DOMAINS,
    TINY_DEV_SPLITS,
    TinyDevCorpusError,
    build_tiny_dev_corpus,
)


def _records():
    model = model_identity()
    prompts = []
    samples = []
    seed = 1
    for split in TINY_DEV_SPLITS:
        for domain in TINY_DEV_DOMAINS:
            cell = f"{split.value}-{domain.value}"
            prompt_record = PromptRecord.create(
                prompt_id=f"prompt-{cell}",
                prompt_family_id=f"family-{cell}",
                domain=domain,
                split=split,
                source_id="tiny-dev-test-prompts",
                source_hash=SOURCE_HASH,
                license_id="CC0-1.0",
                provenance="tests/test_tiny_dev_corpus.py",
                text=f"Write a short English response for the {cell} fixture.",
            )
            prompts.append(prompt_record)
            match_id = f"match-{cell}"
            for label in (WatermarkLabel.UNWATERMARKED, WatermarkLabel.WATERMARKED):
                suffix = seed + 100
                tokens = generation_tokens((7, 8, 9, suffix), model)
                samples.append(
                    CorpusSample.create(
                        sample_id=f"sample-{cell}-{label.value}",
                        match_id=match_id,
                        prompt_id=prompt_record.prompt_id,
                        prompt_family_id=prompt_record.prompt_family_id,
                        domain=domain,
                        split=split,
                        label=label,
                        text=f"Fixture output {cell} {label.value} seed {seed}.",
                        model=model,
                        generation=generation(seed),
                        watermark=watermark(KeySplit.DEV),
                        target_length=64,
                        generation_tokens=tokens,
                    )
                )
                seed += 1
    return prompts, samples


def test_tiny_dev_corpus_builds_frozen_two_split_four_domain_matrix() -> None:
    prompts, samples = _records()
    artifact = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    assert artifact.algorithm_version == TINY_DEV_CORPUS_ALGORITHM_VERSION
    assert artifact.target_length == 64
    assert artifact.pairs_per_cell == 1
    assert artifact.required_splits == TINY_DEV_SPLITS
    assert artifact.required_domains == TINY_DEV_DOMAINS
    assert len(artifact.manifest.prompts) == 8
    assert len(artifact.manifest.samples) == 16
    assert len({sample.match_id for sample in artifact.manifest.samples}) == 8
    assert all(sample.watermark.key_split is KeySplit.DEV for sample in artifact.manifest.samples)
    assert {
        (cell.split, cell.domain, cell.pair_count)
        for cell in artifact.cells
    } == {
        (split, domain, 1)
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    }


def test_tiny_dev_corpus_replays_byte_identically() -> None:
    prompts, samples = _records()
    first = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    for _ in range(10):
        assert build_tiny_dev_corpus("tiny-dev-test", prompts, samples) == first


def test_tiny_dev_corpus_rejects_missing_split_domain_cell() -> None:
    prompts, samples = _records()
    removed_prompt = prompts[-1]
    prompts = prompts[:-1]
    samples = [sample for sample in samples if sample.prompt_id != removed_prompt.prompt_id]
    with pytest.raises(TinyDevCorpusError, match="sixteen|eight|one prompt"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, samples)


def test_tiny_dev_corpus_rejects_test_keys() -> None:
    prompts, samples = _records()
    victim = samples[0]
    changed = replace(victim, watermark=watermark(KeySplit.TEST), record_hash="0" * 64)
    with pytest.raises(ValueError, match="record_hash"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, [changed, *samples[1:]])


def test_tiny_dev_corpus_rejects_mixed_model_identity() -> None:
    prompts, samples = _records()
    victim = samples[0]
    alternate_model = replace(
        victim.model,
        model_id="example/other-model",
        identity_hash="0" * 64,
    )
    with pytest.raises(ValueError, match="identity_hash"):
        replace(victim, model=alternate_model, record_hash="0" * 64)


def test_tiny_dev_corpus_rejects_mixed_generation_signature() -> None:
    prompts, samples = _records()
    victim = samples[0]
    changed_generation = generation(victim.generation.seed, temperature=0.7)
    changed = CorpusSample.create(
        sample_id=victim.sample_id,
        match_id=victim.match_id,
        prompt_id=victim.prompt_id,
        prompt_family_id=victim.prompt_family_id,
        domain=victim.domain,
        split=victim.split,
        label=victim.label,
        text=victim.text,
        model=victim.model,
        generation=changed_generation,
        watermark=victim.watermark,
        target_length=victim.target_length,
        generation_tokens=victim.generation_tokens,
    )
    with pytest.raises(Exception, match="matched non-watermark|generation matching"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, [changed, *samples[1:]])


def test_tiny_dev_corpus_inherits_exact_output_deduplication() -> None:
    prompts, samples = _records()
    first = samples[0]
    second = samples[2]
    duplicate = CorpusSample.create(
        sample_id=second.sample_id,
        match_id=second.match_id,
        prompt_id=second.prompt_id,
        prompt_family_id=second.prompt_family_id,
        domain=second.domain,
        split=second.split,
        label=second.label,
        text=first.text,
        model=second.model,
        generation=second.generation,
        watermark=second.watermark,
        target_length=second.target_length,
        generation_tokens=second.generation_tokens,
    )
    changed = [duplicate if sample.sample_id == second.sample_id else sample for sample in samples]
    with pytest.raises(ValueError, match="deduplicated"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, changed)


def test_tiny_dev_corpus_inherits_prompt_family_partition_firewall() -> None:
    prompts, samples = _records()
    calibration_prompt = next(prompt for prompt in prompts if prompt.split is CorpusSplit.THRESHOLD_CALIBRATION)
    attack_prompt = next(prompt for prompt in prompts if prompt.split is CorpusSplit.ATTACK_DEVELOPMENT)
    changed_prompt = PromptRecord.create(
        prompt_id=attack_prompt.prompt_id,
        prompt_family_id=calibration_prompt.prompt_family_id,
        domain=attack_prompt.domain,
        split=attack_prompt.split,
        source_id=attack_prompt.source_id,
        source_hash=attack_prompt.source_hash,
        license_id=attack_prompt.license_id,
        provenance=attack_prompt.provenance,
        text=attack_prompt.text,
    )
    changed_prompts = [
        changed_prompt if prompt.prompt_id == attack_prompt.prompt_id else prompt
        for prompt in prompts
    ]
    changed_samples = [
        CorpusSample.create(
            sample_id=sample.sample_id,
            match_id=sample.match_id,
            prompt_id=sample.prompt_id,
            prompt_family_id=changed_prompt.prompt_family_id,
            domain=sample.domain,
            split=sample.split,
            label=sample.label,
            text=sample.text,
            model=sample.model,
            generation=sample.generation,
            watermark=sample.watermark,
            target_length=sample.target_length,
            generation_tokens=sample.generation_tokens,
        )
        if sample.prompt_id == attack_prompt.prompt_id
        else sample
        for sample in samples
    ]
    with pytest.raises(ValueError, match="cross corpus partitions"):
        build_tiny_dev_corpus("tiny-dev-test", changed_prompts, changed_samples)


def test_tiny_dev_corpus_artifact_rejects_tampering() -> None:
    prompts, samples = _records()
    artifact = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    with pytest.raises(ValueError, match="artifact_hash"):
        replace(artifact, model_identity_hash="f" * 64)
