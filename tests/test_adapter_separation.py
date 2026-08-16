from fuckmark.adapters import (
    DeepMindReferenceAdapter,
    DeepMindReferenceConfig,
    HuggingFaceSynthIDAdapter,
    HuggingFaceSynthIDConfig,
)
from fuckmark.native_observations import build_native_observations


_TABLE = (
    0,
    1,
    0,
    0,
    0,
    0,
    0,
    1,
    1,
    0,
    1,
    1,
    0,
    1,
    0,
    1,
    0,
    1,
    1,
    0,
    0,
    0,
    1,
    1,
    1,
    0,
    1,
    0,
    0,
    0,
    0,
    1,
)


def test_open_synthid_adapters_preserve_shared_geometry_without_conflating_identity_or_g_values() -> None:
    tokens = (10, 20, 30, 40, 20, 30, 50)
    deepmind = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)
    )
    huggingface = HuggingFaceSynthIDAdapter(
        HuggingFaceSynthIDConfig(
            ngram_len=3,
            keys=(7, 11, 13),
            context_history_size=4,
            sampling_table_seed=123,
            sampling_table_size=len(_TABLE),
        ),
        _TABLE,
        "golden-fixture",
    )
    deepmind_batch = build_native_observations("sample", tokens, 40, deepmind)
    huggingface_batch = build_native_observations("sample", tokens, 40, huggingface)
    assert deepmind_batch.token_ids == huggingface_batch.token_ids == tokens
    assert deepmind_batch.ngram_len == huggingface_batch.ngram_len == 3
    assert deepmind_batch.depth == huggingface_batch.depth == 3
    assert tuple(record.ngram for record in deepmind_batch.records) == tuple(
        record.ngram for record in huggingface_batch.records
    )
    assert tuple(record.context_valid for record in deepmind_batch.records) == tuple(
        record.context_valid for record in huggingface_batch.records
    )
    assert tuple(record.eos_valid for record in deepmind_batch.records) == tuple(
        record.eos_valid for record in huggingface_batch.records
    )
    assert deepmind_batch.adapter_id != huggingface_batch.adapter_id
    assert deepmind_batch.source_id != huggingface_batch.source_id
    assert deepmind_batch.source_commit != huggingface_batch.source_commit
    assert deepmind_batch.adapter_config_hash != huggingface_batch.adapter_config_hash
    assert deepmind_batch.g_values != huggingface_batch.g_values
