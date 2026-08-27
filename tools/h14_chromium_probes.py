#!/usr/bin/env python3
"""H14 Chromium pixel probes for sanitizer-surviving non-width0 classes."""

from __future__ import annotations

import json
from pathlib import Path

from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.unicode_meta import is_default_ignorable_v1
from fuckmark.product.rendering import compare_chrome_pre_screenshots
from fuckmark.product.roundtrip import display_column_width

SOURCE = "I do not agree."

PROBES: tuple[tuple[str, str], ...] = (
    ("mc_hangul_tone_single", "\u302e"),
    ("mc_hangul_tone_double", "\u302f"),
    ("mc_devanagari_aa", "\u093e"),
    ("mc_bengali_aa", "\u09be"),
    ("mc_tamil_aa", "\u0bbe"),
    ("mc_balinese_tedung", "\u1b35"),
    ("mc_bengali_au_length", "\u09d7"),
    ("so_object_replacement", "\ufffc"),
    ("lo_egyptian_full_blank", "\U00013441"),
    ("lo_egyptian_half_blank", "\U00013442"),
    ("po_devanagari_gap_filler", "\ua8f9"),
    ("po_newa_gap_filler", "\U0001144e"),
    ("po_kawi_space_filler", "\U00011f48"),
    ("po_bhaiksuki_gap_filler", "\U00011c44"),
    ("so_braille_blank", "\u2800"),
    ("so_blank_symbol", "\u2422"),
    ("me_enclosing_circle", "\u20dd"),
    ("mn_cgj_control", "\u034f"),
    ("cc_del", "\u007f"),
    ("cc_nul", "\u0000"),
    ("co_pua_bmp", "\ue000"),
    ("cn_noncharacter_fffe", "\ufffe"),
    ("lm_modifier_small_h", "\u02b0"),
    ("zs_ogham_space", "\u1680"),
    ("zs_nbsp", "\u00a0"),
    ("zl_line_separator", "\u2028"),
    ("lo_hangul_filler_di", "\u3164"),
    ("seq_hangul_jamo_fillers", "\u115f\u1160"),
    ("cc_c1_no_device_csi_filtered", "\u007f\u0080\u0091"),
)


def insert_after_letters(source: str, payload: str) -> str:
    chunks: list[str] = []
    for character in source:
        chunks.append(character)
        if character.isascii() and character.isalpha():
            chunks.append(payload)
    return "".join(chunks)


def main() -> None:
    rows = []
    for probe_id, payload in PROBES:
        applied = insert_after_letters(SOURCE, payload)
        keep = required_sanitizers_keep(applied)
        di = all(is_default_ignorable_v1(ord(character)) for character in payload)
        width_delta = display_column_width(applied) - display_column_width(SOURCE)
        comparison = compare_chrome_pre_screenshots(SOURCE, applied)
        row = {
            "id": probe_id,
            "payload_labels": [f"U+{ord(character):04X}" for character in payload],
            "required_sanitizers_keep": keep,
            "payload_all_default_ignorable": di,
            "width_delta": width_delta,
            "chromium_pre": comparison.status,
            "chromium_detail": comparison.detail,
            "equal": comparison.equal,
        }
        rows.append(row)
        print(
            f"{probe_id:36} keep={keep!s:5} di={di!s:5} width={width_delta:3} "
            f"{comparison.status:10} {comparison.detail}"
        )
    payload = {
        "source": SOURCE,
        "rows": rows,
        "pixel_equal_and_sanitizer_keep": [
            row["id"] for row in rows if row["equal"] is True and row["required_sanitizers_keep"] is True
        ],
    }
    destination = Path("evidence/h14-local/chromium-probes.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("pixel_equal_and_sanitizer_keep", payload["pixel_equal_and_sanitizer_keep"])
    print("wrote", destination)


if __name__ == "__main__":
    main()
