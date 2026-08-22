from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fuckmark.corpus import CorpusDomain, CorpusSplit, WatermarkLabel
from fuckmark.experiments.effectiveness_plan import (
    KEY_BLIND_HIGH_COVERAGE_PLAN_VERSION,
    build_key_blind_high_coverage_plan,
    validate_key_blind_high_coverage_plan,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.tiny_dev_effectiveness_score_hf import _summaries
from fuckmark.transforms import KEY_BLIND_HIGH_COVERAGE_PROFILE


class FakeTokenizer:
    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool = False,
    ) -> dict[str, object]:
        assert add_special_tokens is False
        ids = [index + 1 for index in range(len(text))]
        value: dict[str, object] = {"input_ids": ids}
        if return_offsets_mapping:
            value["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return value


def _sample(sample_id: str, label: WatermarkLabel, text: str, identity_hash: str):
    token_ids = tuple(index + 1 for index in range(len(text)))
    return SimpleNamespace(
        sample_id=sample_id,
        split=CorpusSplit.ATTACK_DEVELOPMENT,
        label=label,
        prompt_family_id=f"prompt-{sample_id}",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        text=text,
        text_sha256=sha256_text(text),
        text_only_tokens=SimpleNamespace(token_ids=token_ids),
        model=SimpleNamespace(identity_hash=identity_hash, eos_token_id=50256),
    )


def _corpus():
    identity_hash = sha256_text("fake-tokenizer")
    text = "You are not ready, and we do not stop when the system is in use."
    samples = (
        _sample("negative-1", WatermarkLabel.UNWATERMARKED, text, identity_hash),
        _sample("positive-1", WatermarkLabel.WATERMARKED, text, identity_hash),
    )
    return SimpleNamespace(
        artifact_hash=sha256_text("fake-corpus"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(samples=samples, manifest_hash=sha256_text("fake-manifest")),
    )


def _plan() -> tuple[object, dict[str, object]]:
    corpus = _corpus()
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=KEY_BLIND_HIGH_COVERAGE_PROFILE,
        source_code_commit="a" * 40,
    )
    return corpus, plan


def test_effectiveness_plan_is_deterministic_detector_blind_and_complete() -> None:
    corpus, first = _plan()
    second = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=KEY_BLIND_HIGH_COVERAGE_PROFILE,
        source_code_commit="a" * 40,
    )
    assert first == second
    assert first["algorithm_version"] == KEY_BLIND_HIGH_COVERAGE_PLAN_VERSION
    assert first["detector_access_observed"] is False
    assert first["secret_access_observed"] is False
    assert first["budgets"] == (16,)
    assert first["replicate_count"] == 1
    assert len(first["variants"]) == 2
    assert {row["source_sample_id"] for row in first["variants"]} == {
        "negative-1",
        "positive-1",
    }
    assert all(row["hard_invariant_status"] == "pass" for row in first["variants"])
    assert [row["source_index"] for row in first["variants"]] == [0, 1]
    assert [row["schedule_seed"] for row in first["variants"]] == [1_120_000, 1_120_001]
    assert all(row["requested_budget"] == 16 for row in first["variants"])
    assert all(row["budget"] == min(16, row["candidate_count"]) for row in first["variants"])
    validate_key_blind_high_coverage_plan(
        first,
        corpus,
        KEY_BLIND_HIGH_COVERAGE_PROFILE,
    )
    validate_key_blind_high_coverage_plan(
        json.loads(json.dumps(first)),
        corpus,
        KEY_BLIND_HIGH_COVERAGE_PROFILE,
    )


def test_effectiveness_plan_validation_rejects_hash_and_denominator_tampering() -> None:
    corpus, plan = _plan()
    tampered_hash = {**plan, "source_code_commit": "b" * 40}
    with pytest.raises(ValueError, match="plan hash"):
        validate_key_blind_high_coverage_plan(
            tampered_hash,
            corpus,
            KEY_BLIND_HIGH_COVERAGE_PROFILE,
        )

    missing = {**plan, "variants": tuple(plan["variants"][:-1])}
    payload = {key: value for key, value in missing.items() if key != "plan_hash"}
    missing["plan_hash"] = sha256_json(payload)
    with pytest.raises(ValueError, match="complete source denominator"):
        validate_key_blind_high_coverage_plan(
            missing,
            corpus,
            KEY_BLIND_HIGH_COVERAGE_PROFILE,
        )

    changed_row = dict(plan["variants"][0])
    changed_row["budget"] += 1
    changed_row["variant_hash"] = sha256_json(
        {key: value for key, value in changed_row.items() if key != "variant_hash"}
    )
    changed_budget = {
        **plan,
        "variants": (changed_row, *plan["variants"][1:]),
    }
    changed_budget["plan_hash"] = sha256_json(
        {key: value for key, value in changed_budget.items() if key != "plan_hash"}
    )
    with pytest.raises(ValueError, match="budget does not replay candidate truncation"):
        validate_key_blind_high_coverage_plan(
            changed_budget,
            corpus,
            KEY_BLIND_HIGH_COVERAGE_PROFILE,
        )


def test_effectiveness_planning_import_graph_has_no_scoring_or_secret_dependency() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "fuckmark" / "transforms" / "effectiveness_profile.py",
        root / "fuckmark" / "experiments" / "effectiveness_plan.py",
        root / "fuckmark" / "tiny_dev_effectiveness_plan_hf.py",
    )
    forbidden = ("adapter", "detector", "bayesian", "g_value", "gvalue", "watermark_key", "secret_key")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
        assert all(not any(value in name.lower() for value in forbidden) for name in imported)


def test_effectiveness_scorer_cannot_build_or_select_a_plan() -> None:
    path = Path(__file__).parents[1] / "fuckmark" / "tiny_dev_effectiveness_score_hf.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_names = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert "build_key_blind_high_coverage_plan" not in imported_names
    assert "CandidateScheduler" not in imported_names


def test_effectiveness_summary_keeps_independent_source_count_visible() -> None:
    rows = (
        {
            "source_label": "watermarked",
            "source_sample_id": "source-1",
            "requested_budget": 16,
            "budget": 16,
            "realized_edit_cost": 16,
            "pristine_detected": True,
            "transformed_detected": False,
            "pristine_score": 0.64,
            "transformed_score": 0.54,
            "score_drop": 0.10,
            "word_edit_count": 0,
        },
        {
            "source_label": "watermarked",
            "source_sample_id": "source-2",
            "requested_budget": 16,
            "budget": 16,
            "realized_edit_cost": 3,
            "pristine_detected": True,
            "transformed_detected": True,
            "pristine_score": 0.60,
            "transformed_score": 0.58,
            "score_drop": 0.02,
            "word_edit_count": 1,
        },
    )
    summary = _summaries(rows)[0]
    assert summary["independent_source_count"] == 2
    assert summary["requested_budget"] == 16
    assert summary["transformed_detected_count"] == 1
    assert summary["mean_score_drop"] == pytest.approx(0.06)
