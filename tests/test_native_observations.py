from collections.abc import Sequence

import pytest

from fuckmark.adapters import AdapterSignals, DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.native_observations import NativeObservationBatch, NativeObservationRecord, build_native_observations
from fuckmark.types import SourcePin


def _adapter() -> DeepMindReferenceAdapter:
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)
    )


def test_native_observation_builder_records_source_native_geometry_and_signals() -> None:
    batch = build_native_observations(
        "sample-001",
        [10, 20, 30, 40, 20, 30, 50],
        999,
        _adapter(),
    )
    assert batch.ngram_len == 3
    assert batch.depth == 3
    assert batch.token_count == 7
    assert len(batch.records) == 5
    assert batch.records[0].ngram == (10, 20, 30)
    assert batch.records[0].context == (10, 20)
    assert batch.records[0].current_token == 30
    assert batch.records[0].current_token_index == 2
    assert batch.records[0].g_values == (0, 1, 1)
    assert batch.records[-1].repeated is True
    assert batch.records[-1].context_valid is False
    assert batch.records[-1].eos_valid is True
    assert batch.records[-1].valid is False
    assert batch.valid_mask == (True, True, True, True, False)
    assert batch.repeated_mask == (False, False, False, False, True)


def test_native_observation_builder_keeps_eos_and_repetition_effects_separate() -> None:
    batch = build_native_observations(
        "sample-002",
        [10, 20, 30, 40, 20, 30, 50],
        40,
        _adapter(),
    )
    assert tuple(record.context_valid for record in batch.records) == (True, True, True, True, False)
    assert tuple(record.eos_valid for record in batch.records) == (True, False, False, False, False)
    assert batch.valid_mask == (True, False, False, False, False)


def test_native_observation_builder_preserves_empty_observation_geometry() -> None:
    batch = build_native_observations("short", [1, 2], 99, _adapter())
    assert batch.records == ()
    assert batch.depth == 3
    assert batch.ngram_len == 3
    assert batch.valid_mask == ()
    assert batch.g_values == ()


def test_native_observation_record_rejects_forged_mask_relationships() -> None:
    adapter = _adapter()
    fingerprint = adapter.configuration_fingerprint()
    common = dict(
        sample_id="sample",
        adapter_id=adapter.adapter_id,
        adapter_algorithm_version=adapter.algorithm_version,
        adapter_config_hash=fingerprint,
        source_id=adapter.source_pin.source_id,
        source_commit=adapter.source_pin.commit,
        eos_token_id=99,
        index=0,
        token_start=0,
        token_end_exclusive=3,
        ngram=(1, 2, 3),
        context=(1, 2),
        current_token=3,
        g_values=(0, 1, 0),
    )
    with pytest.raises(ValueError, match="repeated"):
        NativeObservationRecord(
            **common,
            repeated=True,
            context_valid=True,
            eos_valid=True,
            valid=True,
        )
    with pytest.raises(ValueError, match="valid"):
        NativeObservationRecord(
            **common,
            repeated=False,
            context_valid=True,
            eos_valid=False,
            valid=True,
        )


def test_native_observation_record_rejects_forged_ngram_geometry() -> None:
    adapter = _adapter()
    with pytest.raises(ValueError, match="context"):
        NativeObservationRecord(
            sample_id="sample",
            adapter_id=adapter.adapter_id,
            adapter_algorithm_version=adapter.algorithm_version,
            adapter_config_hash=adapter.configuration_fingerprint(),
            source_id=adapter.source_pin.source_id,
            source_commit=adapter.source_pin.commit,
            eos_token_id=99,
            index=0,
            token_start=0,
            token_end_exclusive=3,
            ngram=(1, 2, 3),
            context=(9, 2),
            current_token=3,
            repeated=False,
            context_valid=True,
            eos_valid=True,
            valid=True,
            g_values=(0,),
        )


def test_native_observation_builder_rejects_malformed_adapter_signal_count() -> None:
    class BrokenAdapter:
        adapter_id = "broken"
        algorithm_version = "broken-v1"
        source_pin = SourcePin(
            source_id="broken",
            repository="example/broken",
            commit="1" * 40,
            license_id="Apache-2.0",
            critical_files=("broken.py",),
        )
        ngram_len = 3
        depth = 1

        def configuration_fingerprint(self) -> str:
            return "2" * 64

        def compute_g_values(self, token_ids):
            return ()

        def compute_context_repetition_mask(self, token_ids):
            return ()

        def compute_eos_mask(self, token_ids, eos_token_id):
            return ()

        def signals(self, token_ids, eos_token_id):
            return AdapterSignals(depth=1, g_values=(), context_mask=(), eos_mask=())

    with pytest.raises(ValueError, match="observation count"):
        build_native_observations("sample", [1, 2, 3], 99, BrokenAdapter())


def test_native_observation_batch_rejects_record_identity_mismatch() -> None:
    batch = build_native_observations("sample", [1, 2, 3], 99, _adapter())
    record = batch.records[0]
    forged = NativeObservationRecord(
        sample_id="other",
        adapter_id=record.adapter_id,
        adapter_algorithm_version=record.adapter_algorithm_version,
        adapter_config_hash=record.adapter_config_hash,
        source_id=record.source_id,
        source_commit=record.source_commit,
        eos_token_id=record.eos_token_id,
        index=record.index,
        token_start=record.token_start,
        token_end_exclusive=record.token_end_exclusive,
        ngram=record.ngram,
        context=record.context,
        current_token=record.current_token,
        repeated=record.repeated,
        context_valid=record.context_valid,
        eos_valid=record.eos_valid,
        valid=record.valid,
        g_values=record.g_values,
    )
    with pytest.raises(ValueError, match="sample_id"):
        NativeObservationBatch(
            sample_id=batch.sample_id,
            adapter_id=batch.adapter_id,
            adapter_algorithm_version=batch.adapter_algorithm_version,
            adapter_config_hash=batch.adapter_config_hash,
            source_id=batch.source_id,
            source_commit=batch.source_commit,
            ngram_len=batch.ngram_len,
            depth=batch.depth,
            token_ids=batch.token_ids,
            eos_token_id=batch.eos_token_id,
            records=(forged,),
        )


def test_native_observation_batch_rejects_incoherent_ngram_overlap() -> None:
    batch = build_native_observations("sample", [1, 2, 3, 4], 99, _adapter())
    first, second = batch.records
    forged_second = NativeObservationRecord(
        sample_id=second.sample_id,
        adapter_id=second.adapter_id,
        adapter_algorithm_version=second.adapter_algorithm_version,
        adapter_config_hash=second.adapter_config_hash,
        source_id=second.source_id,
        source_commit=second.source_commit,
        eos_token_id=second.eos_token_id,
        index=second.index,
        token_start=second.token_start,
        token_end_exclusive=second.token_end_exclusive,
        ngram=(9, 3, 4),
        context=(9, 3),
        current_token=4,
        repeated=second.repeated,
        context_valid=second.context_valid,
        eos_valid=second.eos_valid,
        valid=second.valid,
        g_values=second.g_values,
    )
    with pytest.raises(ValueError, match="token_ids"):
        NativeObservationBatch(
            sample_id=batch.sample_id,
            adapter_id=batch.adapter_id,
            adapter_algorithm_version=batch.adapter_algorithm_version,
            adapter_config_hash=batch.adapter_config_hash,
            source_id=batch.source_id,
            source_commit=batch.source_commit,
            ngram_len=batch.ngram_len,
            depth=batch.depth,
            token_ids=batch.token_ids,
            eos_token_id=batch.eos_token_id,
            records=(first, forged_second),
        )


class _SingleIterationSequence(Sequence):
    def __init__(self, values):
        self._values = tuple(values)
        self.iterations = 0

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise RuntimeError("sequence was consumed more than once")
        return iter(self._values)


def test_native_observation_builder_snapshots_input_sequence_once() -> None:
    tokens = _SingleIterationSequence((10, 20, 30, 40))
    batch = build_native_observations("snapshot", tokens, 99, _adapter())
    assert tokens.iterations == 1
    assert batch.token_ids == (10, 20, 30, 40)
