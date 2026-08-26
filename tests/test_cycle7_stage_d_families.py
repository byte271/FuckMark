from pathlib import Path

import pytest

from fuckmark.cycle7.density import durable_density_row, durable_density_table
from fuckmark.cycle7.durable_rules import (
    CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    cycle7_word_boundary_rules,
)
from fuckmark.cycle7.fixtures import WORD_BOUNDARY_RICH, stage_d_fixture_samples
from fuckmark.cycle7.ledger import (
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_D1_TOPIC,
    CYCLE7_STAGE_C_VALIDATION_SEED_BASE,
    CYCLE7_STAGE_C_VALIDATION_TOPIC,
    CYCLE7_VALIDATION_ROLE,
    assert_development_seed,
    assert_rule_construction_seed,
)
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.stage_b import INSUFFICIENT_EVIDENCE, PROMISING_DEVELOPMENT, summarize_density_rows
from fuckmark.cycle7.stage_d import classify_stage_d_density, density_artifact_stage_d
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace, sanitize_cycle7_variant
from fuckmark.cycle7_stage_d_hf import admit_stage_d1_seed
from fuckmark.transforms.format_rules import FormatConstruction
from fuckmark.transforms.hard_invariants import validate_hard_invariants
from fuckmark.transforms.schema import InvariantStatus


def _apply_rule(text: str, rule_id: str) -> str:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate for candidate in enumeration.candidates if candidate.rule_id == rule_id
    )
    assert selected, (rule_id, tuple(candidate.rule_id for candidate in enumeration.candidates), text)
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    return result.output_text


def test_stage_d_ledger_identities_are_frozen_before_inspection() -> None:
    assert CYCLE7_DURABLE_RULE_CATALOG_VERSION == "cycle7-durable-rule-catalog-v5"
    assert CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE == 890000
    assert CYCLE7_STAGE_D1_TOPIC == "document structure"
    assert CYCLE7_STAGE_C_VALIDATION_SEED_BASE == 880000
    assert CYCLE7_STAGE_C_VALIDATION_TOPIC == "independent check"
    with pytest.raises(ValueError, match="rule-construction"):
        assert_rule_construction_seed(890000)
    assert_development_seed(CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    assert_development_seed(CYCLE7_STAGE_C_VALIDATION_SEED_BASE, role=CYCLE7_VALIDATION_ROLE)
    with pytest.raises(ValueError, match="rule-construction"):
        admit_stage_d1_seed(890000, samples_from=None)
    admit_stage_d1_seed(
        890000,
        samples_from=Path("evidence/cycle7-stage-d-2026-08-25/samples.json"),
    )
    with pytest.raises(ValueError, match="exploratory"):
        admit_stage_d1_seed(
            880000,
            samples_from=Path("evidence/cycle7-stage-d-validation-880000-2026-08-25/samples.json"),
        )
    with pytest.raises(ValueError, match="confirmation-reserved"):
        admit_stage_d1_seed(830000, samples_from=Path("evidence/cycle7-stage-d-2026-08-25/samples.json"))


def test_word_boundary_swaps_space_and_newline() -> None:
    rules = cycle7_word_boundary_rules()
    assert len(rules) == 2
    assert all(
        rule._payload()["construction"] == FormatConstruction.WORD_BOUNDARY_NEWLINE.value for rule in rules
    )
    text = "The protocol remains fixed."
    output = _apply_rule(text, "cycle7-word-boundary-newline")
    assert output == "The\nprotocol remains fixed."
    assert collapse_horizontal_ascii_whitespace(output) == output
    for variant in (
        "raw",
        "nfkc",
        "cf_strip",
        "nfkc_cf_strip",
        "ws_collapse",
        "ws_collapse_nfkc_cf_strip",
    ):
        assert sanitize_cycle7_variant(variant, output) == output
    restored = _apply_rule(output, "cycle7-word-boundary-space")
    assert restored == text
    assert validate_hard_invariants(text, output).status is InvariantStatus.PASS


def test_word_boundary_false_positives_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    blocked = (
        "A b c remains.",
        "I am.",
        "See v2 later.",
        "Hello. World.",
        "Failed, X passed.",
        "Value 12 stays.",
        "List a, b, c remains.",
    )
    for text in blocked:
        enumeration = registry.enumerate(text)
        assert not any(
            candidate.rule_id.startswith("cycle7-word-boundary-") for candidate in enumeration.candidates
        ), text


def test_word_boundary_does_not_consume_punctuation_newline_sites() -> None:
    registry = cycle7_durable_transform_registry()
    text = "Careful testing matters. Independent replication remains required."
    enumeration = registry.enumerate(text)
    sentence = tuple(
        candidate for candidate in enumeration.candidates if candidate.rule_id == "cycle7-format-sentence-period-newline"
    )
    wraps = tuple(
        candidate for candidate in enumeration.candidates if candidate.rule_id == "cycle7-word-boundary-newline"
    )
    assert sentence
    assert sentence[0].source_text == ". "
    assert all(candidate.source_text == " " for candidate in wraps)
    assert not any(candidate.start == sentence[0].start + 1 for candidate in wraps)


def test_stage_d_fixtures_have_word_boundary_density() -> None:
    wrap = durable_density_row("word-boundary-rich", WORD_BOUNDARY_RICH)
    assert int(wrap["word_boundary_candidate_count"]) >= 8
    samples = tuple(
        {"sample_id": sample_id, "text": text} for sample_id, text in stage_d_fixture_samples()
    )
    rows = durable_density_table(samples)
    summary = summarize_density_rows(rows)
    assert summary["mean_word_boundary_candidate_count"] >= 8
    decision = classify_stage_d_density(density_summary=summary)
    assert decision["decision"] in {PROMISING_DEVELOPMENT, INSUFFICIENT_EVIDENCE}
    artifact = density_artifact_stage_d(
        samples,
        seed_base=CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["seed_base"] == 890000


def test_stage_d_classifier_requires_word_boundary_density_and_geometry() -> None:
    four_site = {
        "mean_candidate_count": 4.75,
        "mean_format_candidate_count": 2.875,
        "mean_word_boundary_candidate_count": 0.0,
    }
    assert classify_stage_d_density(density_summary=four_site)["decision"] == INSUFFICIENT_EVIDENCE
    dense_weak_geometry = {
        "mean_candidate_count": 22.0,
        "mean_format_candidate_count": 2.0,
        "mean_word_boundary_candidate_count": 18.0,
    }
    weak = classify_stage_d_density(
        density_summary=dense_weak_geometry,
        collapsed_intact_mean=45.0,
        source_root_mean=50.0,
    )
    assert weak["decision"] == INSUFFICIENT_EVIDENCE
    promising = classify_stage_d_density(
        density_summary=dense_weak_geometry,
        collapsed_intact_mean=20.0,
        source_root_mean=50.0,
    )
    assert promising["decision"] == PROMISING_DEVELOPMENT


def test_gpt2_tokenization_changes_for_word_boundary_newline() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
    )
    left = "The protocol remains fixed"
    right = "The\nprotocol remains fixed"
    assert tokenizer.encode(left, add_special_tokens=False) != tokenizer.encode(
        right, add_special_tokens=False
    )
