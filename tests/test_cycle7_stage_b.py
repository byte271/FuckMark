from fuckmark.cycle7.density import durable_density_table
from fuckmark.cycle7.durable_rules import (
    CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    CYCLE7_STAGE_B_DURABLE_RULE_CATALOG_VERSION,
)
from fuckmark.cycle7.fixtures import stage_b_fixture_samples
from fuckmark.cycle7.ledger import (
    CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES,
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_EXPLORATORY_SEED_BASE,
    CYCLE7_LEDGER_VERSION,
    CYCLE7_RULE_CONSTRUCTION_ROLE,
    CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_B1_TOPIC,
    CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE,
    CYCLE7_USED_EXPLORATORY_SEED_BASES,
    CYCLE7_VALIDATION_SEED_BASE,
    CYCLE7_VALIDATION_TOPIC,
    assert_development_seed,
    assert_rule_construction_seed,
    cycle7_seed_ledger_payload,
)
from fuckmark.cycle7.registry import CYCLE7_COMBINED_REGISTRY_ID, CYCLE7_DURABLE_REGISTRY_ID
from fuckmark.cycle7.stage_b import (
    INSUFFICIENT_EVIDENCE,
    PROMISING_DEVELOPMENT,
    classify_stage_b_density,
    density_artifact,
    summarize_density_rows,
)
import pytest


def test_stage_b_catalog_and_ledger_identities() -> None:
    assert CYCLE7_STAGE_B_DURABLE_RULE_CATALOG_VERSION == "cycle7-durable-rule-catalog-v3"
    assert CYCLE7_DURABLE_RULE_CATALOG_VERSION == "cycle7-durable-rule-catalog-v4"
    assert CYCLE7_DURABLE_REGISTRY_ID == "cycle7-durable-catalog-v4"
    assert CYCLE7_COMBINED_REGISTRY_ID == "cycle7-durable-plus-cycle6-spacing-v3"
    assert CYCLE7_LEDGER_VERSION == "cycle7-seed-ledger-v4"
    assert CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE == 860000
    assert CYCLE7_STAGE_B1_TOPIC == "independent replication"
    assert CYCLE7_VALIDATION_TOPIC == "held-out evaluation"
    assert CYCLE7_USED_EXPLORATORY_SEED_BASES == (810000, 860000)
    assert CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES == (870000,)
    payload = cycle7_seed_ledger_payload()
    assert payload["stage_b1_exploratory_seed_base"] == 860000
    assert payload["stage_b1_topic"] == "independent replication"
    assert payload["stage_c1_exploratory_seed_base"] == 870000
    assert payload["stage_c1_topic"] == "measurement protocol"
    assert payload["validation_topic"] == "held-out evaluation"
    assert payload["used_validation_development_seed_bases"] == [820000, 880000]
    assert payload["active_validation_development_seed_bases"] == []
    assert payload["publicly_exposed_seed_bases"] == [880000]


def test_rule_construction_admits_870000_and_blocks_spent_or_reserved_seeds() -> None:
    assert_rule_construction_seed(CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE)
    assert_development_seed(CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    assert_development_seed(CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    assert_development_seed(CYCLE7_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="rule-construction"):
        assert_rule_construction_seed(CYCLE7_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="rule-construction"):
        assert_rule_construction_seed(CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="rule-construction"):
        assert_development_seed(CYCLE7_EXPLORATORY_SEED_BASE, role=CYCLE7_RULE_CONSTRUCTION_ROLE)
    with pytest.raises(ValueError, match="confirmation-reserved"):
        assert_rule_construction_seed(830000)
    with pytest.raises(ValueError, match="confirmation-reserved"):
        assert_rule_construction_seed(840000)
    with pytest.raises(ValueError, match="confirmation-reserved"):
        assert_rule_construction_seed(850000)
    with pytest.raises(ValueError, match="exploratory"):
        assert_development_seed(CYCLE7_VALIDATION_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="publicly exposed"):
        assert_development_seed(880000, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="spent"):
        assert_rule_construction_seed(760000)


def test_stage_b_density_classifier_on_construction_fixtures() -> None:
    samples = tuple(
        {"sample_id": sample_id, "text": text} for sample_id, text in stage_b_fixture_samples()
    )
    rows = durable_density_table(samples)
    summary = summarize_density_rows(rows)
    assert summary["mean_candidate_count"] >= 4
    decision = classify_stage_b_density(density_summary=summary)
    assert decision["decision"] in {PROMISING_DEVELOPMENT, INSUFFICIENT_EVIDENCE}
    artifact = density_artifact(
        samples,
        seed_base=CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )
    assert artifact["detector_access_used_for_selection"] is False
    assert artifact["seed_base"] == 860000
    assert artifact["artifact_hash"]


def test_stage_b_classifier_uses_root_windows_not_post_edit_intact() -> None:
    summary = {
        "mean_candidate_count": 4.25,
        "mean_format_candidate_count": 2.5,
        "mean_coord_comma_candidate_count": 0.75,
    }
    equal_to_post_edit = classify_stage_b_density(
        density_summary=summary,
        collapsed_intact_mean=35.625,
        source_root_mean=35.625,
    )
    assert equal_to_post_edit["decision"] == INSUFFICIENT_EVIDENCE
    versus_root = classify_stage_b_density(
        density_summary=summary,
        collapsed_intact_mean=35.625,
        source_root_mean=49.75,
    )
    assert versus_root["decision"] == PROMISING_DEVELOPMENT
    assert versus_root["collapsed_intact_fraction_of_root"] == 35.625 / 49.75


def test_stage_b_classifier_keeps_low_density_as_insufficient() -> None:
    summary = {
        "mean_candidate_count": 1.5,
        "mean_format_candidate_count": 0.5,
        "mean_coord_comma_candidate_count": 0.0,
    }
    decision = classify_stage_b_density(density_summary=summary)
    assert decision["decision"] == INSUFFICIENT_EVIDENCE
