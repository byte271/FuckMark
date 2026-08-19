from __future__ import annotations

import ast
import inspect
import random

import pytest

from fuckmark.experiments import residual_signal_geometry as residual_module
from fuckmark.experiments.residual_signal_geometry import (
    FINAL_VALID_DENOMINATOR_COLLAPSE,
    REPETITION_MASK_GAMING,
    assert_residual_signal_reference_match,
    compute_residual_signal_geometry,
    compute_residual_signal_geometry_reference,
    strict_residual_signal_gate,
)


def _geometry(root, final, *, ngram_len=3, eos_token_id=9999, context_history_size=1024):
    return compute_residual_signal_geometry(
        root,
        final,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )


def test_identical_text_has_full_residual_inheritance() -> None:
    result = _geometry((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6))
    assert result.root_valid_observation_count == 4
    assert result.final_valid_observation_count == 4
    assert result.preserved_root_valid_observation_count == 4
    assert result.root_survival_fraction == 1.0
    assert result.root_destruction_fraction == 0.0
    assert result.residual_inherited_fraction == 1.0
    assert result.new_context_opportunity_fraction == 0.0
    assert result.valid_denominator_ratio == 1.0


def test_complete_disjoint_replacement_has_zero_rif() -> None:
    result = _geometry((1, 2, 3, 4, 5, 6), (11, 12, 13, 14, 15, 16))
    assert result.preserved_root_valid_observation_count == 0
    assert result.residual_inherited_fraction == 0.0
    assert result.new_context_opportunity_fraction == 1.0


@pytest.mark.parametrize(
    ("root", "final"),
    (
        ((1, 2, 3, 4, 5, 6, 7, 8), (1, 2, 99, 3, 4, 5, 6, 7, 8)),
        ((1, 2, 99, 3, 4, 5, 6, 7, 8), (1, 2, 3, 4, 5, 6, 7, 8)),
    ),
)
def test_insertion_deletion_resynchronization_recovers_exact_suffix(root, final) -> None:
    result = _geometry(root, final)
    assert result.preserved_root_valid_observation_count >= 4
    assert any(left >= 3 and right >= 2 for left, right in result.preserved_pairs)
    assert result == compute_residual_signal_geometry_reference(
        root,
        final,
        eos_token_id=9999,
        ngram_len=3,
    )


def test_repetition_mask_is_counted_and_decomposed() -> None:
    root = (1, 2, 3, 4, 5, 6, 7)
    final = (1, 2, 3, 1, 2, 4, 5, 6, 7)
    result = _geometry(root, final, ngram_len=3)
    assert result.final_repeated_context_count >= 1
    assert result.repetition_mask_delta >= 1
    assert result.preserved_root_valid_observation_count <= result.exact_preserved_root_valid_before_final_mask_count


def test_eos_mask_loss_is_decomposed_from_exact_preservation() -> None:
    root = (1, 2, 3, 4, 5)
    final = (1, 2, 50256, 3, 4, 5)
    result = _geometry(root, final, ngram_len=2, eos_token_id=50256)
    assert result.final_post_eos_count > result.root_post_eos_count
    assert result.preserved_lost_to_eos_only_count + result.preserved_lost_to_repetition_and_eos_count >= 1
    assert result.exact_preserved_root_valid_before_final_mask_count > result.preserved_root_valid_observation_count


def test_zero_valid_observations_follow_declared_denominator_semantics() -> None:
    result = _geometry((1,), (2,), ngram_len=3)
    assert result.root_valid_observation_count == 0
    assert result.final_valid_observation_count == 0
    assert result.root_survival_fraction == 0.0
    assert result.root_destruction_fraction == 1.0
    assert result.residual_inherited_fraction == 0.0
    assert result.new_context_opportunity_fraction == 0.0
    assert result.valid_denominator_ratio == 0.0


def test_strict_gate_rejects_denominator_collapse() -> None:
    result = _geometry(tuple(range(1, 15)), (1, 2, 3, 4), ngram_len=3)
    gate = strict_residual_signal_gate(
        result,
        repetition_mask_growth_cap=10,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
        visible_fidelity_passed=True,
    )
    assert not gate.eligible
    assert FINAL_VALID_DENOMINATOR_COLLAPSE in gate.reason_codes


def test_strict_gate_rejects_repetition_mask_growth() -> None:
    result = _geometry((1, 2, 3, 4, 5, 6, 7), (1, 2, 3, 1, 2, 4, 5, 6, 7), ngram_len=3)
    gate = strict_residual_signal_gate(
        result,
        repetition_mask_growth_cap=0,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
        visible_fidelity_passed=True,
    )
    assert not gate.eligible
    assert REPETITION_MASK_GAMING in gate.reason_codes


def test_property_optimized_equals_intentionally_slow_reference() -> None:
    rng = random.Random(24081926)
    for _ in range(250):
        ngram_len = rng.randint(2, 4)
        root = [rng.randint(1, 8) for _ in range(rng.randint(0, 12))]
        final = list(root)
        for _ in range(rng.randint(0, 4)):
            action = rng.choice(("insert", "delete", "replace"))
            if action == "insert" or not final:
                final.insert(rng.randint(0, len(final)), rng.randint(1, 8))
            elif action == "delete":
                del final[rng.randrange(len(final))]
            else:
                final[rng.randrange(len(final))] = rng.randint(1, 8)
        optimized = _geometry(root, final, ngram_len=ngram_len, context_history_size=5)
        reference = compute_residual_signal_geometry_reference(
            root,
            final,
            eos_token_id=9999,
            ngram_len=ngram_len,
            context_history_size=5,
        )
        assert optimized == reference
        assert 0.0 <= optimized.root_survival_fraction <= 1.0
        assert 0.0 <= optimized.root_destruction_fraction <= 1.0
        assert 0.0 <= optimized.residual_inherited_fraction <= 1.0
        assert 0.0 <= optimized.new_context_opportunity_fraction <= 1.0
        assert optimized.root_survival_fraction + optimized.root_destruction_fraction == 1.0
        if optimized.final_valid_observation_count > 0:
            assert optimized.residual_inherited_fraction + optimized.new_context_opportunity_fraction == 1.0
        assert optimized.preserved_root_valid_observation_count <= optimized.root_valid_observation_count
        assert optimized.preserved_root_valid_observation_count <= optimized.final_valid_observation_count
        assert_residual_signal_reference_match(
            root,
            final,
            eos_token_id=9999,
            ngram_len=ngram_len,
            context_history_size=5,
        )


def test_residual_geometry_import_graph_has_no_detector_or_scorer_dependency() -> None:
    tree = ast.parse(inspect.getsource(residual_module))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    lowered = "\n".join(imported).lower()
    assert "detector" not in lowered
    assert "scorer" not in lowered
    assert "secret" not in lowered
