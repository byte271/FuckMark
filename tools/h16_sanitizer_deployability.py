"""H16 deployability probe for the H12-H15 stress sanitizers.

A sanitizer is only a realistic production countermeasure if a platform could
actually run it on all user text. This probe applies each sanitizer in the
required bundle to ordinary, non-adversarial text in widely used writing
systems and measures the collateral corruption.

Mn-strip and default-ignorable-strip are the two sanitizers the frozen product
contract classifies as ``stress_only_not_frozen`` but that H12-H15 promoted to
hard requirements.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks  # noqa: E402
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters  # noqa: E402

# Ordinary, non-adversarial text. Nothing here is an attack payload; every code
# point is required to spell the sentence correctly.
CORPUS: tuple[tuple[str, str, str], ...] = (
    ("vietnamese", "Tiếng Việt", "Tôi không đồng ý với điều đó."),
    ("hindi", "Devanagari", "मैं इससे सहमत नहीं हूँ।"),
    ("arabic", "Arabic", "أنا لا أوافق على ذلك."),
    ("hebrew", "Hebrew niqqud", "אֲנִי לֹא מַסְכִּים."),
    ("thai", "Thai", "ฉันไม่เห็นด้วยกับสิ่งนั้น"),
    ("korean", "Hangul jamo", "\u1102\u1161\u1102\u1173\u11ab \u1103\u1169\u11bc\u110b\u1174\u1112\u1161\u110c\u1175 \u110b\u1161\u11ba\u1109\u1173\u11b8\u1102\u1175\u1103\u1161."),
    ("french", "French accents", "Je ne suis pas d'accord avec ça."),
    ("czech", "Czech diacritics", "Nesouhlasím s tím."),
    ("persian_zwnj", "Persian ZWNJ", "من با آن موافق نیستم\u200cها."),
    ("emoji_zwj", "Emoji ZWJ family", "Our family \U0001f468\u200d\U0001f469\u200d\U0001f467 disagrees."),
    ("emoji_vs16", "Emoji VS-16", "I disagree \u2764\ufe0f strongly."),
    ("devanagari_zwj", "Devanagari ZWJ conjunct", "क\u094d\u200dष सही नहीं है।"),
)

SANITIZERS = (
    ("nfc", lambda t: unicodedata.normalize("NFC", t), "frozen"),
    ("nfkc", nfkc_normalize, "frozen"),
    ("cf_strip", strip_unicode_format_characters, "frozen"),
    ("mn_strip", strip_nonspacing_marks, "stress_only_not_frozen"),
    ("default_ignorable_strip", strip_default_ignorable, "stress_only_not_frozen"),
)


def main() -> int:
    rows = []
    damage: dict[str, int] = {name: 0 for name, _, _ in SANITIZERS}
    for sample_id, script, text in CORPUS:
        entry = {"id": sample_id, "script": script, "original": text, "results": {}}
        for name, fn, category in SANITIZERS:
            out = fn(text)
            corrupted = out != text
            if corrupted:
                damage[name] += 1
            entry["results"][name] = {
                "category": category,
                "corrupts_ordinary_text": corrupted,
                "output": out,
                "codepoints_lost": len(text) - len(out),
            }
        rows.append(entry)

    total = len(CORPUS)
    print(f"Ordinary-text corpus: {total} samples across widely used writing systems\n")
    print(f"{'sanitizer':26} {'contract category':26} corrupts")
    print("-" * 68)
    for name, _, category in SANITIZERS:
        print(f"{name:26} {category:26} {damage[name]}/{total}")

    print("\nCollateral damage from the two stress-only sanitizers:\n")
    for entry in rows:
        for name in ("mn_strip", "default_ignorable_strip"):
            res = entry["results"][name]
            if res["corrupts_ordinary_text"]:
                print(f"  [{name}] {entry['script']}")
                print(f"      before: {entry['original']}")
                print(f"      after:  {res['output']}")

    payload = {
        "corpus_size": total,
        "sanitizer_damage": {
            name: {"category": category, "corrupted_samples": damage[name], "of": total}
            for name, _, category in SANITIZERS
        },
        "rows": rows,
    }
    out_path = REPO / "evidence" / "h16-local" / "sanitizer-deployability.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
