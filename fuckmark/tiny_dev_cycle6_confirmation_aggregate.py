from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import aggregate_cycle6_confirmation


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-cycle6-confirmation-aggregate")
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, action="append", required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    contract = _load_json(args.contract_json)
    evidence = tuple(_load_json(path) for path in args.evidence_json)
    artifact = aggregate_cycle6_confirmation(evidence, contract=contract)
    write_canonical_json_fsynced(args.json, artifact)
    sys.stdout.write(f"outcome={artifact['outcome']}\n")
    sys.stdout.write(
        f"watermarked_detected={artifact['pooled']['watermarked_detected_per_sanitizer']}/192\n"
    )
    sys.stdout.write(
        f"unwatermarked_detected={artifact['pooled']['unwatermarked_detected_per_sanitizer']}/192\n"
    )
    sys.stdout.write(f"artifact_hash={artifact['artifact_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
