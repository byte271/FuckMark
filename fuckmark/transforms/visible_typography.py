from __future__ import annotations

import re
import unicodedata

from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


VISIBLE_TYPOGRAPHY_RULESET_VERSION = "development-visible-typography-rules-v1"
ASCII_APOSTROPHE = "'"
RIGHT_SINGLE_QUOTATION_MARK = "\N{RIGHT SINGLE QUOTATION MARK}"
HYPHEN_MINUS = "-"
HYPHEN = "\N{HYPHEN}"


class VisibleTypographyRule(LiteralTransformRule):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.family is not TransformFamily.ORTHOGRAPHY:
            raise ValueError("visible typography rules must use the orthography family")
        if self.tier is not TransformTier.SURFACE:
            raise ValueError("visible typography rules must use tier 1 surface")
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("visible typography rules use exact case-sensitive boundaries")
        if (self.source, self.replacement) not in (
            (ASCII_APOSTROPHE, RIGHT_SINGLE_QUOTATION_MARK),
            (HYPHEN_MINUS, HYPHEN),
        ):
            raise ValueError("unsupported visible typography mapping")
        if unicodedata.normalize("NFC", self.replacement) != self.replacement:
            raise ValueError("visible typography replacement must be Unicode NFC")
        if unicodedata.category(self.replacement) not in ("Pd", "Pf"):
            raise ValueError("visible typography replacement must remain visible punctuation")

    def pattern(self) -> re.Pattern[str]:
        if self.source == ASCII_APOSTROPHE:
            return re.compile(r"(?<=[A-Za-z])'(?=[A-Za-z])")
        return re.compile(r"(?<=[A-Za-z])-(?=[A-Za-z])")


def _rule(rule_id: str, source: str, replacement: str) -> VisibleTypographyRule:
    return VisibleTypographyRule.create(
        rule_id=rule_id,
        version=VISIBLE_TYPOGRAPHY_RULESET_VERSION,
        family=TransformFamily.ORTHOGRAPHY,
        tier=TransformTier.SURFACE,
        source=source,
        replacement=replacement,
        whole_word=False,
        preserve_simple_case=False,
        block_all_caps=False,
    )


def development_visible_typography_rules() -> tuple[VisibleTypographyRule, ...]:
    return (
        _rule("visible-typography-internal-apostrophe", ASCII_APOSTROPHE, RIGHT_SINGLE_QUOTATION_MARK),
        _rule("visible-typography-internal-hyphen", HYPHEN_MINUS, HYPHEN),
    )
