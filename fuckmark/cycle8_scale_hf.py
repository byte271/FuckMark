from __future__ import annotations

import argparse
from pathlib import Path

from .config import canonical_json_text
from .cycle8.compare import CYCLE8_SCALE_ARM_IDS
from .cycle8.decision import classify_scale_detector_compare
from .cycle8.ledger import CYCLE8_SCALE_EXPLORATORY_SEED_BASE, CYCLE8_SCALE_PAIR_COUNT
from .cycle8.sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from .cycle8_hf import run_cycle8_detector_compare
from .durable_io import write_canonical_json_fsynced
from .seeds.ledger import assert_new_cycle8_scale_generation_seed


CYCLE8_SCALE_DETECTOR_VERSION = "cycle8-scale-detector-compare-v1"


def run_cycle8_scale_detector_compare(
    *,
    device: str = "cpu",
    seed_base: int = CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    pair_count: int = CYCLE8_SCALE_PAIR_COUNT,
    max_attempts: int = 64,
) -> dict[str, object]:
    assert_new_cycle8_scale_generation_seed(seed_base)
    return run_cycle8_detector_compare(
        device=device,
        seed_base=seed_base,
        pair_count=pair_count,
        max_attempts=max_attempts,
        arm_ids=CYCLE8_SCALE_ARM_IDS,
        sanitizer_ids=CYCLE8_SCALE_SANITIZER_VARIANT_IDS,
        sanitize=sanitize_cycle8_scale_variant,
        algorithm_version=CYCLE8_SCALE_DETECTOR_VERSION,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-scale-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, default=CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    parser.add_argument("--pair-count", type=int, default=CYCLE8_SCALE_PAIR_COUNT)
    parser.add_argument("--max-attempts", type=int, default=64)
    parser.add_argument("--detector-json", type=Path, default=None)
    args = parser.parse_args(argv)
    assert_new_cycle8_scale_generation_seed(args.seed_base)
    if args.detector_json is None:
        args.detector_json = Path(f"evidence/cycle8-scale-{args.seed_base}-2026-08-26/detector-compare.json")
    detector = run_cycle8_scale_detector_compare(
        device=args.device,
        seed_base=args.seed_base,
        pair_count=args.pair_count,
        max_attempts=args.max_attempts,
    )
    args.detector_json.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(args.detector_json, detector)
    decision = classify_scale_detector_compare(detector)
    write_canonical_json_fsynced(args.detector_json.parent / "decision.json", decision)
    print(canonical_json_text(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
