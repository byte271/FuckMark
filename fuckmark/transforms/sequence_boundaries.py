from __future__ import annotations

import re

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


SENTENCE_BOUNDARY_SOFTBREAK_RULE_ALGORITHM_VERSION = "sentence-boundary-softbreak-rule-v1"
SENTENCE_BOUNDARY_SOFTBREAK_RULESET_VERSION = "development-sentence-boundary-softbreak-v1"
ASCII_SPACE = " "
LINE_FEED = "\n"

_TERMINALS = (".", "?", "!")
_OPENING_PUNCTUATION = r'''["'“‘(\[]'''
_SENTENCE_START = rf"(?=(?:{_OPENING_PUNCTUATION}){{0,3}}[A-Z])"
_PERIOD_ABBREVIATIONS = (
    "apr",
    "aug",
    "corp",
    "dec",
    "dept",
    "est",
    "etc",
    "feb",
    "fig",
    "inc",
    "jan",
    "jul",
    "jun",
    "ltd",
    "mar",
    "mrs",
    "nov",
    "oct",
    "prof",
    "sec",
    "sep",
    "sept",
)


class SentenceBoundarySoftbreakRule(LiteralTransformRule):
    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.ORTHOGRAPHY:
            raise ValueError("sentence boundary rules must use the orthography family")
        if self.tier is not TransformTier.FORMAT:
            raise ValueError("sentence boundary rules must use tier 0 format")
        if self.source not in tuple(terminal + ASCII_SPACE for terminal in _TERMINALS):
            raise ValueError("unsupported sentence boundary source")
        if self.replacement != self.source[0] + LINE_FEED:
            raise ValueError("sentence boundary replacement must exchange one ASCII space for one line feed")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("sentence boundary rules use exact case-sensitive boundaries")
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match sentence boundary rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SENTENCE_BOUNDARY_SOFTBREAK_RULE_ALGORITHM_VERSION,
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
    def create(cls, *, rule_id: str, terminal: str) -> SentenceBoundarySoftbreakRule:
        if terminal not in _TERMINALS:
            raise ValueError("unsupported sentence boundary terminal")
        payload = {
            "algorithm_version": SENTENCE_BOUNDARY_SOFTBREAK_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": SENTENCE_BOUNDARY_SOFTBREAK_RULESET_VERSION,
            "family": TransformFamily.ORTHOGRAPHY.value,
            "tier": TransformTier.FORMAT.value,
            "source": terminal + ASCII_SPACE,
            "replacement": terminal + LINE_FEED,
            "whole_word": False,
            "preserve_simple_case": False,
            "block_all_caps": False,
        }
        return cls(
            rule_id=rule_id,
            version=SENTENCE_BOUNDARY_SOFTBREAK_RULESET_VERSION,
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.FORMAT,
            source=terminal + ASCII_SPACE,
            replacement=terminal + LINE_FEED,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(payload),
        )

    def pattern(self) -> re.Pattern[str]:
        terminal = self.source[0]
        if terminal != ".":
            return re.compile(re.escape(self.source) + _SENTENCE_START)
        exclusions = (
            r"(?<![.\d])(?<!\b[A-Za-z])(?<!\b[A-Za-z]{2})"
            r"(?<![^A-Za-z][A-Za-z])(?<![^A-Za-z][A-Za-z]{2})"
        )
        exclusions += "".join(
            rf"(?<!(?i:\b{re.escape(abbreviation)}))"
            for abbreviation in _PERIOD_ABBREVIATIONS
        )
        return re.compile(exclusions + re.escape(self.source) + _SENTENCE_START)


def development_sentence_boundary_softbreak_rules() -> tuple[SentenceBoundarySoftbreakRule, ...]:
    return tuple(
        SentenceBoundarySoftbreakRule.create(
            rule_id=f"sentence-boundary-softbreak-{name}",
            terminal=terminal,
        )
        for name, terminal in (("period", "."), ("question", "?"), ("exclamation", "!"))
    )
