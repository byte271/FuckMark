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


COVERAGE_COMPLETION_EXTENSION_ALGORITHM_VERSION = "coverage-completion-extension-words-v1"


def coverage_completion_extension_words() -> tuple[str, ...]:
    return (
        "an",
        "he",
        "she",
        "his",
        "her",
        "its",
        "our",
        "their",
        "them",
        "him",
        "us",
        "me",
        "my",
        "your",
        "if",
        "when",
        "where",
        "which",
        "who",
        "what",
        "how",
        "why",
        "because",
        "so",
        "than",
        "then",
        "there",
        "here",
        "all",
        "any",
        "each",
        "more",
        "most",
        "some",
        "such",
        "only",
        "very",
        "just",
        "also",
        "into",
        "about",
        "over",
        "under",
        "after",
        "before",
        "between",
        "during",
        "through",
        "without",
        "while",
        "do",
        "does",
        "been",
        "being",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "were",
        "one",
        "even",
        "still",
        "often",
    )


def coverage_completion_surface_rules() -> tuple[SurfaceSpacingRule, ...]:
    base = development_surface_rules()
    base_ids = {rule.rule_id for rule in base}
    base_words = {rule.source for rule in base if rule.source.isalpha()}
    extension_words = coverage_completion_extension_words()
    if len(set(extension_words)) != len(extension_words):
        raise ValueError("coverage completion extension words must be unique")
    if any(word in base_words for word in extension_words):
        raise ValueError("coverage completion extension words must not duplicate the base surface list")
    if any(not word.isalpha() or word != word.lower() or len(word) < 2 for word in extension_words):
        raise ValueError("coverage completion extension words must be lowercase alphabetic words of length >= 2")
    extension_rules = tuple(
        SurfaceSpacingRule.create(
            rule_id=f"surface-space-after-{word}",
            version="v1",
            source=word,
            replacement=word + " ",
        )
        for word in extension_words
    )
    if any(rule.rule_id in base_ids for rule in extension_rules):
        raise ValueError("coverage completion extension rule IDs must not collide with base rules")
    return (*base, *extension_rules)
