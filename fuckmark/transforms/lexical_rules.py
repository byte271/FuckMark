from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .schema import TransformFamily, TransformTier


LEXICAL_TEMPLATE_RULE_ALGORITHM_VERSION = "lexical-template-rule-v1"


class LexicalConstruction(str, Enum):
    SENTENCE_INITIAL_DISCOURSE_MARKER = "sentence_initial_discourse_marker"
    ATTESTED_OPEN_HYPHEN_COMPOUND = "attested_open_hyphen_compound"
    INWORD_TYPOGRAPHIC_APOSTROPHE = "inword_typographic_apostrophe"
    SENTENCE_INITIAL_DISCOURSE_COMMA = "sentence_initial_discourse_comma"
    ATTESTED_PRENOMINAL_HYPHEN_MODIFIER = "attested_prenominal_hyphen_modifier"
    QUANTIFIER_OF_DETERMINER = "quantifier_of_determiner"


@dataclass(frozen=True, slots=True)
class LexicalTemplateRule:
    rule_id: str
    version: str
    family: TransformFamily
    tier: TransformTier
    source: str
    replacement: str
    construction: LexicalConstruction
    ambiguity_blacklist: tuple[str, ...]
    whole_word: bool
    preserve_simple_case: bool
    block_all_caps: bool
    rule_hash: str

    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.LEXICAL_TEMPLATE:
            raise ValueError("lexical template rules must use the lexical template family")
        if self.tier is not TransformTier.LEXICAL:
            raise ValueError("lexical template rules must use tier 2 lexical")
        if not isinstance(self.source, str) or not self.source or "\n" in self.source or "\r" in self.source:
            raise ValueError("source must be non-empty and single-line")
        if not isinstance(self.replacement, str) or not self.replacement or "\n" in self.replacement or "\r" in self.replacement:
            raise ValueError("replacement must be non-empty and single-line")
        if self.source.casefold() == self.replacement.casefold():
            raise ValueError("source and replacement must differ")
        if not isinstance(self.construction, LexicalConstruction):
            raise TypeError("construction must be a LexicalConstruction")
        if not isinstance(self.ambiguity_blacklist, tuple):
            raise TypeError("ambiguity_blacklist must be a tuple")
        normalized_blacklist = tuple(sorted(self.ambiguity_blacklist, key=lambda value: value.casefold()))
        if normalized_blacklist != self.ambiguity_blacklist:
            raise ValueError("ambiguity_blacklist must be canonically ordered")
        if len({value.casefold() for value in normalized_blacklist}) != len(normalized_blacklist):
            raise ValueError("ambiguity_blacklist entries must be unique case-insensitively")
        for value in normalized_blacklist:
            if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
                raise ValueError("ambiguity blacklist entries must be non-empty single-line strings")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match lexical template rule")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": LEXICAL_TEMPLATE_RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "construction": self.construction.value,
            "ambiguity_blacklist": self.ambiguity_blacklist,
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
        construction: LexicalConstruction,
        ambiguity_blacklist: tuple[str, ...] = (),
        whole_word: bool = True,
        preserve_simple_case: bool = True,
        block_all_caps: bool = True,
    ) -> LexicalTemplateRule:
        blacklist = tuple(sorted(tuple(ambiguity_blacklist), key=lambda value: value.casefold()))
        payload = {
            "algorithm_version": LEXICAL_TEMPLATE_RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": version,
            "family": TransformFamily.LEXICAL_TEMPLATE.value,
            "tier": TransformTier.LEXICAL.value,
            "source": source,
            "replacement": replacement,
            "construction": construction.value if isinstance(construction, LexicalConstruction) else construction,
            "ambiguity_blacklist": blacklist,
            "whole_word": whole_word,
            "preserve_simple_case": preserve_simple_case,
            "block_all_caps": block_all_caps,
        }
        return cls(
            rule_id=rule_id,
            version=version,
            family=TransformFamily.LEXICAL_TEMPLATE,
            tier=TransformTier.LEXICAL,
            source=source,
            replacement=replacement,
            construction=construction,
            ambiguity_blacklist=blacklist,
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
            raise ValueError("lexical precondition span is outside text")
        if text[start:end].casefold() != self.source.casefold():
            raise ValueError("lexical precondition span does not match rule source")
        if self.construction is LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_MARKER:
            if end >= len(text) or not text[end].isspace():
                return False
            prefix = text[:start]
            stripped = prefix.rstrip()
            if stripped and stripped[-1] not in ".?!":
                return False
        elif self.construction is LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_COMMA:
            if not sentence_initial_discourse_comma_span_admissible(text, start, end, self.source, self.replacement):
                return False
        elif self.construction is LexicalConstruction.ATTESTED_OPEN_HYPHEN_COMPOUND:
            if not attested_open_hyphen_compound_span_admissible(text, start, end):
                return False
        elif self.construction is LexicalConstruction.ATTESTED_PRENOMINAL_HYPHEN_MODIFIER:
            if not attested_prenominal_hyphen_modifier_span_admissible(text, start, end):
                return False
        elif self.construction is LexicalConstruction.INWORD_TYPOGRAPHIC_APOSTROPHE:
            if not inword_typographic_apostrophe_span_admissible(text, start, end):
                return False
        elif self.construction is LexicalConstruction.QUANTIFIER_OF_DETERMINER:
            if not quantifier_of_determiner_span_admissible(text, start, end):
                return False
        else:
            return False
        context = text[max(0, start - 96) : min(len(text), end + 96)].casefold()
        if any(value.casefold() in context for value in self.ambiguity_blacklist):
            return False
        return True


def attested_open_hyphen_compound_span_admissible(text: str, start: int, end: int) -> bool:
    if start > 0:
        previous = text[start - 1]
        if previous.isalnum() or previous in "_-/\\":
            return False
    if end < len(text):
        nxt = text[end]
        if nxt.isalnum() or nxt in "_-/\\":
            return False
    return "--" not in text[start:end]


_DISCOURSE_DEGREE_FOLLOWERS = frozenset(
    {"much", "many", "long", "far", "little", "few", "often", "hard", "briefly"}
)


def _next_alpha_word(text: str, index: int) -> str:
    cursor = index
    while cursor < len(text) and not text[cursor].isalpha():
        cursor += 1
    begin = cursor
    while cursor < len(text) and text[cursor].isalpha():
        cursor += 1
    return text[begin:cursor]


def sentence_initial_discourse_comma_span_admissible(
    text: str,
    start: int,
    end: int,
    source: str,
    replacement: str,
) -> bool:
    if end >= len(text) or not text[end].isspace():
        return False
    prefix = text[:start]
    stripped = prefix.rstrip()
    if stripped and stripped[-1] not in ".?!":
        return False
    inserting_comma = "," not in source and "," in replacement
    if inserting_comma:
        follower = _next_alpha_word(text, end).casefold()
        if follower in _DISCOURSE_DEGREE_FOLLOWERS:
            return False
    return True


def attested_prenominal_hyphen_modifier_span_admissible(text: str, start: int, end: int) -> bool:
    if not attested_open_hyphen_compound_span_admissible(text, start, end):
        return False
    matched = text[start:end]
    hyphenating = " " in matched and "-" not in matched
    if not hyphenating:
        return True
    rest = text[end:]
    return bool(re.match(r" [a-z]{2,}\b", rest))


def inword_typographic_apostrophe_span_admissible(text: str, start: int, end: int) -> bool:
    if start == 0 or end >= len(text):
        return False
    if end - start != 1:
        return False
    if text[start] not in {"'", "\u2019"}:
        return False
    if not text[start - 1].isalpha() or not text[end].isalpha():
        return False
    if text[start - 1].isupper() and text[end].isupper():
        return False
    return True


def quantifier_of_determiner_span_admissible(text: str, start: int, end: int) -> bool:
    if start > 0:
        previous = text[start - 1]
        if previous.isalnum() or previous in "_-/\\":
            return False
    if end < len(text):
        nxt = text[end]
        if nxt.isalnum() or nxt in "_-/\\":
            return False
    return True


def development_lexical_rules() -> tuple[LexicalTemplateRule, ...]:
    return (
        LexicalTemplateRule.create(
            rule_id="lexical-for-example-for-instance",
            version="v1",
            source="for example,",
            replacement="for instance,",
            construction=LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_MARKER,
        ),
    )
