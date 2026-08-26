from __future__ import annotations

from collections.abc import Sequence

from ..product.carriers import (
    InvisibleCarrierAfterAsciiLetterRule,
    InvisibleCarrierAfterWordFinalAsciiLetterRule,
    space_carrier_rule,
)
from ..product.carrier_invariants import WORD_SIGNATURE_SOURCE_VISIBLE
from ..product.invariants import validate_user_visible_invariants
from ..product.registry import ProductTransformRegistry
from ..transforms.cycle7_quote_policy import (
    PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID,
    QUOTE_INTERIOR_POLICY_IDS,
)
from ..transforms.schema import InvariantStatus, TransformFamily


LETTER_CARRIER_MAX_SELECTED = 192


def cycle8_space_carrier_registry(
    codepoint: int,
    identifiers: Sequence[str] = (),
    *,
    repeats: int = 1,
) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (space_carrier_rule(codepoint, repeats),),
        identifiers,
        approved_carriers=(codepoint,),
    )


def cycle8_letter_carrier_registry(
    codepoint: int,
    identifiers: Sequence[str] = (),
    *,
    max_selected: int | None = LETTER_CARRIER_MAX_SELECTED,
) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (InvisibleCarrierAfterAsciiLetterRule.create(codepoint),),
        identifiers,
        approved_carriers=(codepoint,),
        quote_policy_id=PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID,
        word_signature_source=WORD_SIGNATURE_SOURCE_VISIBLE,
        max_selected=max_selected,
    )


def cycle8_combined_carrier_registry(codepoint: int, identifiers: Sequence[str] = ()) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (space_carrier_rule(codepoint), InvisibleCarrierAfterAsciiLetterRule.create(codepoint)),
        identifiers,
        approved_carriers=(codepoint,),
    )


def cycle8_space_wordfinal_carrier_registry(
    codepoint: int,
    identifiers: Sequence[str] = (),
    *,
    repeats: int = 1,
) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (
            space_carrier_rule(codepoint, repeats),
            InvisibleCarrierAfterWordFinalAsciiLetterRule.create(codepoint),
        ),
        identifiers,
        approved_carriers=(codepoint,),
    )


def _compose_selected(text: str, selected) -> str:
    chunks: list[str] = []
    cursor = 0
    for candidate in selected:
        chunks.append(text[cursor:candidate.start])
        chunks.append(candidate.replacement_text)
        cursor = candidate.end
    chunks.append(text[cursor:])
    return "".join(chunks)


def select_nonoverlapping_candidate_ids(
    enumeration,
    registry: ProductTransformRegistry | None = None,
    *,
    max_selected: int | None = None,
) -> tuple[str, ...]:
    cap = max_selected
    if cap is None and registry is not None:
        cap = getattr(registry, "max_selected", None)
    visible_words = (
        registry is not None and getattr(registry, "word_signature_source", None) == WORD_SIGNATURE_SOURCE_VISIBLE
    )
    selected: list[str] = []
    selected_candidates: list = []
    occupied_until = 0
    for candidate in enumeration.candidates:
        if candidate.start < occupied_until:
            continue
        if candidate.family is not TransformFamily.ORTHOGRAPHY:
            continue
        trial_ids = (*selected, candidate.candidate_id)
        if registry is not None and visible_words:
            trial = _compose_selected(enumeration.input_text, (*selected_candidates, candidate))
            report = registry._trial_invariants(
                enumeration.input_text,
                trial,
                registry.identifiers,
                enumeration.protected_manifest.user_ranges,
                include_quotations=registry.quote_policy_id not in QUOTE_INTERIOR_POLICY_IDS,
            )
            if report.status is not InvariantStatus.PASS:
                continue
            visible = validate_user_visible_invariants(
                enumeration.input_text,
                trial,
                registry.approved_carriers,
            )
            if visible.status is not InvariantStatus.PASS:
                continue
        elif registry is not None:
            try:
                registry.apply(enumeration, trial_ids)
            except ValueError:
                continue
        selected.append(candidate.candidate_id)
        selected_candidates.append(candidate)
        occupied_until = candidate.end
        if cap is not None and len(selected) >= cap:
            break
    return tuple(selected)


def apply_all_candidates(registry: ProductTransformRegistry, text: str) -> str:
    enumeration = registry.enumerate(text)
    selected = select_nonoverlapping_candidate_ids(enumeration, registry=registry)
    if not selected:
        return text
    return registry.apply(enumeration, selected).output_text
