import sys

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig


TOKENS = [10, 20, 30, 40, 20, 30, 50]
CONFIG = DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)


def test_deepmind_reference_golden_hash_iv_ngram_keys_and_g_values() -> None:
    if sys.byteorder != "little":
        pytest.skip("Pinned upstream golden fixture was recorded on little-endian int64 serialization")
    adapter = DeepMindReferenceAdapter(CONFIG)
    assert adapter.hash_iv == 2105788953907569235
    assert adapter.compute_ngram_keys(TOKENS) == (
        (6327938853751861990, -5109004398280069222, 7619268049413516788),
        (-6143546811495644100, 866254010181976304, -4852217615833989302),
        (-4434291247829027772, 2575509573848592632, -3142962052167372974),
        (-3828550583066298140, 3181250238611322264, -2537221387404643342),
        (-4721545863230501034, 2288254958447119370, -3430216667568846236),
    )
    assert adapter.compute_g_values(TOKENS) == (
        (0, 1, 1),
        (1, 0, 1),
        (1, 1, 1),
        (0, 0, 1),
        (0, 1, 0),
    )


def test_deepmind_reference_context_repetition_golden() -> None:
    adapter = DeepMindReferenceAdapter(CONFIG)
    assert adapter.compute_context_repetition_mask(TOKENS) == (True, True, True, True, False)


def test_deepmind_reference_context_history_eviction_is_bounded() -> None:
    tokens = [1, 2, 3, 4, 1, 2, 9]
    short_history = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7,), context_history_size=2)
    )
    long_history = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7,), context_history_size=4)
    )
    assert short_history.compute_context_repetition_mask(tokens) == (True, True, True, True, True)
    assert long_history.compute_context_repetition_mask(tokens) == (True, True, True, True, False)


def test_deepmind_reference_eos_mask_matches_source_alignment() -> None:
    adapter = DeepMindReferenceAdapter(CONFIG)
    assert adapter.compute_eos_mask(TOKENS, 50) == (True, True, True, True, False)
    assert adapter.compute_eos_mask(TOKENS, 40) == (True, False, False, False, False)
    assert adapter.compute_eos_mask(TOKENS, 999) == (True, True, True, True, True)


def test_deepmind_reference_signals_keep_masks_separate() -> None:
    adapter = DeepMindReferenceAdapter(CONFIG)
    signals = adapter.signals(TOKENS, 999)
    assert signals.context_mask == (True, True, True, True, False)
    assert signals.eos_mask == (True, True, True, True, True)
    assert signals.valid_mask == (True, True, True, True, False)
    assert signals.g_values[-1] == (0, 1, 0)


def test_deepmind_reference_short_sequence_is_empty_but_typed() -> None:
    adapter = DeepMindReferenceAdapter(CONFIG)
    signals = adapter.signals([1, 2], 99)
    assert signals.depth == 3
    assert signals.observation_count == 0
    assert signals.g_values == ()
    assert signals.valid_mask == ()


def test_deepmind_reference_config_rejects_invalid_scientific_inputs() -> None:
    with pytest.raises(ValueError):
        DeepMindReferenceConfig(ngram_len=1, keys=(1,), context_history_size=4)
    with pytest.raises(ValueError):
        DeepMindReferenceConfig(ngram_len=3, keys=(), context_history_size=4)
    with pytest.raises(ValueError):
        DeepMindReferenceConfig(ngram_len=3, keys=(1, 1), context_history_size=4)
    with pytest.raises(ValueError):
        DeepMindReferenceConfig(ngram_len=3, keys=(1,), context_history_size=0)
    with pytest.raises(ValueError):
        DeepMindReferenceConfig(ngram_len=3, keys=(1 << 63,), context_history_size=4)


def test_deepmind_reference_fingerprint_is_stable_and_config_sensitive() -> None:
    first = DeepMindReferenceAdapter(CONFIG)
    replay = DeepMindReferenceAdapter(CONFIG)
    changed = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 17), context_history_size=4)
    )
    assert first.configuration_fingerprint() == replay.configuration_fingerprint()
    assert first.configuration_fingerprint() != changed.configuration_fingerprint()


def test_deepmind_reference_rejects_token_ids_outside_signed_int64() -> None:
    adapter = DeepMindReferenceAdapter(CONFIG)
    with pytest.raises(ValueError, match="signed int64"):
        adapter.compute_g_values([1, 2, 1 << 63])
    with pytest.raises(ValueError, match="signed int64"):
        adapter.signals([1, 2, 3], 1 << 63)
