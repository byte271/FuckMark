from __future__ import annotations

from .._validation import require_clean_string
from ..hashing import sha256_text
from ..sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters


WHITESPACE_COLLAPSE_VERSION = "whitespace-collapse-v1"
WHITESPACE_COLLAPSE_SPEC_ID = "ascii-horizontal-run-collapse-preserve-newlines-v1"

CYCLE7_SANITIZER_VARIANT_IDS = (
    "raw",
    "nfkc",
    "cf_strip",
    "nfkc_cf_strip",
    "ws_collapse",
    "ws_collapse_nfkc_cf_strip",
)

_HORIZONTAL = frozenset((" ", "\t"))


def normalize_newlines(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def collapse_horizontal_ascii_whitespace(text: str) -> str:
    """Collapse runs of U+0020 and U+0009 to a single U+0020 per line.

    Specification (whitespace-collapse-v1):
    - Convert CR LF and CR to LF first.
    - Preserve LF as line structure. Do not join lines.
    - On each line, replace every maximal run of SPACE (U+0020) and HT (U+0009)
      with exactly one SPACE.
    - Do not trim leftover single leading or trailing spaces.
    - Do not collapse other Unicode whitespace (including NBSP U+00A0).
    - Do not collapse vertical whitespace other than the CR/LF normalization above.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    lines: list[str] = []
    for line in normalize_newlines(text).split("\n"):
        pieces: list[str] = []
        index = 0
        length = len(line)
        while index < length:
            character = line[index]
            if character in _HORIZONTAL:
                pieces.append(" ")
                index += 1
                while index < length and line[index] in _HORIZONTAL:
                    index += 1
                continue
            pieces.append(character)
            index += 1
        lines.append("".join(pieces))
    return "\n".join(lines)


def sanitize_cycle7_variant(variant_id: str, text: str) -> str:
    require_clean_string("variant_id", variant_id)
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if variant_id == "raw":
        return text
    if variant_id == "nfkc":
        return nfkc_normalize(text)
    if variant_id == "cf_strip":
        return strip_unicode_format_characters(text)
    if variant_id == "nfkc_cf_strip":
        return strip_unicode_format_characters(nfkc_normalize(text))
    if variant_id == "ws_collapse":
        return collapse_horizontal_ascii_whitespace(text)
    if variant_id == "ws_collapse_nfkc_cf_strip":
        collapsed = collapse_horizontal_ascii_whitespace(text)
        normalized = strip_unicode_format_characters(nfkc_normalize(collapsed))
        return collapse_horizontal_ascii_whitespace(normalized)
    raise ValueError(f"unknown Cycle 7 sanitizer variant id: {variant_id}")


def whitespace_collapse_identity_hash() -> str:
    return sha256_text(
        f"{WHITESPACE_COLLAPSE_VERSION}:{WHITESPACE_COLLAPSE_SPEC_ID}:"
        f"{','.join(CYCLE7_SANITIZER_VARIANT_IDS)}"
    )
