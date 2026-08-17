from __future__ import annotations

import hashlib
import re
from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_schedule_stress import (
    StressOpportunityStatus,
    run_synthid_schedule_stress,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy, release_transform_registry


class _StressBackend:
    backend_id = "fake-stress-generation"
    backend_version = "fake-stress-v1"
    model_id = "fake-stress-model"
    detector_id = "unused"
    detector_config_hash = sha256_text("unused-detector")
    ngram_len = 3

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0
        self.score_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        if prompt == "plain":
            return "Ordinary evidence remains stable."
        return (
            "We do not and should not rush. We cannot and will not skip review. "
            "Teams do not and should not ignore evidence."
        )

    def tokenize(self, text: str) -> tuple[int, ...]:
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        return tuple(
            int.from_bytes(hashlib.sha256(piece.encode("utf-8")).digest()[:4], "big")
            for piece in pieces
        )

    def score(self, text: str) -> float:
        self.score_calls += 1
        raise AssertionError("mechanism stress must not request detector scores")


def test_schedule_stress_finds_exact_public_geometry_headroom() -> None:
    prompts = (
        SynthIDSmokePrompt("stress-1", "dense", 101),
        SynthIDSmokePrompt("stress-2", "dense again", 102),
    )
    backend = _StressBackend(expected_generate_calls=4)
    report = run_synthid_schedule_stress(
        prompts,
        backend,
        release_transform_registry(),
        budgets=(1, 2),
        random_seeds=(201, 202, 203, 204),
        spacing_seed=200,
    )
    assert backend.generate_calls == 4
    assert backend.score_calls == 0
    assert report.summary.prompt_count == 2
    assert report.summary.source_count == 4
    assert report.summary.opportunity_count == 8
    assert report.summary.exact_opportunity_count == 8
    assert report.summary.eligible_control_rate == 1.0
    assert report.summary.eligible_watermarked_rate == 1.0
    assert any(row.overlap_loss > 0 for row in report.opportunities)
    assert all(row.status is StressOpportunityStatus.EXACT for row in report.opportunities)
    assert all(row.exact_optimal_coverage >= row.greedy_coverage for row in report.opportunities)
    assert all(row.greedy_regret >= 0 for row in report.opportunities)
    policies = {row.policy for row in report.schedule_rows}
    assert policies == {
        SchedulePolicy.RANDOM_VALID,
        SchedulePolicy.CLUSTERED,
        SchedulePolicy.EVEN_SPACING,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
    }


def test_schedule_stress_keeps_ineligible_sources() -> None:
    prompt = SynthIDSmokePrompt("plain-1", "plain", 1)
    backend = _StressBackend(expected_generate_calls=2)
    report = run_synthid_schedule_stress(
        (prompt,),
        backend,
        release_transform_registry(),
        budgets=(1,),
        random_seeds=(1, 2),
    )
    assert backend.score_calls == 0
    assert report.summary.eligible_control_rate == 0.0
    assert report.summary.eligible_watermarked_rate == 0.0
    assert all(row.status is StressOpportunityStatus.INELIGIBLE for row in report.opportunities)
    assert all(row.candidate_count == 0 for row in report.opportunities)
    assert all(row.exact_optimal_coverage is None for row in report.opportunities)


def test_schedule_stress_report_fails_closed_on_tamper() -> None:
    prompt = SynthIDSmokePrompt("stress-1", "dense", 3)
    backend = _StressBackend(expected_generate_calls=2)
    report = run_synthid_schedule_stress(
        (prompt,),
        backend,
        release_transform_registry(),
        budgets=(1,),
        random_seeds=(1, 2),
    )
    with pytest.raises(ValueError):
        replace(report.opportunities[0], overlap_loss=report.opportunities[0].overlap_loss + 1)
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, spacing_seed=99)


def test_schedule_stress_rejects_duplicate_prompt_ids() -> None:
    prompt = SynthIDSmokePrompt("dup", "dense", 7)
    backend = _StressBackend(expected_generate_calls=0)
    with pytest.raises(ValueError, match="unique"):
        run_synthid_schedule_stress(
            (prompt, replace(prompt, seed=8)),
            backend,
            release_transform_registry(),
        )
