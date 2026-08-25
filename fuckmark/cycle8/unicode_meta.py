from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from ..cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from ..sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters


UNICODE_PROPERTY_SCAN_VERSION = "cycle8-unicode-property-scan-v1"

DEFAULT_IGNORABLE_RANGES_V1 = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)

_BIDI_OVERRIDE = frozenset({"RLE", "LRE", "RLO", "LRO", "RLI", "LRI", "FSI", "PDF", "PDI"})
_VISIBLE_CATEGORIES = frozenset(
    {
        "Lu",
        "Ll",
        "Lt",
        "Lm",
        "Lo",
        "Nd",
        "Nl",
        "No",
        "Pc",
        "Pd",
        "Ps",
        "Pe",
        "Pi",
        "Pf",
        "Po",
        "Sm",
        "Sc",
        "Sk",
        "So",
        "Zs",
        "Zl",
        "Zp",
        "Mc",
    }
)


def is_default_ignorable_v1(codepoint: int) -> bool:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    return any(start <= codepoint <= end for start, end in DEFAULT_IGNORABLE_RANGES_V1)


def iter_default_ignorable_codepoints_v1() -> tuple[int, ...]:
    values: list[int] = []
    for start, end in DEFAULT_IGNORABLE_RANGES_V1:
        values.extend(range(start, end + 1))
    return tuple(value for value in values if 0 <= value <= 0x10FFFF and not (0xD800 <= value <= 0xDFFF))


def codepoint_properties(codepoint: int) -> dict[str, object]:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    if codepoint < 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
        raise ValueError("codepoint must be a Unicode scalar value")
    character = chr(codepoint)
    try:
        name = unicodedata.name(character)
    except ValueError:
        name = ""
    category = unicodedata.category(character)
    combining = unicodedata.combining(character)
    bidirectional = unicodedata.bidirectional(character)
    east_asian_width = unicodedata.east_asian_width(character)
    nfc = unicodedata.normalize("NFC", character)
    nfd = unicodedata.normalize("NFD", character)
    nfkc = unicodedata.normalize("NFKC", character)
    nfkd = unicodedata.normalize("NFKD", character)
    utf8 = character.encode("utf-8")
    cf_stripped = strip_unicode_format_characters(character)
    collapsed = collapse_horizontal_ascii_whitespace(f"A{character}B")
    combined = collapse_horizontal_ascii_whitespace(
        strip_unicode_format_characters(nfkc_normalize(f"A{character}B"))
    )
    return {
        "codepoint": codepoint,
        "label": f"U+{codepoint:04X}",
        "name": name,
        "category": category,
        "combining_class": combining,
        "bidirectional_class": bidirectional,
        "east_asian_width": east_asian_width,
        "default_ignorable": is_default_ignorable_v1(codepoint),
        "nfc": nfc,
        "nfd": nfd,
        "nfkc": nfkc,
        "nfkd": nfkd,
        "nfc_stable": nfc == character,
        "nfd_stable": nfd == character,
        "nfkc_stable": nfkc == character,
        "nfkd_stable": nfkd == character,
        "cf_strip_survives": cf_stripped == character,
        "whitespace_collapse_survives": collapsed == f"A{character}B",
        "combined_ws_nfkc_cf_survives": combined == f"A{character}B",
        "utf8_byte_length": len(utf8),
        "assigned": bool(name),
        "bidi_override": bidirectional in _BIDI_OVERRIDE,
        "visible_category": category in _VISIBLE_CATEGORIES,
        "control_category": category in {"Cc", "Cs"},
        "format_category": category == "Cf",
        "nonspacing_mark": category == "Mn",
    }


def classify_carrier_hypothesis(properties: dict[str, object]) -> str:
    if properties["control_category"] or properties["bidi_override"] or properties["visible_category"]:
        return "REJECTED_RENDERING_OR_CONTROL_RISK"
    if not properties["assigned"]:
        return "REJECTED_UNASSIGNED"
    if properties["format_category"]:
        return "DIAGNOSTIC_CF"
    if not properties["default_ignorable"]:
        return "REJECTED_NOT_DEFAULT_IGNORABLE"
    if not properties["nfkc_stable"] or not properties["nfc_stable"]:
        return "REJECTED_NORMALIZATION"
    if not properties["whitespace_collapse_survives"]:
        return "REJECTED_WHITESPACE_COLLAPSE"
    if properties["nonspacing_mark"] and properties["cf_strip_survives"] and properties["combined_ws_nfkc_cf_survives"]:
        return "DURABLE_TRACK_CANDIDATE"
    return "HYPOTHESIS"


def audit_codepoints(codepoints: Iterable[int]) -> tuple[dict[str, object], ...]:
    rows = []
    for codepoint in codepoints:
        properties = codepoint_properties(codepoint)
        properties["classification"] = classify_carrier_hypothesis(properties)
        rows.append(properties)
    return tuple(rows)
