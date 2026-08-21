import json

import pytest

from diverse_beam_helpers import diverse_beam_fake_corpus
from fuckmark.experiments.normalization_survival import (
    N0_IDENTITY,
    N1_WHITESPACE_COLLAPSE,
    N2_LINE_ENDINGS_LF,
    N3_UNICODE_NFC,
    N4_COPY_PASTE_WHITESPACE,
    NORMALIZATION_BUDGET_WITNESS_LEGACY_VERSION,
    NORMALIZATION_SAMPLE_PROFILE_LEGACY_VERSION,
    NORMALIZATION_SAMPLE_SUMMARY_LEGACY_VERSION,
    NORMALIZATION_SURVIVAL_BENCHMARK_LEGACY_VERSION,
    benchmark_normalization_source,
    build_normalization_survival_benchmark,
    load_normalization_survival_benchmark,
    normalization_profiles,
    normalize_text,
)
from fuckmark.hashing import sha256_json
from fuckmark.transforms.contractions import context_survival_contraction_rules
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import LiteralTransformRule
from fuckmark.transforms.schema import TransformFamily, TransformTier
from fuckmark.transforms.surface_rules import development_surface_rules


def _registry() -> TransformRegistry:
    return TransformRegistry(
        (*context_survival_contraction_rules(), *development_surface_rules())
    )


def _legacy_benchmark(value: dict[str, object]) -> dict[str, object]:
    output = json.loads(json.dumps(value))
    output["algorithm_version"] = NORMALIZATION_SURVIVAL_BENCHMARK_LEGACY_VERSION
    for summary in output["sample_summaries"]:
        summary["algorithm_version"] = NORMALIZATION_SAMPLE_SUMMARY_LEGACY_VERSION
        for profile in summary["profiles"]:
            profile["algorithm_version"] = NORMALIZATION_SAMPLE_PROFILE_LEGACY_VERSION
            for witness in profile["witnesses"]:
                witness["algorithm_version"] = (
                    NORMALIZATION_BUDGET_WITNESS_LEGACY_VERSION
                )
                witness["witness_hash"] = sha256_json(
                    {key: item for key, item in witness.items() if key != "witness_hash"}
                )
            prefix_count = max(
                (
                    witness["budget"]
                    for witness in profile["witnesses"]
                    if witness["reachable"]
                ),
                default=0,
            )
            assert all(
                witness["reachable"] == (prefix_count >= witness["budget"])
                for witness in profile["witnesses"]
            )
            profile.pop("exact_budget_reachable_count")
            profile["verified_compatible_prefix_count"] = prefix_count
            profile["summary_hash"] = sha256_json(
                {key: item for key, item in profile.items() if key != "summary_hash"}
            )
        summary["summary_hash"] = sha256_json(
            {key: item for key, item in summary.items() if key != "summary_hash"}
        )
    output["artifact_hash"] = sha256_json(
        {key: item for key, item in output.items() if key != "artifact_hash"}
    )
    return output


def test_normalization_profiles_apply_frozen_contracts() -> None:
    profiles = {value.profile_id: value for value in normalization_profiles()}
    source = "Cafe\u0301  \talpha \r\nbeta\t \rgamma  "
    assert normalize_text(source, profiles[N0_IDENTITY]) == source
    assert (
        normalize_text(source, profiles[N1_WHITESPACE_COLLAPSE])
        == "Cafe\u0301 alpha\r\nbeta\rgamma"
    )
    assert (
        normalize_text(source, profiles[N2_LINE_ENDINGS_LF])
        == "Cafe\u0301  \talpha \nbeta\t \ngamma  "
    )
    assert (
        normalize_text(source, profiles[N3_UNICODE_NFC])
        == "Caf\u00e9  \talpha \r\nbeta\t \rgamma  "
    )
    assert (
        normalize_text(source, profiles[N4_COPY_PASTE_WHITESPACE])
        == "Cafe\u0301 alpha\nbeta\ngamma"
    )


def test_benchmark_attributes_durable_and_fragile_candidates() -> None:
    summary, rows = benchmark_normalization_source(
        sample_id="sample-1",
        source_text="We do not agree. We are ready.",
        registry=_registry(),
    )
    by_rule_profile = {(value.rule_id, value.profile_id): value for value in rows}
    assert by_rule_profile[("contract-do-not", N1_WHITESPACE_COLLAPSE)].survives
    assert by_rule_profile[("contract-we-are", N4_COPY_PASTE_WHITESPACE)].survives
    assert not by_rule_profile[("surface-space-after-period", N1_WHITESPACE_COLLAPSE)].survives
    assert not by_rule_profile[("surface-space-after-not", N4_COPY_PASTE_WHITESPACE)].survives
    n4 = next(value for value in summary.profiles if value.profile_id == N4_COPY_PASTE_WHITESPACE)
    assert n4.invariant_safe_surviving_count == 2
    assert n4.independent_invariant_safe_surviving_count == 2
    assert n4.exact_budget_reachable_count == 2
    assert tuple(value.reachable for value in n4.witnesses) == (
        True,
        True,
        False,
        False,
    )
    assert len(n4.witnesses[1].candidate_ids) == 2


def test_exact_budget_search_checks_overlapping_alternatives() -> None:
    def rule(rule_id: str, source: str, replacement: str) -> LiteralTransformRule:
        return LiteralTransformRule.create(
            rule_id=rule_id,
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.SURFACE,
            source=source,
            replacement=replacement,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        )

    registry = TransformRegistry(
        (
            rule("bad-0", "x ", " "),
            rule("alt-0", "x ", "z "),
            rule("tail-0", "y ", " "),
        )
    )
    summary, rows = benchmark_normalization_source(
        sample_id="overlap-alternative",
        source_text="are x y not",
        registry=registry,
    )
    n0 = next(value for value in summary.profiles if value.profile_id == N0_IDENTITY)
    by_rule = {
        value.rule_id: value
        for value in rows
        if value.profile_id == N0_IDENTITY
    }
    b2 = next(value for value in n0.witnesses if value.budget == 2)
    assert all(value.invariant_safe and value.survives for value in by_rule.values())
    assert n0.independent_invariant_safe_surviving_count == 2
    assert n0.witness_search_rejection_count == 1
    enumeration = registry.enumerate("are x y not")
    with pytest.raises(ValueError, match="hard content invariants"):
        registry.apply(
            enumeration,
            (by_rule["bad-0"].candidate_id, by_rule["tail-0"].candidate_id),
        )
    assert registry.apply(
        enumeration,
        (by_rule["alt-0"].candidate_id, by_rule["tail-0"].candidate_id),
    ).output_text == "are z  not"
    assert b2.reachable
    assert b2.candidate_ids == (
        by_rule["alt-0"].candidate_id,
        by_rule["tail-0"].candidate_id,
    )


def test_expected_invariant_rejection_fails_closed_per_candidate() -> None:
    registry = _registry()
    enumeration = registry.enumerate("You are not ready.")
    invalid_candidate = next(
        value for value in enumeration.candidates if value.rule_id == "contract-you-are"
    )
    with pytest.raises(ValueError, match="hard content invariants"):
        registry.apply(enumeration, (invalid_candidate.candidate_id,))
    summary, rows = benchmark_normalization_source(
        sample_id="sample-2",
        source_text="You are not ready.",
        registry=registry,
    )
    rejected = [value for value in rows if value.rule_id == "contract-you-are"]
    assert len(rejected) == len(normalization_profiles())
    assert all(not value.invariant_safe for value in rejected)
    assert all(value.survives for value in rejected)
    assert summary.invariant_rejection_count == 1
    n4 = next(value for value in summary.profiles if value.profile_id == N4_COPY_PASTE_WHITESPACE)
    assert n4.invariant_safe_surviving_count == 1


def test_real_shape_benchmark_round_trips_and_rejects_nested_tampering(tmp_path) -> None:
    benchmark = build_normalization_survival_benchmark(
        diverse_beam_fake_corpus(),
        _registry(),
        benchmark_source_code_commit="b" * 40,
        source_workflow_run_id=32504847438,
    )
    path = tmp_path / "normalization.json"
    path.write_text(json.dumps(benchmark), encoding="utf-8")
    loaded = load_normalization_survival_benchmark(path)
    assert sha256_json(loaded) == sha256_json(benchmark)
    assert benchmark["source_sample_count"] == 500
    assert benchmark["candidate_row_count"] > 0
    legacy = _legacy_benchmark(benchmark)
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert load_normalization_survival_benchmark(path) == legacy
    tampered = json.loads(json.dumps(benchmark))
    tampered["candidate_rows"][0]["normalized_output_hash"] = "0" * 64
    payload = {key: value for key, value in tampered.items() if key != "artifact_hash"}
    tampered["artifact_hash"] = sha256_json(payload)
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate row"):
        load_normalization_survival_benchmark(path)
