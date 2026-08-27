from __future__ import annotations

import argparse
from pathlib import Path

from .config import canonical_json_text
from .cycle8.gate_v2 import (
    CYCLE8_GATE_V2_CONFIRMATION_DETECTOR_VERSION,
    CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT,
    GATE_V2_ARM_IDS,
    GATE_V2_CONFIRMATION_SEED_BASES,
    GATE_V2_MIX_ARM_ID,
    GATE_V2_SCORED_SANITIZER_IDS,
    assert_gate_v2_confirmation_generation_seed,
    gate_v2_confirmation_artifact_path,
    sanitize_gate_v2_variant,
)
from .cycle8.decision import classify_scale_detector_compare
from .cycle8_hf import run_cycle8_detector_compare
from .durable_io import write_canonical_json_fsynced
from .seeds.ledger import CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES, CYCLE8_SCALE_VALIDATION_SEED_BASE


def run_cycle8_gate_v2_confirmation_detector_compare(
    *,
    device: str = "cpu",
    seed_base: int,
    pair_count: int = CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT,
    max_attempts: int = 64,
) -> dict[str, object]:
    assert_gate_v2_confirmation_generation_seed(seed_base)
    return run_cycle8_detector_compare(
        device=device,
        seed_base=seed_base,
        pair_count=pair_count,
        max_attempts=max_attempts,
        arm_ids=GATE_V2_ARM_IDS,
        sanitizer_ids=GATE_V2_SCORED_SANITIZER_IDS,
        sanitize=sanitize_gate_v2_variant,
        algorithm_version=CYCLE8_GATE_V2_CONFIRMATION_DETECTOR_VERSION,
        allow_gate_v2_confirmation=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-gate-v2-confirmation-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, required=True)
    parser.add_argument("--pair-count", type=int, default=CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT)
    parser.add_argument("--max-attempts", type=int, default=64)
    parser.add_argument("--detector-json", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.seed_base in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        raise ValueError("spent mix-freeze confirmation seeds must not be reused")
    if args.seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("do not generate 950000")
    if args.seed_base not in GATE_V2_CONFIRMATION_SEED_BASES:
        raise ValueError("seed_base is not a Gate v2 confirmation seed")
    if args.detector_json is None:
        args.detector_json = Path(gate_v2_confirmation_artifact_path(args.seed_base))
    if args.detector_json.exists():
        raise ValueError("Gate v2 confirmation artifact already exists; do not rerun looking for zero")
    detector = run_cycle8_gate_v2_confirmation_detector_compare(
        device=args.device,
        seed_base=args.seed_base,
        pair_count=args.pair_count,
        max_attempts=args.max_attempts,
    )
    args.detector_json.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(args.detector_json, detector)
    decision = classify_scale_detector_compare(
        detector,
        transformed_arm_id=GATE_V2_MIX_ARM_ID,
    )
    write_canonical_json_fsynced(args.detector_json.parent / "decision.json", decision)
    print(canonical_json_text(decision), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
