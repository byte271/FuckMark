from __future__ import annotations

import re
from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_geometry import GeometryLabel
from fuckmark.experiments.synthid_repetition_strata import (
    RepetitionStratum,
    run_synthid_repetition_strata,
)
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.transforms import release_transform_registry


class _FakeBackend:
    backend_id = "fake-repetition-generation"
    backend_version = "fake-v1"
    model_id = "fake-model"
    ngram_len = 3
    eos_token_id = 999999
    context_history_size = 32

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0
        self.tokenize_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        prefix = "WMARK" if watermarked else "CTRL"
        repeats = seed
        repeated = " ".join("We do not panic." for _ in range(repeats))
        return f"{prefix} {repeated} We should not drift. We cannot ignore evidence."

    def tokenize(self, text: str) -> tuple[int, ...]:
        self.tokenize_calls += 1
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        vocabulary = {}
        output = []
        for piece in pieces:
            if piece not in vocabulary:
                vocabulary[piece] = len(vocabulary) + 1
            output.append(vocabulary[piece])
        return tuple(output)


def _prompts() -> tuple[SynthIDSmokePrompt, ...]:
    return tuple(
        SynthIDSmokePrompt(f"r-{index}", f"Repeat structure {index}.", index)
        for index in range(1, 5)
    )


def test_repetition_strata_retains_every_generated_source_and_balances_rank_quartiles() -> None:
    prompts = _prompts()
    backend = _FakeBackend(expected_generate_calls=len(prompts) * 2)
    report = run_synthid_repetition_strata(
        prompts,
        backend,
        release_transform_registry(),
        budgets=(1,),
        schedule_seed=12,
    )
    assert backend.generate_calls == 8
    assert backend.tokenize_calls > backend.generate_calls
    assert report.detector_scores_used is False
    assert report.summary.prompt_count == 4
    assert report.summary.source_count == 8
    assert report.summary.control_source_count == 4
    assert report.summary.watermarked_source_count == 4
    assert len(report.records) == 8
    for label in (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED):
        rows = tuple(row for row in report.records if row.label is label)
        assert {row.stratum for row in rows} == set(RepetitionStratum)
        ordered = tuple(sorted(rows, key=lambda row: row.rank_within_label))
        assert tuple(row.rank_within_label for row in ordered) == (1, 2, 3, 4)
        assert tuple(row.repeated_fraction for row in ordered) == tuple(
            sorted(row.repeated_fraction for row in ordered)
        )
        assert ordered[0].stratum is RepetitionStratum.Q1_LOW
        assert ordered[-1].stratum is RepetitionStratum.Q4_HIGH
    assert len(report.strata) == 8
    assert all(row.source_count == 1 for row in report.strata)


def test_repetition_strata_high_quartile_has_no_less_repetition_than_low_quartile() -> None:
    report = run_synthid_repetition_strata(
        _prompts(),
        _FakeBackend(expected_generate_calls=8),
        release_transform_registry(),
        budgets=(1,),
    )
    for label in (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED):
        low = next(row for row in report.strata if row.label is label and row.stratum is RepetitionStratum.Q1_LOW)
        high = next(row for row in report.strata if row.label is label and row.stratum is RepetitionStratum.Q4_HIGH)
        assert low.max_repeated_fraction is not None
        assert high.min_repeated_fraction is not None
        assert high.min_repeated_fraction >= low.max_repeated_fraction


def test_repetition_strata_report_fails_closed_on_tamper() -> None:
    report = run_synthid_repetition_strata(
        _prompts(),
        _FakeBackend(expected_generate_calls=8),
        release_transform_registry(),
        budgets=(1,),
    )
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, schedule_seed=99)
    with pytest.raises(ValueError, match="record_hash"):
        replace(report.records[0], record_hash="0" * 64)


def test_repetition_strata_rejects_duplicate_prompt_ids() -> None:
    prompt = SynthIDSmokePrompt("dup", "Repeat.", 1)
    with pytest.raises(ValueError, match="unique"):
        run_synthid_repetition_strata(
            (prompt, replace(prompt, seed=2)),
            _FakeBackend(expected_generate_calls=0),
            release_transform_registry(),
        )
