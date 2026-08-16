from dataclasses import replace

import pytest

from corpus_helpers import generation, generation_tokens, model_identity, prompt, sample, watermark
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    GenerationParameters,
    KeySplit,
    PaddingSide,
    PromptBoundaryMode,
    PromptRecord,
    TextOnlyTokenRecord,
    TokenTrack,
    WatermarkLabel,
)
from fuckmark.hashing import sha256_text




def test_generation_matching_signature_excludes_realized_seed() -> None:
    first = generation(seed=1)
    second = generation(seed=2)
    assert first.config_hash != second.config_hash
    assert first.matching_signature_hash == second.matching_signature_hash


def test_generation_matching_signature_changes_with_sampling_parameters() -> None:
    first = generation(seed=1, temperature=0.8)
    second = generation(seed=1, temperature=0.9)
    assert first.matching_signature_hash != second.matching_signature_hash


def test_generation_rejects_invalid_sampling_temperature() -> None:
    with pytest.raises(ValueError, match="positive temperature"):
        GenerationParameters.create(1, "seed-policy", 0.0, 40, 0.95, 64, True, "float16", "cuda:0", "backend", "1")


def test_generation_rejects_boolean_do_sample_before_using_it() -> None:
    with pytest.raises(TypeError, match="do_sample"):
        GenerationParameters.create(1, "seed-policy", 0.8, 40, 0.95, 64, 1, "float16", "cuda:0", "backend", "1")


def test_generation_rejects_unrepresentable_temperature_cleanly() -> None:
    with pytest.raises(ValueError, match="representable"):
        GenerationParameters.create(1, "seed-policy", 10**10000, 40, 0.95, 64, True, "float16", "cuda:0", "backend", "1")
