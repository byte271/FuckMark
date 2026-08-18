from __future__ import annotations

import re
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .schema import TransformFamily, TransformTier


FORMAT_RULE_ALGORITHM_VERSION = "format-transform-rule-v1"


@dataclass(frozen=True, slots=True)
class FormatTransformRule:
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
        if self.family is not TransformFamily.FORMAT:
            raise ValueError("format transform rules must use the format family")
        if self.tier is not TransformTier.FORMAT:
            raise ValueError("format transform rules must use tier 0 format")
        if not isinstance(self.source, str) or not self.source or "\r" in self.source:
            raise ValueError("format source must be non-empty and must not contain carriage returns")
        if not isinstance(self.replacement, str) or not self.replacement or "\r" in self.replacement:
            raise ValueError("format replacement must be non-empty and must not contain carriage returns")
        if self.source == self.replacement:
            raise ValueError("format source and replacement must differ")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("format rules must disable word/case/all-caps semantics")
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match format transform rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": FORMAT_RULE_ALGORITHM_VERSION,
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
        source: str,
        replacement: str,
    ) -> FormatTransformRule:
        payload = {
            "algorithm_version": FORMAT_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": TransformFamily.FORMAT.value,
            "tier": TransformTier.FORMAT.value,
            "source": source,
            "replacement": replacement,
            "whole_word": False,
            "preserve_simple_case": False,
            "block_all_caps": False,
        }
        return cls(
            rule_id=rule_id,
            version=version,
            family=TransformFamily.FORMAT,
            tier=TransformTier.FORMAT,
            source=source,
            replacement=replacement,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(payload),
        )

    def pattern(self) -> re.Pattern[str]:
        return re.compile(re.escape(self.source))


def development_format_rules() -> tuple[FormatTransformRule, ...]:
    return (
        FormatTransformRule.create(
            rule_id="format-collapse-blank-line",
            version="v1",
            source="\n\n",
            replacement="\n",
        ),
    )
