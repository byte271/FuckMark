from __future__ import annotations

import ast
import inspect

from fuckmark.experiments import tiny_dev_residual_replay as replay_module
from fuckmark.experiments.tiny_dev_residual_replay import (
    PRIMARY_POLICIES,
    ResidualReplayDecision,
    TinyDevResidualReplayRow,
    build_tiny_dev_residual_explanation_comparison,
)
from fuckmark.hashing import sha256_text


def _row(source: str, policy: str, budget: int, old: float, new: float, margin: float) -> TinyDevResidualReplayRow:
    payload = {
        "source_sample_id": source,
        "source_label": "watermarked",
        "schedule_policy": policy,
        "budget": budget,
        "schedule_seed": budget,
        "realized_edit_cost": budget,
        "variant_hash": sha256_text(f"variant:{source}:{policy}"),
        "source_text_hash": sha256_text(f"source:{source}"),
        "transformed_text_hash": sha256_text(f"final:{source}:{policy}"),
        "geometry_hash": sha256_text(f"geometry:{source}:{policy}"),
        "root_valid_observation_count": 60,
        "final_valid_observation_count": 60,
        "preserved_root_valid_observation_count": int(round((1.0 - new) * 60)),
        "root_survival_fraction": 1.0 - old,
        "root_destruction_fraction": old,
        "residual_inherited_fraction": 1.0 - new,
        "new_context_opportunity_fraction": new,
        "valid_denominator_ratio": 1.0,
        "repetition_mask_delta": 0,
        "visible_word_edit_rate": budget / 20,
        "visible_character_edit_rate": budget / 100,
        "token_edit_distance": budget,
        "protected_span_violation_count": 0,
        "hard_invariant_status": "pass",
        "old_exact_destruction_ratio": old,
        "margin_drop": margin,
    }
    from fuckmark.hashing import sha256_json
    return TinyDevResidualReplayRow(**payload, row_hash=sha256_json(payload))


def _matrix(*, new_is_better: bool) -> tuple[TinyDevResidualReplayRow, ...]:
    rows = []
    budgets = (1, 2, 4, 6)
    old_positive_control = (0.30, 0.05, 0.25, 0.10)
    for source_index in range(4):
        for policy_index, (policy, budget) in enumerate(zip(PRIMARY_POLICIES, budgets)):
            if new_is_better:
                old = old_positive_control[policy_index] + 0.02 * source_index
                new = 0.05 * budget + 0.01 * source_index
                margin = 0.20 * new
            else:
                old = 0.07 * budget + 0.08 * source_index
                new = old + 0.04 * ((budget + source_index) % 2)
                margin = 0.14 * old + 0.003 * source_index
            rows.append(_row(f"source-{source_index}", policy, budget, old, new, margin))
    return tuple(rows)


def test_replay_gate_retains_residual_only_when_both_fixed_explanation_checks_improve() -> None:
    comparison = build_tiny_dev_residual_explanation_comparison(_matrix(new_is_better=True))
    assert comparison.new_leave_one_source_out_rmse < comparison.old_leave_one_source_out_rmse
    assert abs(comparison.new_source_centered_pearson) > abs(comparison.old_source_centered_pearson)
    assert comparison.decision is ResidualReplayDecision.RESIDUAL_EXPLAINS_BETTER


def test_replay_gate_kills_new_objective_when_it_does_not_explain_better() -> None:
    comparison = build_tiny_dev_residual_explanation_comparison(_matrix(new_is_better=False))
    assert comparison.decision is ResidualReplayDecision.KILL_NEW_OBJECTIVE_KEEP_BEAM_V2


def test_replay_analysis_module_does_not_import_detector_or_scorer_classes() -> None:
    tree = ast.parse(inspect.getsource(replay_module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    lowered = "\n".join(imported).lower()
    assert "detector" not in lowered
    assert "scorer" not in lowered
