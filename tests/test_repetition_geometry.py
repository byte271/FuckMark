from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fuckmark.geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from fuckmark.hashing import sha256_text


class IntegerTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        if not text.strip():
            return []
        return [int(value) for value in text.split()]


def _engine(policy: PublicRepetitionGeometry) -> CounterfactualGeometryEngine:
    config = GeometryConfig.create(
        tokenizer_identity_hash=sha256_text("integer-tokenizer-v1"),
        ngram_len=policy.ngram_len,
        repetition_mask_policy_id=policy.policy_id,
    )
    return CounterfactualGeometryEngine(
        tokenizer=IntegerTokenizer(),
        config=config,
        eligibility_policy=policy.eligibility_policy,
    )


def test_repeated_context_is_masked_after_first_occurrence() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    report = policy.evaluate((1, 2, 3, 1, 2, 4))
    assert report.eligible_windows == (True, True, True, False)
    assert report.repeated_context_indices == (3,)
    assert report.eligible_count == 3
    assert report.repeated_count == 1
    assert report.repeated_ratio == 0.25


def test_context_history_eviction_matches_finite_public_history() -> None:
    short_history = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=2)
    long_history = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=3)
    tokens = (1, 2, 3, 1, 2, 4)
    assert short_history.evaluate(tokens).eligible_windows == (True, True, True, True)
    assert long_history.evaluate(tokens).eligible_windows == (True, True, True, False)


def test_zero_history_never_marks_a_context_repeated() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=2, context_history_size=0)
    report = policy.evaluate((7, 7, 7, 7))
    assert report.eligible_windows == (True, True, True)
    assert report.repeated_count == 0
    assert report.repeated_ratio == 0.0


def test_short_sequence_has_explicit_empty_mask() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=5, context_history_size=1024)
    report = policy.evaluate((1, 2, 3, 4))
    assert report.context_count == 0
    assert report.eligible_windows == ()
    assert report.repeated_context_indices == ()
    assert report.repeated_ratio == 0.0


def test_repetition_hashes_are_deterministic_and_config_bound() -> None:
    first = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    second = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    other = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=2)
    a = first.evaluate((1, 2, 3, 1, 2, 4))
    b = second.evaluate((1, 2, 3, 1, 2, 4))
    assert first.policy_hash == second.policy_hash
    assert first.policy_id == second.policy_id
    assert a.report_hash == b.report_hash
    assert a.mask_hash == b.mask_hash
    assert first.policy_hash != other.policy_hash
    assert first.policy_id != other.policy_id


def test_geometry_engine_uses_public_repetition_policy_for_root_eligibility() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    engine = _engine(policy)
    root = engine.build_root(source_sample_id="repetition-root", source_text="1 2 3 1 2 4")
    identity = engine.evaluate_output(
        root=root,
        current_text=root.source_text,
        output_text=root.source_text,
        candidate_id=sha256_text("identity"),
        rule_hash=sha256_text("identity-rule"),
        visible_cost_class=0,
        family="identity",
        tier=0,
    )
    assert root.observations.observations[-1].eligible is False
    assert identity.survival_report.root_observation_count == 4
    assert identity.survival_report.root_eligible_count == 3
    assert identity.survival_report.surviving_count == 3
    assert identity.survival_report.newly_masked_ratio == 0.0
    assert identity.survival_ratio == 1.0


def test_counterfactual_can_create_a_new_publicly_masked_context() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=2, context_history_size=16)
    engine = _engine(policy)
    root = engine.build_root(source_sample_id="new-mask", source_text="1 2 3 4")
    result = engine.evaluate_output(
        root=root,
        current_text=root.source_text,
        output_text="1 3 9 2 3 4",
        candidate_id=sha256_text("insert-repeated-context"),
        rule_hash=sha256_text("insert-repeated-context-rule"),
        visible_cost_class=1,
        family="test",
        tier=1,
    )
    assert root.observations.observations[-1].eligible is True
    assert result.newly_masked_count == 1
    assert result.survival_report.newly_masked_ratio == pytest.approx(1.0 / 3.0)
    assert result.survival_report.root_eligible_count == 3
    assert result.surviving_count == 1
    assert result.destroyed_count == 2


def test_geometry_config_mismatch_fails_closed() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    config = GeometryConfig.create(
        tokenizer_identity_hash=sha256_text("integer-tokenizer-v1"),
        ngram_len=3,
        repetition_mask_policy_id="different-public-policy",
    )
    with pytest.raises(ValueError, match="policy identity"):
        policy.eligibility_policy((1, 2, 3), config)


def test_repetition_geometry_has_no_detector_or_secret_imports() -> None:
    path = Path(__file__).parents[1] / "fuckmark" / "geometry" / "repetition.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = ("detector", "g_value", "bayesian", "secret_key", "watermark_key")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert all(all(value not in name.lower() for value in forbidden) for name in names), names


def test_repetition_geometry_exposes_no_secret_access() -> None:
    policy = PublicRepetitionGeometry.create(ngram_len=3, context_history_size=16)
    assert policy.detector_access_observed is False
    assert policy.secret_access_observed is False
