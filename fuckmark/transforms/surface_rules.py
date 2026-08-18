from __future__ import annotations

from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v1"


def development_surface_rules() -> tuple[LiteralTransformRule, ...]:
    pairs = (
        ("surface-space-after-is", " is ", " is  "),
        ("surface-space-after-the", " the ", " the  "),
        ("surface-space-after-of", " of ", " of  "),
        ("surface-space-after-to", " to ", " to  "),
        ("surface-space-after-but", " but ", " but  "),
    )
    return tuple(
        LiteralTransformRule.create(
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
        for rule_id, source, replacement in pairs
    )
