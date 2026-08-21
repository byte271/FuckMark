from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.diverse_beam_corpus import (
    freeze_diverse_beam_corpus,
    load_diverse_beam_generation_shard,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-diverse-beam-corpus-freeze")
    parser.add_argument("--shard-dir", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = tuple(sorted(args.shard_dir.glob("diverse-beam-generation-*.json")))
    if not paths:
        raise ValueError("shard directory contains no Diverse Beam generation shards")
    corpus = freeze_diverse_beam_corpus(
        tuple(load_diverse_beam_generation_shard(path) for path in paths)
    )
    write_canonical_json_fsynced(args.json, corpus.as_dict())
    sys.stdout.write(f"artifact_hash={corpus.artifact_hash}\n")
    sys.stdout.write(f"generated_sample_count={corpus.generated_sample_count}\n")
    sys.stdout.write(f"duplicate_excluded_count={corpus.duplicate_excluded_count}\n")
    sys.stdout.write(
        f"surplus_unique_excluded_count={corpus.surplus_unique_excluded_count}\n"
    )
    sys.stdout.write(f"eligible_sample_count={corpus.eligible_sample_count}\n")
    sys.stdout.write(f"samples_per_target_length={corpus.samples_per_target_length}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
