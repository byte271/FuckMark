from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _load_corpus_texts(corpus_path: Path) -> dict[str, str]:
    corpus = _load(corpus_path)
    return {sample["sample_id"]: sample["text"] for sample in corpus["manifest"]["samples"]}


def build_render_page(plan: dict, corpus_texts: dict[str, str]) -> tuple[str, list[dict]]:
    blocks: list[str] = []
    manifest: list[dict] = []
    for index, variant in enumerate(plan["variants"]):
        source_id = variant["source_sample_id"]
        source_text = corpus_texts[source_id]
        transformed_text = variant["transformed_text"]
        blocks.append(
            "<section class=\"pair\" id=\"pair-{index}\">"
            "<h2>Pair {index}: {source_id} (budget {budget})</h2>"
            "<div class=\"source\" data-pair=\"{index}\" data-role=\"source\">{source}</div>"
            "<div class=\"transformed\" data-pair=\"{index}\" data-role=\"transformed\">{transformed}</div>"
            "</section>".format(
                index=index,
                source_id=html.escape(source_id),
                budget=variant["requested_budget"],
                source=html.escape(source_text),
                transformed=html.escape(transformed_text),
            )
        )
        manifest.append(
            {
                "pair_index": index,
                "source_sample_id": source_id,
                "requested_budget": variant["requested_budget"],
                "source_text_hash": variant["source_text_hash"],
                "transformed_text_hash": variant["transformed_text_hash"],
                "variant_hash": variant["variant_hash"],
            }
        )
    page = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>FuckMark budget-scaled render check</title>"
        "<style>body{font-family:monospace;margin:20px;} "
        ".pair{border:1px solid #999;margin:16px 0;padding:8px;} "
        ".source{background:#f4f4f4;white-space:pre-wrap;} "
        ".transformed{background:#e8f4e8;white-space:pre-wrap;} "
        "h2{font-size:14px;}</style></head><body>"
        + "".join(blocks)
        + "</body></html>"
    )
    return page, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="budget-scaled-render-page")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--manifest-json", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = _load(args.plan_json)
    corpus_texts = _load_corpus_texts(args.corpus_json)
    page, manifest = build_render_page(plan, corpus_texts)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(page, encoding="utf-8")
    args.manifest_json.write_text(
        json.dumps({"pair_count": len(manifest), "plan_hash": plan["plan_hash"], "pairs": manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"pair_count={len(manifest)}")
    print(f"html={args.html.as_posix()}")
    print(f"manifest_json={args.manifest_json.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
