from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from .candidate_artifacts import TransformCandidate
from .contractions import contraction_inverse_semantic_resolver
from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


DURABLE_SURFACE_RULE_ALGORITHM_VERSION = "durable-surface-rule-v1"
DURABLE_SURFACE_PAIR_ALGORITHM_VERSION = "durable-surface-pair-v1"
DURABLE_SURFACE_RULESET_VERSION = "development-durable-surface-rules-v1"
_NEXT_WORD_RE = re.compile(r"\s+([A-Za-z]+(?:['’][A-Za-z]+)?)")
_ASCII_ELLIPSIS_RE = re.compile(r"(?<![.\d])\.\.\.(?![.\d])")
_UNICODE_ELLIPSIS_RE = re.compile(r"(?<![\d…])…(?![\d…])")
_DASH_BULLET_RE = re.compile(r"(?m)^- (?=\S)")
_STAR_BULLET_RE = re.compile(r"(?m)^\* (?=\S)")
_ORDERED_DOT_RE = re.compile(r"(?m)(?<=^[0-9])\. (?=\S)")
_ORDERED_PAREN_RE = re.compile(r"(?m)(?<=^[0-9])\) (?=\S)")
PERFECT_AUXILIARY_PARTICIPLES = tuple(
    sorted(
        (
            "added",
            "allowed",
            "analyzed",
            "applied",
            "become",
            "been",
            "built",
            "changed",
            "chosen",
            "come",
            "compared",
            "completed",
            "conducted",
            "considered",
            "created",
            "decided",
            "defined",
            "demonstrated",
            "described",
            "designed",
            "determined",
            "developed",
            "discussed",
            "done",
            "established",
            "evaluated",
            "expected",
            "explained",
            "found",
            "generated",
            "given",
            "gone",
            "got",
            "identified",
            "implemented",
            "improved",
            "included",
            "increased",
            "kept",
            "known",
            "learned",
            "left",
            "made",
            "maintained",
            "measured",
            "mentioned",
            "noted",
            "observed",
            "performed",
            "provided",
            "published",
            "put",
            "read",
            "recognized",
            "reduced",
            "relied",
            "removed",
            "reported",
            "required",
            "reviewed",
            "run",
            "said",
            "seen",
            "set",
            "shown",
            "supported",
            "taken",
            "tested",
            "thought",
            "tried",
            "used",
            "verified",
            "worked",
            "written",
        )
    )
)
PERFECT_AUXILIARY_ADVERBS = tuple(
    sorted(
        (
            "already",
            "also",
            "always",
            "carefully",
            "clearly",
            "ever",
            "fully",
            "just",
            "never",
            "now",
            "often",
            "only",
            "previously",
            "recently",
            "sometimes",
            "successfully",
            "yet",
        )
    )
)


class DurableSurfaceConstruction(str, Enum):
    PERFECT_AUXILIARY = "perfect_auxiliary"
    ELLIPSIS = "ellipsis"
    MARKDOWN_UNORDERED_BULLET = "markdown_unordered_bullet"
    MARKDOWN_ORDERED_DELIMITER = "markdown_ordered_delimiter"


_PERFECT_FORM_PAIRS = frozenset(
    frozenset((expanded.casefold(), contracted.casefold()))
    for expanded, contracted in (
        ("I have", "I've"),
        ("you have", "you've"),
        ("we have", "we've"),
        ("they have", "they've"),
    )
)


def _validate_construction_forms(
    construction: DurableSurfaceConstruction,
    first: str,
    second: str,
) -> None:
    if not isinstance(first, str) or not first or not isinstance(second, str) or not second:
        raise ValueError("durable construction forms must be non-empty strings")
    forms = frozenset((first.casefold(), second.casefold()))
    if construction is DurableSurfaceConstruction.PERFECT_AUXILIARY:
        valid = forms in _PERFECT_FORM_PAIRS
    elif construction is DurableSurfaceConstruction.ELLIPSIS:
        valid = forms == frozenset(("...", "…"))
    elif construction is DurableSurfaceConstruction.MARKDOWN_UNORDERED_BULLET:
        valid = forms == frozenset(("- ", "* "))
    elif construction is DurableSurfaceConstruction.MARKDOWN_ORDERED_DELIMITER:
        valid = forms == frozenset((". ", ") "))
    else:
        raise ValueError("unsupported durable construction")
    if not valid:
        raise ValueError("durable rule forms disagree with their construction")


def _require_word_tuple(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique and canonically ordered")
    for value in values:
        require_clean_string(name, value)
        if not value.isalpha() or value != value.lower():
            raise ValueError(f"{name} must contain lowercase alphabetic words")


@dataclass(frozen=True, slots=True)
class DurableSurfaceRule(LiteralTransformRule):
    construction: DurableSurfaceConstruction
    allowed_following_words: tuple[str, ...]
    allowed_following_adverbs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.construction, DurableSurfaceConstruction):
            raise TypeError("construction must be a DurableSurfaceConstruction")
        if self.version != "v1":
            raise ValueError("durable rule version must be v1")
        _validate_construction_forms(self.construction, self.source, self.replacement)
        _require_word_tuple("allowed_following_words", self.allowed_following_words)
        _require_word_tuple("allowed_following_adverbs", self.allowed_following_adverbs)
        contraction_constructions = {DurableSurfaceConstruction.PERFECT_AUXILIARY}
        expected_family = (
            TransformFamily.CONTRACTION
            if self.construction in contraction_constructions
            else TransformFamily.ORTHOGRAPHY
        )
        format_constructions = {
            DurableSurfaceConstruction.MARKDOWN_UNORDERED_BULLET,
            DurableSurfaceConstruction.MARKDOWN_ORDERED_DELIMITER,
        }
        expected_tier = (
            TransformTier.FORMAT
            if self.construction in format_constructions
            else TransformTier.SURFACE
        )
        if self.family is not expected_family or self.tier is not expected_tier:
            raise ValueError("durable rule family or tier disagrees with its construction")
        actual_flags = (
            self.whole_word,
            self.preserve_simple_case,
            self.block_all_caps,
        )
        if actual_flags != (
            (True, True, True)
            if self.construction is DurableSurfaceConstruction.PERFECT_AUXILIARY
            else (False, False, False)
        ):
            raise ValueError("durable rule matching flags disagree with its construction")
        if self.construction is DurableSurfaceConstruction.PERFECT_AUXILIARY:
            if not self.allowed_following_words:
                raise ValueError("perfect-auxiliary rules require a participle allowlist")
        elif self.allowed_following_words or self.allowed_following_adverbs:
            raise ValueError("only perfect-auxiliary rules accept following-word guards")
        LiteralTransformRule.__post_init__(self)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": DURABLE_SURFACE_RULE_ALGORITHM_VERSION,
            "rule_id": self.rule_id,
            "version": self.version,
            "family": self.family.value,
            "tier": self.tier.value,
            "source": self.source,
            "replacement": self.replacement,
            "whole_word": self.whole_word,
            "preserve_simple_case": self.preserve_simple_case,
            "block_all_caps": self.block_all_caps,
            "construction": self.construction.value,
            "allowed_following_words": self.allowed_following_words,
            "allowed_following_adverbs": self.allowed_following_adverbs,
        }

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        source: str,
        replacement: str,
        construction: DurableSurfaceConstruction,
        allowed_following_words: tuple[str, ...] = (),
        allowed_following_adverbs: tuple[str, ...] = (),
    ) -> DurableSurfaceRule:
        contraction = construction is DurableSurfaceConstruction.PERFECT_AUXILIARY
        format_rule = construction in {
            DurableSurfaceConstruction.MARKDOWN_UNORDERED_BULLET,
            DurableSurfaceConstruction.MARKDOWN_ORDERED_DELIMITER,
        }
        words = tuple(allowed_following_words)
        adverbs = tuple(allowed_following_adverbs)
        fields = {
            "rule_id": rule_id,
            "version": "v1",
            "family": (
                TransformFamily.CONTRACTION
                if contraction
                else TransformFamily.ORTHOGRAPHY
            ),
            "tier": TransformTier.FORMAT if format_rule else TransformTier.SURFACE,
            "source": source,
            "replacement": replacement,
            "whole_word": contraction,
            "preserve_simple_case": contraction,
            "block_all_caps": contraction,
            "construction": construction,
            "allowed_following_words": words,
            "allowed_following_adverbs": adverbs,
        }
        payload = {
            "algorithm_version": DURABLE_SURFACE_RULE_ALGORITHM_VERSION,
            **{
                key: value.value if isinstance(value, Enum) else value
                for key, value in fields.items()
            },
        }
        return cls(**fields, rule_hash=sha256_json(payload))

    def pattern(self) -> re.Pattern[str]:
        if self.construction is DurableSurfaceConstruction.ELLIPSIS:
            return _ASCII_ELLIPSIS_RE if self.source == "..." else _UNICODE_ELLIPSIS_RE
        if self.construction is DurableSurfaceConstruction.MARKDOWN_UNORDERED_BULLET:
            return _DASH_BULLET_RE if self.source == "- " else _STAR_BULLET_RE
        if self.construction is DurableSurfaceConstruction.MARKDOWN_ORDERED_DELIMITER:
            return _ORDERED_DOT_RE if self.source == ". " else _ORDERED_PAREN_RE
        return LiteralTransformRule.pattern(self)

    def precondition(self, text: str, start: int, end: int) -> bool:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if start < 0 or end <= start or end > len(text):
            raise ValueError("durable precondition span is outside text")
        if text[start:end].casefold() != self.source.casefold():
            raise ValueError("durable precondition span does not match rule source")
        if self.construction is not DurableSurfaceConstruction.PERFECT_AUXILIARY:
            return True
        first = _NEXT_WORD_RE.match(text, end)
        if first is None:
            return False
        following = first.group(1).replace("’", "'").lower()
        if following in self.allowed_following_adverbs:
            second = _NEXT_WORD_RE.match(text, first.end())
            if second is None:
                return False
            following = second.group(1).replace("’", "'").lower()
        return following in self.allowed_following_words


@dataclass(frozen=True, slots=True)
class DurableSurfacePair:
    pair_id: str
    forward_rule_id: str
    reverse_rule_id: str
    expanded_form: str
    alternate_form: str
    construction: DurableSurfaceConstruction
    allowed_following_words: tuple[str, ...]
    allowed_following_adverbs: tuple[str, ...]
    pair_hash: str

    def __post_init__(self) -> None:
        for name in ("pair_id", "forward_rule_id", "reverse_rule_id"):
            require_clean_string(name, getattr(self, name))
        for name in ("expanded_form", "alternate_form"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(self.construction, DurableSurfaceConstruction):
            raise TypeError("construction must be a DurableSurfaceConstruction")
        _validate_construction_forms(
            self.construction,
            self.expanded_form,
            self.alternate_form,
        )
        _require_word_tuple("allowed_following_words", self.allowed_following_words)
        _require_word_tuple("allowed_following_adverbs", self.allowed_following_adverbs)
        require_sha256("pair_hash", self.pair_hash)
        if self.pair_hash != sha256_json(self.payload()):
            raise ValueError("durable surface pair hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        pair_id: str,
        forward_rule_id: str,
        reverse_rule_id: str,
        expanded_form: str,
        alternate_form: str,
        construction: DurableSurfaceConstruction,
        allowed_following_words: tuple[str, ...] = (),
        allowed_following_adverbs: tuple[str, ...] = (),
    ) -> DurableSurfacePair:
        fields = {
            "pair_id": pair_id,
            "forward_rule_id": forward_rule_id,
            "reverse_rule_id": reverse_rule_id,
            "expanded_form": expanded_form,
            "alternate_form": alternate_form,
            "construction": construction,
            "allowed_following_words": tuple(allowed_following_words),
            "allowed_following_adverbs": tuple(allowed_following_adverbs),
        }
        payload = {
            "algorithm_version": DURABLE_SURFACE_PAIR_ALGORITHM_VERSION,
            **{
                key: value.value if isinstance(value, Enum) else value
                for key, value in fields.items()
            },
        }
        return cls(**fields, pair_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": DURABLE_SURFACE_PAIR_ALGORITHM_VERSION,
            "pair_id": self.pair_id,
            "forward_rule_id": self.forward_rule_id,
            "reverse_rule_id": self.reverse_rule_id,
            "expanded_form": self.expanded_form,
            "alternate_form": self.alternate_form,
            "construction": self.construction.value,
            "allowed_following_words": self.allowed_following_words,
            "allowed_following_adverbs": self.allowed_following_adverbs,
        }


def durable_surface_pairs() -> tuple[DurableSurfacePair, ...]:
    rows = (
        ("perfect-i-have", "I have", "I've"),
        ("perfect-you-have", "you have", "you've"),
        ("perfect-we-have", "we have", "we've"),
        ("perfect-they-have", "they have", "they've"),
    )
    perfect = tuple(
        DurableSurfacePair.create(
            pair_id=pair_id,
            forward_rule_id=f"durable-{pair_id}-contract",
            reverse_rule_id=f"durable-{pair_id}-expand",
            expanded_form=expanded,
            alternate_form=contracted,
            construction=DurableSurfaceConstruction.PERFECT_AUXILIARY,
            allowed_following_words=PERFECT_AUXILIARY_PARTICIPLES,
            allowed_following_adverbs=PERFECT_AUXILIARY_ADVERBS,
        )
        for pair_id, expanded, contracted in rows
    )
    remaining = (
        DurableSurfacePair.create(
            pair_id="ellipsis",
            forward_rule_id="durable-ellipsis-unicode",
            reverse_rule_id="durable-ellipsis-ascii",
            expanded_form="...",
            alternate_form="…",
            construction=DurableSurfaceConstruction.ELLIPSIS,
        ),
        DurableSurfacePair.create(
            pair_id="markdown-unordered-bullet",
            forward_rule_id="durable-markdown-bullet-star",
            reverse_rule_id="durable-markdown-bullet-dash",
            expanded_form="- ",
            alternate_form="* ",
            construction=DurableSurfaceConstruction.MARKDOWN_UNORDERED_BULLET,
        ),
        DurableSurfacePair.create(
            pair_id="markdown-ordered-delimiter",
            forward_rule_id="durable-markdown-ordered-paren",
            reverse_rule_id="durable-markdown-ordered-dot",
            expanded_form=". ",
            alternate_form=") ",
            construction=DurableSurfaceConstruction.MARKDOWN_ORDERED_DELIMITER,
        ),
    )
    return (*perfect, *remaining)


def development_durable_surface_rules() -> tuple[DurableSurfaceRule, ...]:
    output = []
    for pair in durable_surface_pairs():
        common = {
            "construction": pair.construction,
            "allowed_following_words": pair.allowed_following_words,
            "allowed_following_adverbs": pair.allowed_following_adverbs,
        }
        output.append(
            DurableSurfaceRule.create(
                rule_id=pair.forward_rule_id,
                source=pair.expanded_form,
                replacement=pair.alternate_form,
                **common,
            )
        )
        output.append(
            DurableSurfaceRule.create(
                rule_id=pair.reverse_rule_id,
                source=pair.alternate_form,
                replacement=pair.expanded_form,
                **common,
            )
        )
    return tuple(output)


@dataclass(frozen=True, slots=True)
class DurableSemanticSite:
    group_id: str
    site_id: str
    direction: str

    def __post_init__(self) -> None:
        require_clean_string("group_id", self.group_id)
        require_clean_string("site_id", self.site_id)
        if self.direction not in ("forward", "reverse"):
            raise ValueError("direction must be forward or reverse")


def durable_semantic_site(
    text: str,
    candidate: TransformCandidate,
) -> DurableSemanticSite | None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(candidate, TransformCandidate):
        raise TypeError("candidate must be a TransformCandidate")
    rules = {value.rule_id: value for value in development_durable_surface_rules()}
    pairs = durable_surface_pairs()
    resolved = None
    for pair in pairs:
        if candidate.rule_id == pair.forward_rule_id:
            resolved = (pair, "forward")
            break
        if candidate.rule_id == pair.reverse_rule_id:
            resolved = (pair, "reverse")
            break
    if resolved is None:
        return None
    pair, direction = resolved
    rule = rules[candidate.rule_id]
    if candidate.rule_hash != rule.rule_hash:
        raise ValueError("durable candidate rule hash drifted")
    occurrences = []
    for rule_id in (pair.forward_rule_id, pair.reverse_rule_id):
        occurrence_rule = rules[rule_id]
        for match in occurrence_rule.pattern().finditer(text):
            if occurrence_rule.precondition(text, match.start(), match.end()):
                occurrences.append((match.start(), match.end(), rule_id))
    occurrences.sort()
    matching = tuple(
        index
        for index, value in enumerate(occurrences)
        if value[0] == candidate.start and value[1] == candidate.end
    )
    if len(matching) != 1:
        raise ValueError("durable candidate does not resolve to one semantic occurrence")
    return DurableSemanticSite(pair.pair_id, f"{pair.pair_id}:{matching[0]}", direction)


def durable_surface_inverse_semantic_resolver(
    state: Any,
    candidate: TransformCandidate,
) -> Any:
    text = getattr(state, "text", None)
    if not isinstance(text, str):
        raise TypeError("state must expose string text")
    site = durable_semantic_site(text, candidate)
    if site is None:
        return None
    from ..scheduling.context_survival import InverseSemanticOperation

    return InverseSemanticOperation(site.group_id, site.site_id, site.direction)


def portfolio_inverse_semantic_resolver(
    state: Any,
    candidate: TransformCandidate,
) -> Any:
    contraction = contraction_inverse_semantic_resolver(state, candidate)
    if contraction is not None:
        return contraction
    return durable_surface_inverse_semantic_resolver(state, candidate)
