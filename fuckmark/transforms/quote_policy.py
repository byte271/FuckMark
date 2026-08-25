from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .protected_artifacts import ProtectedSpan
from .rules import GeneralWordLeadingSpacingRule, GeneralWordSpacingRule, SurfaceSpacingRule
from .schema import ProtectedSpanKind

if TYPE_CHECKING:
    from .trace import TransformOperation


BLANKET_QUOTE_PROTECTION_POLICY_ID = "blanket-quotation-exact-v1"
QUOTE_SAFE_SURFACE_POLICY_ID = "quote-container-surface-spacing-v1"


def quotation_spans(spans: Sequence[ProtectedSpan]) -> tuple[ProtectedSpan, ...]:
    return tuple(span for span in spans if ProtectedSpanKind.QUOTATION in span.kinds)


def is_surface_editable_quotation(span: ProtectedSpan) -> bool:
    text = span.exact_text
    if len(text) < 2:
        return False
    return (
        (text.startswith('"') and (text.endswith('"') or text.count('"') == 1))
        or (text.startswith("“") and (text.endswith("”") or "”" not in text))
        or (text.startswith("'") and text.endswith("'"))
        or (text.startswith("‘") and text.endswith("’"))
    )


def is_quote_safe_surface_rule(rule: object) -> bool:
    return isinstance(
        rule,
        (GeneralWordLeadingSpacingRule, GeneralWordSpacingRule, SurfaceSpacingRule),
    ) and getattr(rule, "rule_id", "").startswith("surface-space-")


def validate_quote_safe_surface_operations(
    source_text: str,
    operations: Sequence[TransformOperation],
) -> None:
    from .protected import ProtectedSpanExtractor

    manifest = ProtectedSpanExtractor().extract(source_text)
    quotes = quotation_spans(manifest.spans)
    for operation in operations:
        overlaps = tuple(
            span
            for span in quotes
            if operation.source_start < span.end and span.start < operation.source_end
        )
        if not overlaps:
            continue
        if len(overlaps) != 1 or not is_surface_editable_quotation(overlaps[0]):
            raise ValueError("quote-safe operation must stay inside one quotation container")
        quote = overlaps[0]
        if operation.source_start <= quote.start or operation.source_end >= quote.end:
            raise ValueError("quote-safe operation must not alter quotation delimiters")
        if not operation.rule_id.startswith("surface-space-"):
            raise ValueError("only surface-spacing rules may operate inside quotations")
        if operation.after_text not in (
            operation.before_text + " ",
            " " + operation.before_text,
        ):
            raise ValueError("quote-safe surface operation must add exactly one ASCII space")
