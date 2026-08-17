from __future__ import annotations

import re
from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_high_repetition_detector import (
    TARGET_STRATUM,
    build_high_repetition_detector_plan,
    run_synthid_high_repetition_detector_pilot,
    score_high_repetition_detector_plan,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.synthid_high_repetition_detector_hf import (
    _RecordingBackend,
    _build_source_manifest,
    _validate_plan_against_source_manifest,
)
from fuckmark.transforms import release_transform_registry


class _PlanBackend:
    backend_id = "fake-high-repetition-generation"
    backend_version = "fake-v1"
    model_id = "fake-model"
    ngram_len = 3
    eos_token_id = 999999
    context_history_size = 32

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        prefix = "WMARK" if watermarked else "CTRL"
        repeated = " ".join("We do not panic." for _ in range(seed))
        return f"{prefix} {repeated} We should not drift. We cannot ignore evidence."

    def tokenize(self, text: str) -> tuple[int, ...]:
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        vocabulary = {}
        output = []
        for piece in pieces:
            if piece not in vocabulary:
                vocabulary[piece] = len(vocabulary) + 1
            output.append(vocabulary[piece])
        return tuple(output)


class _ScoringBackend(_PlanBackend):
    detector_id = "fake-weighted-mean"
    detector_config_hash = "1" * 64

    def __init__(self, expected_generate_calls: int) -> None:
        super().__init__(expected_generate_calls)
        self.score_calls = 0

    def score(self, text: str) -> float:
        assert self.generate_calls == self.expected_generate_calls
        self.score_calls += 1
        return len(self.tokenize(text)) / 1000.0


def _prompts() -> tuple[SynthIDSmokePrompt, ...]:
    return tuple(
        SynthIDSmokePrompt(f"hr-{index}", f"Repeat structure {index}.", index)
        for index in range(1, 5)
    )


def test_high_repetition_plan_is_frozen_before_detector_scoring() -> None:
    prompts = _prompts()
    backend = _PlanBackend(expected_generate_calls=8)
    plan = build_high_repetition_detector_plan(
        prompts,
        backend,
        release_transform_registry(),
        budgets=(1,),
        schedule_seed=41,
    )
    assert backend.generate_calls == 8
    assert plan.detector_scores_used is False
    assert plan.selection_feedback_used is False
    assert plan.target_stratum is TARGET_STRATUM
    assert len(plan.sources) == 2
    assert all(row.budget == 1 for row in plan.pairs)
    assert {row.source_record_hash for row in plan.pairs} <= {row.source_record_hash for row in plan.sources}


def test_high_repetition_pilot_scores_only_after_every_selection_is_frozen() -> None:
    prompts = _prompts()
    backend = _ScoringBackend(expected_generate_calls=8)
    plan, report = run_synthid_high_repetition_detector_pilot(
        prompts,
        backend,
        release_transform_registry(),
        budgets=(1,),
        schedule_seed=42,
    )
    assert backend.generate_calls == 8
    assert backend.score_calls > 0
    assert report.plan_hash == plan.plan_hash
    assert report.selection_feedback_used is False
    assert report.summary.high_source_count == len(plan.sources)
    assert report.summary.plan_pair_count == len(plan.pairs)
    assert len(report.pairs) == len(plan.pairs)


def test_high_repetition_plan_and_report_fail_closed_on_tamper() -> None:
    backend = _ScoringBackend(expected_generate_calls=8)
    plan, report = run_synthid_high_repetition_detector_pilot(
        _prompts(),
        backend,
        release_transform_registry(),
        budgets=(1,),
    )
    with pytest.raises(ValueError, match="plan_hash"):
        replace(plan, plan_hash="0" * 64)
    if plan.pairs:
        with pytest.raises(ValueError, match="pair_plan_hash"):
            replace(plan.pairs[0], all_transformed_text=plan.pairs[0].all_transformed_text + " changed")
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, detector_config_hash="2" * 64)


def test_high_repetition_scoring_rejects_backend_identity_drift() -> None:
    plan = build_high_repetition_detector_plan(
        _prompts(),
        _PlanBackend(expected_generate_calls=8),
        release_transform_registry(),
        budgets=(1,),
    )
    backend = _ScoringBackend(expected_generate_calls=0)
    backend.backend_version = "fake-v2"
    with pytest.raises(ValueError, match="backend_version"):
        score_high_repetition_detector_plan(plan, backend)


def test_source_manifest_retains_all_sources_and_reconstructs_the_same_q4() -> None:
    prompts = _prompts()
    raw = _PlanBackend(expected_generate_calls=8)
    prompt_ids = {(row.text, row.seed): row.prompt_id for row in prompts}
    backend = _RecordingBackend(raw, prompt_ids)
    plan = build_high_repetition_detector_plan(
        prompts,
        backend,
        release_transform_registry(),
        budgets=(1,),
        schedule_seed=43,
    )
    manifest = _build_source_manifest(backend, 8)
    assert manifest["detector_scores_used"] is False
    assert manifest["source_count"] == 8
    sources = manifest["sources"]
    assert isinstance(sources, list)
    assert len(sources) == 8
    q4 = tuple(row for row in sources if row["stratum"] == TARGET_STRATUM.value)
    assert len(q4) == 2
    _validate_plan_against_source_manifest(plan, manifest)

    tampered = dict(manifest)
    tampered_sources = [dict(row) for row in sources]
    first_q4 = next(index for index, row in enumerate(tampered_sources) if row["stratum"] == TARGET_STRATUM.value)
    tampered_sources[first_q4]["stratum"] = "Q1_LOW"
    tampered["sources"] = tampered_sources
    with pytest.raises(RuntimeError, match="Q4 plan"):
        _validate_plan_against_source_manifest(plan, tampered)
