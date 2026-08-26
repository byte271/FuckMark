from __future__ import annotations

import argparse
from pathlib import Path

from fuckmark.config import canonical_json_text
from fuckmark.cycle8.tokenizer_screen import GPT2_FIXTURE, require_gpt2_encoder, screen_carrier_tokenizer
from fuckmark.cycle8.unicode_meta import audit_codepoints, iter_default_ignorable_codepoints_v1
from fuckmark.hashing import sha256_json
from fuckmark.product.rendering import compare_chrome_pre_screenshots
from fuckmark.product.visible_projection import is_carrier_insertion_v1


FOCUS_CODEPOINTS = (
    0x200C,
    0x200B,
    0x200D,
    0x2060,
    0xFEFF,
    0x034F,
    0xFE00,
    0xFE0E,
    0xFE0F,
    0x180B,
    0x17B4,
    0x115F,
    0x00AD,
    0x00A0,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args(argv)
    rows = audit_codepoints(iter_default_ignorable_codepoints_v1())
    focus = audit_codepoints(FOCUS_CODEPOINTS)
    encoder = require_gpt2_encoder()
    tokenizer_rows = [screen_carrier_tokenizer(codepoint, encoder=encoder) for codepoint in FOCUS_CODEPOINTS]
    rendering = []
    fixture = GPT2_FIXTURE
    if args.render:
        for codepoint in (0x200C, 0x034F, 0xFE00, 0x17B4, 0x115F):
            carrier = chr(codepoint)
            transformed = "".join(
                character + carrier if character.isascii() and character.isalpha() else character for character in fixture
            )
            comparison = compare_chrome_pre_screenshots(fixture, transformed)
            rendering.append(
                {
                    "codepoint": codepoint,
                    "label": f"U+{codepoint:04X}",
                    "visible_ok": is_carrier_insertion_v1(fixture, transformed, (codepoint,)),
                    "environment": comparison.environment,
                    "status": comparison.status,
                    "equal": comparison.equal,
                    "detail": comparison.detail,
                }
            )
    classification_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["classification"])
        classification_counts[key] = classification_counts.get(key, 0) + 1
    durable = [row for row in rows if row["classification"] == "DURABLE_TRACK_CANDIDATE"]
    summary = {
        "scan_version": "cycle8-carrier-screen-v1",
        "default_ignorable_count": len(rows),
        "classification_counts": classification_counts,
        "durable_track_count": len(durable),
        "durable_track_labels": [row["label"] for row in durable],
        "focus": focus,
        "tokenizer": tokenizer_rows,
        "rendering": rendering,
        "gpt2_encoder": "unavailable" if encoder is None else "gpt2",
        "chromium_render": "requested" if args.render else "UNKNOWN",
    }
    payload = {key: value for key, value in summary.items()}
    summary["summary_hash"] = sha256_json(payload)
    destination = Path("specs/cycle8/carrier-screen-v1.summary.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(summary) + "\n", encoding="utf-8")
    print(destination)
    print("default_ignorable_count", len(rows))
    print("durable_track_count", len(durable))
    print("gpt2_encoder", summary["gpt2_encoder"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
