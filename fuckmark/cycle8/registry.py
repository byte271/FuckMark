from __future__ import annotations

from collections.abc import Sequence

from ..product.carriers import InvisibleCarrierAfterAsciiLetterRule, space_carrier_rule
from ..product.registry import ProductTransformRegistry
from ..transforms.schema import TransformFamily


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


def cycle8_letter_carrier_registry(codepoint: int, identifiers: Sequence[str] = ()) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (InvisibleCarrierAfterAsciiLetterRule.create(codepoint),),
        identifiers,
        approved_carriers=(codepoint,),
    )


def cycle8_combined_carrier_registry(codepoint: int, identifiers: Sequence[str] = ()) -> ProductTransformRegistry:
    return ProductTransformRegistry(
        (space_carrier_rule(codepoint), InvisibleCarrierAfterAsciiLetterRule.create(codepoint)),
        identifiers,
        approved_carriers=(codepoint,),
    )


def select_nonoverlapping_candidate_ids(enumeration) -> tuple[str, ...]:
    selected: list[str] = []
    occupied_until = 0
    for candidate in enumeration.candidates:
        if candidate.start < occupied_until:
            continue
        if candidate.family is not TransformFamily.ORTHOGRAPHY:
            continue
        selected.append(candidate.candidate_id)
        occupied_until = candidate.end
    return tuple(selected)


def apply_all_candidates(registry: ProductTransformRegistry, text: str) -> str:
    enumeration = registry.enumerate(text)
    selected = select_nonoverlapping_candidate_ids(enumeration)
    if not selected:
        return text
    return registry.apply(enumeration, selected).output_text
