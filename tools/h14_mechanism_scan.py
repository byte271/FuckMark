from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path

from fuckmark.cycle8.control_carrier import (
    CONTROL_MIX_ELIGIBLE_CODEPOINTS,
    HOSTILE_CONTROL_CODEPOINTS,
    LAYOUT_CONTROL_CODEPOINTS,
    required_sanitizers_keep,
)
from fuckmark.cycle8.post_sanitizer_extended import (
    H14_RESEARCH_EXTRA_INSTALL,
    is_simple_empty_true_type_glyph,
)
from fuckmark.cycle8.unicode_meta import is_default_ignorable_v1
from fuckmark.product.roundtrip import display_column_width
from fuckmark.sanitizer_robustness import strip_unicode_format_characters

DEJAVU_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
SOURCE = "I do not agree."
OFFICIAL_DI_RANGES_UCD15 = (
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
NAME_NEEDLES = ("FILLER", "INVISIBLE", "BLANK", "JOINER", "TAG ", " TAG", "PAD", "EMPTY", "VOID", "NULL")
INTERESTING_SINGLETONS = (
    0x00A0,
    0x00AD,
    0x034F,
    0x115F,
    0x1160,
    0x1680,
    0x180A,
    0x180E,
    0x200B,
    0x2060,
    0x2061,
    0x2062,
    0x2063,
    0x2064,
    0x2800,
    0x302E,
    0x302F,
    0x3164,
    0xFEFF,
    0xFF9E,
    0xFF9F,
    0xFFA0,
    0xFFFC,
    0xFFFD,
    0xFFFE,
    0xFFFF,
    0xE000,
    0xF8FF,
    0xFDD0,
)


def _assigned_name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def _in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def official_di_ucd15(codepoint: int) -> bool:
    return _in_ranges(codepoint, OFFICIAL_DI_RANGES_UCD15)


def _tt_font_class():
    try:
        from fontTools.ttLib import TTFont
    except ImportError as error:
        raise SystemExit(f"fonttools is required: {H14_RESEARCH_EXTRA_INSTALL}") from error
    return TTFont


def load_dejavu_metrics(path: Path) -> dict[int, dict[str, object]]:
    font = _tt_font_class()(path)
    cmap = font.getBestCmap() or {}
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    units = int(font["head"].unitsPerEm)
    rows: dict[int, dict[str, object]] = {}
    for codepoint, glyph_name in cmap.items():
        glyph = glyf[glyph_name]
        contours = int(getattr(glyph, "numberOfContours", 0))
        advance, lsb = hmtx[glyph_name]
        rows[int(codepoint)] = {
            "glyph": glyph_name,
            "contours": contours,
            "advance": int(advance),
            "lsb": int(lsb),
            "empty": is_simple_empty_true_type_glyph(contours),
            "zero_advance": int(advance) == 0,
        }
    font.close()
    return {"units_per_em": units, "glyphs": rows}


def iter_scalars():
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        yield codepoint


def classify_row(codepoint: int, dejavu: dict[int, dict[str, object]]) -> dict[str, object]:
    character = chr(codepoint)
    name = _assigned_name(codepoint)
    category = unicodedata.category(character)
    inserted = f"A{character}B"
    width_delta = display_column_width(inserted) - display_column_width("AB")
    font = dejavu.get(codepoint)
    return {
        "codepoint": codepoint,
        "label": f"U+{codepoint:04X}",
        "name": name,
        "category": category,
        "assigned": name is not None,
        "default_ignorable_project": is_default_ignorable_v1(codepoint),
        "default_ignorable_ucd15": official_di_ucd15(codepoint),
        "required_sanitizers_keep": required_sanitizers_keep(inserted),
        "cf_strip_keeps": strip_unicode_format_characters(inserted) == inserted,
        "nfc_stable": unicodedata.normalize("NFC", character) == character,
        "nfkc_stable": unicodedata.normalize("NFKC", character) == character,
        "nfkc": unicodedata.normalize("NFKC", character),
        "width_delta": width_delta,
        "in_dejavu": font is not None,
        "dejavu_contours": None if font is None else font["contours"],
        "dejavu_advance": None if font is None else font["advance"],
        "dejavu_empty": None if font is None else font["empty"],
        "dejavu_zero_advance": None if font is None else font["zero_advance"],
        "layout_control": codepoint in LAYOUT_CONTROL_CODEPOINTS,
        "hostile_control": codepoint in HOSTILE_CONTROL_CODEPOINTS,
        "h12_eligible": codepoint in CONTROL_MIX_ELIGIBLE_CODEPOINTS,
        "name_interesting": bool(name) and any(needle in name for needle in NAME_NEEDLES),
    }


def mechanism_bucket(row: dict[str, object]) -> str:
    category = row["category"]
    if row["h12_eligible"]:
        return "h12_cc_del_c1"
    if row["layout_control"]:
        return "cc_layout"
    if row["hostile_control"]:
        return "cc_nul"
    if category == "Cc":
        return "cc_other"
    if category == "Mn":
        return "mn"
    if category == "Cf":
        return "cf"
    if category == "Me":
        return "me"
    if category == "Mc":
        return "mc_spacing_combining"
    if category == "Lm":
        return "lm_modifier_letter"
    if category == "Zs":
        return "zs_space"
    if category in {"Zl", "Zp"}:
        return "z_separator"
    if category == "Co":
        return "co_pua"
    if category == "Cn":
        return "cn_unassigned_or_noncharacter"
    if row["name_interesting"]:
        return "named_filler_or_invisible"
    if row["dejavu_empty"] is True and row["dejavu_zero_advance"] is True:
        return "dejavu_empty_zero_advance"
    if row["dejavu_empty"] is True:
        return "dejavu_empty_nonzero_advance"
    if row["width_delta"] == 0:
        return "width0_other"
    return "visible_or_unclassified"


def scan(dejavu_glyphs: dict[int, dict[str, object]]) -> dict[str, object]:
    project_only_di = []
    ucd_only_di = []
    survivors = []
    for codepoint in iter_scalars():
        project = is_default_ignorable_v1(codepoint)
        official = official_di_ucd15(codepoint)
        if project != official:
            row = classify_row(codepoint, dejavu_glyphs)
            if project and not official:
                project_only_di.append(row["label"])
            else:
                ucd_only_di.append(row["label"])
        name = _assigned_name(codepoint)
        category = unicodedata.category(chr(codepoint))
        pua_probe = codepoint in {0xE000, 0xF8FF, 0xF0000, 0x10FFFD}
        noncharacter_probe = 0xFDD0 <= codepoint <= 0xFDEF or (codepoint & 0xFFFF) in {0xFFFE, 0xFFFF}
        interesting = (
            codepoint in INTERESTING_SINGLETONS
            or category in {"Cc", "Cf", "Mn", "Me", "Mc", "Lm", "Zs", "Zl", "Zp"}
            or pua_probe
            or noncharacter_probe
            or (name is not None and any(needle in name for needle in NAME_NEEDLES))
            or (codepoint in dejavu_glyphs and dejavu_glyphs[codepoint]["empty"])
        )
        if not interesting:
            continue
        row = classify_row(codepoint, dejavu_glyphs)
        if row["required_sanitizers_keep"]:
            row["bucket"] = mechanism_bucket(row)
            survivors.append(row)

    seen = {row["codepoint"] for row in survivors}
    for codepoint in iter_scalars():
        if codepoint in seen:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        font = dejavu_glyphs.get(codepoint)
        if category not in {"Mc", "Lm", "Me"} and not (font and font["empty"]):
            continue
        row = classify_row(codepoint, dejavu_glyphs)
        if row["required_sanitizers_keep"]:
            row["bucket"] = mechanism_bucket(row)
            survivors.append(row)
            seen.add(codepoint)

    buckets = Counter(row["bucket"] for row in survivors)
    chromium_candidates = []
    for row in survivors:
        if row["bucket"] in {
            "h12_cc_del_c1",
            "cc_layout",
            "cc_nul",
            "cc_other",
            "mn",
            "cf",
        }:
            continue
        if row["bucket"] in {
            "mc_spacing_combining",
            "lm_modifier_letter",
            "me",
            "dejavu_empty_zero_advance",
            "dejavu_empty_nonzero_advance",
            "named_filler_or_invisible",
            "width0_other",
            "co_pua",
            "cn_unassigned_or_noncharacter",
            "zs_space",
        }:
            chromium_candidates.append(row)

    dejavu_empty_survivors = [
        row
        for row in survivors
        if row["in_dejavu"] and row["dejavu_empty"] is True
    ]
    mc_survivors = [row for row in survivors if row["category"] == "Mc"]
    lm_survivors = [row for row in survivors if row["category"] == "Lm"]
    return {
        "source_probe": SOURCE,
        "di_list_complete_vs_ucd15": not project_only_di and not ucd_only_di,
        "project_only_di": project_only_di,
        "ucd15_only_di": ucd_only_di,
        "survivor_count": len(survivors),
        "buckets": dict(sorted(buckets.items())),
        "dejavu_empty_survivor_labels": [row["label"] for row in dejavu_empty_survivors],
        "dejavu_empty_zero_advance_labels": [
            row["label"] for row in dejavu_empty_survivors if row["dejavu_zero_advance"]
        ],
        "mc_survivor_count": len(mc_survivors),
        "mc_in_dejavu": [row["label"] for row in mc_survivors if row["in_dejavu"]],
        "mc_dejavu_empty": [
            row["label"] for row in mc_survivors if row["dejavu_empty"]
        ],
        "lm_survivor_count": len(lm_survivors),
        "lm_name_interesting": [
            {"label": row["label"], "name": row["name"], "in_dejavu": row["in_dejavu"]}
            for row in lm_survivors
            if row["name_interesting"] or row["codepoint"] in {0xFF9E, 0xFF9F}
        ],
        "chromium_candidate_count": len(chromium_candidates),
        "chromium_candidates": [
            {
                "label": row["label"],
                "name": row["name"],
                "category": row["category"],
                "bucket": row["bucket"],
                "width_delta": row["width_delta"],
                "in_dejavu": row["in_dejavu"],
                "dejavu_empty": row["dejavu_empty"],
                "dejavu_advance": row["dejavu_advance"],
            }
            for row in sorted(chromium_candidates, key=lambda item: item["codepoint"])
        ],
        "ff9e_ff9f": [row for row in survivors if row["codepoint"] in {0xFF9E, 0xFF9F}],
        "hangul_tone_mc": [row for row in survivors if row["codepoint"] in {0x302E, 0x302F}],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/h14-local/scan.json")
    args = parser.parse_args()
    metrics = load_dejavu_metrics(DEJAVU_MONO)
    payload = scan(metrics["glyphs"])
    payload["dejavu_path"] = str(DEJAVU_MONO)
    payload["dejavu_units_per_em"] = metrics["units_per_em"]
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in payload if key != "chromium_candidates"}, indent=2))
    print(f"wrote {destination} candidates={payload['chromium_candidate_count']}")


if __name__ == "__main__":
    main()
