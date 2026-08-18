from __future__ import annotations

import os

import pytest

from fuckmark.geometry import PublicRepetitionGeometry


EXTERNAL_CONFORMANCE = os.environ.get("FUCKMARK_EXTERNAL_REPETITION_CONFORMANCE") == "1"
pytestmark = pytest.mark.skipif(
    not EXTERNAL_CONFORMANCE,
    reason="external SynthID repetition references are not installed",
)


def _deepmind_mask(tokens: tuple[int, ...], ngram_len: int, history_size: int) -> tuple[bool, ...]:
    import torch
    from synthid_text.logits_processing import SynthIDLogitsProcessor

    processor = SynthIDLogitsProcessor(
        ngram_len=ngram_len,
        keys=[11, 17],
        context_history_size=history_size,
        temperature=1.0,
        top_k=10,
        device=torch.device("cpu"),
    )
    input_ids = torch.tensor([tokens], dtype=torch.long)
    return tuple(bool(value) for value in processor.compute_context_repetition_mask(input_ids)[0].tolist())


def _transformers_mask(tokens: tuple[int, ...], ngram_len: int, history_size: int) -> tuple[bool, ...]:
    import torch
    from transformers.generation.logits_process import SynthIDTextWatermarkLogitsProcessor

    processor = SynthIDTextWatermarkLogitsProcessor(
        ngram_len=ngram_len,
        keys=[11, 17],
        sampling_table_size=64,
        sampling_table_seed=5,
        context_history_size=history_size,
        device=torch.device("cpu"),
    )
    input_ids = torch.tensor([tokens], dtype=torch.long)
    return tuple(bool(value) for value in processor.compute_context_repetition_mask(input_ids)[0].tolist())


def _reference_rejects_short(callable_value) -> bool:
    try:
        callable_value()
    except (RuntimeError, ValueError):
        return True
    return False


@pytest.mark.parametrize(
    ("tokens", "ngram_len", "history_size"),
    (
        ((1, 2, 3, 1, 2, 4), 3, 16),
        ((1, 2, 3, 1, 2, 4), 3, 2),
        ((7, 8, 7, 9, 7, 10), 2, 3),
        ((5, 5, 5, 5), 2, 0),
        ((1, 2, 3, 4, 1, 2, 3, 5), 4, 8),
    ),
)
def test_public_mask_matches_both_open_implementations(
    tokens: tuple[int, ...],
    ngram_len: int,
    history_size: int,
) -> None:
    ours = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=history_size,
    ).evaluate(tokens)
    deepmind = _deepmind_mask(tokens, ngram_len, history_size)
    transformers = _transformers_mask(tokens, ngram_len, history_size)
    assert ours.eligible_windows == deepmind
    assert ours.eligible_windows == transformers
    assert ours.repeated_context_indices == tuple(
        index for index, eligible in enumerate(deepmind) if not eligible
    )


def test_finite_context_history_matches_both_references() -> None:
    tokens = (1, 2, 3, 1, 2, 4)
    short_ours = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=2).evaluate(tokens)
    long_ours = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=3).evaluate(tokens)
    assert short_ours.eligible_windows == _deepmind_mask(tokens, 3, 2)
    assert short_ours.eligible_windows == _transformers_mask(tokens, 3, 2)
    assert long_ours.eligible_windows == _deepmind_mask(tokens, 3, 3)
    assert long_ours.eligible_windows == _transformers_mask(tokens, 3, 3)
    assert short_ours.eligible_windows != long_ours.eligible_windows


def test_short_sequence_reference_behavior_is_explicitly_normalized() -> None:
    tokens = (1, 2)
    ours = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16).evaluate(tokens)
    assert ours.eligible_windows == ()
    assert _reference_rejects_short(lambda: _deepmind_mask(tokens, 3, 16))
    assert _reference_rejects_short(lambda: _transformers_mask(tokens, 3, 16))
