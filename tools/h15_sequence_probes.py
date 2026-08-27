from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.cycle8.post_sanitizer_sequences import post_sanitizer_sequences_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/h15-live-payload.json")
    args = parser.parse_args()
    payload = post_sanitizer_sequences_payload()
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary = {key: payload[key] for key in payload if key != "classes"}
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
