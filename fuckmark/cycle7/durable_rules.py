from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from ..transforms.contractions import (
    development_forward_contraction_rules,
    reverse_contraction_rules,
    zrd_forward_contraction_extension_rules,
    zrd_reverse_contraction_extension_rules,
)
from ..transforms.lexical_rules import development_lexical_rules
from ..transforms.rules import LiteralTransformRule
from ..transforms.schema import TransformFamily, TransformTier
from ..transforms.syntax_rules import development_syntax_rules


CYCLE7_DURABLE_RULE_CATALOG_VERSION = "cycle7-durable-rule-catalog-v1"


@dataclass(frozen=True, slots=True)
class Cycle7DurableRewrite:
    rule_id: str
    inverse_rule_id: str
    family: TransformFamily
    source: str
    replacement: str
    inverse_group_id: str
    whitespace_collapse_survives: bool
    ambiguous: bool
    notes: str
    metadata_hash: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "inverse_rule_id", "inverse_group_id", "notes"):
            require_clean_string(name, getattr(self, name))
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("source must be non-empty")
        if not isinstance(self.replacement, str) or not self.replacement:
            raise ValueError("replacement must be non-empty")
        if self.source.casefold() == self.replacement.casefold():
            raise ValueError("source and replacement must differ")
        if self.family not in (TransformFamily.CONTRACTION, TransformFamily.ORTHOGRAPHY):
            raise ValueError("Cycle 7 durable rewrites must be contraction or orthography")
        if self.ambiguous:
            raise ValueError("ambiguous Cycle 7 rewrites are not admitted")
        if not self.whitespace_collapse_survives:
            raise ValueError("Cycle 7 durable rewrites must survive whitespace collapse")
        require_sha256("metadata_hash", self.metadata_hash)
        if self.metadata_hash != sha256_json(self.payload()):
            raise ValueError("metadata_hash does not match Cycle 7 durable rewrite")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": CYCLE7_DURABLE_RULE_CATALOG_VERSION,
            "rule_id": self.rule_id,
            "inverse_rule_id": self.inverse_rule_id,
            "family": self.family.value,
            "source": self.source,
            "replacement": self.replacement,
            "inverse_group_id": self.inverse_group_id,
            "whitespace_collapse_survives": self.whitespace_collapse_survives,
            "ambiguous": self.ambiguous,
            "notes": self.notes,
        }

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        inverse_rule_id: str,
        family: TransformFamily,
        source: str,
        replacement: str,
        inverse_group_id: str,
        notes: str,
    ) -> Cycle7DurableRewrite:
        payload = {
            "algorithm_version": CYCLE7_DURABLE_RULE_CATALOG_VERSION,
            "rule_id": rule_id,
            "inverse_rule_id": inverse_rule_id,
            "family": family.value,
            "source": source,
            "replacement": replacement,
            "inverse_group_id": inverse_group_id,
            "whitespace_collapse_survives": True,
            "ambiguous": False,
            "notes": notes,
        }
        return cls(
            rule_id=rule_id,
            inverse_rule_id=inverse_rule_id,
            family=family,
            source=source,
            replacement=replacement,
            inverse_group_id=inverse_group_id,
            whitespace_collapse_survives=True,
            ambiguous=False,
            notes=notes,
            metadata_hash=sha256_json(payload),
        )


def cycle7_new_contraction_metadata() -> tuple[Cycle7DurableRewrite, ...]:
    rows = (
        (
            "cycle7-contract-i-have",
            "cycle7-expand-i-have",
            "I have",
            "I've",
            "cycle7-contraction-i-have",
            "Unambiguous auxiliary have. Inverse restores 'I have'.",
        ),
        (
            "cycle7-contract-you-have",
            "cycle7-expand-you-have",
            "you have",
            "you've",
            "cycle7-contraction-you-have",
            "Unambiguous auxiliary have.",
        ),
        (
            "cycle7-contract-we-have",
            "cycle7-expand-we-have",
            "we have",
            "we've",
            "cycle7-contraction-we-have",
            "Unambiguous auxiliary have.",
        ),
        (
            "cycle7-contract-they-have",
            "cycle7-expand-they-have",
            "they have",
            "they've",
            "cycle7-contraction-they-have",
            "Unambiguous auxiliary have.",
        ),
    )
    return tuple(
        Cycle7DurableRewrite.create(
            rule_id=rule_id,
            inverse_rule_id=inverse_rule_id,
            family=TransformFamily.CONTRACTION,
            source=source,
            replacement=replacement,
            inverse_group_id=group_id,
            notes=notes,
        )
        for rule_id, inverse_rule_id, source, replacement, group_id, notes in rows
    )


def cycle7_bounded_copula_metadata() -> tuple[Cycle7DurableRewrite, ...]:
    rows = (
        (
            "cycle7-expand-its-like",
            "cycle7-contract-its-like",
            "it's like",
            "it is like",
            "cycle7-copula-its-like",
            "it's+like is it is. Bare it's and it's not are excluded: it's not trips hard-invariant negation identity, and it's is otherwise is/has-ambiguous.",
        ),
        (
            "cycle7-expand-its-important",
            "cycle7-contract-its-important",
            "it's important",
            "it is important",
            "cycle7-copula-its-important",
            "it's+important is it is.",
        ),
        (
            "cycle7-expand-its-a",
            "cycle7-contract-its-a",
            "it's a",
            "it is a",
            "cycle7-copula-its-a",
            "it's+a is it is. Does not match it's been.",
        ),
        (
            "cycle7-expand-its-an",
            "cycle7-contract-its-an",
            "it's an",
            "it is an",
            "cycle7-copula-its-an",
            "it's+an is it is.",
        ),
        (
            "cycle7-expand-its-the",
            "cycle7-contract-its-the",
            "it's the",
            "it is the",
            "cycle7-copula-its-the",
            "it's+the is it is.",
        ),
    )
    return tuple(
        Cycle7DurableRewrite.create(
            rule_id=rule_id,
            inverse_rule_id=inverse_rule_id,
            family=TransformFamily.CONTRACTION,
            source=source,
            replacement=replacement,
            inverse_group_id=group_id,
            notes=notes,
        )
        for rule_id, inverse_rule_id, source, replacement, group_id, notes in rows
    )


def cycle7_orthography_metadata() -> tuple[Cycle7DurableRewrite, ...]:
    rows = (
        (
            "cycle7-ortho-towards-toward",
            "cycle7-ortho-toward-towards",
            "towards",
            "toward",
            "cycle7-ortho-toward",
            "UK/US prepositional variant. Token boundary change survives space collapse.",
        ),
        (
            "cycle7-ortho-toward-towards",
            "cycle7-ortho-towards-toward",
            "toward",
            "towards",
            "cycle7-ortho-toward",
            "Inverse of towards/toward. Adjective 'toward' is rare; whole-word still required.",
        ),
        (
            "cycle7-ortho-amongst-among",
            "cycle7-ortho-among-amongst",
            "amongst",
            "among",
            "cycle7-ortho-among",
            "UK/US prepositional variant.",
        ),
        (
            "cycle7-ortho-among-amongst",
            "cycle7-ortho-amongst-among",
            "among",
            "amongst",
            "cycle7-ortho-among",
            "Inverse of amongst/among.",
        ),
    )
    return tuple(
        Cycle7DurableRewrite.create(
            rule_id=rule_id,
            inverse_rule_id=inverse_rule_id,
            family=TransformFamily.ORTHOGRAPHY,
            source=source,
            replacement=replacement,
            inverse_group_id=group_id,
            notes=notes,
        )
        for rule_id, inverse_rule_id, source, replacement, group_id, notes in rows
    )


def _rules_from_metadata(rows: tuple[Cycle7DurableRewrite, ...]) -> tuple[LiteralTransformRule, ...]:
    return tuple(
        LiteralTransformRule.create(
            rule_id=row.rule_id,
            version="v1",
            family=row.family,
            tier=TransformTier.SURFACE,
            source=row.source,
            replacement=row.replacement,
        )
        for row in rows
    )


def cycle7_new_contraction_rules() -> tuple[LiteralTransformRule, ...]:
    forward = _rules_from_metadata(cycle7_new_contraction_metadata())
    reverse_meta = tuple(
        Cycle7DurableRewrite.create(
            rule_id=row.inverse_rule_id,
            inverse_rule_id=row.rule_id,
            family=row.family,
            source=row.replacement,
            replacement=row.source,
            inverse_group_id=row.inverse_group_id,
            notes=f"Inverse of {row.rule_id}.",
        )
        for row in cycle7_new_contraction_metadata()
    )
    return (*forward, *_rules_from_metadata(reverse_meta))


def cycle7_bounded_copula_rules() -> tuple[LiteralTransformRule, ...]:
    forward = _rules_from_metadata(cycle7_bounded_copula_metadata())
    reverse_meta = tuple(
        Cycle7DurableRewrite.create(
            rule_id=row.inverse_rule_id,
            inverse_rule_id=row.rule_id,
            family=row.family,
            source=row.replacement,
            replacement=row.source,
            inverse_group_id=row.inverse_group_id,
            notes=f"Inverse of {row.rule_id}.",
        )
        for row in cycle7_bounded_copula_metadata()
    )
    return (*forward, *_rules_from_metadata(reverse_meta))


def cycle7_orthography_rules() -> tuple[LiteralTransformRule, ...]:
    return _rules_from_metadata(cycle7_orthography_metadata())


def cycle7_durable_rules() -> tuple[object, ...]:
    return (
        *development_forward_contraction_rules(),
        *reverse_contraction_rules(),
        *zrd_forward_contraction_extension_rules(),
        *zrd_reverse_contraction_extension_rules(),
        *cycle7_new_contraction_rules(),
        *cycle7_bounded_copula_rules(),
        *cycle7_orthography_rules(),
        *development_lexical_rules(),
        *development_syntax_rules(),
    )


def rejected_ambiguous_contraction_examples() -> tuple[tuple[str, str], ...]:
    return (
        ("he would", "he'd"),
        ("she would", "she'd"),
        ("I would", "I'd"),
        ("it is", "it's"),
        ("that is", "that's"),
        ("let us", "let's"),
        ("it's not", "it is not"),
        ("it's been", "it is been"),
    )
