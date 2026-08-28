from __future__ import annotations


PRODUCT_DOMAIN_ID = "ordinary-english-ascii-v1"
_ALLOWED = frozenset({9, 10, 13, *range(0x20, 0x7F)})
PRODUCT_MAX_INPUT_CHARS = 2_000_000


def is_supported_product_domain_v1(text: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return all(ord(character) in _ALLOWED for character in text)


def first_unsupported_product_domain_v1(text: str) -> tuple[int, int] | None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    for index, character in enumerate(text):
        codepoint = ord(character)
        if codepoint not in _ALLOWED:
            return index, codepoint
    return None
