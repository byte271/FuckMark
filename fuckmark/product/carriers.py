from __future__ import annotations

import re
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms.rules import LiteralTransformRule, RULE_ALGORITHM_VERSION
from ..transforms.schema import TransformFamily, TransformTier
from .visible_projection import is_carrier_insertion_v1, normalize_approved_carriers


INVISIBLE_CARRIER_RULE_ALGORITHM_VERSION = "invisible-carrier-rule-v1"
INVISIBLE_LETTER_CARRIER_SENTINEL = "letter"
INVISIBLE_WORD_FINAL_CARRIER_PATTERN = "invisible-word-final-carrier-rule-v1"


def codepoint_label(codepoint: int) -> str:
    require_int("codepoint", codepoint)
    if codepoint < 0 or codepoint > 0x10FFFF:
        raise ValueError("codepoint must be a Unicode scalar value")
    return f"U+{codepoint:04X}"


def space_carrier_rule(codepoint: int, repeats: int = 1) -> LiteralTransformRule:
    require_int("codepoint", codepoint)
    require_int("repeats", repeats)
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    carrier = chr(codepoint) * repeats
    suffix = "" if repeats == 1 else f"-x{repeats}"
    return LiteralTransformRule.create(
        rule_id=f"product-carrier-space-{codepoint:04X}{suffix}",
        version="v1",
        family=TransformFamily.ORTHOGRAPHY,
        tier=TransformTier.EXPERIMENTAL,
        source=" ",
        replacement=" " + carrier,
        whole_word=False,
        preserve_simple_case=False,
        block_all_caps=False,
    )


@dataclass(frozen=True, slots=True)
class InvisibleCarrierAfterAsciiLetterRule(LiteralTransformRule):
    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("version", self.version)
        if self.family is not TransformFamily.ORTHOGRAPHY:
            raise ValueError("invisible letter-carrier rules must use the orthography family")
        if self.tier is not TransformTier.EXPERIMENTAL:
            raise ValueError("invisible letter-carrier rules must use experimental tier")
        if self.source != INVISIBLE_LETTER_CARRIER_SENTINEL:
            raise ValueError("invisible letter-carrier rules use the fixed letter sentinel")
        if not self.replacement.startswith(INVISIBLE_LETTER_CARRIER_SENTINEL):
            raise ValueError("invisible letter-carrier replacement must keep the letter sentinel")
        carrier = self.replacement[len(INVISIBLE_LETTER_CARRIER_SENTINEL) :]
        if not carrier:
            raise ValueError("invisible letter-carrier rules insert at least one carrier")
        if "\n" in self.source or "\r" in self.source or "\n" in self.replacement or "\r" in self.replacement:
            raise ValueError("invisible letter-carrier rules must stay single-line")
        require_bool("whole_word", self.whole_word)
        require_bool("preserve_simple_case", self.preserve_simple_case)
        require_bool("block_all_caps", self.block_all_caps)
        if self.whole_word or self.preserve_simple_case or self.block_all_caps:
            raise ValueError("invisible letter-carrier rules use an exact ASCII-letter contract")
        require_sha256("rule_hash", self.rule_hash)
        if self.rule_hash != sha256_json(self._payload()):
            raise ValueError("rule_hash does not match invisible letter-carrier rule")

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
            "carrier_pattern": INVISIBLE_CARRIER_RULE_ALGORITHM_VERSION,
        }

    @classmethod
    def create(cls, codepoint: int, repeats: int = 1) -> "InvisibleCarrierAfterAsciiLetterRule":
        require_int("codepoint", codepoint)
        require_int("repeats", repeats)
        if repeats <= 0:
            raise ValueError("repeats must be positive")
        carrier = chr(codepoint) * repeats
        suffix = "" if repeats == 1 else f"-x{repeats}"
        rule_id = f"product-carrier-letter-{codepoint:04X}{suffix}"
        hashed = {
            "algorithm_version": RULE_ALGORITHM_VERSION,
            "rule_id": rule_id,
            "version": "v1",
            "family": TransformFamily.ORTHOGRAPHY.value,
            "tier": TransformTier.EXPERIMENTAL.value,
            "source": INVISIBLE_LETTER_CARRIER_SENTINEL,
            "replacement": INVISIBLE_LETTER_CARRIER_SENTINEL + carrier,
            "whole_word": False,
            "preserve_simple_case": False,
            "block_all_caps": False,
            "carrier_pattern": INVISIBLE_CARRIER_RULE_ALGORITHM_VERSION,
        }
        return cls(
            rule_id=rule_id,
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.EXPERIMENTAL,
            source=INVISIBLE_LETTER_CARRIER_SENTINEL,
            replacement=INVISIBLE_LETTER_CARRIER_SENTINEL + carrier,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(hashed),
        )

    def pattern(self) -> re.Pattern[str]:
        return re.compile(r"[A-Za-z]")

    def replacement_for(self, source_text: str) -> str:
        return source_text + self.replacement[len(INVISIBLE_LETTER_CARRIER_SENTINEL) :]


class InvisibleCarrierAfterWordFinalAsciiLetterRule(InvisibleCarrierAfterAsciiLetterRule):
    def _payload(self) -> dict[str, object]:
        return {**super()._payload(), "carrier_pattern": INVISIBLE_WORD_FINAL_CARRIER_PATTERN}

    @classmethod
    def create(cls, codepoint: int) -> "InvisibleCarrierAfterWordFinalAsciiLetterRule":
        require_int("codepoint", codepoint)
        carrier = chr(codepoint)
        hashed = {
            "algorithm_version": RULE_ALGORITHM_VERSION,
            "rule_id": f"product-carrier-word-final-letter-{codepoint:04X}",
            "version": "v1",
            "family": TransformFamily.ORTHOGRAPHY.value,
            "tier": TransformTier.EXPERIMENTAL.value,
            "source": INVISIBLE_LETTER_CARRIER_SENTINEL,
            "replacement": INVISIBLE_LETTER_CARRIER_SENTINEL + carrier,
            "whole_word": False,
            "preserve_simple_case": False,
            "block_all_caps": False,
            "carrier_pattern": INVISIBLE_WORD_FINAL_CARRIER_PATTERN,
        }
        return cls(
            rule_id=f"product-carrier-word-final-letter-{codepoint:04X}",
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.EXPERIMENTAL,
            source=INVISIBLE_LETTER_CARRIER_SENTINEL,
            replacement=INVISIBLE_LETTER_CARRIER_SENTINEL + carrier,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash=sha256_json(hashed),
        )

    def pattern(self) -> re.Pattern[str]:
        return re.compile(r"[A-Za-z](?![A-Za-z])")


def rule_preserves_visible_projection(rule: LiteralTransformRule, approved_carriers=None) -> bool:
    approved = normalize_approved_carriers(approved_carriers)
    if isinstance(rule, InvisibleCarrierAfterAsciiLetterRule):
        sample_source = "A"
        sample_replacement = rule.replacement_for(sample_source)
        return is_carrier_insertion_v1(sample_source, sample_replacement, approved)
    source = getattr(rule, "source", None)
    replacement = getattr(rule, "replacement", None)
    if not isinstance(source, str) or not isinstance(replacement, str):
        return False
    return is_carrier_insertion_v1(source, replacement, approved)
