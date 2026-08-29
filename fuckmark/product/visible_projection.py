from __future__ import annotations

from collections.abc import Iterable

from .._validation import require_int


VISIBLE_PROJECTION_ALGORITHM_VERSION = "fuckmark-visible-projection-v1"
PRODUCT_CONTRACT_ID = "fuckmark-user-visible-invariance-v1"


def product_approved_carriers_v1() -> frozenset[int]:
    from ..cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS

    return frozenset(LETTER_MIX_APPROVED_CARRIERS)


def normalize_approved_carriers(carriers: Iterable[int] | None) -> frozenset[int]:
    if carriers is None:
        return product_approved_carriers_v1()
    values = frozenset(carriers)
    for value in values:
        require_int("carrier", value)
        if value < 0 or value > 0x10FFFF:
            raise ValueError("carrier must be a Unicode scalar value")
        if 0xD800 <= value <= 0xDFFF:
            raise ValueError("carrier must not be a surrogate")
    return values


def project_visible_v1(text: str, approved_carriers: Iterable[int] | None = None) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    approved = normalize_approved_carriers(approved_carriers)
    if not approved:
        return text
    return "".join(character for character in text if ord(character) not in approved)


def is_carrier_insertion_v1(
    original: str,
    transformed: str,
    approved_carriers: Iterable[int] | None = None,
) -> bool:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    approved = normalize_approved_carriers(approved_carriers)
    index = 0
    original_length = len(original)
    for character in transformed:
        if index < original_length and character == original[index]:
            index += 1
            continue
        if ord(character) in approved:
            continue
        return False
    return index == original_length
