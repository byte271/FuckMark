from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


FORMAT_BOUNDARY_RULE_ALGORITHM_VERSION = "format-boundary-rule-v1"

_SENTENCE_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "mz",
        "dr",
        "prof",
        "sr",
        "jr",
        "vs",
        "etc",
        "fig",
        "eq",
        "vol",
        "no",
        "nos",
        "inc",
        "ltd",
        "st",
        "ave",
        "blvd",
        "dept",
        "est",
        "al",
        "eg",
        "ie",
        "us",
        "usa",
        "uk",
        "pm",
        "am",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "ch",
        "sec",
        "pp",
        "ed",
        "eds",
        "rev",
        "ca",
        "cf",
        "nb",
        "viz",
    }
)


class FormatConstruction(str, Enum):
    SENTENCE_BOUNDARY_NEWLINE = "sentence_boundary_newline"
    CLAUSE_PUNCTUATION_NEWLINE = "clause_punctuation_newline"


def _word_before_punct(text: str, punct_index: int) -> str:
    index = punct_index
    while index > 0 and text[index - 1] in ".?!":
        index -= 1
    end = index
    while index > 0 and text[index - 1].isalpha():
        index -= 1
    return text[index:end]


def sentence_boundary_span_admissible(text: str, start: int, end: int) -> bool:
    if start < 0 or end <= start or end > len(text):
        return False
    if end < len(text) and text[end] == "\n":
        return False
    if end >= len(text) or not text[end].isupper() or not text[end].isalpha():
        return False
    if start > 0 and text[start - 1].isdigit():
        return False
    if start > 0 and text[start - 1] in ".?!":
        return False
    word = _word_before_punct(text, start)
    if not word:
        return False
    if len(word) == 1 and word.isalpha():
        return False
    if word.casefold() in _SENTENCE_ABBREVIATIONS:
        return False
    return True


def _follower_alpha_word(text: str, index: int) -> str:
    cursor = index
    while cursor < len(text) and text[cursor].isalpha():
        cursor += 1
    return text[index:cursor]


def clause_punctuation_span_admissible(text: str, start: int, end: int) -> bool:
    if start < 0 or end <= start or end > len(text):
        return False
    if end < len(text) and text[end] == "\n":
        return False
    if end >= len(text) or not text[end].isalpha():
        return False
    if start == 0:
        return False
    previous = text[start - 1]
    if previous.isdigit() or previous in ",.;:?!":
        return False
    if not (previous.isalpha() or previous in "\"')]" ):
        return False
    follower = _follower_alpha_word(text, end)
    if len(follower) < 2:
        return False
    return True


@dataclass(frozen=True, slots=True)
class FormatBoundaryRule(LiteralTransformRule):
    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.ORTHOGRAPHY:
            raise ValueError("format boundary rules must use the orthography family")
        if self.tier is not TransformTier.SURFACE:
            raise ValueError("format boundary rules must use tier 1 surface")
        if not isinstance(self.source, str) or not self.source or "\r" in self.source:
            raise ValueError("source must be a non-empty string without carriage returns")
        if not isinstance(self.replacement, str) or not self.replacement or "\r" in self.replacement:
            raise ValueError("replacement must be a non-empty string without carriage returns")
        mark = self.source[:1]
        if mark not in ".?!,;:":
            raise ValueError("format boundary source must start with sentence or clause punctuation")
        forward = self.source == f"{mark} " and self.replacement == f"{mark}\n"
        inverse = self.source == f"{mark}\n" and self.replacement == f"{mark} "
        if not forward and not inverse:
            raise ValueError("format boundary rules must swap a single space with a single newline after punctuation")
        if self.source.casefold() == self.replacement.casefold():
            raise ValueError("source and replacement must differ")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("format boundary rules use an exact punctuation contract")
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match format boundary rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": FORMAT_BOUNDARY_RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "construction": (
                FormatConstruction.SENTENCE_BOUNDARY_NEWLINE.value
                if self.source[:1] in ".?!"
                else FormatConstruction.CLAUSE_PUNCTUATION_NEWLINE.value
            ),
            "whole_word": self.whole_word,
            "preserve_simple_case": self.preserve_simple_case,
            "block_all_caps": self.block_all_caps,
        }

    @classmethod
    def create(cls, rule_id: str, version: str, source: str, replacement: str) -> FormatBoundaryRule:
        payload = {
            "algorithm_version": FORMAT_BOUNDARY_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": TransformFamily.ORTHOGRAPHY.value,
            "tier": TransformTier.SURFACE.value,
            "source": source,
            "replacement": replacement,
            "construction": (
                FormatConstruction.SENTENCE_BOUNDARY_NEWLINE.value
                if source[:1] in ".?!"
                else FormatConstruction.CLAUSE_PUNCTUATION_NEWLINE.value
            ),
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
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(payload),
        )

    def pattern(self) -> re.Pattern[str]:
        mark = re.escape(self.source[0])
        if self.source.endswith("\n"):
            return re.compile(rf"{mark}\n")
        return re.compile(rf"{mark} ")

    def replacement_for(self, source_text: str) -> str:
        mark = source_text[0]
        if "\n" in self.replacement:
            return f"{mark}\n"
        return f"{mark} "

    def precondition(self, text: str, start: int, end: int) -> bool:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if start < 0 or end <= start or end > len(text):
            raise ValueError("format precondition span is outside text")
        if text[start:end] != self.source:
            raise ValueError("format precondition span does not match rule source")
        if self.source[:1] in ".?!":
            return sentence_boundary_span_admissible(text, start, end)
        return clause_punctuation_span_admissible(text, start, end)
