from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from fuckmark.corpus import CorpusSplit, WatermarkLabel
from fuckmark.experiments.context_survival_plan import (
    BASELINE_INVARIANT_SCREEN_ALGORITHM_VERSION,
    BEAM_B4_POLICY,
    EXACT_B2_POLICY,
    _baseline_invariant_screen,
    _filter_scheduler_input,
)
from fuckmark.hashing import sha256_text
from fuckmark.scheduling.beam_v2 import CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
from fuckmark.tiny_dev_context_survival_plan_hf import (
    TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION,
    TINY_DEV_VISIBLE_TYPOGRAPHY_PLAN_VERSION,
    VISIBLE_TYPOGRAPHY_REGISTRY_PROFILE,
    _build_context_survival_plan_v3,
    _build_visible_typography_plan_v1,
)
from fuckmark.transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    LiteralTransformRule,
    SchedulePolicy,
    TransformFamily,
    TransformRegistry,
    TransformTier,
)


class _Tokenizer:
    def _pieces(self, text):
        return tuple(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text))

    def encode(self, text, add_special_tokens=True):
        return [
            int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
            for match in self._pieces(text)
        ]

    def __call__(self, text, add_special_tokens=True, return_offsets_mapping=False):
        matches = self._pieces(text)
        output = {
            "input_ids": [
                int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
                for match in matches
            ]
        }
        if return_offsets_mapping:
            output["offset_mapping"] = [(match.start(), match.end()) for match in matches]
        return output


def _fake_corpus():
    tokenizer = _Tokenizer()
    identity_hash = sha256_text("fake-tokenizer-v2")
    samples = []
    for index in range(8):
        text = f"We do not know and the result is clear in the plan for item {index}."
        label = WatermarkLabel.WATERMARKED if index < 4 else WatermarkLabel.UNWATERMARKED
        samples.append(
            SimpleNamespace(
                sample_id=f"sample-{index}",
                split=CorpusSplit.ATTACK_DEVELOPMENT,
                label=label,
                text=text,
                text_sha256=sha256_text(text),
                prompt_family_id="fake-prompt",
                domain=SimpleNamespace(value="technical"),
                model=SimpleNamespace(identity_hash=identity_hash, eos_token_id=0),
                text_only_tokens=SimpleNamespace(token_ids=tuple(tokenizer.encode(text, add_special_tokens=False))),
            )
        )
    corpus = SimpleNamespace(
        artifact_hash=sha256_text("fake-corpus-v2"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(
            samples=tuple(samples),
            manifest_hash=sha256_text("fake-manifest-v2"),
        ),
    )
    return corpus, tokenizer


def test_plan_v3_covers_exact_b2_and_beam_b4_with_dynamic_attestation() -> None:
    corpus, tokenizer = _fake_corpus()
    plan = _build_context_survival_plan_v3(
        corpus,
        tokenizer,
        ngram_len=2,
        context_history_size=4,
        budgets=(2, 4),
        random_seed_count=1,
        beam_width=2,
        max_risk_tier=1,
        source_code_commit="test-v3-commit",
    )
    policies = {row["schedule_policy"] for row in plan["variants"]}
    assert plan["algorithm_version"] == TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION
    assert "registry_profile" not in plan
    assert plan["beam_algorithm_version"] == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    assert plan["attested_expander_count"] == 8
    assert plan["detector_access_observed"] is False
    assert plan["secret_access_observed"] is False
    assert EXACT_B2_POLICY in policies
    assert BEAM_B4_POLICY in policies


def test_visible_typography_plan_has_a_distinct_replay_identity() -> None:
    corpus, tokenizer = _fake_corpus()
    plan = _build_visible_typography_plan_v1(
        corpus,
        tokenizer,
        ngram_len=2,
        context_history_size=4,
        budgets=(1,),
        random_seed_count=1,
        beam_width=2,
        max_risk_tier=1,
        source_code_commit="test-visible-typography-commit",
    )
    assert plan["algorithm_version"] == TINY_DEV_VISIBLE_TYPOGRAPHY_PLAN_VERSION
    assert plan["registry_profile"] == VISIBLE_TYPOGRAPHY_REGISTRY_PROFILE
    assert plan["attested_expander_count"] == 8
    assert plan["detector_access_observed"] is False
    assert plan["secret_access_observed"] is False


def test_detector_blind_import_audit_checks_modules_and_imported_symbols() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "fuckmark" / "experiments" / "context_survival_plan.py",
        root / "fuckmark" / "scheduling" / "beam_v2.py",
        root / "fuckmark" / "tiny_dev_context_survival_plan_hf.py",
    )
    forbidden = ("detector", "g_value", "gvalue", "bayesian", "secret_key", "watermark_key")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
                names.extend(alias.name for alias in node.names)
        assert all(not any(value in name.lower() for value in forbidden) for name in names)


def test_baseline_screen_rejects_context_invalid_candidate_before_scheduling() -> None:
    rules = (
        LiteralTransformRule.create(
            rule_id="contract-you-are",
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source="you are",
            replacement="you're",
        ),
        LiteralTransformRule.create(
            rule_id="contract-do-not",
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source="do not",
            replacement="don't",
        ),
    )
    registry = TransformRegistry(rules)
    enumeration = registry.enumerate("If you are not ready, do not continue.")
    invalid = next(value for value in enumeration.candidates if value.rule_id == "contract-you-are")
    safe = next(value for value in enumeration.candidates if value.rule_id == "contract-do-not")
    with pytest.raises(ValueError, match="hard content invariants"):
        registry.apply(enumeration, (invalid.candidate_id,))
    screen = _baseline_invariant_screen(registry, enumeration)
    assert screen["algorithm_version"] == BASELINE_INVARIANT_SCREEN_ALGORITHM_VERSION
    assert screen["safe_candidate_ids"] == (safe.candidate_id,)
    assert screen["rejected_candidate_ids"] == (invalid.candidate_id,)
    scheduler_input = _filter_scheduler_input(
        KeyBlindScheduleInput.from_enumeration(enumeration),
        screen["safe_candidate_ids"],
    )
    schedule = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=2,
        seed=0,
    )
    assert schedule.selected_candidate_ids == (safe.candidate_id,)
    assert registry.apply(enumeration, schedule.selected_candidate_ids).output_text.endswith("don't continue.")


def test_baseline_screen_does_not_hide_validator_programming_errors(monkeypatch) -> None:
    import fuckmark.experiments.context_survival_plan as module

    registry = TransformRegistry(
        (
            LiteralTransformRule.create(
                rule_id="contract-do-not",
                version="v1",
                family=TransformFamily.CONTRACTION,
                tier=TransformTier.SURFACE,
                source="do not",
                replacement="don't",
            ),
        )
    )
    enumeration = registry.enumerate("Do not continue.")

    def fail(*args, **kwargs):
        raise RuntimeError("validator programming error")

    monkeypatch.setattr(module, "validate_hard_invariants", fail)
    with pytest.raises(RuntimeError, match="programming error"):
        _baseline_invariant_screen(registry, enumeration)
