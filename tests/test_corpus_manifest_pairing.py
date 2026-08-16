from dataclasses import replace

import pytest

from corpus_helpers import generation, generation_tokens, model_identity, prompt, sample
from fuckmark.corpus import (
    CorpusIntegrityError,
    CorpusLeakageError,
    CorpusPairingError,
    CorpusSplit,
    KeySplit,
    WatermarkLabel,
    build_corpus_manifest,
)


def pair(prompt_record, match_id: str = "match-1"):
    first = sample("wm-1", match_id, WatermarkLabel.WATERMARKED, prompt_record, "Watermarked output.", 1)
    second = sample("control-1", match_id, WatermarkLabel.UNWATERMARKED, prompt_record, "Control output.", 2)
    return first, second




def test_manifest_rejects_match_group_with_one_sample() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1)
    with pytest.raises(CorpusPairingError, match="exactly two"):
        build_corpus_manifest("corpus-v1", [p], [first])


def test_manifest_rejects_match_group_without_both_labels() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked A", 1)
    second = sample("wm-2", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked B", 2)
    with pytest.raises(CorpusPairingError, match="one watermarked and one unwatermarked"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_allows_different_actual_seeds_under_same_seed_policy() -> None:
    p = prompt()
    first, second = pair(p)
    assert first.generation.seed != second.generation.seed
    manifest = build_corpus_manifest("corpus-v1", [p], [first, second])
    assert len(manifest.samples) == 2


def test_manifest_rejects_temperature_drift_inside_matched_group() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1)
    second = sample(
        "control-1",
        "match-1",
        WatermarkLabel.UNWATERMARKED,
        p,
        "Control",
        2,
        generation_parameters=generation(2, temperature=0.9),
    )
    with pytest.raises(CorpusPairingError, match="matched non-watermark"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_rejects_model_revision_drift_inside_matched_group() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1)
    base = model_identity()
    changed_model = base.__class__.create(
        model_id=base.model_id,
        model_revision="d" * 40,
        tokenizer_id=base.tokenizer_id,
        tokenizer_revision=base.tokenizer_revision,
        chat_template_present=base.chat_template_present,
        chat_template_hash=base.chat_template_hash,
        special_token_map_hash=base.special_token_map_hash,
        padding_side=base.padding_side,
        bos_token_id=base.bos_token_id,
        eos_token_id=base.eos_token_id,
        pad_token_id=base.pad_token_id,
        add_bos_token=base.add_bos_token,
        add_eos_token=base.add_eos_token,
    )
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Control", 2, model=changed_model)
    with pytest.raises(CorpusPairingError, match="matched non-watermark"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_rejects_key_identity_drift_inside_matched_group() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1)
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Control", 2)
    changed_watermark = second.watermark.__class__.create(second.watermark.watermark_config_hash, second.watermark.key_split, "key-002")
    second = second.__class__.create(
        sample_id=second.sample_id,
        match_id=second.match_id,
        prompt_id=second.prompt_id,
        prompt_family_id=second.prompt_family_id,
        domain=second.domain,
        split=second.split,
        label=second.label,
        text=second.text,
        model=second.model,
        generation=second.generation,
        watermark=changed_watermark,
        target_length=second.target_length,
        generation_tokens=second.generation_tokens,
    )
    with pytest.raises(CorpusPairingError, match="matched non-watermark"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_rejects_different_exact_templated_inputs_inside_matched_group() -> None:
    p = prompt()
    identity = model_identity()
    first_tokens = generation_tokens((7, 8), identity)
    second_tokens = first_tokens.__class__.create(
        input_token_ids=(0, 0, 0, 5, 6),
        attention_mask=(0, 0, 0, 1, 1),
        generated_sequence_ids=(0, 0, 0, 5, 6, 9, 10),
        continuation_start_index=5,
        continuation_token_ids=(9, 10),
        prompt_length_after_templating=2,
        model_tokenizer_identity_hash=identity.identity_hash,
    )
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1, model=identity, tokens=first_tokens)
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Control", 2, model=identity, tokens=second_tokens)
    with pytest.raises(CorpusPairingError, match="matched non-watermark"):
        build_corpus_manifest("corpus-v1", [p], [first, second])
