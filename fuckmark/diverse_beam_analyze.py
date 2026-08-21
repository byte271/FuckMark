from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.diverse_beam_ab import (
    analyze_diverse_beam_search,
    load_diverse_beam_analysis,
    load_diverse_beam_search_shard,
)
from .experiments.diverse_beam_corpus import load_diverse_beam_frozen_corpus


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-diverse-beam-analyze")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--shard-dir", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = tuple(sorted(args.shard_dir.glob("diverse-beam-search-*.json")))
    if not paths:
        raise ValueError("shard directory contains no Diverse Beam search shards")
    corpus = load_diverse_beam_frozen_corpus(args.corpus_json)
    analysis = analyze_diverse_beam_search(
        corpus,
        tuple(load_diverse_beam_search_shard(path) for path in paths),
    )
    write_canonical_json_fsynced(args.json, analysis)
    load_diverse_beam_analysis(args.json)
    aggregate = analysis["aggregate"]
    sys.stdout.write(f"artifact_hash={analysis['artifact_hash']}\n")
    sys.stdout.write(f"sample_count={analysis['sample_count']}\n")
    sys.stdout.write(f"row_count={analysis['row_count']}\n")
    sys.stdout.write(f"diverse_gain_count={aggregate['diverse_gain_count']}\n")
    sys.stdout.write(f"diverse_loss_count={aggregate['diverse_loss_count']}\n")
    sys.stdout.write(f"decision={analysis['decision']}\n")
    sys.stdout.write(f"promoted={str(analysis['promoted']).lower()}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
