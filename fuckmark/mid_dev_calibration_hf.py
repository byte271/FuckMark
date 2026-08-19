from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus.mid_dev_calibration_generation import build_real_mid_dev_calibration
from .mid_dev_corpus_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    HuggingFaceMidDevBackend,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-calibration-hf")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/mid-dev-length-calibration.json"),
    )
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
    artifact = build_real_mid_dev_calibration(backend)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"source_profile_hash={artifact.source_profile_hash}\n")
    sys.stdout.write(f"sample_count={len(artifact.manifest.samples)}\n")
    sys.stdout.write(f"negatives_per_length={artifact.negatives_per_length}\n")
    sys.stdout.write(f"target_lengths={','.join(str(value) for value in artifact.target_lengths)}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
