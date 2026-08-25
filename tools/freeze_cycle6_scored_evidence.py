from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from fuckmark.hashing import sha256_json
from tools.cycle5_dev_paired_run import scored_result_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", required=True)
    parser.add_argument("--source-container-hash", required=True)
    parser.add_argument("--source-content-hash", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    scored = json.loads(Path(args.scored).read_text(encoding="utf-8"))
    result_hash = sha256_json(scored_result_payload(scored))
    if "result_hash" in scored and scored["result_hash"] != result_hash:
        raise ValueError("scored result hash does not match scientific payload")
    scored["result_hash"] = result_hash
    payload = {
        "algorithm_version": "cycle6-scored-evidence-wrapper-v1",
        "source_corpus_container_hash": args.source_container_hash,
        "source_corpus_content_hash": args.source_content_hash,
        "source_commit": args.source_commit,
        "scored_artifact": scored,
    }
    payload["evidence_hash"] = sha256_json(payload)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(output)
    print(result_hash)
    print(payload["evidence_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
