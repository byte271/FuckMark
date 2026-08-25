from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .lexical_rules import LexicalTemplateRule
from .quote_policy import (
    QUOTE_SAFE_SURFACE_POLICY_ID,
    is_quote_safe_surface_rule,
    is_surface_editable_quotation,
    quotation_spans,
)
from .rules import (
    GeneralWordLeadingSpacingRule,
    GeneralWordSpacingRule,
    LiteralTransformRule,
    SurfaceSpacingRule,
)
from .schema import TransformFamily
from .syntax_rules import SyntaxTemplateRule

if TYPE_CHECKING:
    from .trace import TransformOperation


CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID = "quote-container-durable-v1"
CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID = "quote-container-durable-or-spacing-v1"

QUOTE_INTERIOR_POLICY_IDS = frozenset(
    {
        QUOTE_SAFE_SURFACE_POLICY_ID,
        CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID,
        CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID,
    }
)

_DURABLE_RULE_PREFIXES = (
    "contract-",
    "expand-",
    "cycle7-contract-",
    "cycle7-expand-",
    "cycle7-ortho-",
    "lexical-",
    "syntax-",
)


def is_cycle7_quote_durable_rule(rule: object) -> bool:
    if isinstance(rule, (GeneralWordLeadingSpacingRule, GeneralWordSpacingRule, SurfaceSpacingRule)):
        return False
    if isinstance(rule, LiteralTransformRule):
        if rule.family is TransformFamily.CONTRACTION:
            return getattr(rule, "rule_id", "").startswith(
                ("contract-", "expand-", "cycle7-contract-", "cycle7-expand-")
            )
        return rule.family is TransformFamily.ORTHOGRAPHY and getattr(rule, "rule_id", "").startswith(
            "cycle7-ortho-"
        )
    return isinstance(rule, (LexicalTemplateRule, SyntaxTemplateRule))


def is_cycle7_quote_durable_rule_id(rule_id: str) -> bool:
    if not isinstance(rule_id, str) or not rule_id:
        return False
    return rule_id.startswith(_DURABLE_RULE_PREFIXES)


def quote_interior_rule_allowed(quote_policy_id: str, rule: object) -> bool:
    if quote_policy_id == QUOTE_SAFE_SURFACE_POLICY_ID:
        return is_quote_safe_surface_rule(rule)
    if quote_policy_id == CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID:
        return is_cycle7_quote_durable_rule(rule)
    if quote_policy_id == CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID:
        return is_quote_safe_surface_rule(rule) or is_cycle7_quote_durable_rule(rule)
    return False


def _quote_overlaps_for_operation(
    quotes: Sequence[Any],
    operation: TransformOperation,
) -> tuple[Any, ...]:
    return tuple(
        span
        for span in quotes
        if operation.source_start < span.end and span.start < operation.source_end
    )


def validate_cycle7_quote_operations(
    source_text: str,
    operations: Sequence[TransformOperation],
    quote_policy_id: str,
) -> None:
    from .protected import ProtectedSpanExtractor

    if quote_policy_id not in (
        CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID,
        CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID,
    ):
        raise ValueError("unsupported Cycle 7 quotation protection policy")
    manifest = ProtectedSpanExtractor().extract(source_text)
    quotes = quotation_spans(manifest.spans)
    mixed = quote_policy_id == CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID
    for operation in operations:
        overlaps = _quote_overlaps_for_operation(quotes, operation)
        if not overlaps:
            continue
        if len(overlaps) != 1 or not is_surface_editable_quotation(overlaps[0]):
            raise ValueError("quote-safe operation must stay inside one quotation container")
        quote = overlaps[0]
        if operation.source_start <= quote.start or operation.source_end >= quote.end:
            raise ValueError("quote-safe operation must not alter quotation delimiters")
        spacing = operation.rule_id.startswith("surface-space-")
        durable = is_cycle7_quote_durable_rule_id(operation.rule_id)
        if mixed and spacing:
            if operation.after_text not in (
                operation.before_text + " ",
                " " + operation.before_text,
            ):
                raise ValueError("quote-safe surface operation must add exactly one ASCII space")
            continue
        if not durable:
            raise ValueError("only durable Cycle 7 rules may operate inside quotations under this policy")
        if operation.after_text == operation.before_text:
            raise ValueError("quote-safe durable operation must change the quoted interior")
        if operation.after_text in (
            operation.before_text + " ",
            " " + operation.before_text,
        ) and operation.after_text.replace(" ", "") == operation.before_text.replace(" ", ""):
            raise ValueError("quote-safe durable policy must not use spacing-only rewrites")
