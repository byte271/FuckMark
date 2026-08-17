from __future__ import annotations

from .rules import LiteralTransformRule
from .schema import TransformFamily, TransformTier


MECHANISM_STRESS_RULESET_VERSION = "mechanism-stress-rules-v1"


def mechanism_stress_rules() -> tuple[LiteralTransformRule, ...]:
    contraction_pairs = (
        ("stress-contract-is-not", "is not", "isn't"),
        ("stress-contract-are-not", "are not", "aren't"),
        ("stress-contract-was-not", "was not", "wasn't"),
        ("stress-contract-were-not", "were not", "weren't"),
        ("stress-contract-has-not", "has not", "hasn't"),
        ("stress-contract-have-not", "have not", "haven't"),
        ("stress-contract-had-not", "had not", "hadn't"),
        ("stress-contract-would-not", "would not", "wouldn't"),
        ("stress-contract-could-not", "could not", "couldn't"),
        ("stress-contract-must-not", "must not", "mustn't"),
        ("stress-contract-we-are", "we are", "we're"),
        ("stress-contract-they-are", "they are", "they're"),
        ("stress-contract-you-are", "you are", "you're"),
        ("stress-contract-it-is", "it is", "it's"),
        ("stress-contract-that-is", "that is", "that's"),
        ("stress-contract-there-is", "there is", "there's"),
        ("stress-contract-i-am", "I am", "I'm"),
    )
    phrase_pairs = (
        ("stress-reduce-in-order-to", "in order to", "to"),
        ("stress-rephrase-in-other-words", "in other words,", "that is,"),
        ("stress-rephrase-for-example", "for example,", "for instance,"),
        ("stress-rephrase-as-a-result", "as a result,", "therefore,"),
    )
    contractions = tuple(
        LiteralTransformRule.create(
            rule_id=rule_id,
            version="v1",
            family=TransformFamily.CONTRACTION,
            tier=TransformTier.EXPERIMENTAL,
            source=source,
            replacement=replacement,
        )
        for rule_id, source, replacement in contraction_pairs
    )
    phrases = tuple(
        LiteralTransformRule.create(
            rule_id=rule_id,
            version="v1",
            family=TransformFamily.LEXICAL_TEMPLATE,
            tier=TransformTier.EXPERIMENTAL,
            source=source,
            replacement=replacement,
        )
        for rule_id, source, replacement in phrase_pairs
    )
    return contractions + phrases
