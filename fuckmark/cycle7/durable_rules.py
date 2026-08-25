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
from ..transforms.format_rules import FormatBoundaryRule
from ..transforms.lexical_rules import LexicalConstruction, LexicalTemplateRule, development_lexical_rules
from ..transforms.rules import LiteralTransformRule
from ..transforms.schema import TransformFamily, TransformTier
from ..transforms.syntax_rules import SyntaxConstruction, SyntaxTemplateRule, development_syntax_rules


CYCLE7_DURABLE_RULE_CATALOG_VERSION = "cycle7-durable-rule-catalog-v3"


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


CYCLE7_ATTESTED_COMPOUND_PAIRS = (
    ("proof of concept", "proof-of-concept"),
    ("point of view", "point-of-view"),
    ("step by step", "step-by-step"),
    ("case by case", "case-by-case"),
    ("end to end", "end-to-end"),
    ("state of the art", "state-of-the-art"),
    ("face to face", "face-to-face"),
)


def cycle7_compound_rules() -> tuple[LexicalTemplateRule, ...]:
    rules: list[LexicalTemplateRule] = []
    for open_form, hyphen_form in CYCLE7_ATTESTED_COMPOUND_PAIRS:
        slug = hyphen_form
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-compound-hyphenate-{slug}",
                version="v1",
                source=open_form,
                replacement=hyphen_form,
                construction=LexicalConstruction.ATTESTED_OPEN_HYPHEN_COMPOUND,
            )
        )
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-compound-open-{slug}",
                version="v1",
                source=hyphen_form,
                replacement=open_form,
                construction=LexicalConstruction.ATTESTED_OPEN_HYPHEN_COMPOUND,
            )
        )
    return tuple(rules)


def cycle7_typographic_apostrophe_rules() -> tuple[LexicalTemplateRule, ...]:
    return (
        LexicalTemplateRule.create(
            rule_id="lexical-apostrophe-ascii-to-typographic",
            version="v1",
            source="'",
            replacement="\u2019",
            construction=LexicalConstruction.INWORD_TYPOGRAPHIC_APOSTROPHE,
        ),
        LexicalTemplateRule.create(
            rule_id="lexical-apostrophe-typographic-to-ascii",
            version="v1",
            source="\u2019",
            replacement="'",
            construction=LexicalConstruction.INWORD_TYPOGRAPHIC_APOSTROPHE,
        ),
    )


CYCLE7_PRENOMINAL_MODIFIER_PAIRS = (
    ("well known", "well-known"),
    ("long term", "long-term"),
    ("short term", "short-term"),
    ("real world", "real-world"),
    ("high level", "high-level"),
    ("low level", "low-level"),
    ("large scale", "large-scale"),
    ("small scale", "small-scale"),
    ("open source", "open-source"),
    ("full time", "full-time"),
    ("part time", "part-time"),
    ("high quality", "high-quality"),
    ("low cost", "low-cost"),
    ("third party", "third-party"),
    ("first order", "first-order"),
    ("second order", "second-order"),
    ("so called", "so-called"),
    ("decision making", "decision-making"),
    ("problem solving", "problem-solving"),
    ("data driven", "data-driven"),
)

CYCLE7_DISCOURSE_COMMA_MARKERS = (
    "However",
    "Therefore",
    "Moreover",
    "Furthermore",
    "Thus",
    "Indeed",
    "Meanwhile",
    "Instead",
    "Finally",
    "Additionally",
    "Consequently",
    "Nevertheless",
    "Nonetheless",
    "Similarly",
    "Specifically",
    "Notably",
    "Importantly",
    "Subsequently",
    "Conversely",
    "Accordingly",
    "Otherwise",
    "In fact",
)

CYCLE7_PARENTHETICAL_ADVERBS = (
    "however",
    "therefore",
    "moreover",
    "instead",
    "meanwhile",
    "nevertheless",
    "nonetheless",
    "consequently",
    "accordingly",
    "similarly",
)

CYCLE7_COORDINATING_CONJUNCTIONS = (
    "and",
    "but",
    "or",
)


def cycle7_prenominal_modifier_rules() -> tuple[LexicalTemplateRule, ...]:
    rules: list[LexicalTemplateRule] = []
    for open_form, hyphen_form in CYCLE7_PRENOMINAL_MODIFIER_PAIRS:
        slug = hyphen_form
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-prenominal-hyphenate-{slug}",
                version="v1",
                source=open_form,
                replacement=hyphen_form,
                construction=LexicalConstruction.ATTESTED_PRENOMINAL_HYPHEN_MODIFIER,
            )
        )
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-prenominal-open-{slug}",
                version="v1",
                source=hyphen_form,
                replacement=open_form,
                construction=LexicalConstruction.ATTESTED_PRENOMINAL_HYPHEN_MODIFIER,
            )
        )
    return tuple(rules)


def cycle7_discourse_comma_rules() -> tuple[LexicalTemplateRule, ...]:
    rules: list[LexicalTemplateRule] = []
    for marker in CYCLE7_DISCOURSE_COMMA_MARKERS:
        slug = marker.casefold().replace(" ", "-")
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-discourse-drop-comma-{slug}",
                version="v1",
                source=f"{marker},",
                replacement=marker,
                construction=LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_COMMA,
            )
        )
        rules.append(
            LexicalTemplateRule.create(
                rule_id=f"lexical-discourse-insert-comma-{slug}",
                version="v1",
                source=marker,
                replacement=f"{marker},",
                construction=LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_COMMA,
            )
        )
    return tuple(rules)


def cycle7_format_boundary_rules() -> tuple[FormatBoundaryRule, ...]:
    rules: list[FormatBoundaryRule] = []
    for mark, name in ((".", "period"), ("?", "question"), ("!", "exclamation")):
        rules.append(
            FormatBoundaryRule.create(
                rule_id=f"cycle7-format-sentence-{name}-newline",
                version="v1",
                source=f"{mark} ",
                replacement=f"{mark}\n",
            )
        )
        rules.append(
            FormatBoundaryRule.create(
                rule_id=f"cycle7-format-sentence-{name}-space",
                version="v1",
                source=f"{mark}\n",
                replacement=f"{mark} ",
            )
        )
    return tuple(rules)


def cycle7_complementizer_that_rules() -> tuple[SyntaxTemplateRule, ...]:
    return (
        SyntaxTemplateRule.create(
            rule_id="cycle7-syntax-complementizer-that-drop",
            version="v1",
            source=" that ",
            replacement=" ",
            construction=SyntaxConstruction.BOUNDED_COMPLEMENTIZER_THAT_DROP,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=True,
        ),
        SyntaxTemplateRule.create(
            rule_id="cycle7-syntax-complementizer-that-insert",
            version="v1",
            source="I think ",
            replacement="I think that ",
            construction=SyntaxConstruction.BOUNDED_COMPLEMENTIZER_THAT_INSERT,
            whole_word=False,
            preserve_simple_case=True,
            block_all_caps=True,
        ),
        SyntaxTemplateRule.create(
            rule_id="cycle7-syntax-relative-that-drop",
            version="v1",
            source=" that ",
            replacement=" ",
            construction=SyntaxConstruction.BOUNDED_OBJECT_RELATIVE_THAT_DROP,
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=True,
        ),
    )


def cycle7_parenthetical_adverb_rules() -> tuple[SyntaxTemplateRule, ...]:
    rules: list[SyntaxTemplateRule] = []
    for adverb in CYCLE7_PARENTHETICAL_ADVERBS:
        rules.append(
            SyntaxTemplateRule.create(
                rule_id=f"cycle7-syntax-parenthetical-drop-{adverb}",
                version="v1",
                source=f", {adverb}, ",
                replacement=f" {adverb} ",
                construction=SyntaxConstruction.PARENTHETICAL_CONJUNCTIVE_ADVERB,
                whole_word=False,
                preserve_simple_case=True,
                block_all_caps=True,
            )
        )
        rules.append(
            SyntaxTemplateRule.create(
                rule_id=f"cycle7-syntax-parenthetical-insert-{adverb}",
                version="v1",
                source=f" {adverb} ",
                replacement=f", {adverb}, ",
                construction=SyntaxConstruction.PARENTHETICAL_CONJUNCTIVE_ADVERB,
                whole_word=False,
                preserve_simple_case=True,
                block_all_caps=True,
            )
        )
    return tuple(rules)


def cycle7_coordinating_conjunction_comma_rules() -> tuple[SyntaxTemplateRule, ...]:
    rules: list[SyntaxTemplateRule] = []
    for conjunction in CYCLE7_COORDINATING_CONJUNCTIONS:
        rules.append(
            SyntaxTemplateRule.create(
                rule_id=f"cycle7-syntax-coord-comma-drop-{conjunction}",
                version="v1",
                source=f", {conjunction} ",
                replacement=f" {conjunction} ",
                construction=SyntaxConstruction.COORDINATING_CONJUNCTION_COMMA,
                whole_word=False,
                preserve_simple_case=False,
                block_all_caps=True,
            )
        )
        rules.append(
            SyntaxTemplateRule.create(
                rule_id=f"cycle7-syntax-coord-comma-insert-{conjunction}",
                version="v1",
                source=f" {conjunction} ",
                replacement=f", {conjunction} ",
                construction=SyntaxConstruction.COORDINATING_CONJUNCTION_COMMA,
                whole_word=False,
                preserve_simple_case=False,
                block_all_caps=True,
            )
        )
    return tuple(rules)


def cycle7_durable_rules() -> tuple[object, ...]:
    return (
        *development_forward_contraction_rules(),
        *reverse_contraction_rules(),
        *zrd_forward_contraction_extension_rules(),
        *zrd_reverse_contraction_extension_rules(),
        *cycle7_new_contraction_rules(),
        *cycle7_bounded_copula_rules(),
        *cycle7_orthography_rules(),
        *cycle7_compound_rules(),
        *cycle7_prenominal_modifier_rules(),
        *cycle7_typographic_apostrophe_rules(),
        *cycle7_discourse_comma_rules(),
        *cycle7_format_boundary_rules(),
        *cycle7_complementizer_that_rules(),
        *cycle7_parenthetical_adverb_rules(),
        *cycle7_coordinating_conjunction_comma_rules(),
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
