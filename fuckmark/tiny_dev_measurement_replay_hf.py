from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .config import canonical_json_text
from .experiments.tiny_dev_calibration_opportunity_audit import audit_frozen_tiny_dev_calibration_opportunity
from .experiments.tiny_dev_residual_replay import replay_frozen_tiny_dev_residual_signal


DEFAULT_MODEL_ID = "openai-community/gpt2"
DEFAULT_MODEL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"


def _load(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json_text(value) + "\n", encoding="utf-8", newline="\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-measurement-replay-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--calibration-audit-json", type=Path, required=True)
    parser.add_argument("--residual-replay-json", type=Path, required=True)
    return parser


def _token_ids(tokenizer, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        if len(ids) != 1:
            raise RuntimeError("unexpected batched tokenizer output")
        ids = ids[0]
    return tuple(int(value) for value in ids)


def _verify_attack_source_roundtrip(corpus: Mapping[str, object], tokenizer) -> None:
    manifest = corpus.get("manifest")
    if not isinstance(manifest, Mapping):
        raise TypeError("corpus manifest must be a mapping")
    samples = manifest.get("samples")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes, bytearray)):
        raise TypeError("corpus samples must be a sequence")
    checked = 0
    for value in samples:
        if not isinstance(value, Mapping):
            raise TypeError("corpus sample must be a mapping")
        if value.get("split") != "attack_development":
            continue
        text = value.get("text")
        track = value.get("text_only_tokens")
        if not isinstance(text, str) or not isinstance(track, Mapping):
            raise TypeError("attack sample text/token track is invalid")
        recorded = track.get("token_ids")
        if not isinstance(recorded, Sequence) or isinstance(recorded, (str, bytes, bytearray)):
            raise TypeError("attack sample token IDs are invalid")
        if _token_ids(tokenizer, text) != tuple(int(item) for item in recorded):
            raise RuntimeError(f"public tokenizer replay drifted for {value.get('sample_id')}")
        checked += 1
    if checked != 8:
        raise RuntimeError("expected eight TinyDev attack-development source samples")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.model != DEFAULT_MODEL_ID or args.model_revision != DEFAULT_MODEL_REVISION:
        raise RuntimeError("TinyDev measurement replay requires the frozen public tokenizer identity")
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error
    corpus = _load(args.corpus_json)
    plan = _load(args.plan_json)
    evidence = _load(args.evidence_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("TinyDev measurement replay requires a fast public tokenizer")
    _verify_attack_source_roundtrip(corpus, tokenizer)
    calibration = audit_frozen_tiny_dev_calibration_opportunity(corpus, evidence)
    replay = replay_frozen_tiny_dev_residual_signal(
        plan,
        evidence,
        corpus,
        retokenize=lambda text: _token_ids(tokenizer, text),
    )
    calibration_payload = calibration.payload() | {"audit_hash": calibration.audit_hash}
    replay_payload = replay.payload() | {"artifact_hash": replay.artifact_hash}
    _write(args.calibration_audit_json, calibration_payload)
    _write(args.residual_replay_json, replay_payload)
    comparison = replay.comparison
    sys.stdout.write(f"calibration_audit_hash={calibration.audit_hash}\n")
    sys.stdout.write(f"calibration_resolution_pass={calibration.calibration_resolution_pass}\n")
    sys.stdout.write(f"nominal_length_proxy_pass={calibration.nominal_length_proxy_pass}\n")
    sys.stdout.write(f"valid_opportunity_cv={calibration.valid_observations.coefficient_of_variation:.12f}\n")
    sys.stdout.write(f"residual_replay_hash={replay.artifact_hash}\n")
    sys.stdout.write(f"old_source_centered_pearson={comparison.old_source_centered_pearson:.12f}\n")
    sys.stdout.write(f"new_source_centered_pearson={comparison.new_source_centered_pearson:.12f}\n")
    sys.stdout.write(f"old_loso_rmse={comparison.old_leave_one_source_out_rmse:.12f}\n")
    sys.stdout.write(f"new_loso_rmse={comparison.new_leave_one_source_out_rmse:.12f}\n")
    sys.stdout.write(f"predictor_pearson={comparison.predictor_pearson:.12f}\n")
    sys.stdout.write(f"decision={comparison.decision.value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
