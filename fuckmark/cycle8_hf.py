from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .config import canonical_json_text
from .corpus.schema import CorpusDomain, WatermarkLabel
from .corpus.tiny_dev import TINY_DEV_TARGET_LENGTH
from .corpus.tiny_dev_generation import TINY_DEV_PAIR_SEED_STRIDE
from .cycle7.whitespace_collapse import CYCLE7_SANITIZER_VARIANT_IDS, sanitize_cycle7_variant
from .cycle8.compare import (
    CYCLE8_DETECTOR_ARM_IDS,
    CYCLE8_MAX_ATTEMPTS,
    measure_carrier_arm,
    summarize_arm,
)
from .cycle8.decision import classify_fixture_compare
from .cycle8.ledger import (
    CYCLE8_EXPLORATORY_ROLE,
    CYCLE8_EXPLORATORY_SEED_BASE,
    CYCLE8_EXPLORATORY_TOPIC,
    assert_cycle8_development_seed,
)
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from .hashing import sha256_json, sha256_text
from .product.domain import is_supported_product_domain_v1


CYCLE8_DETECTOR_VERSION = "cycle8-exploratory-detector-compare-v1"
_CYCLE8_TEMPLATES = {
    CorpusDomain.GENERAL_EXPLANATORY: (
        "Explain in plain English why {topic} matters in careful scientific work. "
        "Write one coherent paragraph without a list."
    ),
    CorpusDomain.TECHNICAL_EXPLANATION: (
        "Give a technical explanation of {topic} in software experiments. "
        "Define the main idea, one failure mode, and one validation check."
    ),
    CorpusDomain.CONVERSATIONAL_PROSE: (
        "Answer a colleague who asks why {topic} matters. "
        "Use natural conversational prose while keeping the explanation precise."
    ),
    CorpusDomain.STRUCTURED_INSTRUCTIONAL: (
        "Write a short three-step instruction for applying {topic} in an experiment. "
        "Use complete sentences and keep each step concrete."
    ),
}


def _detector_arm_summary(rows: tuple[dict[str, object], ...], arm_id: str) -> dict[str, object]:
    watermarked = tuple(
        row for row in rows if row["label"] == WatermarkLabel.WATERMARKED.value and row["arm_id"] == arm_id
    )
    unwatermarked = tuple(
        row for row in rows if row["label"] == WatermarkLabel.UNWATERMARKED.value and row["arm_id"] == arm_id
    )

    def _count(selected, variant, field):
        return sum(bool(row["sanitizers"][variant][field]) for row in selected)

    def _mean(selected, variant):
        return sum(float(row["sanitizers"][variant]["score"]) for row in selected) / len(selected)

    return {
        "arm_id": arm_id,
        "watermarked_row_count": len(watermarked),
        "unwatermarked_row_count": len(unwatermarked),
        "pristine_watermarked_detected": sum(bool(row["pristine_detected"]) for row in watermarked),
        "pristine_unwatermarked_detected": sum(bool(row["pristine_detected"]) for row in unwatermarked),
        "raw_watermarked_detected": _count(watermarked, "raw", "detected"),
        "raw_unwatermarked_detected": _count(unwatermarked, "raw", "detected"),
        "ws_collapse_watermarked_detected": _count(watermarked, "ws_collapse", "detected"),
        "ws_collapse_unwatermarked_detected": _count(unwatermarked, "ws_collapse", "detected"),
        "cf_strip_watermarked_detected": _count(watermarked, "cf_strip", "detected"),
        "nfkc_watermarked_detected": _count(watermarked, "nfkc", "detected"),
        "raw_watermarked_mean_score": _mean(watermarked, "raw"),
        "ws_collapse_watermarked_mean_score": _mean(watermarked, "ws_collapse"),
        "visible_pass_count": sum(bool(row["geometry"]["visible_ok"]) for row in (*watermarked, *unwatermarked)),
        "visible_total_count": len(watermarked) + len(unwatermarked),
    }


def _generate_cycle8_samples(backend: Any, seed_base: int, max_attempts: int) -> tuple[dict[str, object], ...]:
    assert_cycle8_development_seed(seed_base, role=CYCLE8_EXPLORATORY_ROLE)
    samples: list[dict[str, object]] = []
    for pair_index, domain in enumerate(CorpusDomain):
        prompt = _CYCLE8_TEMPLATES[domain].format(topic=CYCLE8_EXPLORATORY_TOPIC)
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = None
        for attempt in range(max_attempts):
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
            if not is_supported_product_domain_v1(control.text):
                continue
            if not is_supported_product_domain_v1(watermarked.text):
                continue
            accepted = (seed, control, watermarked)
            break
        if accepted is None:
            raise RuntimeError(f"Cycle 8 failed to generate an ASCII pair for {domain.value}")
        seed, control, watermarked = accepted
        for label, generated in (
            (WatermarkLabel.UNWATERMARKED, control),
            (WatermarkLabel.WATERMARKED, watermarked),
        ):
            sample_id = f"cycle8-890000-{domain.value}-{label.value}"
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


def _evaluate_samples(
    samples: tuple[dict[str, object], ...],
    tokenizer: Any,
    adapter: Any,
    eos: int,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], dict[str, object]]:
    from .cycle7_stage_a_hf import _score_text
    from .tiny_dev_transform_hf import _encode_text

    def encoder(text: str) -> tuple[int, ...]:
        return _encode_text(tokenizer, text)

    scored_rows: list[dict[str, object]] = []
    geometry_rows: list[dict[str, object]] = []
    for sample in samples:
        measurements = {}
        for arm_id in CYCLE8_DETECTOR_ARM_IDS:
            measurements[arm_id] = measure_carrier_arm(
                arm_id=arm_id,
                source_sample_id=str(sample["sample_id"]),
                source_text=str(sample["text"]),
                encoder=encoder,
            )
        geometry_rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "arms": {arm_id: summarize_arm(measurement) for arm_id, measurement in measurements.items()},
            }
        )
        pristine = _score_text(
            f"{sample['sample_id']}-pristine",
            str(sample["text"]),
            tokenizer,
            adapter,
            eos,
        )
        for arm_id, measurement in measurements.items():
            sanitizers = {}
            for variant in CYCLE7_SANITIZER_VARIANT_IDS:
                text = sanitize_cycle7_variant(variant, str(measurement["transformed_text"]))
                score = _score_text(
                    f"{sample['sample_id']}-{arm_id}-{variant}",
                    text,
                    tokenizer,
                    adapter,
                    eos,
                )
                sanitizers[variant] = {
                    "text_hash": sha256_text(text),
                    "score": score,
                    "detected": score >= CYCLE6_THRESHOLD,
                    "equals_source": text == str(sample["text"]),
                }
            scored_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "label": sample["label"],
                    "domain": sample["domain"],
                    "arm_id": arm_id,
                    "pristine_score": pristine,
                    "pristine_detected": pristine >= CYCLE6_THRESHOLD,
                    "geometry": summarize_arm(measurement),
                    "sanitizers": sanitizers,
                }
            )
    summaries = {
        arm_id: _detector_arm_summary(tuple(scored_rows), arm_id) for arm_id in CYCLE8_DETECTOR_ARM_IDS
    }
    return tuple(geometry_rows), tuple(scored_rows), summaries


def _build_detector_artifact(
    samples: tuple[dict[str, object], ...],
    geometry_rows: tuple[dict[str, object], ...],
    scored_rows: tuple[dict[str, object], ...],
    summaries: dict[str, object],
) -> dict[str, object]:
    from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION

    visible_pass = sum(int(summary["visible_pass_count"]) for summary in summaries.values())
    visible_total = sum(int(summary["visible_total_count"]) for summary in summaries.values())
    artifact = {
        "algorithm_version": CYCLE8_DETECTOR_VERSION,
        "seed_base": CYCLE8_EXPLORATORY_SEED_BASE,
        "topic": CYCLE8_EXPLORATORY_TOPIC,
        "model": DEFAULT_MODEL_ID,
        "model_revision": DEFAULT_MODEL_REVISION,
        "threshold": CYCLE6_THRESHOLD,
        "sanitizer_ids": CYCLE7_SANITIZER_VARIANT_IDS,
        "arm_ids": CYCLE8_DETECTOR_ARM_IDS,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "samples": tuple(
            {
                "sample_id": sample["sample_id"],
                "domain": sample["domain"],
                "label": sample["label"],
                "seed": sample["seed"],
                "text": sample["text"],
                "text_sha256": sample["text_sha256"],
            }
            for sample in samples
        ),
        "geometry_rows": geometry_rows,
        "scored_rows": scored_rows,
        "summaries": summaries,
        "detector_access_used_for_selection": False,
        "secret_access_used_for_selection": False,
    }
    return {**artifact, "artifact_hash": sha256_json({key: value for key, value in artifact.items() if key != "artifact_hash"})}


def run_cycle8_detector_compare(*, device: str = "cpu", max_attempts: int = CYCLE8_MAX_ATTEMPTS) -> dict[str, object]:
    from .cycle7_stage_a_hf import _adapter_and_tokenizer

    assert_cycle8_development_seed(CYCLE8_EXPLORATORY_SEED_BASE, role=CYCLE8_EXPLORATORY_ROLE)
    backend, tokenizer, adapter, _identity_hash, eos = _adapter_and_tokenizer(device)
    samples = _generate_cycle8_samples(backend, CYCLE8_EXPLORATORY_SEED_BASE, max_attempts)
    geometry_rows, scored_rows, summaries = _evaluate_samples(samples, tokenizer, adapter, eos)
    return _build_detector_artifact(samples, geometry_rows, scored_rows, summaries)


def rescore_cycle8_detector_compare(previous: dict[str, object], *, device: str = "cpu") -> dict[str, object]:
    from .cycle7_stage_a_hf import _adapter_and_tokenizer

    assert_cycle8_development_seed(CYCLE8_EXPLORATORY_SEED_BASE, role=CYCLE8_EXPLORATORY_ROLE)
    _backend, tokenizer, adapter, _identity_hash, eos = _adapter_and_tokenizer(device)
    samples = tuple(previous["samples"])
    geometry_rows, scored_rows, summaries = _evaluate_samples(samples, tokenizer, adapter, eos)
    return _build_detector_artifact(samples, geometry_rows, scored_rows, summaries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--max-attempts", type=int, default=CYCLE8_MAX_ATTEMPTS)
    parser.add_argument(
        "--detector-json",
        type=Path,
        default=Path("evidence/cycle8-exploratory-890000-2026-08-25/detector-compare.json"),
    )
    parser.add_argument("--skip-detector", action="store_true")
    parser.add_argument("--rescore-from", type=Path, default=None)
    args = parser.parse_args(argv)
    from .cycle8.compare import run_fixture_compare
    from .cycle8.tokenizer_screen import load_gpt2_encoder

    fixture = run_fixture_compare(encoder=load_gpt2_encoder())
    args.detector_json.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(args.detector_json.parent / "fixture-compare.json", fixture)
    detector = None
    if not args.skip_detector:
        if args.rescore_from is not None:
            import json

            previous = json.loads(args.rescore_from.read_text(encoding="utf-8"))
            detector = rescore_cycle8_detector_compare(previous, device=args.device)
        else:
            detector = run_cycle8_detector_compare(device=args.device, max_attempts=args.max_attempts)
        write_canonical_json_fsynced(args.detector_json, detector)
        fixture = {
            **{key: value for key, value in fixture.items() if key != "artifact_hash"},
            "detector": {"available": True, **detector["summaries"]},
        }
        fixture = {
            **fixture,
            "artifact_hash": sha256_json({key: value for key, value in fixture.items() if key != "artifact_hash"}),
        }
        write_canonical_json_fsynced(args.detector_json.parent / "fixture-compare.json", fixture)
    decision = classify_fixture_compare(fixture)
    write_canonical_json_fsynced(args.detector_json.parent / "decision.json", decision)
    print(canonical_json_text(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
