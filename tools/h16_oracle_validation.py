"""H16 shaping oracle validation against real Chromium ``pre`` pixels.

The exhaustive H16 closure scan uses a HarfBuzz shaping oracle instead of one
screenshot per code point. This script checks that oracle against the Chromium
comparator the earlier cycles used, on a stratified sample covering every class
the closure argument depends on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from h16_shaping_closure_scan import CHROMIUM_PRE_FONT, ShapingOracle  # noqa: E402

from fuckmark.cycle8.control_carrier import required_sanitizers_keep  # noqa: E402
from fuckmark.product.rendering import compare_chrome_pre_screenshots  # noqa: E402

SOURCE = "I do not agree."

SAMPLE: tuple[tuple[str, int], ...] = (
    ("mn_cgj", 0x034F),
    ("mn_variation_selector_1", 0xFE00),
    ("mn_devanagari_nukta", 0x093C),
    ("cf_zwsp", 0x200B),
    ("cf_zwnj", 0x200C),
    ("cf_zwj", 0x200D),
    ("cf_word_joiner", 0x2060),
    ("cf_soft_hyphen", 0x00AD),
    ("cf_mongolian_vowel_separator", 0x180E),
    ("lm_tatweel", 0x0640),
    ("lm_modifier_small_h", 0x02B0),
    ("mc_devanagari_aa", 0x093E),
    ("mc_hangul_tone", 0x302E),
    ("me_enclosing_circle", 0x20DD),
    ("so_braille_blank", 0x2800),
    ("so_object_replacement", 0xFFFC),
    ("lo_hangul_filler", 0x3164),
    ("lo_hangul_jamo_v_filler", 0x1160),
    ("lo_egyptian_full_blank", 0x13441),
    ("zs_nbsp", 0x00A0),
    ("zs_ogham_space", 0x1680),
    ("cc_del", 0x007F),
    ("cc_c1_pad", 0x0080),
)


def insert_after_letters(source: str, payload: str) -> str:
    chunks: list[str] = []
    for character in source:
        chunks.append(character)
        if character.isascii() and character.isalpha():
            chunks.append(payload)
    return "".join(chunks)


def main() -> int:
    oracle = ShapingOracle(CHROMIUM_PRE_FONT)
    rows = []
    agree = 0
    disagree = []
    for probe_id, codepoint in SAMPLE:
        applied = insert_after_letters(SOURCE, chr(codepoint))
        comparison = compare_chrome_pre_screenshots(SOURCE, applied)
        shaping_invisible = oracle.invisible(codepoint)
        chromium_invisible = comparison.equal
        matched = shaping_invisible == chromium_invisible
        agree += int(matched)
        if not matched:
            disagree.append(probe_id)
        rows.append(
            {
                "id": probe_id,
                "codepoint": f"U+{codepoint:04X}",
                "shaping_oracle_invisible": shaping_invisible,
                "chromium_pre_invisible": chromium_invisible,
                "chromium_status": comparison.status,
                "agree": matched,
                "required_sanitizers_keep": required_sanitizers_keep(applied),
            }
        )
        print(
            f"{probe_id:32} {f'U+{codepoint:04X}':10} shaping={shaping_invisible!s:5} "
            f"chromium={chromium_invisible!s:5} {'OK' if matched else 'DISAGREE'}"
        )

    payload = {
        "source": SOURCE,
        "font": CHROMIUM_PRE_FONT,
        "sample_size": len(SAMPLE),
        "agreement": agree,
        "disagreement_ids": disagree,
        "rows": rows,
    }
    destination = REPO / "evidence" / "h16-local" / "oracle-validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nagreement {agree}/{len(SAMPLE)}; disagreements: {disagree}")
    print("wrote", destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
