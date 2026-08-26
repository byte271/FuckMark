from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import canonical_json_text
from .cycle7.durable_rules import CYCLE7_DURABLE_RULE_CATALOG_VERSION
from .cycle7.ledger import (
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_STAGE_C_VALIDATION_SEED_BASE,
    CYCLE7_STAGE_C_VALIDATION_TOPIC,
    CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_D1_TOPIC,
    CYCLE7_VALIDATION_ROLE,
    assert_development_seed,
    assert_rule_construction_seed,
)
from .cycle7.stage_d import classify_stage_d_density, density_artifact_stage_d
from .cycle7_stage_a_hf import _adapter_and_tokenizer, _build_detector_artifact, _evaluate_samples
from .cycle7_stage_b_hf import _generate_stage_b_samples, _geometry_artifact
from .durable_io import write_canonical_json_fsynced
from .hashing import sha256_json


CYCLE7_STAGE_D_DETECTOR_VERSION = "cycle7-stage-d-detector-compare-v1"


def admit_stage_d1_seed(seed_base: int, *, samples_from: Path | None) -> None:
    if samples_from is None:
        assert_rule_construction_seed(seed_base)
        return
    assert_development_seed(seed_base, role=CYCLE7_EXPLORATORY_ROLE)


def run_stage_d1(
    *,
    device: str = "cpu",
    skip_detector: bool = True,
    samples_from: Path | None = None,
) -> dict[str, object]:
    seed_base = CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE
    topic = CYCLE7_STAGE_D1_TOPIC
    admit_stage_d1_seed(seed_base, samples_from=samples_from)
    backend, tokenizer, adapter, identity_hash, eos = _adapter_and_tokenizer(device)
    if samples_from is not None:
        previous = json.loads(samples_from.read_text(encoding="utf-8"))
        samples = tuple(previous["samples"])
        if int(previous["seed_base"]) != seed_base:
            raise ValueError("Stage D sample file seed_base does not match the requested ledger seed")
    else:
        samples = _generate_stage_b_samples(backend, seed_base, topic, "cycle7-stage-d1")
    density_samples = tuple(
        {"sample_id": sample["sample_id"], "text": sample["text"]} for sample in samples
    )
    density = density_artifact_stage_d(
        density_samples,
        seed_base=seed_base,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )
    geometry = _geometry_artifact(samples, tokenizer, identity_hash, seed_base)
    density_decision = classify_stage_d_density(
        density_summary=density["summary"],
        collapsed_intact_mean=float(geometry["durable_intact_means"]["mean_collapsed_intact_window_count"]),
        source_root_mean=float(geometry["durable_intact_means"]["mean_root_window_count"]),
    )
    detector = None
    if not skip_detector:
        geometry_rows, scored_rows, summaries = _evaluate_samples(
            samples, tokenizer, identity_hash, adapter, eos
        )
        detector = _build_detector_artifact(
            samples,
            geometry_rows,
            scored_rows,
            summaries,
            catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
        )
        detector = {
            **{k: v for k, v in detector.items() if k != "artifact_hash"},
            "algorithm_version": CYCLE7_STAGE_D_DETECTOR_VERSION,
            "seed_base": seed_base,
            "stage": "D1",
            "topic": topic,
        }
        detector = {
            **detector,
            "artifact_hash": sha256_json({k: v for k, v in detector.items() if k != "artifact_hash"}),
        }
    return {
        "samples": samples,
        "density": density,
        "geometry": geometry,
        "decision": density_decision,
        "detector": detector,
        "seed_base": seed_base,
        "topic": topic,
        "stage": "D1",
    }


def run_stage_d_validation(
    *,
    device: str = "cpu",
    skip_detector: bool = True,
    samples_from: Path | None = None,
) -> dict[str, object]:
    seed_base = CYCLE7_STAGE_C_VALIDATION_SEED_BASE
    topic = CYCLE7_STAGE_C_VALIDATION_TOPIC
    assert_development_seed(seed_base, role=CYCLE7_VALIDATION_ROLE)
    backend, tokenizer, adapter, identity_hash, eos = _adapter_and_tokenizer(device)
    if samples_from is not None:
        previous = json.loads(samples_from.read_text(encoding="utf-8"))
        samples = tuple(previous["samples"])
        if int(previous["seed_base"]) != seed_base:
            raise ValueError("Stage D sample file seed_base does not match the requested ledger seed")
    else:
        samples = _generate_stage_b_samples(backend, seed_base, topic, "cycle7-stage-d-validation")
    density_samples = tuple(
        {"sample_id": sample["sample_id"], "text": sample["text"]} for sample in samples
    )
    density = density_artifact_stage_d(
        density_samples,
        seed_base=seed_base,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )
    geometry = _geometry_artifact(samples, tokenizer, identity_hash, seed_base)
    density_decision = classify_stage_d_density(
        density_summary=density["summary"],
        collapsed_intact_mean=float(geometry["durable_intact_means"]["mean_collapsed_intact_window_count"]),
        source_root_mean=float(geometry["durable_intact_means"]["mean_root_window_count"]),
    )
    detector = None
    if not skip_detector:
        geometry_rows, scored_rows, summaries = _evaluate_samples(
            samples, tokenizer, identity_hash, adapter, eos
        )
        detector = _build_detector_artifact(
            samples,
            geometry_rows,
            scored_rows,
            summaries,
            catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
        )
        detector = {
            **{k: v for k, v in detector.items() if k != "artifact_hash"},
            "algorithm_version": CYCLE7_STAGE_D_DETECTOR_VERSION,
            "seed_base": seed_base,
            "stage": "D-validation",
            "topic": topic,
        }
        detector = {
            **detector,
            "artifact_hash": sha256_json({k: v for k, v in detector.items() if k != "artifact_hash"}),
        }
    return {
        "samples": samples,
        "density": density,
        "geometry": geometry,
        "decision": density_decision,
        "detector": detector,
        "seed_base": seed_base,
        "topic": topic,
        "stage": "D-validation",
    }


def _write_stage_d_bundle(output_dir: Path, bundle: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_payload = {
        "algorithm_version": "cycle7-stage-d-samples-v1",
        "seed_base": bundle["seed_base"],
        "topic": bundle["topic"],
        "stage": bundle["stage"],
        "durable_catalog_version": CYCLE7_DURABLE_RULE_CATALOG_VERSION,
        "samples": tuple(
            {
                "sample_id": sample["sample_id"],
                "domain": sample["domain"],
                "label": sample["label"],
                "prompt": sample["prompt"],
                "seed": sample["seed"],
                "text": sample["text"],
                "text_sha256": sample["text_sha256"],
            }
            for sample in bundle["samples"]
        ),
        "detector_access_used_for_selection": False,
    }
    sample_payload = {
        **sample_payload,
        "artifact_hash": sha256_json({k: v for k, v in sample_payload.items() if k != "artifact_hash"}),
    }
    write_canonical_json_fsynced(output_dir / "samples.json", sample_payload)
    write_canonical_json_fsynced(output_dir / "density.json", bundle["density"])
    write_canonical_json_fsynced(output_dir / "geometry.json", bundle["geometry"])
    write_canonical_json_fsynced(output_dir / "decision.json", bundle["decision"])
    if bundle["detector"] is not None:
        write_canonical_json_fsynced(output_dir / "detector-compare.json", bundle["detector"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle7-stage-d")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/cycle7-stage-d-2026-08-25"),
    )
    parser.add_argument("--skip-detector", action="store_true", default=True)
    parser.add_argument("--with-detector", action="store_true")
    parser.add_argument("--samples-from", type=Path, default=None)
    parser.add_argument("--validation", action="store_true")
    args = parser.parse_args(argv)
    skip_detector = not args.with_detector
    if args.validation:
        if args.output_dir == Path("evidence/cycle7-stage-d-2026-08-25"):
            args.output_dir = Path("evidence/cycle7-stage-d-validation-880000-2026-08-25")
        bundle = run_stage_d_validation(
            device=args.device,
            skip_detector=skip_detector,
            samples_from=args.samples_from,
        )
    else:
        bundle = run_stage_d1(
            device=args.device,
            skip_detector=skip_detector,
            samples_from=args.samples_from,
        )
    _write_stage_d_bundle(args.output_dir, bundle)
    print(canonical_json_text(bundle["decision"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
