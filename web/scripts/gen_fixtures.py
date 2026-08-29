#!/usr/bin/env python3
"""Golden fixtures: Python product engine output for the JS port."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fuckmark.cli import transform_text
from fuckmark.cycle8.letter_mix import hard_machine_intervals, select_letter_mix_sites
from fuckmark.product.detect import detect_fuckmark_insertions


CASES: tuple[tuple[str, str], ...] = (
    ("empty", ""),
    ("ascii-agree", "I do not agree."),
    ("ascii-apostrophe", "I don't agree."),
    ("curly-apostrophe", "I don’t agree."),
    ("accented", "I do not agree é."),
    ("latin-only", "ééé"),
    ("han-only", "中文"),
    ("emoji-only", "😀"),
    ("emoji-zwj", "👩‍🚀"),
    ("flag", "🇺🇸"),
    ("keycap", "1️⃣"),
    ("mixed-scripts", "Hello κόσμος привет 日本語 한글 ㄅㄆ café 😀"),
    ("url-prose", "Keep going item 7 and we never wait at https://example.com/ab."),
    ("unclosed-math", r"Keep going \[item 7 and we never wait at https://example.com/ab."),
    ("quoted", 'He said "hello world" and left.'),
    ("and-or", "Use and/or input/output here."),
    ("src-path", "Read src/main.py now."),
    ("docs-path", "Read docs/README.md now."),
    ("windows-forward", "Open C:/Users/Alice/notes.txt now."),
    ("posix-windows-url-email", (
        "See /var/tmp/report.json and C:\\Temp\\report.json plus "
        "https://example.com/do-not-touch and a.b+tag@example.com please."
    )),
    ("markdown-ref", "[click][ref]\n\n[ref]: https://example.com\n"),
    ("markdown-inline", "See [docs](https://example.com/a) please."),
    ("ftp-url", "Mirror ftp://files.example.org/pack.tar.gz today."),
    ("www-url", "Visit www.example.com/path now."),
    ("bare-domain", "Read example.com/docs please."),
    ("ipv4", "The host 192.168.1.20 is down."),
    ("iso-date", "Shipped on 2026-08-18 as planned."),
    ("month-date", "Shipped on August 18, 2026 as planned."),
    ("slash-date", "Shipped on 08/18/2026 as planned."),
    ("currency", "It costs $12.50 USD today."),
    ("percent", "Coverage is 12.5% complete."),
    ("number", "There are 1,234 items here."),
    ("cli-flag", "Run with --visible and -q please."),
    ("email-only-prose", "Write to a.b+tag@example.com please."),
    ("html-tag", "Use <span class=\"x\">hello</span> there."),
    ("html-entity", "Tom &amp; Jerry went home."),
    ("inline-code", "Use `src/main.py` in the docs."),
    ("fenced-code", "Intro\n\n```\ncode path\n```\n\nOutro letters."),
    ("indented-code", "Para\n\n    indented code here\n\nMore letters."),
    ("posix-home", "Open ~/My final notes.txt later."),
    ("windows-spaced", "Open C:/Users/Alice/My final notes.txt later."),
    ("scripts-build", "See scripts/build please."),
    ("ambiguous-and-or-path", "See src/lib and/or tests/unit please."),
    ("already-mark", "A\u034fB"),
    ("no-letters", "!!! ???"),
    ("digits-only", "12345"),
    ("newlines", "Hello\r\nworld\nagain."),
    ("nfd-accent", "cafe\u0301 time"),
    ("greek", "Αθήνα is a city."),
    ("cyrillic", "Москва is a city."),
    ("hangul", "한글은 글자다."),
    ("bopomofo", "ㄅㄆㄇ still letters."),
    ("prolonged", "コーヒー drinks"),
    ("copyright-emoji", "©2026 ACME"),
    ("long-alphabet", "abcdefghijklmnopqrstuvwxyz" * 12),
    ("markdown-ref-case", "[Click][REF]\n\n[ref]: https://example.com/x\nMore text."),
    ("multiline-md", "[text][lab]\n\n[lab]: https://example.com/a/b\n"),
    ("file-url", "Open file://localhost/tmp/a.txt now."),
    ("ws-url", "Connect wss://example.com/socket please."),
    ("git-url", "Clone git://example.com/repo.git please."),
    ("code-fence-tilde", "Intro\n\n~~~\nsecret()\n~~~\n\nDone now."),
    ("unclosed-fence", "Start\n\n```js\nconst x = 1;\nStill letters after."),
    ("double-backtick", "Use `` a ` b `` here."),
    ("windows-unc", r"See \\SERVER\share\file.txt please."),
    ("relative-dot", "Open ./src/main.py now."),
    ("parent-path", "Open ../docs/readme.md now."),
    ("extensionless-src", "See src/main please."),
    ("prose-slash-he-she", "Ask he/she to wait here."),
    ("currency-euro", "Pay €20 now."),
    ("scientific", "Value 1.2e-3 is tiny."),
    ("ipv6-like", "Bind ::1 please wait."),
    ("date-invalid", "The code 2026-13-40 is not a date word."),
    ("mixed-url-han", "见 https://例.com/a 中文"),
    ("emoji-text", "I agree 👍 now."),
    ("tab-space", "Hello\tworld again."),
    ("nbsp", "Hello\u00a0world"),
    ("bom-hello", "\ufeffHello"),
    ("quotes-nested", 'Say "don\'t wait" now.'),
    ("html-void", "Break<br/>please now."),
    ("md-angle-dest", "See [x](<https://example.com/a b>) please."),
    ("list-code", "1. hello `code` world"),
    ("blockquote-code", "> hello world now"),
)


def pack_detect(text: str) -> dict[str, object]:
    scan = detect_fuckmark_insertions(text)
    return {
        "detected": scan.detected,
        "found": scan.found,
        "mark": scan.mark_count,
        "cc": scan.cc_count,
        "me": scan.me_count,
        "cf": scan.cf_count,
        "ia": scan.ia_count,
        "first": scan.first_hit,
        "source_length": scan.source_length,
    }


def main() -> None:
    rows: list[dict[str, object]] = []
    for name, source in CASES:
        result = transform_text(source)
        rows.append(
            {
                "name": name,
                "source": source,
                "sites": list(select_letter_mix_sites(source)),
                "blocked": [list(interval) for interval in hard_machine_intervals(source)],
                "output": result.output_text,
                "reason": result.reason,
                "change_count": result.change_count,
                "site_count": result.site_count,
                "capped": result.capped,
                "last_source_index": result.last_source_index,
                "first_unsupported": result.first_unsupported,
                "source_length": result.source_length,
                "detect_source": pack_detect(source),
                "detect_output": pack_detect(result.output_text),
            }
        )
    destination = Path(__file__).resolve().parents[1] / "src" / "engine" / "generated" / "fixtures.json"
    destination.write_text(json.dumps({"cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases -> {destination}")


if __name__ == "__main__":
    main()
