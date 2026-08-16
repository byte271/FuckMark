import pytest

from fuckmark.adapters.base import AdapterSignals
from fuckmark.native_observations import build_native_observations
from fuckmark.types import SourcePin


class _StableAdapter:
    adapter_id = "stable"
    algorithm_version = "stable-v1"
    source_pin = SourcePin("stable", "example/stable", "1" * 40, "Apache-2.0", ("a.py",))
    ngram_len = 3
    depth = 1

    def configuration_fingerprint(self):
        return "2" * 64

    def compute_g_values(self, token_ids):
        return ((1,),) * max(0, len(token_ids) - 2)

    def compute_context_repetition_mask(self, token_ids):
        return (True,) * max(0, len(token_ids) - 2)

    def compute_eos_mask(self, token_ids, eos_token_id):
        return (True,) * max(0, len(token_ids) - 2)

    def signals(self, token_ids, eos_token_id):
        count = max(0, len(token_ids) - 2)
        return AdapterSignals(1, ((1,),) * count, (True,) * count, (True,) * count)


class _ChangingAdapter(_StableAdapter):
    def __init__(self):
        self._fingerprint = "2" * 64

    def configuration_fingerprint(self):
        return self._fingerprint

    def signals(self, token_ids, eos_token_id):
        self._fingerprint = "3" * 64
        return super().signals(token_ids, eos_token_id)


class _BadSourcePinAdapter(_StableAdapter):
    source_pin = "not-a-source-pin"


def test_native_builder_rejects_adapter_identity_mutation_during_signal_computation() -> None:
    with pytest.raises(ValueError, match="identity changed"):
        build_native_observations("sample", [1, 2, 3], 99, _ChangingAdapter())


def test_native_builder_rejects_non_source_pin_provenance_cleanly() -> None:
    with pytest.raises(TypeError, match="source_pin"):
        build_native_observations("sample", [1, 2, 3], 99, _BadSourcePinAdapter())


def test_native_builder_stable_adapter_still_builds() -> None:
    batch = build_native_observations("sample", [1, 2, 3, 4], 99, _StableAdapter())
    assert batch.g_values == ((1,), (1,))
