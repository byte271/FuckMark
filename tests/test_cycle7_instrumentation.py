from fuckmark.cycle7.compare import (
    CYCLE6_SPACING_ARM_ID,
    CYCLE7_DURABLE_ARM_ID,
    run_fixture_stage_a,
)
from fuckmark.cycle7.decision import PROMISING_DEVELOPMENT, classify_fixture_stage_a
from fuckmark.cycle7.fixtures import CONTRACTION_RICH, CONTRACTION_SPARSE
from fuckmark.cycle7.instrumentation import measure_arm
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from fuckmark.hashing import sha256_text
from fuckmark.transforms import quote_safe_zrd_transform_registry


class _OffsetTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode("utf-8"))

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        data = text.encode("utf-8")
        result = {"input_ids": list(data)}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(data))]
        return result


TOKENIZER_HASH = sha256_text("cycle7-fixture-tokenizer")


def test_instrumentation_records_density_geometry_and_collapse() -> None:
    measurement = measure_arm(
        arm_id="cycle7_durable",
        source_sample_id="rich",
        source_text=CONTRACTION_RICH,
        registry=cycle7_durable_transform_registry(),
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash=TOKENIZER_HASH,
        budget=14,
    )
    assert measurement.candidate_count > 0
    assert measurement.selected_count > 0
    assert measurement.measurement_hash == __import__(
        "fuckmark.hashing", fromlist=["sha256_json"]
    ).sha256_json(measurement.payload())
    assert measurement.collapsed_equals_collapsed_source is False
    assert "insufficient_transform_density" not in measurement.failure_classes
    assert measurement.root_window_count >= 0
    assert measurement.quote_blocked_count >= 0
    assert measurement.protected_blocked_count >= 0


def test_cycle6_spacing_is_undone_by_whitespace_collapse_on_rich_text() -> None:
    probe = "Careful testing matters before any claim becomes knowledge."
    measurement = measure_arm(
        arm_id="cycle6_spacing_b14",
        source_sample_id="spacing-probe",
        source_text=probe,
        registry=quote_safe_zrd_transform_registry(),
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash=TOKENIZER_HASH,
        budget=14,
    )
    if measurement.selected_count and all(
        rule_id.startswith("surface-space-") for rule_id in measurement.selected_rule_ids
    ):
        assert measurement.collapsed_equals_collapsed_source is True
        assert collapse_horizontal_ascii_whitespace(measurement.transformed_text) == (
            collapse_horizontal_ascii_whitespace(probe)
        )


def test_fixture_stage_a_compares_three_arms_and_classifies() -> None:
    report = run_fixture_stage_a(_OffsetTokenizer(), TOKENIZER_HASH)
    assert report["artifact_hash"]
    rich = next(row for row in report["rows"] if row["source_sample_id"] == "contraction-rich")
    sparse = next(row for row in report["rows"] if row["source_sample_id"] == "contraction-sparse")
    assert rich["arms"][CYCLE7_DURABLE_ARM_ID]["selected_count"] > 0
    assert rich["arms"][CYCLE7_DURABLE_ARM_ID]["collapsed_equals_collapsed_source"] is False
    assert CYCLE6_SPACING_ARM_ID in rich["arms"]
    assert sparse["source_sample_id"] == "contraction-sparse"
    decision = classify_fixture_stage_a(report)
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert CONTRACTION_SPARSE
