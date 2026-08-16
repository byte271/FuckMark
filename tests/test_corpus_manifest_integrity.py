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




def test_manifest_is_deterministic_across_input_order() -> None:
    p = prompt()
    first, second = pair(p)
    left = build_corpus_manifest("corpus-v1", [p], [first, second])
    right = build_corpus_manifest("corpus-v1", [p], [second, first])
    assert left == right
    assert left.manifest_hash == right.manifest_hash


def test_manifest_rejects_duplicate_exact_utf8_outputs() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Same output", 1)
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Same output", 2)
    with pytest.raises(CorpusIntegrityError, match="deduplicated"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_does_not_collapse_unicode_equivalents() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "caf\u00e9", 1)
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "cafe\u0301", 2)
    manifest = build_corpus_manifest("corpus-v1", [p], [first, second])
    assert len(manifest.samples) == 2


def test_manifest_rejects_unknown_prompt_reference() -> None:
    p = prompt()
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked output.", 1)
    first = first.__class__.create(
        sample_id=first.sample_id,
        match_id=first.match_id,
        prompt_id="prompt-missing",
        prompt_family_id=first.prompt_family_id,
        domain=first.domain,
        split=first.split,
        label=first.label,
        text=first.text,
        model=first.model,
        generation=first.generation,
        watermark=first.watermark,
        target_length=first.target_length,
        generation_tokens=first.generation_tokens,
    )
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Control output.", 2)
    with pytest.raises(CorpusIntegrityError, match="unknown prompt_id"):
        build_corpus_manifest("corpus-v1", [p], [first, second])


def test_manifest_rejects_unused_prompt() -> None:
    p = prompt()
    unused = prompt(prompt_id="prompt-002", family_id="family-002", text="Unused prompt")
    first, second = pair(p)
    with pytest.raises(CorpusIntegrityError, match="unused prompts"):
        build_corpus_manifest("corpus-v1", [p, unused], [first, second])


def test_manifest_rejects_prompt_family_crossing_partitions() -> None:
    first_prompt = prompt(prompt_id="prompt-001", family_id="family-shared", split=CorpusSplit.ATTACK_DEVELOPMENT)
    second_prompt = prompt(prompt_id="prompt-002", family_id="family-shared", split=CorpusSplit.THRESHOLD_CALIBRATION, text="Second family prompt")
    first_pair = pair(first_prompt, "match-1")
    second_wm = sample("wm-2", "match-2", WatermarkLabel.WATERMARKED, second_prompt, "Watermarked B", 3)
    second_control = sample("control-2", "match-2", WatermarkLabel.UNWATERMARKED, second_prompt, "Control B", 4)
    with pytest.raises(CorpusLeakageError, match="cross corpus partitions"):
        build_corpus_manifest("corpus-v1", [first_prompt, second_prompt], [*first_pair, second_wm, second_control])


def test_manifest_hash_rejects_tampering() -> None:
    p = prompt()
    first, second = pair(p)
    manifest = build_corpus_manifest("corpus-v1", [p], [first, second])
    with pytest.raises(ValueError, match="manifest_hash"):
        replace(manifest, manifest_hash="0" * 64)


def test_manifest_split_selection_is_canonical() -> None:
    p = prompt(split=CorpusSplit.ATTACK_DEVELOPMENT)
    first, second = pair(p)
    manifest = build_corpus_manifest("corpus-v1", [p], [first, second])
    selected = manifest.samples_for_split(CorpusSplit.ATTACK_DEVELOPMENT)
    assert tuple(value.sample_id for value in selected) == ("control-1", "wm-1")


def test_final_test_pair_accepts_only_test_key_metadata() -> None:
    p = prompt(split=CorpusSplit.FINAL_TEST)
    first = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, p, "Watermarked", 1, key_split=KeySplit.TEST)
    second = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, p, "Control", 2, key_split=KeySplit.TEST)
    manifest = build_corpus_manifest("test-corpus-v1", [p], [first, second])
    assert manifest.samples_for_split(CorpusSplit.FINAL_TEST) == manifest.samples


def test_manifest_rejects_identical_prompt_text_under_different_identities() -> None:
    first_prompt = prompt(prompt_id="prompt-001", family_id="family-001", split=CorpusSplit.ATTACK_DEVELOPMENT, text="Same prompt")
    second_prompt = prompt(prompt_id="prompt-002", family_id="family-002", split=CorpusSplit.THRESHOLD_CALIBRATION, text="Same prompt")
    first_wm = sample("wm-1", "match-1", WatermarkLabel.WATERMARKED, first_prompt, "Watermarked A", 1)
    first_control = sample("control-1", "match-1", WatermarkLabel.UNWATERMARKED, first_prompt, "Control A", 2)
    second_wm = sample("wm-2", "match-2", WatermarkLabel.WATERMARKED, second_prompt, "Watermarked B", 3)
    second_control = sample("control-2", "match-2", WatermarkLabel.UNWATERMARKED, second_prompt, "Control B", 4)
    with pytest.raises(CorpusLeakageError, match="prompt texts"):
        build_corpus_manifest(
            "corpus-v1",
            [first_prompt, second_prompt],
            [first_wm, first_control, second_wm, second_control],
        )
