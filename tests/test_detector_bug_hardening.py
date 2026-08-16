from dataclasses import replace

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors import mean_evidence, weighted_mean_evidence, weighted_mean_score
from fuckmark.native_observations import build_native_observations


def _adapter(depth: int = 3) -> DeepMindReferenceAdapter:
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=tuple(range(1, depth + 1)),
            context_history_size=4,
        )
    )


def test_weighted_mean_all_one_score_never_exceeds_one_from_roundoff() -> None:
    depth = 39
    values = ((1,) * depth,)
    score = weighted_mean_score(values, (1,))
    assert score == 1.0
    batch = build_native_observations("roundoff", tuple(range(depth + 2)), 10**9, _adapter(depth))
    all_one_records = tuple(replace(record, g_values=(1,) * depth) for record in batch.records)
    all_one_batch = replace(batch, records=all_one_records)
    evidence = weighted_mean_evidence(all_one_batch)
    assert evidence.raw_score == 1.0


def test_weighted_mean_rejects_unrepresentable_integer_weights_cleanly() -> None:
    with pytest.raises(ValueError, match="representable"):
        weighted_mean_score(((1, 0),), (1,), (10**10000, 1))


def test_detector_evidence_binds_exact_native_observation_batch() -> None:
    adapter = _adapter()
    first_batch = build_native_observations("same-id", (0, 0, 0, 0, 0), 999, adapter)
    second_batch = build_native_observations("same-id", (0, 0, 0, 0, 1), 999, adapter)
    first = mean_evidence(first_batch)
    second = mean_evidence(second_batch)
    assert first.raw_score == second.raw_score
    assert first.total_observation_count == second.total_observation_count
    assert first.valid_observation_count == second.valid_observation_count
    assert first.observation_batch_hash != second.observation_batch_hash
    assert first != second


def test_detector_evidence_rejects_forged_detector_config_hash() -> None:
    batch = build_native_observations("config", (1, 2, 3, 4), 999, _adapter())
    evidence = mean_evidence(batch)
    with pytest.raises(ValueError, match="detector_config_hash"):
        replace(evidence, detector_config_hash="0" * 64)
