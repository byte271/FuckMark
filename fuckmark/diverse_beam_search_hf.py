from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.diverse_beam_ab import (
    DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT,
    run_diverse_beam_search_shard,
)
from .experiments.diverse_beam_corpus import load_diverse_beam_frozen_corpus
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-diverse-beam-search-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument(
        "--shard-count", type=int, default=DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT
    )
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Install the pinned Transformers tokenizer runtime first"
        ) from error
    corpus = load_diverse_beam_frozen_corpus(args.corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("Diverse Beam search requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(
        tokenizer, args.model, args.model_revision
    )
    shard = run_diverse_beam_search_shard(
        corpus,
        tokenizer,
        runtime_tokenizer_identity_hash=identity.identity_hash,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        source_code_commit=args.source_code_commit,
    )
    write_canonical_json_fsynced(args.json, shard.as_dict())
    sys.stdout.write(f"artifact_hash={shard.artifact_hash}\n")
    sys.stdout.write(f"frozen_corpus_hash={shard.frozen_corpus_hash}\n")
    sys.stdout.write(f"shard_index={shard.shard_index}\n")
    sys.stdout.write(f"row_count={len(shard.rows)}\n")
    sys.stdout.write(
        f"detector_access_observed={str(shard.detector_access_observed).lower()}\n"
    )
    sys.stdout.write(
        f"secret_access_observed={str(shard.secret_access_observed).lower()}\n"
    )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
