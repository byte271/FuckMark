from __future__ import annotations

from .rules import SurfaceSpacingRule


SURFACE_RULESET_ALGORITHM_VERSION = "development-surface-rules-v4"


def development_surface_rules() -> tuple[SurfaceSpacingRule, ...]:
    words = (
        "is",
        "of",
        "to",
        "the",
        "and",
        "in",
        "for",
        "on",
        "with",
        "as",
        "from",
        "that",
        "this",
        "was",
        "are",
        "be",
        "can",
        "will",
        "have",
        "has",
        "not",
        "but",
        "or",
        "by",
        "at",
        "it",
        "we",
        "you",
        "they",
    )
    punctuation = (
        ("period", ". "),
        ("comma", ", "),
        ("semicolon", "; "),
        ("colon", ": "),
        ("question", "? "),
        ("exclamation", "! "),
    )
    word_rules = tuple(
        SurfaceSpacingRule.create(
            rule_id=f"surface-space-after-{word}",
            version="v1",
            source=word,
            replacement=word + " ",
        )
        for word in words
    )
    punctuation_rules = tuple(
        SurfaceSpacingRule.create(
            rule_id=f"surface-space-after-{name}",
            version="v1",
            source=source,
            replacement=source + " ",
        )
        for name, source in punctuation
    )
    return (*word_rules, *punctuation_rules)
