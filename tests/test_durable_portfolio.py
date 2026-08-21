import json
from functools import lru_cache

import pytest

from diverse_beam_helpers import diverse_beam_fake_corpus
from fuckmark.experiments.durable_portfolio import (
    DURABLE_PORTFOLIO_REJECT,
    DURABLE_PORTFOLIO_RELEASE_STATUS,
    compare_durable_portfolio_benchmarks,
    load_durable_portfolio_comparison,
)
from fuckmark.experiments.normalization_survival import (
    build_normalization_survival_benchmark,
)
from fuckmark.hashing import sha256_json
from fuckmark.transforms import durable_portfolio_transform_registry
from fuckmark.transforms.contractions import context_survival_contraction_rules
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.surface_rules import development_surface_rules


@lru_cache(maxsize=1)
def _benchmarks():
    corpus = diverse_beam_fake_corpus()
    baseline = build_normalization_survival_benchmark(
        corpus,
        TransformRegistry(
            (*context_survival_contraction_rules(), *development_surface_rules())
        ),
        benchmark_source_code_commit="b" * 40,
        source_workflow_run_id=32504847438,
    )
    portfolio = build_normalization_survival_benchmark(
        corpus,
        durable_portfolio_transform_registry(),
        benchmark_source_code_commit="b" * 40,
        source_workflow_run_id=32504847438,
    )
    return baseline, portfolio


def _write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_comparison_replays_matched_inputs_and_keeps_release_blocked(tmp_path) -> None:
    baseline, portfolio = _benchmarks()
    baseline_path = tmp_path / "baseline.json"
    portfolio_path = tmp_path / "portfolio.json"
    comparison_path = tmp_path / "comparison.json"
    _write(baseline_path, baseline)
    _write(portfolio_path, portfolio)
    comparison = compare_durable_portfolio_benchmarks(
        baseline_path,
        portfolio_path,
    )
    _write(comparison_path, comparison)
    loaded = load_durable_portfolio_comparison(comparison_path)
    assert sha256_json(loaded) == sha256_json(comparison)
    assert comparison["raw_candidate_gain"] == 0
    assert comparison["portfolio_decision"] == DURABLE_PORTFOLIO_REJECT
    assert comparison["release_decision"] == DURABLE_PORTFOLIO_RELEASE_STATUS
    assert comparison["release_eligible_rule_count"] == 0
    assert not comparison["detector_access_observed"]
    assert not comparison["secret_access_observed"]


def test_comparison_loader_rejects_rehashed_nested_arithmetic_tampering(tmp_path) -> None:
    baseline, portfolio = _benchmarks()
    baseline_path = tmp_path / "baseline.json"
    portfolio_path = tmp_path / "portfolio.json"
    comparison_path = tmp_path / "comparison.json"
    _write(baseline_path, baseline)
    _write(portfolio_path, portfolio)
    comparison = compare_durable_portfolio_benchmarks(
        baseline_path,
        portfolio_path,
    )
    comparison["n4_exact_budget_comparison"][0][
        "portfolio_reachable_sample_count"
    ] += 1
    payload = {
        key: value for key, value in comparison.items() if key != "artifact_hash"
    }
    comparison["artifact_hash"] = sha256_json(payload)
    _write(comparison_path, comparison)
    with pytest.raises(ValueError, match="exact-budget accounting"):
        load_durable_portfolio_comparison(comparison_path)


def test_comparison_loader_rejects_rehashed_release_promotion(tmp_path) -> None:
    baseline, portfolio = _benchmarks()
    baseline_path = tmp_path / "baseline.json"
    portfolio_path = tmp_path / "portfolio.json"
    comparison_path = tmp_path / "comparison.json"
    _write(baseline_path, baseline)
    _write(portfolio_path, portfolio)
    comparison = compare_durable_portfolio_benchmarks(
        baseline_path,
        portfolio_path,
    )
    comparison["rule_qualification"][0]["release_eligible"] = True
    comparison["release_eligible_rule_count"] = 1
    payload = {
        key: value for key, value in comparison.items() if key != "artifact_hash"
    }
    comparison["artifact_hash"] = sha256_json(payload)
    _write(comparison_path, comparison)
    with pytest.raises(ValueError, match="release qualification"):
        load_durable_portfolio_comparison(comparison_path)
