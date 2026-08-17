from __future__ import annotations

import hashlib
import re

from fuckmark.experiments.synthid_geometry import build_public_candidate_coverage
from fuckmark.experiments.synthid_schedule_stress import run_synthid_schedule_stress
from fuckmark.experiments.synthid_smoke import SynthIDSmokePrompt
from fuckmark.hashing import sha256_text
from fuckmark.transforms import development_transform_registry, release_transform_registry
from fuckmark.transforms.mechanism_registry import mechanism_stress_transform_registry
from fuckmark.transforms.mechanism_rules import mechanism_stress_rules
from fuckmark.transforms.schema import TransformTier


_FIXTURE = (
    "We are careful and do not rush. In order to verify this, we should not skip review. "
    "In other words, we are ready. For example, we could not ignore a failure. "
    "As a result, it is useful."
)


class _MechanismBackend:
    backend_id = "mechanism-fixture-generation"
    backend_version = "mechanism-fixture-v1"
    model_id = "mechanism-fixture-model"
    detector_id = "unused"
    detector_config_hash = sha256_text("unused-mechanism-detector")
    ngram_len = 5

    def __init__(self, expected_generate_calls: int) -> None:
        self.expected_generate_calls = expected_generate_calls
        self.generate_calls = 0
        self.score_calls = 0

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        self.generate_calls += 1
        return _FIXTURE

    def tokenize(self, text: str) -> tuple[int, ...]:
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        return tuple(
            int.from_bytes(hashlib.sha256(piece.encode("utf-8")).digest()[:4], "big")
            for piece in pieces
        )

    def score(self, text: str) -> float:
        self.score_calls += 1
        raise AssertionError("mechanism headroom test must not request detector scores")


def _coverage_size(intervals) -> int:
    return sum(value.end - value.start for value in intervals)


def test_mechanism_rules_are_isolated_and_experimental() -> None:
    release_ids = {rule.rule_id for rule in release_transform_registry().rules}
    development_ids = {rule.rule_id for rule in development_transform_registry().rules}
    mechanism = mechanism_stress_transform_registry()
    stress_ids = {rule.rule_id for rule in mechanism.rules if rule.rule_id.startswith("stress-")}
    assert stress_ids
    assert not any(rule_id.startswith("stress-") for rule_id in release_ids)
    assert not any(rule_id.startswith("stress-") for rule_id in development_ids)
    assert stress_ids == {rule.rule_id for rule in mechanism_stress_rules()}
    assert all(rule.tier is TransformTier.EXPERIMENTAL for rule in mechanism.rules if rule.rule_id.startswith("stress-"))
    assert mechanism.ruleset_hash != release_transform_registry().ruleset_hash
    assert mechanism.ruleset_hash != development_transform_registry().ruleset_hash


def test_mechanism_candidates_apply_individually_under_hard_invariants() -> None:
    registry = mechanism_stress_transform_registry()
    enumeration = registry.enumerate(_FIXTURE)
    stress_candidates = tuple(row for row in enumeration.candidates if row.rule_id.startswith("stress-"))
    assert len(stress_candidates) >= 6
    for candidate in stress_candidates:
        result = registry.apply(enumeration, (candidate.candidate_id,), seed=0)
        assert result.output_text != _FIXTURE
        assert result.trace.protected_span_violation_count == 0


def test_mechanism_registry_creates_heterogeneous_public_geometry() -> None:
    backend = _MechanismBackend(expected_generate_calls=0)
    registry = mechanism_stress_transform_registry()
    enumeration = registry.enumerate(_FIXTURE)
    coverage = build_public_candidate_coverage(registry, enumeration, backend.tokenize, backend.ngram_len)
    sizes = {
        _coverage_size(coverage[row.candidate_id])
        for row in enumeration.candidates
        if coverage[row.candidate_id]
    }
    assert len(sizes) > 1


def test_mechanism_registry_exposes_random_vs_optimal_headroom() -> None:
    prompts = (
        SynthIDSmokePrompt("mechanism-1", "fixture one", 1),
        SynthIDSmokePrompt("mechanism-2", "fixture two", 2),
    )
    backend = _MechanismBackend(expected_generate_calls=4)
    report = run_synthid_schedule_stress(
        prompts,
        backend,
        mechanism_stress_transform_registry(),
        budgets=(1, 2),
        random_seeds=tuple(range(100, 132)),
        spacing_seed=99,
    )
    assert backend.generate_calls == 4
    assert backend.score_calls == 0
    exact = tuple(row for row in report.opportunities if row.exact_optimal_coverage is not None)
    assert exact
    assert all(row.exact_optimal_coverage >= row.greedy_coverage for row in exact)
    assert all(row.greedy_regret >= 0 for row in exact)
    assert any((row.random_headroom_to_optimum or 0.0) > 0.0 for row in exact)
    assert any((row.greedy_advantage_over_random or 0.0) > 0.0 for row in exact)
