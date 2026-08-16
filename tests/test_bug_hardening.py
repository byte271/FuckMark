import sys
from collections.abc import Sequence

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig, HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from fuckmark.adapters._lcg import BoundedHashHistory
from fuckmark.adapters.base import AdapterSignals
from fuckmark.alignment import AlignmentOp, AlignmentResult, AlignmentStep, align_tokens, validate_alignment
from fuckmark.native_observations import build_native_observations
from fuckmark.observations import build_token_ngrams, structural_observation_diff, summarize_structural_observations
from fuckmark.types import SourcePin


class _SnapshotOnlySequence(Sequence):
    def __init__(self, values):
        self._values = tuple(values)
        self.iterations = 0

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        if self.iterations:
            raise RuntimeError("sequence accessed after snapshot")
        return self._values[index]

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise RuntimeError("sequence consumed more than once")
        return iter(self._values)


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


def test_alignment_snapshots_sequence_inputs_once() -> None:
    original = _SnapshotOnlySequence((1, 2, 3))
    transformed = _SnapshotOnlySequence((1, 9, 3))
    result = align_tokens(original, transformed)
    assert result.distance == 1
    assert original.iterations == 1
    assert transformed.iterations == 1


def test_alignment_rejects_traceback_object_explosion_before_allocation() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        align_tokens(list(range(11)), [], max_steps=10)
    with pytest.raises(TypeError):
        align_tokens([1], [1], max_steps=True)
    with pytest.raises(ValueError):
        align_tokens([1], [1], max_steps=0)


def test_validate_alignment_rejects_nonminimal_structurally_valid_path() -> None:
    forged = AlignmentResult(
        distance=2,
        steps=(
            AlignmentStep(AlignmentOp.MATCH, 0, 0, 1, 1),
            AlignmentStep(AlignmentOp.DELETE, 1, None, 2, None),
            AlignmentStep(AlignmentOp.INSERT, None, 1, None, 9),
            AlignmentStep(AlignmentOp.MATCH, 2, 2, 3, 3),
        ),
        original_to_transformed=(0, None, 2),
        transformed_to_original=(0, None, 2),
        original_to_transformed_aligned=(0, None, 2),
        transformed_to_original_aligned=(0, None, 2),
        ambiguous_ties=0,
    )
    with pytest.raises(ValueError, match="canonical|minimum"):
        validate_alignment([1, 2, 3], [1, 9, 3], forged)


def test_validate_alignment_rejects_alternate_minimal_tie_path() -> None:
    canonical = align_tokens([1, 1, 2], [1, 2])
    alternate = AlignmentResult(
        distance=1,
        steps=(
            AlignmentStep(AlignmentOp.MATCH, 0, 0, 1, 1),
            AlignmentStep(AlignmentOp.DELETE, 1, None, 1, None),
            AlignmentStep(AlignmentOp.MATCH, 2, 1, 2, 2),
        ),
        original_to_transformed=(0, None, 1),
        transformed_to_original=(0, 2),
        original_to_transformed_aligned=(0, None, 1),
        transformed_to_original_aligned=(0, 2),
        ambiguous_ties=canonical.ambiguous_ties,
    )
    with pytest.raises(ValueError, match="canonical"):
        validate_alignment([1, 1, 2], [1, 2], alternate)


def test_validate_alignment_rejects_forged_canonical_tie_count() -> None:
    canonical = align_tokens([1, 1, 2], [1, 2])
    forged = AlignmentResult(
        distance=canonical.distance,
        steps=canonical.steps,
        original_to_transformed=canonical.original_to_transformed,
        transformed_to_original=canonical.transformed_to_original,
        original_to_transformed_aligned=canonical.original_to_transformed_aligned,
        transformed_to_original_aligned=canonical.transformed_to_original_aligned,
        ambiguous_ties=canonical.ambiguous_ties + 1,
    )
    with pytest.raises(ValueError, match="ambiguous_ties"):
        validate_alignment([1, 1, 2], [1, 2], forged)


def test_observation_boundaries_snapshot_sequences_once() -> None:
    tokens = _SnapshotOnlySequence((1, 2, 3, 4))
    ngrams = build_token_ngrams(tokens, 3)
    assert tuple(ngram.tokens for ngram in ngrams) == ((1, 2, 3), (2, 3, 4))
    assert tokens.iterations == 1


def test_structural_summary_snapshots_diff_rows_once() -> None:
    original = [1, 2, 3]
    transformed = [1, 9, 3]
    alignment = align_tokens(original, transformed)
    rows = structural_observation_diff(original, transformed, 2, alignment)
    diffs = _SnapshotOnlySequence(rows)
    summary = summarize_structural_observations(original, transformed, 2, diffs)
    assert summary.original_count == 2
    assert diffs.iterations == 1


def test_bounded_hash_history_matches_zero_initialized_fixed_window() -> None:
    values = (0, 5, 0, 7, 5, 9, 0, 11)
    for size in range(1, 7):
        compact = BoundedHashHistory(size)
        naive = [0] * size
        for value in values:
            assert compact.contains(value) == (value in naive)
            compact.push(value)
            naive = [value, *naive[:-1]]


def test_context_history_does_not_preallocate_declared_capacity() -> None:
    history = BoundedHashHistory(10**9)
    assert len(history._values) == 0
    history.push(7)
    assert len(history._values) == 1
    deepmind = DeepMindReferenceAdapter(DeepMindReferenceConfig(3, (7,), 10**9))
    huggingface = HuggingFaceSynthIDAdapter(
        HuggingFaceSynthIDConfig(3, (7,), context_history_size=10**9, sampling_table_size=8),
        bytes((0, 1, 0, 1, 0, 1, 0, 1)),
        "fixture",
    )
    assert deepmind.compute_context_repetition_mask([1, 2, 3, 4]) == (True, True)
    assert huggingface.compute_context_repetition_mask([1, 2, 3, 4]) == (True, True)


def test_huggingface_sampling_table_storage_is_compact_and_behavior_preserving() -> None:
    table = (0, 1, 0, 1, 1, 0, 1, 0)
    config = HuggingFaceSynthIDConfig(3, (7, 11), sampling_table_size=len(table))
    tuple_adapter = HuggingFaceSynthIDAdapter(config, table, "tuple")
    byte_adapter = HuggingFaceSynthIDAdapter(config, bytes(table), "bytes")
    assert isinstance(tuple_adapter._sampling_table, bytes)
    assert sys.getsizeof(tuple_adapter._sampling_table) < 128
    assert tuple_adapter.sampling_table_hash == byte_adapter.sampling_table_hash
    assert tuple_adapter.compute_g_values([1, 2, 3, 4]) == byte_adapter.compute_g_values([1, 2, 3, 4])


def test_huggingface_from_torch_rejects_wrong_config_type() -> None:
    with pytest.raises(TypeError):
        HuggingFaceSynthIDAdapter.from_torch({"ngram_len": 3, "keys": [1]})


def test_native_builder_rejects_adapter_identity_mutation_during_signals() -> None:
    with pytest.raises(ValueError, match="identity changed"):
        build_native_observations("sample", [1, 2, 3], 99, _ChangingAdapter())


def test_native_builder_rejects_non_source_pin_provenance() -> None:
    with pytest.raises(TypeError, match="source_pin"):
        build_native_observations("sample", [1, 2, 3], 99, _BadSourcePinAdapter())


def test_native_builder_stable_adapter_still_builds() -> None:
    batch = build_native_observations("sample", [1, 2, 3, 4], 99, _StableAdapter())
    assert batch.g_values == ((1,), (1,))
