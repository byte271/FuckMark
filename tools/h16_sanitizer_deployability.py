from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.threat_model_audit import DEPLOYABILITY_CORPUS
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters

SCRIPT_LABELS = {
    "devanagari": "Devanagari",
    "hebrew_niqqud": "Hebrew niqqud",
    "thai": "Thai",
    "persian_zwnj": "Persian ZWNJ",
    "emoji_zwj_family": "Emoji ZWJ family",
    "emoji_vs16": "Emoji VS-16",
    "devanagari_zwj_conjunct": "Devanagari ZWJ conjunct",
}

SANITIZERS = (
    ("nfc", lambda text: unicodedata.normalize("NFC", text), "frozen"),
    ("nfkc", nfkc_normalize, "frozen"),
    ("cf_strip", strip_unicode_format_characters, "frozen"),
    ("mn_strip", strip_nonspacing_marks, "stress_only_not_frozen"),
    ("default_ignorable_strip", strip_default_ignorable, "stress_only_not_frozen"),
)


def main() -> int:
    rows = []
    damage = {name: 0 for name, _, _ in SANITIZERS}
    for sample_id, text in DEPLOYABILITY_CORPUS:
        entry: dict[str, object] = {
            "id": sample_id,
            "script": SCRIPT_LABELS.get(sample_id, sample_id),
            "original": text,
            "results": {},
        }
        for name, function, category in SANITIZERS:
            output = function(text)
            corrupted = output != text
            if corrupted:
                damage[name] += 1
            entry["results"][name] = {
                "category": category,
                "corrupts_ordinary_text": corrupted,
                "output": output,
                "codepoints_lost": len(text) - len(output),
            }
        rows.append(entry)

    total = len(DEPLOYABILITY_CORPUS)
    print(f"Ordinary-text corpus: {total} samples across widely used writing systems\n")
    print(f"{'sanitizer':26} {'contract category':26} corrupts")
    print("-" * 68)
    for name, _, category in SANITIZERS:
        print(f"{name:26} {category:26} {damage[name]}/{total}")

    print("\nCollateral damage from the two stress-only sanitizers:\n")
    for entry in rows:
        for name in ("mn_strip", "default_ignorable_strip"):
            result = entry["results"][name]
            if result["corrupts_ordinary_text"]:
                print(f"  [{name}] {entry['script']}")
                print(f"      before: {entry['original']}")
                print(f"      after:  {result['output']}")

    payload = {
        "corpus_size": total,
        "sanitizer_damage": {
            name: {"category": category, "corrupted_samples": damage[name], "of": total}
            for name, _, category in SANITIZERS
        },
        "rows": rows,
    }
    destination = Path("evidence/h16-local/sanitizer-deployability.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
