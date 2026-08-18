from __future__ import annotations

import re
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .schema import TransformFamily, TransformTier


SURFACE_RULE_ALGORITHM_VERSION = "surface-spacing-rule-v1"
SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v2"


@dataclass(frozen=True, slots=True)
class SurfaceSpacingRule:
    rule_id: str
    version: str
    family: TransformFamily
    tier: TransformTier
    source: str
    replacement: str
    requires_following_whitespace: bool
    whole_word: bool
    preserve_simple_case: bool
    block_all_caps: bool
    rule_hash: str

    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.ORTHOGRAPHY:
            raise ValueError("surface spacing rules must use the orthography family")
        if self.tier is not TransformTier.SURFACE:
            raise ValueError("surface spacing rules must use tier 1 surface")
        if not isinstance(self.source, str) or not self.source or "\n" in self.source or "\r" in self.source:
            raise ValueError("surface source must be non-empty and single-line")
        if not isinstance(self.replacement, str) or not self.replacement or "\n" in self.replacement or "\r" in self.replacement:
            raise ValueError("surface replacement must be non-empty and single-line")
        if self.source == self.replacement:
            raise ValueError("surface source and replacement must differ")
        require_bool("requires_following_whitespace", self.requires_following_whitespace)
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("surface spacing rules use their own exact case-sensitive boundary contract")
        if self.requires_following_whitespace:
            if not self.source.isalpha() or self.source != self.source.lower():
                raise ValueError("whitespace-anchored surface sources must be lowercase alphabetic words")
            if self.replacement != self.source + " ":
                raise ValueError("whitespace-anchored surface replacement must add exactly one trailing space")
        elif self.replacement != self.source + " ":
            raise ValueError("literal surface replacement must add exactly one trailing space")
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match surface spacing rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SURFACE_RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "requires_following_whitespace": self.requires_following_whitespace,
            "whole_word": self.whole_word,
            "preserve_simple_case": self.preserve_simple_case,
            "block_all_caps": self.block_all_caps,
        }

    @classmethod
    def create(
        cls,
        rule_id: str,
        version: str,
        source: str,
        replacement: str,
        *,
        requires_following_whitespace: bool,
    ) -> SurfaceSpacingRule:
        payload = {
            "algorithm_version": SURFACE_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": TransformFamily.ORTHOGRAPHY.value,
            "tier": TransformTier.SURFACE.value,
            "source": source,
            "replacement": replacement,
            "requires_following_whitespace": requires_following_whitespace,
            "whole_word": False,
            "preserve_simple_case": False,
            "block_all_caps": False,
        }
        return cls(
            rule_id=rule_id,
            version=version,
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.SURFACE,
            source=source,
            replacement=replacement,
            requires_following_whitespace=requires_following_whitespace,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(payload),
        )

    def pattern(self) -> re.Pattern[str]:
        literal = re.escape(self.source)
        if self.requires_following_whitespace:
            return re.compile(rf"(?<!\w){literal}(?=\s)")
        return re.compile(literal)


def development_surface_rules() -> tuple[SurfaceSpacingRule, ...]:
    return (
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-is",
            version="v1",
            source="is",
            replacement="is ",
            requires_following_whitespace=True,
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-of",
            version="v1",
            source="of",
            replacement="of ",
            requires_following_whitespace=True,
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-to",
            version="v1",
            source="to",
            replacement="to ",
            requires_following_whitespace=True,
        ),
        SurfaceSpacingRule.create(
            rule_id="surface-space-after-period",
            version="v1",
            source=". ",
            replacement=".  ",
            requires_following_whitespace=False,
        ),
    )
