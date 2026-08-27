"""H16 threat-model probe: what real detector tokenizers do to carrier code points.

SynthID-Text scores model tokens, not raw characters. If the production
tokenizer normalizes a carrier away, the carrier never reaches the detector and
no external "sanitizer" is involved at all. If it survives as distinct tokens,
tokenization itself is the disruption channel. This probe answers which.
"""

from __future__ import annotations

import glob
import json
import sys
import unicodedata
from pathlib import Path

from tokenizers import Tokenizer

CACHE = Path.home() / ".cache/huggingface/hub"

MODELS = {
    "gemma-2-2b-it": "models--unsloth--gemma-2-2b-it",
    "gemma-3-1b-it": "models--unsloth--gemma-3-1b-it",
    "gpt2": "models--openai-community--gpt2",
    "llama-2-7b": "models--NousResearch--Llama-2-7b-hf",
    "llama-3-8b": "models--unsloth--llama-3-8b-Instruct",
    "mistral-7b-v0.2": "models--mistralai--Mistral-7B-Instruct-v0.2",
    "xlm-roberta-base": "models--FacebookAI--xlm-roberta-base",
    "t5-small": "models--google-t5--t5-small",
}

CARRIERS = {
    "U+034F CGJ (Mn)": "\u034f",
    "U+FE00 VS-1 (Mn)": "\ufe00",
    "U+200B ZWSP (Cf)": "\u200b",
    "U+200C ZWNJ (Cf)": "\u200c",
    "U+2060 WJ (Cf)": "\u2060",
    "U+00AD SHY (Cf)": "\u00ad",
    "U+FEFF BOM (Cf)": "\ufeff",
    "U+007F DEL (Cc)": "\u007f",
    "U+0080 PAD (Cc)": "\u0080",
}

SOURCE = "I do not agree."


def find(model_dir: str) -> Path | None:
    hits = glob.glob(str(CACHE / model_dir / "snapshots" / "*" / "tokenizer.json"))
    return Path(hits[0]) if hits else None


def insert_after_letters(source: str, payload: str) -> str:
    out = []
    for ch in source:
        out.append(ch)
        if ch.isascii() and ch.isalpha():
            out.append(payload)
    return "".join(out)


def main() -> int:
    results = {}
    for name, model_dir in MODELS.items():
        path = find(model_dir)
        if path is None:
            print(f"{name}: tokenizer.json not cached, skipped")
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        normalizer = spec.get("normalizer")
        tok = Tokenizer.from_file(str(path))
        baseline = tok.encode(SOURCE, add_special_tokens=False).ids

        norm_kind = None
        if isinstance(normalizer, dict):
            norm_kind = normalizer.get("type")
            if norm_kind == "Sequence":
                norm_kind = "Sequence" + str(
                    [n.get("type") for n in normalizer.get("normalizers", [])]
                )

        rows = {}
        for label, payload in CARRIERS.items():
            applied = insert_after_letters(SOURCE, payload)
            ids = tok.encode(applied, add_special_tokens=False).ids
            # Does the carrier reach the token stream at all?
            reaches = ids != baseline
            rows[label] = {
                "baseline_token_count": len(baseline),
                "carrier_token_count": len(ids),
                "token_ids_changed": reaches,
                "decoded_roundtrip_preserves_carrier": payload in tok.decode(ids),
            }
        results[name] = {
            "normalizer": norm_kind,
            "normalizer_strips_carriers": False,
            "baseline_tokens": len(baseline),
            "carriers": rows,
        }
        surviving = [k for k, v in rows.items() if v["token_ids_changed"]]
        dropped = [k for k, v in rows.items() if not v["token_ids_changed"]]
        print(f"\n=== {name} ===")
        print(f"  normalizer: {norm_kind}")
        print(f"  baseline tokens: {len(baseline)}")
        print(f"  carrier REACHES token stream ({len(surviving)}/{len(CARRIERS)}):")
        for k in surviving:
            print(f"      {k:22} tokens {len(baseline)} -> {rows[k]['carrier_token_count']}")
        if dropped:
            print(f"  carrier DROPPED by tokenizer ({len(dropped)}):")
            for k in dropped:
                print(f"      {k}")

    out = Path("/workspace/evidence/h16-local/tokenizer-threat-model.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
