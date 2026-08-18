from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .lexical_rules import LexicalTemplateRule
from .schema import TransformFamily, TransformTier
from .surface_rules import SurfaceSpacingRule
from .syntax_rules import SyntaxTemplateRule


RULE_ALGORITHM_VERSION = "literal-transform-rule-v2"
_MAX_RULES = 100_000


@dataclass(frozen=True, slots=True)
class LiteralTransformRule:
    rule_id: str
    version: str
    family: TransformFamily
    tier: TransformTier
    source: str
    replacement: str
    whole_word: bool
    preserve_simple_case: bool
    block_all_caps: bool
    rule_hash: str

    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if not isinstance(self.family, TransformFamily):
            raise TypeError("family must be a TransformFamily")
        if not isinstance(self.tier, TransformTier):
            raise TypeError("tier must be a TransformTier")
        if not isinstance(self.source, str) or not self.source or "\n" in self.source or "\r" in self.source:
            raise ValueError("source must be non-empty and single-line")
        if not isinstance(self.replacement, str) or not self.replacement or "\n" in self.replacement or "\r" in self.replacement:
            raise ValueError("replacement must be non-empty and single-line")
        if self.source.casefold() == self.replacement.casefold():
            raise ValueError("source and replacement must differ")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match transform rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "whole_word": self.whole_word,
            "preserve_simple_case": self.preserve_simple_case,
            "block_all_caps": self.block_all_caps,
        }

    @classmethod
    def create(
        cls,
        rule_id: str,
        version: str,
        family: TransformFamily,
        tier: TransformTier,
        source: str,
        replacement: str,
        whole_word: bool = True,
        preserve_simple_case: bool = True,
        block_all_caps: bool = True,
    ) -> LiteralTransformRule:
        payload = {
            "algorithm_version": RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": family.value if isinstance(family, TransformFamily) else family,
            "tier": tier.value if isinstance(tier, TransformTier) else tier,
            "source": source,
            "replacement": replacement,
            "whole_word": whole_word,
            "preserve_simple_case": preserve_simple_case,
            "block_all_caps": block_all_caps,
        }
        return cls(
            rule_id,
            version,
            family,
            tier,
            source,
            replacement,
            whole_word,
            preserve_simple_case,
            block_all_caps,
            sha256_json(payload),
        )

    def pattern(self) -> re.Pattern[str]:
        literal = rf"(?ai:{re.escape(self.source)})"
        pattern = literal
        if self.whole_word:
            if self.source[0].isalnum() or self.source[0] == "_":
                pattern = rf"(?<!\w){pattern}"
            if self.source[-1].isalnum() or self.source[-1] == "_":
                pattern = rf"{pattern}(?!\w)"
        return re.compile(pattern)


def default_contraction_rules() -> tuple[LiteralTransformRule, ...]:
    pairs = (
        ("contract-do-not", "do not", "don't"),
        ("contract-does-not", "does not", "doesn't"),
        ("contract-did-not", "did not", "didn't"),
        ("contract-cannot", "cannot", "can't"),
        ("contract-will-not", "will not", "won't"),
        ("contract-should-not", "should not", "shouldn't"),
    )
    return tuple(
        LiteralTransformRule.create(
            rule_id=rule_id,
            version="v2",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source=source,
            replacement=replacement,
        )
        for rule_id, source, replacement in pairs
    )


TransformRule = SurfaceSpacingRule | LiteralTransformRule | LexicalTemplateRule | SyntaxTemplateRule


def validate_rules(rules: Sequence[TransformRule]) -> tuple[TransformRule, ...]:
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes, bytearray)):
        raise TypeError("rules must be a sequence")
    if len(rules) > _MAX_RULES:
        raise ValueError("rules exceeded resource limit")
    normalized = tuple(rules)
    if not normalized:
        raise ValueError("rules must not be empty")
    if any(
        not isinstance(rule, (SurfaceSpacingRule, LiteralTransformRule, LexicalTemplateRule, SyntaxTemplateRule))
        for rule in normalized
    ):
        raise TypeError("rules must contain supported transform rule values")
    identities = tuple((rule.rule_id, rule.version) for rule in normalized)
    if len(set(identities)) != len(identities):
        raise ValueError("rule identities must be unique")
    if len({rule.rule_hash for rule in normalized}) != len(normalized):
        raise ValueError("rule hashes must be unique")
    return tuple(sorted(normalized, key=lambda rule: (rule.rule_id, rule.version, rule.rule_hash)))
