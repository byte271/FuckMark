from __future__ import annotations

import hashlib
import re
from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_geometry import (
    GeometryLabel,
    GeometryPairStatus,
    build_public_candidate_coverage,
    run_synthid_geometry_pilot,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy, historical_visible_edit_transform_registry


class _FakeBackend:
    backend_id = "fake-synthid-generation"
    backend_version = "fake-v1"
    model_id = "fake-model"
    detector_id = "fake-weighted-mean"
    detector_config_hash = sha256_text("fake-detector-config")
    ngram_len = 3

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0
        self.tokenize_calls = 0
        self.score_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        if prompt == "plain output please":
            return "Ordinary words remain stable."
        return "We do not panic. We should not drift. We cannot ignore evidence."

    def tokenize(self, text: str) -> tuple[int, ...]:
        self.tokenize_calls += 1
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        return tuple(
            int.from_bytes(hashlib.sha256(piece.encode("utf-8")).digest()[:4], "big")
            for piece in pieces
        )

    def score(self, text: str) -> float:
        assert self.generate_calls == self.expected_generate_calls
        assert self.tokenize_calls > self.generate_calls
        self.score_calls += 1
        return 0.55 - 0.01 * text.count("'")


def _prompts() -> tuple[SynthIDSmokePrompt, ...]:
    return (
        SynthIDSmokePrompt("g-1", "Explain careful testing.", 10),
        SynthIDSmokePrompt("g-2", "Explain independent replication.", 11),
    )


def test_public_candidate_coverage_uses_tokenizer_geometry_only() -> None:
    backend = _FakeBackend(expected_generate_calls=0)
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(
        "We do not panic. We should not drift. We cannot ignore evidence."
    )
    coverage = build_public_candidate_coverage(
        registry,
        enumeration,
        backend.tokenize,
        backend.ngram_len,
    )
    assert set(coverage) == {row.candidate_id for row in enumeration.candidates}
    assert len(coverage) == 3
    assert all(coverage[row.candidate_id] for row in enumeration.candidates)


def test_geometry_pilot_builds_matched_random_vs_greedy_pairs_before_scoring() -> None:
    prompts = _prompts()
    backend = _FakeBackend(expected_generate_calls=len(prompts) * 2)
    report = run_synthid_geometry_pilot(
        prompts,
        backend,
        historical_visible_edit_transform_registry(),
        budgets=(1, 2),
        random_seeds=(101, 102, 103, 104),
        greedy_seed=100,
    )
    assert backend.score_calls > 0
    assert report.summary.prompt_count == 2
    assert report.summary.source_count == 4
    assert report.summary.variant_count == 4 * 2 * 5
    assert report.summary.min_budget_control_eligible_rate == 1.0
    assert report.summary.min_budget_watermarked_eligible_rate == 1.0
    assert report.summary.matched_pair_count == 8
    assert all(row.status is GeometryPairStatus.MATCHED for row in report.pairs)
    assert all(len(row.matched_random_variant_hashes) == 4 for row in report.pairs)
    assert {row.policy for row in report.variants} == {
        SchedulePolicy.RANDOM_VALID,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
    }
    assert {row.label for row in report.variants} == {
        GeometryLabel.CONTROL,
        GeometryLabel.WATERMARKED,
    }
    assert all(row.predicted_coverage_count <= row.original_observation_count for row in report.variants)


def test_geometry_pilot_keeps_ineligible_sources_in_report() -> None:
    prompts = (SynthIDSmokePrompt("plain-1", "plain output please", 20),)
    backend = _FakeBackend(expected_generate_calls=2)
    report = run_synthid_geometry_pilot(
        prompts,
        backend,
        historical_visible_edit_transform_registry(),
        budgets=(1,),
        random_seeds=(1, 2),
    )
    assert report.summary.min_budget_control_eligible_rate == 0.0
    assert report.summary.min_budget_watermarked_eligible_rate == 0.0
    assert all(row.status is GeometryPairStatus.INELIGIBLE for row in report.pairs)
    assert all(row.realized_edit_cost == 0 for row in report.variants)
    assert all(row.source_text == row.transformed_text for row in report.variants)


def test_geometry_report_and_variants_fail_closed_on_tamper() -> None:
    prompts = (SynthIDSmokePrompt("g-1", "Explain careful testing.", 10),)
    backend = _FakeBackend(expected_generate_calls=2)
    report = run_synthid_geometry_pilot(
        prompts,
        backend,
        historical_visible_edit_transform_registry(),
        budgets=(1,),
        random_seeds=(1, 2),
    )
    with pytest.raises(ValueError):
        replace(report.variants[0], transformed_score=report.variants[0].transformed_score + 0.001)
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, greedy_seed=99)


def test_geometry_pilot_rejects_duplicate_prompt_ids() -> None:
    prompt = SynthIDSmokePrompt("dup", "Explain testing.", 1)
    backend = _FakeBackend(expected_generate_calls=0)
    with pytest.raises(ValueError, match="unique"):
        run_synthid_geometry_pilot(
            (prompt, replace(prompt, seed=2)),
            backend,
            historical_visible_edit_transform_registry(),
        )
