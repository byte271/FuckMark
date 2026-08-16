import pytest

from fuckmark.adapters import (
    DEEPMIND_REFERENCE_ADAPTER_ID,
    HUGGINGFACE_SYNTHID_ADAPTER_ID,
    AdapterRegistry,
    DeepMindReferenceAdapter,
    default_adapter_registry,
)


def test_default_adapter_registry_constructs_deepmind_reference_adapter() -> None:
    registry = default_adapter_registry()
    adapter = registry.create(
        DEEPMIND_REFERENCE_ADAPTER_ID,
        {"ngram_len": 3, "keys": [7, 11, 13], "context_history_size": 4},
    )
    assert isinstance(adapter, DeepMindReferenceAdapter)
    assert registry.adapter_ids == (DEEPMIND_REFERENCE_ADAPTER_ID, HUGGINGFACE_SYNTHID_ADAPTER_ID)
    assert adapter.ngram_len == 3
    assert adapter.depth == 3
    assert len(adapter.configuration_fingerprint()) == 64


def test_adapter_registry_rejects_duplicates_unknown_ids_and_bad_names() -> None:
    registry = AdapterRegistry()
    factory = lambda config: None
    with pytest.raises(ValueError):
        registry.register("Bad Adapter", factory)
    registry.register("example", factory)
    with pytest.raises(ValueError):
        registry.register("example", factory)
    with pytest.raises(KeyError):
        registry.create("missing", {})


def test_adapter_registry_rejects_factory_adapter_id_mismatch() -> None:
    registry = AdapterRegistry()
    real = default_adapter_registry().create(
        DEEPMIND_REFERENCE_ADAPTER_ID,
        {"ngram_len": 3, "keys": [7], "context_history_size": 4},
    )
    registry.register("other", lambda config: real)
    with pytest.raises(ValueError, match="mismatched adapter_id"):
        registry.create("other", {})


def test_adapter_registry_rejects_non_mapping_config() -> None:
    registry = default_adapter_registry()
    with pytest.raises(TypeError):
        registry.create(DEEPMIND_REFERENCE_ADAPTER_ID, [])


def test_deepmind_factory_rejects_unknown_config_fields() -> None:
    registry = default_adapter_registry()
    with pytest.raises(ValueError, match="fields do not match schema"):
        registry.create(
            DEEPMIND_REFERENCE_ADAPTER_ID,
            {"ngram_len": 3, "keys": [7], "context_history_size": 4, "extra": 1},
        )
