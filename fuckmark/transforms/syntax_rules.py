from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .schema import TransformFamily, TransformTier


SYNTAX_TEMPLATE_RULE_ALGORITHM_VERSION = "syntax-template-rule-v1"


class SyntaxConstruction(str, Enum):
    SEMICOLON_CONJUNCTIVE_ADVERB_SPLIT = "semicolon_conjunctive_adverb_split"


@dataclass(frozen=True, slots=True)
class SyntaxTemplateRule:
    rule_id: str
    version: str
    family: TransformFamily
    tier: TransformTier
    source: str
    replacement: str
    construction: SyntaxConstruction
    minimum_clause_word_count: int
    whole_word: bool
    preserve_simple_case: bool
    block_all_caps: bool
    rule_hash: str

    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.SYNTAX_TEMPLATE:
            raise ValueError("syntax template rules must use the syntax template family")
        if self.tier is not TransformTier.SYNTAX:
            raise ValueError("syntax template rules must use tier 3 syntax")
        if not isinstance(self.source, str) or not self.source or "\n" in self.source or "\r" in self.source:
            raise ValueError("source must be non-empty and single-line")
        if not isinstance(self.replacement, str) or not self.replacement or "\n" in self.replacement or "\r" in self.replacement:
            raise ValueError("replacement must be non-empty and single-line")
        if self.source.casefold() == self.replacement.casefold():
            raise ValueError("source and replacement must differ")
        if not isinstance(self.construction, SyntaxConstruction):
            raise TypeError("construction must be a SyntaxConstruction")
        require_int("minimum_clause_word_count", self.minimum_clause_word_count)
        if self.minimum_clause_word_count < 2:
            raise ValueError("minimum_clause_word_count must be at least two")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match syntax template rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SYNTAX_TEMPLATE_RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "construction": self.construction.value,
            "minimum_clause_word_count": self.minimum_clause_word_count,
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
        construction: SyntaxConstruction,
        minimum_clause_word_count: int = 2,
        whole_word: bool = False,
        preserve_simple_case: bool = False,
        block_all_caps: bool = True,
    ) -> SyntaxTemplateRule:
        payload = {
            "algorithm_version": SYNTAX_TEMPLATE_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": TransformFamily.SYNTAX_TEMPLATE.value,
            "tier": TransformTier.SYNTAX.value,
            "source": source,
            "replacement": replacement,
            "construction": construction.value if isinstance(construction, SyntaxConstruction) else construction,
            "minimum_clause_word_count": minimum_clause_word_count,
            "whole_word": whole_word,
            "preserve_simple_case": preserve_simple_case,
            "block_all_caps": block_all_caps,
        }
        return cls(
            rule_id=rule_id,
            version=version,
            family=TransformFamily.SYNTAX_TEMPLATE,
            tier=TransformTier.SYNTAX,
            source=source,
            replacement=replacement,
            construction=construction,
            minimum_clause_word_count=minimum_clause_word_count,
            whole_word=whole_word,
            preserve_simple_case=preserve_simple_case,
            block_all_caps=block_all_caps,
            rule_hash=sha256_json(payload),
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

    def precondition(self, text: str, start: int, end: int) -> bool:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if start < 0 or end <= start or end > len(text):
            raise ValueError("syntax precondition span is outside text")
        if text[start:end].casefold() != self.source.casefold():
            raise ValueError("syntax precondition span does not match rule source")
        if self.construction is not SyntaxConstruction.SEMICOLON_CONJUNCTIVE_ADVERB_SPLIT:
            return False
        prefix = text[:start]
        line = prefix[prefix.rfind("\n") + 1 :].lstrip()
        if re.match(r"(?:[-*+]\s|\d+[.)]\s)", line):
            return False
        boundary = max(prefix.rfind("."), prefix.rfind("?"), prefix.rfind("!"), prefix.rfind("\n"))
        left_clause = prefix[boundary + 1 :].strip()
        right = text[end:]
        next_boundaries = tuple(index for mark in ".?!\n" if (index := right.find(mark)) >= 0)
        right_clause = right[: min(next_boundaries)] if next_boundaries else right
        words = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
        if len(words.findall(left_clause)) < self.minimum_clause_word_count:
            return False
        if len(words.findall(right_clause)) < self.minimum_clause_word_count:
            return False
        return True


def development_syntax_rules() -> tuple[SyntaxTemplateRule, ...]:
    return (
        SyntaxTemplateRule.create(
            rule_id="syntax-semicolon-however-split",
            version="v1",
            source="; however, ",
            replacement=". However, ",
            construction=SyntaxConstruction.SEMICOLON_CONJUNCTIVE_ADVERB_SPLIT,
        ),
    )
