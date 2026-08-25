from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from fuckmark.hashing import sha256_json
from tools.cycle5_dev_paired_run import corpus_content_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--source-container-hash", required=True)
    parser.add_argument("--expected-content-hash", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    content_hash = sha256_json(corpus_content_payload(corpus))
    if content_hash != args.expected_content_hash:
        raise ValueError("corpus content does not match the expected frozen identity")
    payload = {
        "algorithm_version": "cycle6-frozen-content-snapshot-v1",
        "source_container_hash": args.source_container_hash,
        "content_hash": content_hash,
        "model": corpus["model"],
        "model_revision": corpus["model_revision"],
        "seed_base": corpus["seed_base"],
        "prompt_count": corpus["prompt_count"],
        "sample_count": corpus["sample_count"],
        "generation_note": corpus["generation_note"],
        "samples": corpus["samples"],
    }
    payload["snapshot_hash"] = sha256_json(payload)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(output)
    print(payload["snapshot_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
