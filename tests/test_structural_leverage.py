from __future__ import annotations

from fuckmark.experiments.residual_signal_geometry import compute_residual_signal_geometry
from fuckmark.experiments.structural_leverage import (
    build_structural_leverage_sidecar,
    character_edit_distance,
    character_edit_rate,
)
from fuckmark.hashing import sha256_text


def test_character_edit_distance_and_rate() -> None:
    assert character_edit_distance("abc", "abc") == 0
    assert character_edit_distance("abc", "axc") == 1
    assert character_edit_distance("abc", "abxc") == 1
    assert character_edit_rate("abc", "axc") == 1 / 3
    assert character_edit_rate("", "x") == 1.0


def test_structural_leverage_reports_cost_denominators_separately() -> None:
    geometry = compute_residual_signal_geometry(
        (1, 2, 3, 4, 5, 6, 7),
        (1, 2, 99, 3, 4, 5, 6, 7),
        eos_token_id=9999,
        ngram_len=3,
    )
    row = build_structural_leverage_sidecar(
        variant_hash=sha256_text("variant"),
        source_text="one two three four five",
        transformed_text="one two changed three four five",
        geometry=geometry,
        operation_count=1,
    )
    assert row.rif_reduction is not None
    assert row.rif_reduction_per_operation == row.rif_reduction
    assert row.visible_word_edit_rate > 0.0
    assert row.visible_character_edit_rate > 0.0
    assert row.token_edit_distance == geometry.alignment_distance
    assert row.rif_reduction_per_word_edit_rate is not None
    assert row.rif_reduction_per_character_edit_rate is not None
    assert row.rif_reduction_per_token_edit is not None


def test_zero_cost_sidecar_does_not_invent_structural_leverage() -> None:
    geometry = compute_residual_signal_geometry(
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5),
        eos_token_id=9999,
        ngram_len=3,
    )
    row = build_structural_leverage_sidecar(
        variant_hash=sha256_text("noop"),
        source_text="same text",
        transformed_text="same text",
        geometry=geometry,
        operation_count=0,
    )
    assert row.rif_reduction == 0.0
    assert row.rif_reduction_per_operation is None
    assert row.rif_reduction_per_word_edit_rate is None
    assert row.rif_reduction_per_character_edit_rate is None
    assert row.rif_reduction_per_token_edit is None
