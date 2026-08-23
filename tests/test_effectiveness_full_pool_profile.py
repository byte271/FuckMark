from __future__ import annotations

from types import SimpleNamespace

import pytest

from fuckmark.corpus import CorpusDomain, CorpusSplit, WatermarkLabel
from fuckmark.experiments.effectiveness_plan import (
    build_key_blind_high_coverage_plan,
    validate_key_blind_high_coverage_plan,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
    KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE,
    KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    key_blind_full_pool_coverage_profile,
    resolve_effectiveness_profile,
)
from fuckmark.tiny_dev_effectiveness_plan_hf import _parse_budgets
from fuckmark.tiny_dev_effectiveness_score_hf import _parse_budgets as _parse_budgets_score


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


def test_full_pool_profile_is_deterministic_and_binds_budgets() -> None:
    first = key_blind_full_pool_coverage_profile((16, 24, 32, 48))
    second = key_blind_full_pool_coverage_profile((16, 24, 32, 48))
    assert first == second
    assert first.profile_id == KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID
    assert first.budgets == (16, 24, 32, 48)
    assert first.schedule_seed_base == KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE
    assert first.ruleset_hash == resolve_effectiveness_profile(
        KEY_BLIND_HIGH_COVERAGE_PROFILE_ID
    ).ruleset_hash
    other = key_blind_full_pool_coverage_profile((32,))
    assert other.profile_hash != first.profile_hash


def test_resolve_effectiveness_profile_rejects_invalid_requests() -> None:
    with pytest.raises(ValueError):
        resolve_effectiveness_profile("unknown-profile")
    with pytest.raises(ValueError):
        resolve_effectiveness_profile(KEY_BLIND_HIGH_COVERAGE_PROFILE_ID, (16,))
    with pytest.raises(ValueError):
        resolve_effectiveness_profile(KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID)
    with pytest.raises(ValueError):
        key_blind_full_pool_coverage_profile((48, 16))


def test_full_pool_plan_covers_every_budget_with_derived_seeds() -> None:
    corpus = _corpus()
    profile = key_blind_full_pool_coverage_profile((24, 32))
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=profile,
        source_code_commit="a" * 40,
    )
    validate_key_blind_high_coverage_plan(plan, corpus, profile)
    assert plan["budgets"] == (24, 32)
    assert len(plan["variants"]) == 4
    assert {row["requested_budget"] for row in plan["variants"]} == {24, 32}
    assert [row["schedule_seed"] for row in plan["variants"]] == [
        KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE,
        KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE,
        KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE + 1,
        KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE + 1,
    ]
    assert all(row["detector_access_observed"] is False for row in plan["variants"])
    assert all(row["secret_access_observed"] is False for row in plan["variants"])


def test_full_pool_plan_rejects_mismatched_profile_on_validation() -> None:
    corpus = _corpus()
    profile = key_blind_full_pool_coverage_profile((24,))
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=profile,
        source_code_commit="a" * 40,
    )
    with pytest.raises(ValueError):
        validate_key_blind_high_coverage_plan(
            plan,
            corpus,
            key_blind_full_pool_coverage_profile((32,)),
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("", ()),
        ("16", (16,)),
        ("16,24,32,48", (16, 24, 32, 48)),
    ),
)
def test_budget_parsing_accepts_valid_lists(raw: str, expected: tuple[int, ...]) -> None:
    assert _parse_budgets(raw) == expected
    assert _parse_budgets_score(raw) == expected


@pytest.mark.parametrize("raw", ("16,,24", "0", "-4", "24,16", "16,16"))
def test_budget_parsing_rejects_invalid_lists(raw: str) -> None:
    with pytest.raises(ValueError):
        _parse_budgets(raw)
    with pytest.raises(ValueError):
        _parse_budgets_score(raw)
