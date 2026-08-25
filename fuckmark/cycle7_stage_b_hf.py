from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import canonical_json_text
from .corpus.schema import CorpusDomain, WatermarkLabel
from .corpus.tiny_dev import TINY_DEV_TARGET_LENGTH
from .corpus.tiny_dev_generation import TINY_DEV_DEFAULT_MAX_ATTEMPTS, TINY_DEV_PAIR_SEED_STRIDE
from .cycle7.compare import (
    CYCLE6_SPACING_ARM_ID,
    CYCLE7_COMBINED_ARM_ID,
    CYCLE7_DURABLE_ARM_ID,
    compare_arms_on_text,
    summarize_arm,
)
from .cycle7.durable_rules import CYCLE7_DURABLE_RULE_CATALOG_VERSION
from .cycle7.ledger import (
    CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_B1_TOPIC,
    CYCLE7_VALIDATION_ROLE,
    CYCLE7_VALIDATION_SEED_BASE,
    CYCLE7_VALIDATION_TOPIC,
    assert_development_seed,
    assert_rule_construction_seed,
)
from .cycle7.stage_b import classify_stage_b_density, density_artifact, geometry_intact_means
from .cycle7_stage_a_hf import (
    _STAGE_A_TEMPLATES,
    _adapter_and_tokenizer,
    _build_detector_artifact,
    _evaluate_samples,
)
from .durable_io import write_canonical_json_fsynced
from .hashing import sha256_json, sha256_text
from .tiny_dev_corpus_hf import HuggingFaceTinyDevBackend


CYCLE7_STAGE_B_DETECTOR_VERSION = "cycle7-stage-b-detector-compare-v1"


def _generate_stage_b_samples(
    backend: HuggingFaceTinyDevBackend,
    seed_base: int,
    topic: str,
    sample_prefix: str,
) -> tuple[dict[str, object], ...]:
    samples: list[dict[str, object]] = []
    for pair_index, domain in enumerate(CorpusDomain):
        prompt = _STAGE_A_TEMPLATES[domain].format(topic=topic)
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = None
        for attempt in range(TINY_DEV_DEFAULT_MAX_ATTEMPTS):
            seed = pair_seed_base + attempt
            try:
                control = backend.generate(prompt, seed, watermarked=False)
                watermarked = backend.generate(prompt, seed, watermarked=True)
            except RuntimeError as error:
                message = str(error)
                if "empty decoded continuation" not in message and "text-only re-encoding" not in message:
                    raise
                continue
            if len(control.continuation_token_ids) != TINY_DEV_TARGET_LENGTH:
                continue
            if len(watermarked.continuation_token_ids) != TINY_DEV_TARGET_LENGTH:
                continue
            if control.text == watermarked.text:
                continue
            accepted = (seed, control, watermarked)
            break
        if accepted is None:
            raise RuntimeError(f"Cycle 7 Stage B failed to generate a pair for {domain.value}")
        seed, control, watermarked = accepted
        for label, generated in (
            (WatermarkLabel.UNWATERMARKED, control),
            (WatermarkLabel.WATERMARKED, watermarked),
        ):
            sample_id = f"{sample_prefix}-{domain.value}-{label.value}"
            samples.append(
                {
                    "sample_id": sample_id,
                    "domain": domain.value,
                    "label": label.value,
                    "prompt": prompt,
                    "seed": seed,
                    "text": generated.text,
                    "text_sha256": sha256_text(generated.text),
                    "text_only_token_ids": generated.text_only_token_ids,
                }
            )
    return tuple(samples)


def _generate_stage_b1_samples(backend: HuggingFaceTinyDevBackend, seed_base: int) -> tuple[dict[str, object], ...]:
    assert_rule_construction_seed(seed_base)
    return _generate_stage_b_samples(
        backend,
        seed_base,
        CYCLE7_STAGE_B1_TOPIC,
        "cycle7-stage-b1",
    )


def _geometry_artifact(
    samples: tuple[dict[str, object], ...],
    tokenizer: Any,
    identity_hash: str,
    seed_base: int,
) -> dict[str, object]:
    rows = []
    for sample in samples:
        arms = compare_arms_on_text(
            source_sample_id=str(sample["sample_id"]),
            source_text=str(sample["text"]),
            tokenizer=tokenizer,
            tokenizer_identity_hash=identity_hash,
        )
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "arms": {arm_id: summarize_arm(measurement) for arm_id, measurement in arms.items()},
            }
        )
    durable_samples = tuple(
        {"sample_id": sample["sample_id"], "text": sample["text"]} for sample in samples
    )
    intact = geometry_intact_means(durable_samples, tokenizer, identity_hash)
    payload = {
        "algorithm_version": "cycle7-stage-b-geometry-v1",
        "seed_base": seed_base,
        "durable_catalog_version": CYCLE7_DURABLE_RULE_CATALOG_VERSION,
        "detector_access_used_for_selection": False,
        "rows": tuple(rows),
        "durable_intact_means": intact,
        "arm_ids": (CYCLE6_SPACING_ARM_ID, CYCLE7_DURABLE_ARM_ID, CYCLE7_COMBINED_ARM_ID),
    }
    return {**payload, "artifact_hash": sha256_json({k: v for k, v in payload.items() if k != "artifact_hash"})}


def run_stage_b(
    *,
    seed_base: int,
    topic: str,
    stage: str,
    sample_prefix: str,
    admit,
    device: str = "cpu",
    skip_detector: bool = True,
    samples_from: Path | None = None,
) -> dict[str, object]:
    admit(seed_base)
    backend, tokenizer, adapter, identity_hash, eos = _adapter_and_tokenizer(device)
    if samples_from is not None:
        previous = json.loads(samples_from.read_text(encoding="utf-8"))
        samples = tuple(previous["samples"])
        if int(previous["seed_base"]) != seed_base:
            raise ValueError("Stage B sample file seed_base does not match the requested ledger seed")
    else:
        samples = _generate_stage_b_samples(backend, seed_base, topic, sample_prefix)
    density_samples = tuple(
        {"sample_id": sample["sample_id"], "text": sample["text"]} for sample in samples
    )
    density = density_artifact(
        density_samples,
        seed_base=seed_base,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )
    geometry = _geometry_artifact(samples, tokenizer, identity_hash, seed_base)
    density_decision = classify_stage_b_density(
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
            "algorithm_version": CYCLE7_STAGE_B_DETECTOR_VERSION,
            "seed_base": seed_base,
            "stage": stage,
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
        "stage": stage,
    }


def run_stage_b1(
    *,
    device: str = "cpu",
    skip_detector: bool = True,
    samples_from: Path | None = None,
) -> dict[str, object]:
    return run_stage_b(
        seed_base=CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
        topic=CYCLE7_STAGE_B1_TOPIC,
        stage="B1",
        sample_prefix="cycle7-stage-b1",
        admit=assert_rule_construction_seed,
        device=device,
        skip_detector=skip_detector,
        samples_from=samples_from,
    )


def run_stage_b_validation(
    *,
    device: str = "cpu",
    skip_detector: bool = True,
    samples_from: Path | None = None,
) -> dict[str, object]:
    def _admit(seed_base: int) -> None:
        assert_development_seed(seed_base, role=CYCLE7_VALIDATION_ROLE)

    return run_stage_b(
        seed_base=CYCLE7_VALIDATION_SEED_BASE,
        topic=CYCLE7_VALIDATION_TOPIC,
        stage="B3",
        sample_prefix="cycle7-stage-b3",
        admit=_admit,
        device=device,
        skip_detector=skip_detector,
        samples_from=samples_from,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle7-stage-b")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/cycle7-stage-b-2026-08-25"),
    )
    parser.add_argument("--skip-detector", action="store_true", default=True)
    parser.add_argument("--with-detector", action="store_true")
    parser.add_argument("--samples-from", type=Path, default=None)
    parser.add_argument("--validation", action="store_true")
    args = parser.parse_args(argv)
    skip_detector = not args.with_detector
    if args.validation:
        if args.output_dir == Path("evidence/cycle7-stage-b-2026-08-25"):
            args.output_dir = Path("evidence/cycle7-stage-b-validation-820000-2026-08-25")
        bundle = run_stage_b_validation(
            device=args.device,
            skip_detector=skip_detector,
            samples_from=args.samples_from,
        )
    else:
        bundle = run_stage_b1(
            device=args.device,
            skip_detector=skip_detector,
            samples_from=args.samples_from,
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sample_payload = {
        "algorithm_version": "cycle7-stage-b-samples-v1",
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
    write_canonical_json_fsynced(args.output_dir / "samples.json", sample_payload)
    write_canonical_json_fsynced(args.output_dir / "density.json", bundle["density"])
    write_canonical_json_fsynced(args.output_dir / "geometry.json", bundle["geometry"])
    write_canonical_json_fsynced(args.output_dir / "decision.json", bundle["decision"])
    if bundle["detector"] is not None:
        write_canonical_json_fsynced(args.output_dir / "detector-compare.json", bundle["detector"])
    print(canonical_json_text(bundle["decision"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
