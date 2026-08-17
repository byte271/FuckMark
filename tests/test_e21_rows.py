import pytest

from test_e20_bundle import _bundle_fixture, _synthetic_outcome
from fuckmark.experiments.e21_rows import (
    E21FailureRow,
    E21IdentityFields,
    E21OutcomeRow,
)
from fuckmark.hashing import sha256_text


def test_e21_outcome_has_independent_identity_and_preserves_confirmatory_invariants() -> None:
    _, _, _, condition_plan, failures = _bundle_fixture()
    condition = condition_plan.conditions[0]
    source = _synthetic_outcome(
        failures[0],
        condition,
        transformed_hash=sha256_text("e21-transformed-text"),
    )
    execution_id = sha256_text("e21-independent-execution")
    identity = E21IdentityFields(
        execution_id,
        execution_id,
        "E21",
        source.identity.condition_id,
        "e21-sample-0",
        "e21-pair-0",
    )
    row = E21OutcomeRow.create(
        identity,
        source.source,
        source.model,
        source.watermark,
        source.generation,
        source.text,
        source.transform,
        source.fidelity,
        source.alignment,
        source.observation,
        source.gvalues,
        source.detector,
        source.statistics,
        source.audit,
    )
    assert row.identity.experiment_id == "E21"
    assert row.row_hash != source.row_hash
    assert row.standardized_margin_drop == source.standardized_margin_drop


def test_e21_identity_rejects_e20_experiment_id() -> None:
    execution_id = sha256_text("e21-independent-execution")
    with pytest.raises(ValueError, match="experiment_id E21"):
        E21IdentityFields(
            execution_id,
            execution_id,
            "E20",
            "condition",
            "sample",
            "pair",
        )


def test_e21_failure_row_reuses_failure_semantics_without_e20_identity() -> None:
    _, _, _, _, failures = _bundle_fixture()
    source = failures[0]
    execution_id = sha256_text("e21-failure-execution")
    identity = E21IdentityFields(
        execution_id,
        execution_id,
        "E21",
        source.identity.condition_id,
        "e21-failure-sample",
        "e21-failure-pair",
    )
    row = E21FailureRow.create(
        identity,
        source.stage,
        source.reason_code,
        source.source_sample_record_hash,
        source.detail_hash,
        source.audit,
    )
    assert row.identity.experiment_id == "E21"
    assert row.reason_code is source.reason_code
