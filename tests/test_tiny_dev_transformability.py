from dataclasses import replace

import pytest

from fuckmark.experiments.tiny_dev_transformability import (
    TINY_DEV_TRANSFORMABILITY_MIN_CANDIDATES,
    TinyDevTransformabilityStatus,
    build_tiny_dev_transformability_audit,
)
from fuckmark.transforms import (
    LiteralTransformRule,
    TransformFamily,
    TransformRegistry,
    TransformTier,
    default_transform_registry,
)
from tiny_dev_experiment_helpers import tiny_dev_artifact


def _dense_fixture_registry() -> TransformRegistry:
    return TransformRegistry(
        tuple(
            LiteralTransformRule.create(
                rule_id=f"fixture-rule-{index}",
                version="v1",
                family=TransformFamily.ORTHOGRAPHY,
                tier=TransformTier.SURFACE,
                source=source,
                replacement=replacement,
                whole_word=True,
                preserve_simple_case=False,
                block_all_caps=False,
            )
            for index, (source, replacement) in enumerate(
                (
                    ("Experiment", "Study"),
                    ("fixture", "example"),
                    ("output", "result"),
                    ("seed", "trial"),
                )
            )
        )
    )


def test_transformability_audit_fails_closed_when_attack_sources_lack_candidates() -> None:
    audit = build_tiny_dev_transformability_audit(
        tiny_dev_artifact(),
        default_transform_registry(),
    )
    assert audit.status is TinyDevTransformabilityStatus.INSUFFICIENT_CANDIDATES
    assert audit.expected_source_count == 4
    assert audit.transformable_source_count == 0
    assert len(audit.blocked_source_ids) == 4
    assert all(row.candidate_count < TINY_DEV_TRANSFORMABILITY_MIN_CANDIDATES for row in audit.rows)


def test_transformability_audit_requires_four_candidates_on_each_source() -> None:
    registry = _dense_fixture_registry()
    audit = build_tiny_dev_transformability_audit(tiny_dev_artifact(), registry)
    assert audit.status is TinyDevTransformabilityStatus.READY
    assert audit.transformable_source_count == 4
    assert audit.blocked_source_ids == ()
    assert {row.candidate_count for row in audit.rows} == {4}
    assert all(row.rejection_count == 0 for row in audit.rows)
    assert all(len(row.candidate_ids) == 4 for row in audit.rows)
    assert all(len(row.rule_ids) == 4 for row in audit.rows)


def test_transformability_audit_is_tamper_evident() -> None:
    audit = build_tiny_dev_transformability_audit(tiny_dev_artifact(), _dense_fixture_registry())
    with pytest.raises(ValueError, match="audit_hash"):
        replace(audit, audit_hash="0" * 64)
    with pytest.raises(ValueError, match="row_hash"):
        replace(audit.rows[0], row_hash="0" * 64)
