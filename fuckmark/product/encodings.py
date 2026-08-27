from __future__ import annotations


PRODUCT_TEXT_ENCODING = "utf-8"
PRODUCT_ENCODING_POLICY_VERSION = "product-text-encoding-v1"
_ALIASES = {
    "utf8": "utf-8",
    "utf-8": "utf-8",
    "latin1": "latin-1",
    "latin-1": "latin-1",
    "iso8859-1": "latin-1",
    "iso-8859-1": "latin-1",
    "ascii": "ascii",
    "us-ascii": "ascii",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
}
UNSUPPORTED_PRODUCT_ENCODINGS = frozenset({"latin-1", "ascii", "cp1252"})


def canonical_product_encoding_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("encoding name must be a non-empty string")
    folded = name.strip().casefold().replace("_", "-")
    return _ALIASES.get(folded, folded)


def is_supported_product_encoding(name: str) -> bool:
    return canonical_product_encoding_name(name) == PRODUCT_TEXT_ENCODING


def require_supported_product_encoding(name: str) -> str:
    canonical = canonical_product_encoding_name(name)
    if canonical != PRODUCT_TEXT_ENCODING:
        raise ValueError(f"unsupported product encoding {name!r}; only {PRODUCT_TEXT_ENCODING} is supported")
    return canonical


def encoding_roundtrip_survives(text: str, encoding: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    canonical = canonical_product_encoding_name(encoding)
    try:
        return text.encode(canonical).decode(canonical) == text
    except (LookupError, UnicodeError):
        return False
