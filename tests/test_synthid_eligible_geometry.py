from __future__ import annotations

import hashlib
import re
from dataclasses import replace

import pytest

from fuckmark.coverage import Interval
from fuckmark.experiments.synthid_eligible_geometry import (
    EligibilityGeometryBasis,
    EligibilityPairStatus,
    filter_candidate_coverage_by_public_eligibility,
    run_synthid_eligible_geometry_pilot,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.hashing import sha256_text
from fuckmark.public_eligibility import build_huggingface_public_eligibility
from fuckmark.transforms import historical_visible_edit_transform_registry


class _FakeBackend:
    backend_id = "fake-eligible-generation"
    backend_version = "fake-v1"
    model_id = "fake-model"
    detector_id = "fake-weighted-mean"
    detector_config_hash = sha256_text("fake-eligible-detector")
    ngram_len = 3
    eos_token_id = 9999
    context_history_size = 8

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0
        self.tokenize_calls = 0
        self.score_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        prefix = "WMARK" if watermarked else "CTRL"
        return (
            f"{prefix} we do not drift for seed {seed}. "
            "We should not panic, and we cannot ignore careful testing."
        )

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
        base = 0.70 if "WMARK" in text else 0.45
        return base - 0.01 * text.count("'")


def test_public_eligibility_filter_removes_repeated_and_post_eos_observations() -> None:
    eligibility = build_huggingface_public_eligibility(
        (1, 2, 9, 1, 2, 8, 99, 1, 2),
        99,
        3,
        context_history_size=4,
    )
    filtered = filter_candidate_coverage_by_public_eligibility(
        {
            "candidate-a": (Interval(0, 7),),
            "candidate-b": (Interval(3, 7),),
        },
        eligibility,
    )
    assert filtered["candidate-a"] == (Interval(0, 3),)
    assert filtered["candidate-b"] == ()


def test_eligible_geometry_pilot_builds_both_bases_before_scoring() -> None:
    prompts = (
        SynthIDSmokePrompt("e-1", "Explain careful testing.", 10),
        SynthIDSmokePrompt("e-2", "Explain replication.", 11),
    )
    backend = _FakeBackend(expected_generate_calls=4)
    report = run_synthid_eligible_geometry_pilot(
        prompts,
        backend,
        historical_visible_edit_transform_registry(),
        budgets=(1, 2),
        schedule_seed=100,
    )
    assert backend.score_calls > 0
    assert report.summary.prompt_count == 2
    assert report.summary.source_count == 4
    assert report.summary.variant_count == 16
    assert report.summary.pair_count == 8
    assert report.summary.matched_pair_count == 8
    assert report.summary.matched_same_selection_rate == 1.0
    assert report.summary.mean_control_score_drop_advantage == 0.0
    assert report.summary.mean_watermarked_score_drop_advantage == 0.0
    assert {row.basis for row in report.variants} == {
        EligibilityGeometryBasis.ALL_OBSERVATIONS,
        EligibilityGeometryBasis.PUBLIC_ELIGIBLE,
    }
    assert all(row.status is EligibilityPairStatus.MATCHED for row in report.pairs)


def test_eligible_geometry_report_fails_closed_on_tamper() -> None:
    prompt = SynthIDSmokePrompt("e-1", "Explain careful testing.", 10)
    backend = _FakeBackend(expected_generate_calls=2)
    report = run_synthid_eligible_geometry_pilot(
        (prompt,),
        backend,
        historical_visible_edit_transform_registry(),
        budgets=(1,),
    )
    with pytest.raises(ValueError, match="variant_hash"):
        replace(report.variants[0], transformed_score=report.variants[0].transformed_score + 0.001)
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, schedule_seed=99)


def test_eligible_geometry_rejects_duplicate_prompt_ids() -> None:
    prompt = SynthIDSmokePrompt("dup", "Explain testing.", 1)
    backend = _FakeBackend(expected_generate_calls=0)
    with pytest.raises(ValueError, match="unique"):
        run_synthid_eligible_geometry_pilot(
            (prompt, replace(prompt, seed=2)),
            backend,
            historical_visible_edit_transform_registry(),
        )
