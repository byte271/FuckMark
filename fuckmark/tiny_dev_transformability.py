from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_json
from .experiments.tiny_dev_transformability import build_tiny_dev_transformability_audit
from .transforms import development_transform_registry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-transformability")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-transformability.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    audit = build_tiny_dev_transformability_audit(
        corpus,
        development_transform_registry(),
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(audit) + "\n", encoding="utf-8")
    sys.stdout.write(f"audit_hash={audit.audit_hash}\n")
    sys.stdout.write(f"ruleset_hash={audit.ruleset_hash}\n")
    sys.stdout.write(f"status={audit.status.value}\n")
    sys.stdout.write(
        f"transformable_sources={audit.transformable_source_count}/{audit.expected_source_count}\n"
    )
    for row in audit.rows:
        sys.stdout.write(
            f"source={row.sample_id} domain={row.domain.value} "
            f"candidates={row.candidate_count} rejections={row.rejection_count} "
            f"rules={','.join(row.rule_ids) or '-'}\n"
        )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
