from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import canonical_json_text
from .cycle8.detector_transfer import (
    CYCLE8_MIX_DETECTOR_TRANSFER_PATH,
    build_mix_mean_transfer_scorecard,
    confirmation_source_paths,
)
from .cycle8.letter_mix import apply_letter_alternating_mix
from .cycle7_stage_a_hf import _adapter_and_tokenizer
from .detectors.mean import mean_evidence, weighted_mean_evidence
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from .hashing import sha256_text
from .native_observations import build_native_observations
from .tiny_dev_transform_hf import _encode_text


def _score(sample_id: str, text: str, tokenizer, adapter, eos: int) -> dict[str, object]:
    tokens = _encode_text(tokenizer, text)
    batch = build_native_observations(sample_id, tokens, eos, adapter)
    mean = mean_evidence(batch)
    weighted = weighted_mean_evidence(batch)
    mean_score = float(mean.raw_score)
    weighted_score = float(weighted.raw_score)
    return {
        "mean_score": mean_score,
        "weighted_mean_score": weighted_score,
        "mean_detected": mean_score >= CYCLE6_THRESHOLD,
        "weighted_mean_detected": weighted_score >= CYCLE6_THRESHOLD,
        "text_sha256": sha256_text(text),
    }


def collect_mix_mean_transfer_rows(*, device: str = "cpu") -> list[dict[str, object]]:
    _backend, tokenizer, adapter, _identity, eos = _adapter_and_tokenizer(device)
    rows: list[dict[str, object]] = []
    for seed_base, relative in confirmation_source_paths():
        artifact = Path(relative)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        for sample in payload["samples"]:
            source = str(sample["text"])
            transformed = apply_letter_alternating_mix(source)
            sample_id = str(sample["sample_id"])
            rows.append(
                {
                    "sample_id": sample_id,
                    "seed_base": seed_base,
                    "label": sample["label"],
                    "domain": sample["domain"],
                    "source_sha256": sample["text_sha256"],
                    "identity": _score(f"{sample_id}-identity", source, tokenizer, adapter, eos),
                    "mix": _score(f"{sample_id}-mix", transformed, tokenizer, adapter, eos),
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-mix-mean-transfer")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--json", type=Path, default=Path(CYCLE8_MIX_DETECTOR_TRANSFER_PATH))
    args = parser.parse_args(argv)
    rows = collect_mix_mean_transfer_rows(device=args.device)
    scorecard = build_mix_mean_transfer_scorecard(rows)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(args.json, scorecard)
    print(canonical_json_text({key: scorecard[key] for key in scorecard if key != "rows"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
