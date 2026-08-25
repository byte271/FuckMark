import pytest

from fuckmark.cycle7.density import durable_density_row, durable_density_table
from fuckmark.cycle7.durable_rules import (
    CYCLE7_STAGE_C_DURABLE_RULE_CATALOG_VERSION,
    cycle7_clause_punctuation_rules,
    cycle7_quantifier_of_rules,
)
from fuckmark.cycle7.fixtures import CLAUSE_PUNCT_RICH, QUANTIFIER_RICH, stage_c_fixture_samples
from fuckmark.cycle7.ledger import (
    CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_C1_TOPIC,
    CYCLE7_STAGE_C_VALIDATION_SEED_BASE,
    CYCLE7_STAGE_C_VALIDATION_TOPIC,
)
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.stage_b import INSUFFICIENT_EVIDENCE, PROMISING_DEVELOPMENT, summarize_density_rows
from fuckmark.cycle7.stage_c import classify_stage_c_density, density_artifact_stage_c
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace, sanitize_cycle7_variant
from fuckmark.transforms.format_rules import FormatConstruction
from fuckmark.transforms.hard_invariants import validate_hard_invariants
from fuckmark.transforms.lexical_rules import LexicalConstruction
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


def test_stage_c_ledger_identities_are_frozen_before_inspection() -> None:
    assert CYCLE7_STAGE_C_DURABLE_RULE_CATALOG_VERSION == "cycle7-durable-rule-catalog-v4"
    assert CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE == 870000
    assert CYCLE7_STAGE_C1_TOPIC == "measurement protocol"
    assert CYCLE7_STAGE_C_VALIDATION_SEED_BASE == 880000
    assert CYCLE7_STAGE_C_VALIDATION_TOPIC == "independent check"


def test_clause_punctuation_swaps_space_and_newline() -> None:
    rules = cycle7_clause_punctuation_rules()
    assert len(rules) == 6
    assert all(
        rule._payload()["construction"] == FormatConstruction.CLAUSE_PUNCTUATION_NEWLINE.value for rule in rules
    )
    text = "The first replica failed, and the second replica passed."
    output = _apply_rule(text, "cycle7-format-clause-comma-newline")
    assert output == "The first replica failed,\nand the second replica passed."
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
    restored = _apply_rule(output, "cycle7-format-clause-comma-space")
    assert restored == text
    assert validate_hard_invariants(text, output).status is InvariantStatus.PASS


def test_clause_semicolon_and_colon_boundaries_fire() -> None:
    semi = _apply_rule("The notes stayed; the logs were empty.", "cycle7-format-clause-semicolon-newline")
    assert semi == "The notes stayed;\nthe logs were empty."
    colon = _apply_rule("Protocol: The threshold stayed fixed.", "cycle7-format-clause-colon-newline")
    assert colon == "Protocol:\nThe threshold stayed fixed."


def test_clause_punctuation_false_positives_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    blocked = (
        "The total is 1, 000 units.",
        "See v2, and stop.",
        "Hello, X stays.",
        "Visit https://example.com/path,then continue.",
        "Time 3: 00 remains.",
        "List a, b, c remains.",
    )
    for text in blocked:
        enumeration = registry.enumerate(text)
        assert not any(
            candidate.rule_id.startswith("cycle7-format-clause-") for candidate in enumeration.candidates
        ), text


def test_quantifier_of_drop_and_insert_are_reversible() -> None:
    rules = cycle7_quantifier_of_rules()
    assert all(rule.construction is LexicalConstruction.QUANTIFIER_OF_DETERMINER for rule in rules)
    dropped = _apply_rule("All of the replicas failed.", "lexical-quantifier-drop-all-of-the")
    assert dropped == "All the replicas failed."
    inserted = _apply_rule("All the replicas failed.", "lexical-quantifier-insert-all-of-the")
    assert inserted == "All of the replicas failed."
    both = _apply_rule("Both of these logs were empty.", "lexical-quantifier-drop-both-of-these")
    assert both == "Both these logs were empty."
    half = _apply_rule("Half the notes stayed.", "lexical-quantifier-insert-half-of-the")
    assert half == "Half of the notes stayed."
    assert validate_hard_invariants("All of the replicas failed.", dropped).status is InvariantStatus.PASS
    collapsed = collapse_horizontal_ascii_whitespace(dropped)
    assert collapsed == dropped


def test_quantifier_of_false_positives_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    blocked = (
        "All of them failed.",
        "Both of us waited.",
        "Half of it remained.",
        "All of a sudden the run stopped.",
        "Some of the replicas failed.",
        "Most of the logs were empty.",
        "Each of the notes stayed.",
        "ALL OF THE REPLICAS FAILED.",
    )
    for text in blocked:
        enumeration = registry.enumerate(text)
        assert not any(
            candidate.rule_id.startswith("lexical-quantifier-") for candidate in enumeration.candidates
        ), text


def test_stage_c_fixtures_have_clause_and_quantifier_density() -> None:
    clause = durable_density_row("clause-punct-rich", CLAUSE_PUNCT_RICH)
    quantifier = durable_density_row("quantifier-rich", QUANTIFIER_RICH)
    assert int(clause["format_clause_candidate_count"]) >= 2
    assert int(quantifier["quantifier_of_candidate_count"]) >= 2
    samples = tuple(
        {"sample_id": sample_id, "text": text} for sample_id, text in stage_c_fixture_samples()
    )
    rows = durable_density_table(samples)
    summary = summarize_density_rows(rows)
    assert summary["mean_candidate_count"] >= 4
    decision = classify_stage_c_density(density_summary=summary)
    assert decision["decision"] in {PROMISING_DEVELOPMENT, INSUFFICIENT_EVIDENCE}
    artifact = density_artifact_stage_c(
        samples,
        seed_base=CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE,
        catalog_version=CYCLE7_STAGE_C_DURABLE_RULE_CATALOG_VERSION,
    )
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["seed_base"] == 870000


def test_stage_c_classifier_requires_higher_density_than_stage_b() -> None:
    summary = {
        "mean_candidate_count": 4.25,
        "mean_format_candidate_count": 2.5,
        "mean_format_clause_candidate_count": 1.0,
        "mean_quantifier_of_candidate_count": 0.25,
        "mean_coord_comma_candidate_count": 0.75,
    }
    decision = classify_stage_c_density(density_summary=summary)
    assert decision["decision"] == INSUFFICIENT_EVIDENCE
    high = {
        "mean_candidate_count": 9.0,
        "mean_format_candidate_count": 6.0,
        "mean_format_clause_candidate_count": 4.0,
        "mean_quantifier_of_candidate_count": 1.5,
        "mean_coord_comma_candidate_count": 0.5,
    }
    promising = classify_stage_c_density(
        density_summary=high,
        collapsed_intact_mean=20.0,
        source_root_mean=50.0,
    )
    assert promising["decision"] == PROMISING_DEVELOPMENT


def test_gpt2_tokenization_changes_for_stage_c_channels() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
    )
    pairs = (
        ("Hello, World", "Hello,\nWorld"),
        ("All of the replicas failed", "All the replicas failed"),
        ("Protocol: The threshold stayed", "Protocol:\nThe threshold stayed"),
    )
    for left, right in pairs:
        assert tokenizer.encode(left, add_special_tokens=False) != tokenizer.encode(
            right, add_special_tokens=False
        )
