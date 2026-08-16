import pytest

from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig


TOKENS = [10, 20, 30, 40, 20, 30, 50]
TABLE = (
    0, 1, 0, 0, 0, 0, 0, 1,
    1, 0, 1, 1, 0, 1, 0, 1,
    0, 1, 1, 0, 0, 0, 1, 1,
    1, 0, 1, 0, 0, 0, 0, 1,
)
CONFIG = HuggingFaceSynthIDConfig(
    ngram_len=3,
    keys=(7, 11, 13),
    context_history_size=4,
    sampling_table_seed=123,
    sampling_table_size=32,
)


def _adapter() -> HuggingFaceSynthIDAdapter:
    return HuggingFaceSynthIDAdapter(CONFIG, TABLE, "torch-fixture")


def test_huggingface_synthid_golden_ngram_keys_and_g_values() -> None:
    adapter = _adapter()
    assert adapter.compute_ngram_keys(TOKENS) == (
        (1860351210394783604, 8870152032072404008, 3151680406056438402),
        (7835609618856829130, -3601333633175102082, 9126938814518483928),
        (-8901878891186106158, -1892078069508485754, -7610549695524451360),
        (-8296138226423376526, -1286337404745756122, -7004809030761721728),
        (-9189133506587579420, -2179332684909959016, -7897804310925924622),
    )
    assert adapter.compute_g_values(TOKENS) == (
        (0, 1, 0),
        (1, 0, 1),
        (1, 0, 0),
        (1, 0, 0),
        (0, 1, 1),
    )


def test_huggingface_synthid_context_and_eos_masks_match_pinned_source_behavior() -> None:
    adapter = _adapter()
    assert adapter.compute_context_repetition_mask(TOKENS) == (True, True, True, True, False)
    assert adapter.compute_eos_mask(TOKENS, 50) == (True, True, True, True, False)
    assert adapter.compute_eos_mask(TOKENS, 40) == (True, False, False, False, False)
    assert adapter.compute_eos_mask(TOKENS, 999) == (True, True, True, True, True)


def test_huggingface_synthid_signals_keep_masks_separate() -> None:
    signals = _adapter().signals(TOKENS, 999)
    assert signals.context_mask == (True, True, True, True, False)
    assert signals.eos_mask == (True, True, True, True, True)
    assert signals.valid_mask == (True, True, True, True, False)
    assert signals.g_values[-1] == (0, 1, 1)


def test_huggingface_synthid_sampling_table_is_part_of_behavioral_fingerprint() -> None:
    first = HuggingFaceSynthIDAdapter(CONFIG, TABLE, "provenance-a")
    same_behavior = HuggingFaceSynthIDAdapter(CONFIG, TABLE, "provenance-b")
    changed_table = HuggingFaceSynthIDAdapter(CONFIG, (*TABLE[:-1], 0), "provenance-a")
    assert first.configuration_fingerprint() == same_behavior.configuration_fingerprint()
    assert first.configuration_fingerprint() != changed_table.configuration_fingerprint()
    assert first.sampling_table_hash == same_behavior.sampling_table_hash
    assert first.sampling_table_provenance != same_behavior.sampling_table_provenance


def test_huggingface_synthid_from_torch_reproduces_fixture_when_torch_is_available() -> None:
    pytest.importorskip("torch")
    generated = HuggingFaceSynthIDAdapter.from_torch(CONFIG)
    fixture = _adapter()
    assert generated.sampling_table_hash == fixture.sampling_table_hash
    assert generated.compute_g_values(TOKENS) == fixture.compute_g_values(TOKENS)
    assert generated.configuration_fingerprint() == fixture.configuration_fingerprint()


def test_huggingface_synthid_config_defaults_match_pinned_interface() -> None:
    config = HuggingFaceSynthIDConfig.from_mapping({"ngram_len": 5, "keys": [1, 2, 3]})
    assert config.context_history_size == 1024
    assert config.sampling_table_seed == 0
    assert config.sampling_table_size == 2**16
    assert config.skip_first_ngram_calls is False
    assert config.debug_mode is False


def test_huggingface_synthid_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        HuggingFaceSynthIDConfig(ngram_len=1, keys=(1,))
    with pytest.raises(ValueError):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=())
    with pytest.raises(ValueError):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=(1, 1))
    with pytest.raises(ValueError):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), sampling_table_size=0)
    with pytest.raises(ValueError):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), sampling_table_size=2**24 + 1)
    with pytest.raises(TypeError):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), skip_first_ngram_calls=1)


def test_huggingface_synthid_rejects_malformed_sampling_tables() -> None:
    with pytest.raises(ValueError, match="length"):
        HuggingFaceSynthIDAdapter(CONFIG, TABLE[:-1], "fixture")
    with pytest.raises(ValueError, match="binary"):
        HuggingFaceSynthIDAdapter(CONFIG, (*TABLE[:-1], 2), "fixture")


def test_huggingface_synthid_rejects_token_ids_outside_signed_int64() -> None:
    adapter = _adapter()
    with pytest.raises(ValueError, match="signed int64"):
        adapter.compute_g_values([1, 2, 1 << 63])
    with pytest.raises(ValueError, match="signed int64"):
        adapter.signals([1, 2, 3], 1 << 63)


def test_huggingface_synthid_sampling_seed_matches_torch_integer_range() -> None:
    low = HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), sampling_table_seed=-(1 << 63))
    high = HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), sampling_table_seed=(1 << 64) - 1)
    assert low.sampling_table_seed == -(1 << 63)
    assert high.sampling_table_seed == (1 << 64) - 1
    with pytest.raises(ValueError, match="Torch generator seed range"):
        HuggingFaceSynthIDConfig(ngram_len=3, keys=(1,), sampling_table_seed=1 << 64)
