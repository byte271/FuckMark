from collections.abc import Mapping

from fuckmark.adapters.base import AdapterRegistry, AdapterSignals
from fuckmark.types import SourcePin


class _SingleIterationMapping(Mapping):
    def __init__(self, values):
        self._values = dict(values)
        self.iterations = 0

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise RuntimeError("mapping consumed more than once")
        return iter(self._values)

    def __getitem__(self, key):
        return self._values[key]


class _Adapter:
    adapter_id = "example"
    algorithm_version = "example-v1"
    source_pin = SourcePin("example", "example/repo", "1" * 40, "Apache-2.0", ("a.py",))
    ngram_len = 2
    depth = 1

    def configuration_fingerprint(self):
        return "2" * 64

    def compute_g_values(self, token_ids):
        return ((1,),) * max(0, len(token_ids) - 1)

    def compute_context_repetition_mask(self, token_ids):
        return (True,) * max(0, len(token_ids) - 1)

    def compute_eos_mask(self, token_ids, eos_token_id):
        return (True,) * max(0, len(token_ids) - 1)

    def signals(self, token_ids, eos_token_id):
        count = max(0, len(token_ids) - 1)
        return AdapterSignals(1, ((1,),) * count, (True,) * count, (True,) * count)


def test_adapter_registry_snapshots_config_mapping_once() -> None:
    registry = AdapterRegistry()
    registry.register("example", lambda config: _Adapter())
    config = _SingleIterationMapping({"value": 1})
    adapter = registry.create("example", config)
    assert adapter.adapter_id == "example"
    assert config.iterations == 1
