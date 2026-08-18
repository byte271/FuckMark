from __future__ import annotations

from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v1"


def development_surface_rules() -> tuple[LiteralTransformRule, ...]:
    return (
        LiteralTransformRule.create(
            rule_id="surface-period-space-double",
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.SURFACE,
            source=". ",
            replacement=".  ",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        ),
    )
