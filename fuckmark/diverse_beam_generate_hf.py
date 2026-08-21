from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .durable_io import write_canonical_json_fsynced
from .experiments.diverse_beam_corpus import (
    DIVERSE_BEAM_GENERATION_SHARD_COUNT,
    generate_diverse_beam_shard,
)
from .mid_dev_corpus_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    HuggingFaceMidDevBackend,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-diverse-beam-generate-hf")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument(
        "--shard-count", type=int, default=DIVERSE_BEAM_GENERATION_SHARD_COUNT
    )
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    backend = HuggingFaceMidDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    shard = generate_diverse_beam_shard(
        backend,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        source_code_commit=args.source_code_commit,
    )
    write_canonical_json_fsynced(args.json, shard.as_dict())
    sys.stdout.write(f"artifact_hash={shard.artifact_hash}\n")
    sys.stdout.write(f"prompt_profile_hash={shard.prompt_profile_hash}\n")
    sys.stdout.write(f"shard_index={shard.shard_index}\n")
    sys.stdout.write(f"sample_count={len(shard.samples)}\n")
    sys.stdout.write(f"model_identity_hash={shard.model_identity_hash}\n")
    sys.stdout.write(f"watermark_condition_hash={shard.watermark_condition_hash}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
