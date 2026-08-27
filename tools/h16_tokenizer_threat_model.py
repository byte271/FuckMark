from __future__ import annotations

import glob
import json
from pathlib import Path

from fuckmark.cycle8.threat_model_audit import AUDIT_SOURCE, H16_RESEARCH_EXTRA_INSTALL

CACHE = Path.home() / ".cache/huggingface/hub"

MODELS: tuple[tuple[str, str], ...] = (
    ("gemma-2-2b-it", "models--unsloth--gemma-2-2b-it"),
    ("gemma-3-1b-it", "models--unsloth--gemma-3-1b-it"),
    ("gpt2", "models--openai-community--gpt2"),
    ("llama-2-7b", "models--NousResearch--Llama-2-7b-hf"),
    ("llama-3-8b", "models--unsloth--llama-3-8b-Instruct"),
    ("mistral-7b-v0.2", "models--mistralai--Mistral-7B-Instruct-v0.2"),
    ("xlm-roberta-base", "models--FacebookAI--xlm-roberta-base"),
    ("t5-small", "models--google-t5--t5-small"),
)

CARRIERS: tuple[tuple[str, str], ...] = (
    ("U+034F CGJ (Mn)", "\u034f"),
    ("U+FE00 VS-1 (Mn)", "\ufe00"),
    ("U+200B ZWSP (Cf)", "\u200b"),
    ("U+200C ZWNJ (Cf)", "\u200c"),
    ("U+2060 WJ (Cf)", "\u2060"),
    ("U+00AD SHY (Cf)", "\u00ad"),
    ("U+FEFF BOM (Cf)", "\ufeff"),
    ("U+007F DEL (Cc)", "\u007f"),
    ("U+0080 PAD (Cc)", "\u0080"),
)


def _tokenizer_class():
    try:
        from tokenizers import Tokenizer
    except ImportError as error:
        raise SystemExit(f"tokenizers is required: {H16_RESEARCH_EXTRA_INSTALL}") from error
    return Tokenizer


def find_tokenizer(model_dir: str) -> Path | None:
    hits = sorted(glob.glob(str(CACHE / model_dir / "snapshots" / "*" / "tokenizer.json")))
    return Path(hits[0]) if hits else None


def insert_after_letters(source: str, payload: str) -> str:
    chunks: list[str] = []
    for character in source:
        chunks.append(character)
        if character.isascii() and character.isalpha():
            chunks.append(payload)
    return "".join(chunks)


def normalizer_label(spec: dict[str, object]) -> str | None:
    normalizer = spec.get("normalizer")
    if not isinstance(normalizer, dict):
        return None
    kind = normalizer.get("type")
    if kind != "Sequence":
        return kind
    inner = [entry.get("type") for entry in normalizer.get("normalizers", [])]
    return f"Sequence[{', '.join(str(value) for value in inner)}]"


def main() -> int:
    tokenizer_class = _tokenizer_class()
    results: dict[str, object] = {}
    for name, model_dir in MODELS:
        path = find_tokenizer(model_dir)
        if path is None:
            print(f"{name}: tokenizer.json not cached, skipped")
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        tokenizer = tokenizer_class.from_file(str(path))
        baseline = tokenizer.encode(AUDIT_SOURCE, add_special_tokens=False).ids

        rows = {}
        for label, payload in CARRIERS:
            ids = tokenizer.encode(insert_after_letters(AUDIT_SOURCE, payload), add_special_tokens=False).ids
            rows[label] = {
                "baseline_token_count": len(baseline),
                "carrier_token_count": len(ids),
                "reaches_token_stream": ids != baseline,
            }
        reaching = [label for label, row in rows.items() if row["reaches_token_stream"]]
        dropped = [label for label, row in rows.items() if not row["reaches_token_stream"]]
        results[name] = {
            "normalizer": normalizer_label(spec),
            "baseline_token_count": len(baseline),
            "carriers_probed": len(CARRIERS),
            "carriers_reaching_token_stream": len(reaching),
            "carriers_dropped": dropped,
            "carriers": rows,
        }
        print(f"\n=== {name} ===")
        print(f"  normalizer: {normalizer_label(spec)}")
        print(f"  baseline tokens: {len(baseline)}")
        print(f"  carriers reaching the token stream: {len(reaching)}/{len(CARRIERS)}")
        for label in reaching:
            print(f"      {label:22} tokens {len(baseline)} -> {rows[label]['carrier_token_count']}")
        for label in dropped:
            print(f"      DROPPED {label}")

    destination = Path("evidence/h16-local/tokenizer-threat-model.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
