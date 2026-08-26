from __future__ import annotations


PRODUCT_DOMAIN_ID = "ordinary-english-ascii-v1"
_ALLOWED = frozenset({9, 10, 13, *range(0x20, 0x7F)})


def is_supported_product_domain_v1(text: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return all(ord(character) in _ALLOWED for character in text)
