from __future__ import annotations

from .rules import SurfaceSpacingRule


SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v3"


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
            rule_id="surface-space-after-the",
            version="v1",
            source="the",
            replacement="the ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-and",
            version="v1",
            source="and",
            replacement="and ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-in",
            version="v1",
            source="in",
            replacement="in ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-for",
            version="v1",
            source="for",
            replacement="for ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-on",
            version="v1",
            source="on",
            replacement="on ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-with",
            version="v1",
            source="with",
            replacement="with ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-as",
            version="v1",
            source="as",
            replacement="as ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-from",
            version="v1",
            source="from",
            replacement="from ",
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-period",
            version="v1",
            source=". ",
            replacement=".  ",
        ),
    )
