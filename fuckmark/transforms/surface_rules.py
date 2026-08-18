from __future__ import annotations

from .rules import SurfaceSpacingRule


SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v2"


def development_surface_rules() -> tuple[SurfaceSpacingRule, ...]:
    return (
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-is",
            version="v1",
            source="is",
            replacement="is ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-of",
            version="v1",
            source="of",
            replacement="of ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-to",
            version="v1",
            source="to",
            replacement="to ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-period",
            version="v1",
            source=". ",
            replacement=".  ",
        ),
    )
