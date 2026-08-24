from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from .candidate_artifacts import TransformCandidate
from .rules import LiteralTransformRule, default_contraction_rules
from .schema import TransformFamily, TransformTier


REVERSIBLE_CONTRACTION_ALGORITHM_VERSION = "reversible-contraction-v1"


@dataclass(frozen=True, slots=True)
class ReversibleContractionMetadata:
    forward_rule_id: str
    reverse_rule_id: str
    inverse_semantic_group_id: str
    expanded_form: str
    contracted_form: str
    metadata_hash: str

    def __post_init__(self) -> None:
        for name in ("forward_rule_id", "reverse_rule_id", "inverse_semantic_group_id"):
            require_clean_string(name, getattr(self, name))
        if not isinstance(self.expanded_form, str) or not self.expanded_form:
            raise ValueError("expanded_form must be non-empty")
        if not isinstance(self.contracted_form, str) or not self.contracted_form:
            raise ValueError("contracted_form must be non-empty")
        if self.expanded_form.casefold() == self.contracted_form.casefold():
            raise ValueError("expanded and contracted forms must differ")
        require_sha256("metadata_hash", self.metadata_hash)
        if self.metadata_hash != sha256_json(self.payload()):
            raise ValueError("metadata_hash does not match reversible contraction metadata")

    @classmethod
    def create(
        cls,
        *,
        forward_rule_id: str,
        reverse_rule_id: str,
        inverse_semantic_group_id: str,
        expanded_form: str,
        contracted_form: str,
    ) -> ReversibleContractionMetadata:
        payload = {
            "algorithm_version": REVERSIBLE_CONTRACTION_ALGORITHM_VERSION,
            "forward_rule_id": forward_rule_id,
            "reverse_rule_id": reverse_rule_id,
            "inverse_semantic_group_id": inverse_semantic_group_id,
            "expanded_form": expanded_form,
            "contracted_form": contracted_form,
        }
        return cls(
            forward_rule_id=forward_rule_id,
            reverse_rule_id=reverse_rule_id,
            inverse_semantic_group_id=inverse_semantic_group_id,
            expanded_form=expanded_form,
            contracted_form=contracted_form,
            metadata_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": REVERSIBLE_CONTRACTION_ALGORITHM_VERSION,
            "forward_rule_id": self.forward_rule_id,
            "reverse_rule_id": self.reverse_rule_id,
            "inverse_semantic_group_id": self.inverse_semantic_group_id,
            "expanded_form": self.expanded_form,
            "contracted_form": self.contracted_form,
        }


@dataclass(frozen=True, slots=True)
class ContractionSemanticSite:
    group_id: str
    site_id: str
    direction: str

    def __post_init__(self) -> None:
        require_clean_string("group_id", self.group_id)
        require_clean_string("site_id", self.site_id)
        require_clean_string("direction", self.direction)
        if self.direction not in ("forward", "reverse"):
            raise ValueError("direction must be forward or reverse")


def reversible_contraction_metadata() -> tuple[ReversibleContractionMetadata, ...]:
    rows = (
        ("contract-do-not", "expand-do-not", "contraction-do-not", "do not", "don't"),
        ("contract-does-not", "expand-does-not", "contraction-does-not", "does not", "doesn't"),
        ("contract-did-not", "expand-did-not", "contraction-did-not", "did not", "didn't"),
        ("contract-cannot", "expand-cannot", "contraction-cannot", "cannot", "can't"),
        ("contract-will-not", "expand-will-not", "contraction-will-not", "will not", "won't"),
        ("contract-should-not", "expand-should-not", "contraction-should-not", "should not", "shouldn't"),
        ("contract-could-not", "expand-could-not", "contraction-could-not", "could not", "couldn't"),
        ("contract-would-not", "expand-would-not", "contraction-would-not", "would not", "wouldn't"),
        ("contract-is-not", "expand-is-not", "contraction-is-not", "is not", "isn't"),
        ("contract-are-not", "expand-are-not", "contraction-are-not", "are not", "aren't"),
        ("contract-was-not", "expand-was-not", "contraction-was-not", "was not", "wasn't"),
        ("contract-were-not", "expand-were-not", "contraction-were-not", "were not", "weren't"),
        ("contract-has-not", "expand-has-not", "contraction-has-not", "has not", "hasn't"),
        ("contract-have-not", "expand-have-not", "contraction-have-not", "have not", "haven't"),
        ("contract-had-not", "expand-had-not", "contraction-had-not", "had not", "hadn't"),
        ("contract-i-am", "expand-i-am", "contraction-i-am", "I am", "I'm"),
        ("contract-you-are", "expand-you-are", "contraction-you-are", "you are", "you're"),
        ("contract-we-are", "expand-we-are", "contraction-we-are", "we are", "we're"),
        ("contract-they-are", "expand-they-are", "contraction-they-are", "they are", "they're"),
        ("contract-must-not", "expand-must-not", "contraction-must-not", "must not", "mustn't"),
    )
    return tuple(
        ReversibleContractionMetadata.create(
            forward_rule_id=forward_rule_id,
            reverse_rule_id=reverse_rule_id,
            inverse_semantic_group_id=group_id,
            expanded_form=expanded_form,
            contracted_form=contracted_form,
        )
        for forward_rule_id, reverse_rule_id, group_id, expanded_form, contracted_form in rows
    )


ZRD_CONTRACTION_EXTENSION_ALGORITHM_VERSION = "reversible-contraction-extension-v1"


def zrd_contraction_extension_metadata() -> tuple[ReversibleContractionMetadata, ...]:
    rows = (
        ("contract-she-is-not-x", "expand-she-is-not-x", "contraction-she-is-not-x", "she is not", "she isn't"),
        ("contract-he-is-not-x", "expand-he-is-not-x", "contraction-he-is-not-x", "he is not", "he isn't"),
        ("contract-that-is-not-x", "expand-that-is-not-x", "contraction-that-is-not-x", "that is not", "that isn't"),
        ("contract-there-was-not-x", "expand-there-was-not-x", "contraction-there-was-not-x", "there was not", "there wasn't"),
        ("contract-one-does-not-x", "expand-one-does-not-x", "contraction-one-does-not-x", "one does not", "one doesn't"),
    )
    return tuple(
        ReversibleContractionMetadata.create(
            forward_rule_id=forward_rule_id,
            reverse_rule_id=reverse_rule_id,
            inverse_semantic_group_id=group_id,
            expanded_form=expanded_form,
            contracted_form=contracted_form,
        )
        for forward_rule_id, reverse_rule_id, group_id, expanded_form, contracted_form in rows
    )


def zrd_forward_contraction_extension_rules() -> tuple[LiteralTransformRule, ...]:
    return tuple(
        LiteralTransformRule.create(
            rule_id=value.forward_rule_id,
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source=value.expanded_form,
            replacement=value.contracted_form,
        )
        for value in zrd_contraction_extension_metadata()
    )


def zrd_reverse_contraction_extension_rules() -> tuple[LiteralTransformRule, ...]:
    return tuple(
        LiteralTransformRule.create(
            rule_id=value.reverse_rule_id,
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source=value.contracted_form,
            replacement=value.expanded_form,
        )
        for value in zrd_contraction_extension_metadata()
    )


def development_forward_contraction_rules() -> tuple[LiteralTransformRule, ...]:
    existing = {rule.rule_id: rule for rule in default_contraction_rules()}
    output: list[LiteralTransformRule] = []
    for value in reversible_contraction_metadata():
        rule = existing.get(value.forward_rule_id)
        if rule is None:
            rule = LiteralTransformRule.create(
                rule_id=value.forward_rule_id,
                version="v1",
                family=TransformFamily.CONTRACTION,
                tier=TransformTier.SURFACE,
                source=value.expanded_form,
                replacement=value.contracted_form,
            )
        if rule.source != value.expanded_form or rule.replacement != value.contracted_form:
            raise ValueError("forward contraction rule disagrees with reversible metadata")
        output.append(rule)
    return tuple(output)


def reverse_contraction_rules() -> tuple[LiteralTransformRule, ...]:
    return tuple(
        LiteralTransformRule.create(
            rule_id=value.reverse_rule_id,
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.SURFACE,
            source=value.contracted_form,
            replacement=value.expanded_form,
        )
        for value in reversible_contraction_metadata()
    )


def context_survival_contraction_rules() -> tuple[LiteralTransformRule, ...]:
    return tuple((*development_forward_contraction_rules(), *reverse_contraction_rules()))


def contraction_semantic_site(text: str, candidate: TransformCandidate) -> ContractionSemanticSite | None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(candidate, TransformCandidate):
        raise TypeError("candidate must be a TransformCandidate")
    by_rule: dict[str, tuple[ReversibleContractionMetadata, str, str]] = {}
    for metadata in reversible_contraction_metadata():
        by_rule[metadata.forward_rule_id] = (metadata, "forward", metadata.expanded_form)
        by_rule[metadata.reverse_rule_id] = (metadata, "reverse", metadata.contracted_form)
    resolved = by_rule.get(candidate.rule_id)
    if resolved is None:
        return None
    metadata, direction, expected_source = resolved
    if candidate.family is not TransformFamily.CONTRACTION or candidate.tier is not TransformTier.SURFACE:
        raise ValueError("known contraction candidate has invalid family or tier")
    if candidate.source_text.casefold() != expected_source.casefold():
        raise ValueError("known contraction candidate source does not match reversible metadata")
    occurrences: list[tuple[int, int, str]] = []
    for form in (metadata.expanded_form, metadata.contracted_form):
        for match in _literal_pattern(form).finditer(text):
            occurrences.append((match.start(), match.end(), form.casefold()))
    occurrences.sort(key=lambda value: (value[0], value[1], value[2]))
    matching_indices = tuple(
        index
        for index, value in enumerate(occurrences)
        if value[0] == candidate.start and value[1] == candidate.end
    )
    if len(matching_indices) != 1:
        raise ValueError("contraction candidate does not resolve to exactly one semantic occurrence")
    site_id = f"{metadata.inverse_semantic_group_id}:{matching_indices[0]}"
    return ContractionSemanticSite(metadata.inverse_semantic_group_id, site_id, direction)


def contraction_inverse_semantic_resolver(state: Any, candidate: TransformCandidate) -> Any:
    text = getattr(state, "text", None)
    if not isinstance(text, str):
        raise TypeError("state must expose string text")
    site = contraction_semantic_site(text, candidate)
    if site is None:
        return None
    from ..scheduling.context_survival import InverseSemanticOperation

    return InverseSemanticOperation(site.group_id, site.site_id, site.direction)


def _literal_pattern(value: str) -> re.Pattern[str]:
    literal = rf"(?ai:{re.escape(value)})"
    pattern = literal
    if value[0].isalnum() or value[0] == "_":
        pattern = rf"(?<!\w){pattern}"
    if value[-1].isalnum() or value[-1] == "_":
        pattern = rf"{pattern}(?!\w)"
    return re.compile(pattern)
