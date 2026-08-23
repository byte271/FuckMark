from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .corpus.measurement_calibration_io import load_measurement_calibration_corpus_json
from .durable_io import write_canonical_json_fsynced
from .experiments.measurement_threshold import build_fixed_threshold_artifact
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    runtime_tokenizer_identity_public,
)
from .tiny_dev_detector_hf import default_watermark_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-measurement-threshold-hf")
    parser.add_argument("--calibration-corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    corpus = load_measurement_calibration_corpus_json(args.calibration_corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match the calibration corpus")
    watermark_payload = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=watermark_payload["ngram_len"],
            keys=watermark_payload["keys"],
            context_history_size=watermark_payload["context_history_size"],
            sampling_table_seed=watermark_payload["sampling_table_seed"],
            sampling_table_size=watermark_payload["sampling_table_size"],
            skip_first_ngram_calls=watermark_payload["skip_first_ngram_calls"],
            debug_mode=watermark_payload["debug_mode"],
        ),
        device=args.device,
    )
    artifact = build_fixed_threshold_artifact(
        corpus,
        adapter,
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    write_canonical_json_fsynced(args.json, artifact)
    sys.stdout.write(f"artifact_hash={artifact['artifact_hash']}\n")
    sys.stdout.write(f"threshold={artifact['threshold']!r}\n")
    sys.stdout.write(f"calibration_exceedances={artifact['calibration_exceedances']}/{artifact['calibration_negative_count']}\n")
    sys.stdout.write(f"audit_exceedances={artifact['audit_exceedances']}/{artifact['audit_negative_count']}\n")
    sys.stdout.write(f"audit_realized_fpr={artifact['audit_realized_fpr']}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
