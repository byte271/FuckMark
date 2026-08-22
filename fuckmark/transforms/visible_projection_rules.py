from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


VISIBLE_PROJECTION_RULESET_VERSION = "visible-projection-rules-v2-u200c-only"
VISIBLE_PROJECTION_EXPERIMENTAL_RULE_ID = "visible-projection-zero-width-non-joiner"


def visible_projection_experimental_rules() -> tuple[LiteralTransformRule, ...]:
    return (
        LiteralTransformRule.create(
            rule_id=VISIBLE_PROJECTION_EXPERIMENTAL_RULE_ID,
            version="v2",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.EXPERIMENTAL,
            source=" ",
            replacement=" \u200c",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        ),
    )
