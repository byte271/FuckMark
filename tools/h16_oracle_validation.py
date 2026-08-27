from __future__ import annotations

import json
from pathlib import Path

from h16_shaping_closure_scan import ShapingOracle

from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.threat_model_audit import AUDIT_SOURCE, CHROMIUM_PRE_FONT
from fuckmark.product.rendering import compare_chrome_pre_screenshots

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
    agreement = 0
    disagreements: list[str] = []
    for probe_id, codepoint in SAMPLE:
        applied = insert_after_letters(AUDIT_SOURCE, chr(codepoint))
        comparison = compare_chrome_pre_screenshots(AUDIT_SOURCE, applied)
        shaping_invisible = oracle.invisible(codepoint)
        matched = shaping_invisible == comparison.equal
        agreement += int(matched)
        if not matched:
            disagreements.append(probe_id)
        rows.append(
            {
                "id": probe_id,
                "codepoint": f"U+{codepoint:04X}",
                "shaping_oracle_invisible": shaping_invisible,
                "chromium_pre_invisible": comparison.equal,
                "chromium_status": comparison.status,
                "agree": matched,
                "required_sanitizers_keep": required_sanitizers_keep(applied),
            }
        )
        print(
            f"{probe_id:32} {f'U+{codepoint:04X}':10} shaping={shaping_invisible!s:5} "
            f"chromium={comparison.equal!s:5} {'OK' if matched else 'DISAGREE'}"
        )

    payload = {
        "source": AUDIT_SOURCE,
        "font": CHROMIUM_PRE_FONT,
        "sample_size": len(SAMPLE),
        "agreement": agreement,
        "disagreement_ids": disagreements,
        "rows": rows,
    }
    destination = Path("evidence/h16-local/oracle-validation.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nagreement {agreement}/{len(SAMPLE)}; disagreements: {disagreements}")
    print("wrote", destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
