from dataclasses import replace

import pytest

from corpus_helpers import SOURCE_HASH, generation, generation_tokens, model_identity, watermark
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    PromptRecord,
    WatermarkLabel,
)
from fuckmark.corpus.tiny_dev import (
    TINY_DEV_ATTACK_PAIRS_PER_DOMAIN,
    TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
    TINY_DEV_CORPUS_ALGORITHM_VERSION,
    TINY_DEV_DOMAINS,
    TINY_DEV_SPLITS,
    TinyDevCorpusError,
    build_tiny_dev_corpus,
)
from fuckmark.hashing import sha256_text


def _pairs_for_split(split: CorpusSplit) -> int:
    if split is CorpusSplit.THRESHOLD_CALIBRATION:
        return TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
    return TINY_DEV_ATTACK_PAIRS_PER_DOMAIN


def _records():
    model = model_identity()
    prompts = []
    samples = []
    seed = 1
    for split in TINY_DEV_SPLITS:
        for domain in TINY_DEV_DOMAINS:
            for pair_index in range(_pairs_for_split(split)):
                cell = f"{split.value}-{domain.value}-{pair_index:02d}"
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
                    tokens = generation_tokens((7, 8, 9, seed + 100), model)
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


def _alternate_model() -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id="example/other-model",
        model_revision="d" * 40,
        tokenizer_id="example/other-tokenizer",
        tokenizer_revision="e" * 40,
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text("{}"),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=2,
        pad_token_id=0,
        add_bos_token=False,
        add_eos_token=False,
    )


def test_tiny_dev_corpus_builds_calibration_resolvable_profile() -> None:
    prompts, samples = _records()
    artifact = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    assert artifact.algorithm_version == TINY_DEV_CORPUS_ALGORITHM_VERSION
    assert artifact.target_length == 64
    assert artifact.calibration_pairs_per_domain == 25
    assert artifact.attack_pairs_per_domain == 1
    assert artifact.required_splits == TINY_DEV_SPLITS
    assert artifact.required_domains == TINY_DEV_DOMAINS
    assert len(artifact.manifest.prompts) == 104
    assert len(artifact.manifest.samples) == 208
    assert len({sample.match_id for sample in artifact.manifest.samples}) == 104
    calibration_negatives = tuple(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
        and sample.label is WatermarkLabel.UNWATERMARKED
    )
    assert len(calibration_negatives) == 100
    assert all(sample.watermark.key_split is KeySplit.DEV for sample in artifact.manifest.samples)
    assert {
        (cell.split, cell.domain, cell.pair_count)
        for cell in artifact.cells
    } == {
        (split, domain, _pairs_for_split(split))
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    }


def test_tiny_dev_corpus_replays_byte_identically() -> None:
    prompts, samples = _records()
    first = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    for _ in range(3):
        assert build_tiny_dev_corpus("tiny-dev-test", prompts, samples) == first


def test_tiny_dev_corpus_rejects_missing_split_domain_pair() -> None:
    prompts, samples = _records()
    attack_prompt = next(
        prompt
        for prompt in prompts
        if prompt.split is CorpusSplit.ATTACK_DEVELOPMENT
    )
    prompts = [prompt for prompt in prompts if prompt.prompt_id != attack_prompt.prompt_id]
    samples = [sample for sample in samples if sample.prompt_id != attack_prompt.prompt_id]
    with pytest.raises(TinyDevCorpusError, match="208|104|one prompt"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, samples)


def test_corpus_sample_rejects_test_keys_before_tiny_dev_construction() -> None:
    _, samples = _records()
    victim = samples[0]
    with pytest.raises(ValueError, match="TEST_KEYS"):
        replace(victim, watermark=watermark(KeySplit.TEST), record_hash="0" * 64)


def test_tiny_dev_corpus_rejects_mixed_model_identity() -> None:
    prompts, samples = _records()
    target_match = samples[0].match_id
    alternate_model = _alternate_model()
    changed = []
    for sample in samples:
        if sample.match_id != target_match:
            changed.append(sample)
            continue
        changed_tokens = generation_tokens(
            sample.generation_tokens.continuation_token_ids,
            alternate_model,
        )
        changed.append(
            CorpusSample.create(
                sample_id=sample.sample_id,
                match_id=sample.match_id,
                prompt_id=sample.prompt_id,
                prompt_family_id=sample.prompt_family_id,
                domain=sample.domain,
                split=sample.split,
                label=sample.label,
                text=sample.text,
                model=alternate_model,
                generation=sample.generation,
                watermark=sample.watermark,
                target_length=sample.target_length,
                generation_tokens=changed_tokens,
            )
        )
    with pytest.raises(TinyDevCorpusError, match="one model/tokenizer identity"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, changed)


def test_tiny_dev_corpus_rejects_mixed_generation_signature() -> None:
    prompts, samples = _records()
    target_match = samples[0].match_id
    changed = []
    for sample in samples:
        if sample.match_id != target_match:
            changed.append(sample)
            continue
        changed.append(
            CorpusSample.create(
                sample_id=sample.sample_id,
                match_id=sample.match_id,
                prompt_id=sample.prompt_id,
                prompt_family_id=sample.prompt_family_id,
                domain=sample.domain,
                split=sample.split,
                label=sample.label,
                text=sample.text,
                model=sample.model,
                generation=generation(sample.generation.seed, temperature=0.7),
                watermark=sample.watermark,
                target_length=sample.target_length,
                generation_tokens=sample.generation_tokens,
            )
        )
    with pytest.raises(TinyDevCorpusError, match="one generation matching signature"):
        build_tiny_dev_corpus("tiny-dev-test", prompts, changed)


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


def test_tiny_dev_corpus_artifact_rejects_hash_tampering() -> None:
    prompts, samples = _records()
    artifact = build_tiny_dev_corpus("tiny-dev-test", prompts, samples)
    with pytest.raises(ValueError, match="artifact_hash"):
        replace(artifact, artifact_hash="f" * 64)
