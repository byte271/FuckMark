from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_json
from .experiments.tiny_dev_detector_evidence import (
    TINY_DEV_PRIMARY_FPR,
    build_tiny_dev_detector_evidence,
)
from .hashing import sha256_json
from .tiny_dev_corpus_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


DEFAULT_CONTEXT_HISTORY_SIZE = 1024
DEFAULT_SAMPLING_TABLE_SEED = 0
DEFAULT_SAMPLING_TABLE_SIZE = 2**16
DEFAULT_SKIP_FIRST_NGRAM_CALLS = False
DEFAULT_DEBUG_MODE = False


def default_watermark_payload() -> dict[str, object]:
    return {
        "ngram_len": DEFAULT_NGRAM_LEN,
        "keys": DEFAULT_KEYS,
        "context_history_size": DEFAULT_CONTEXT_HISTORY_SIZE,
        "sampling_table_seed": DEFAULT_SAMPLING_TABLE_SEED,
        "sampling_table_size": DEFAULT_SAMPLING_TABLE_SIZE,
        "skip_first_ngram_calls": DEFAULT_SKIP_FIRST_NGRAM_CALLS,
        "debug_mode": DEFAULT_DEBUG_MODE,
    }


def default_watermark_config_hash() -> str:
    return sha256_json(default_watermark_payload())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-detector-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/tiny-dev-detector-evidence.json"),
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    payload = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=payload["ngram_len"],
            keys=payload["keys"],
            context_history_size=payload["context_history_size"],
            sampling_table_seed=payload["sampling_table_seed"],
            sampling_table_size=payload["sampling_table_size"],
            skip_first_ngram_calls=payload["skip_first_ngram_calls"],
            debug_mode=payload["debug_mode"],
        ),
        device=args.device,
    )
    evidence = build_tiny_dev_detector_evidence(
        corpus,
        adapter,
        expected_watermark_config_hash=default_watermark_config_hash(),
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(evidence) + "\n", encoding="utf-8")

    sys.stdout.write(f"artifact_hash={evidence.artifact_hash}\n")
    sys.stdout.write(f"corpus_artifact_hash={evidence.tiny_dev_artifact_hash}\n")
    sys.stdout.write(f"adapter_config_hash={evidence.adapter_config_hash}\n")
    sys.stdout.write(f"sampling_table_hash={adapter.sampling_table_hash}\n")
    sys.stdout.write(f"sampling_table_provenance={adapter.sampling_table_provenance}\n")
    for family in evidence.family_evidence:
        sys.stdout.write(f"detector={family.detector_family.value}\n")
        for evaluation in family.threshold_evaluations:
            sys.stdout.write(
                "threshold "
                f"target_fpr={evaluation.target_fpr:g} "
                f"value={evaluation.threshold_value:.17g} "
                f"achieved_calibration_fpr={evaluation.achieved_calibration_fpr:.17g} "
                f"pristine_tpr={evaluation.pristine_baseline.tpr:.17g} "
                f"baseline_status={evaluation.pristine_baseline.status.value} "
                f"attack_negative_fpr={evaluation.attack_negative_fpr:.17g}\n"
            )
        primary = next(
            value for value in family.threshold_evaluations
            if value.target_fpr == TINY_DEV_PRIMARY_FPR
        )
        sys.stdout.write(
            f"primary detector={family.detector_family.value} "
            f"target_fpr={TINY_DEV_PRIMARY_FPR:g} "
            f"pristine_detected={primary.pristine_baseline.detected_count}/"
            f"{primary.pristine_baseline.sample_count} "
            f"status={primary.pristine_baseline.status.value}\n"
        )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
