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
    CYCLE8_REPLICATION_ROLE,
    CYCLE8_REPLICATION_TOPIC,
    CYCLE8_SCALE_EXPLORATORY_ROLE,
    CYCLE8_SCALE_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_REPLICATION_ROLE,
    CYCLE8_SCALE_REPLICATION_TOPIC,
    CYCLE8_SCALE_VALIDATION_ROLE,
    CYCLE8_SCALE_VALIDATION_TOPIC,
    CYCLE8_DENSITY_EXPLORATORY_ROLE,
    CYCLE8_DENSITY_EXPLORATORY_TOPIC,
    CYCLE8_LETTER_EXPLORATORY_ROLE,
    CYCLE8_LETTER_EXPLORATORY_TOPIC,
    CYCLE8_LETTER_BENCHMARK_PRIMARY_ROLE,
    CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC,
    CYCLE8_LETTER_BENCHMARK_REPLICATION_ROLE,
    CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC,
    CYCLE8_VALIDATION_ROLE,
    CYCLE8_VALIDATION_TOPIC,
    assert_cycle8_development_seed,
    role_for_seed_base,
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

    def _score_stats(selected, variant):
        values = tuple(float(row["sanitizers"][variant]["score"]) for row in selected)
        ordered = tuple(sorted(values))
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
        return {
            "mean": sum(values) / len(values),
            "median": median,
            "min": ordered[0],
            "max": ordered[-1],
        }

    raw_wm = _score_stats(watermarked, "raw") if watermarked else {"mean": None, "median": None, "min": None, "max": None}
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
        "nfkc_cf_strip_watermarked_detected": _count(watermarked, "nfkc_cf_strip", "detected"),
        "ws_collapse_nfkc_cf_strip_watermarked_detected": _count(watermarked, "ws_collapse_nfkc_cf_strip", "detected"),
        "nfc_watermarked_detected": (
            _count(watermarked, "nfc", "detected") if watermarked and "nfc" in watermarked[0]["sanitizers"] else None
        ),
        "raw_watermarked_mean_score": raw_wm["mean"],
        "raw_watermarked_median_score": raw_wm["median"],
        "raw_watermarked_min_score": raw_wm["min"],
        "raw_watermarked_max_score": raw_wm["max"],
        "ws_collapse_watermarked_mean_score": _mean(watermarked, "ws_collapse") if watermarked else None,
        "visible_pass_count": sum(bool(row["geometry"]["visible_ok"]) for row in (*watermarked, *unwatermarked)),
        "visible_total_count": len(watermarked) + len(unwatermarked),
        "inserted_count_mean": (
            sum(int(row["geometry"]["inserted_count"]) for row in (*watermarked, *unwatermarked))
            / (len(watermarked) + len(unwatermarked))
            if watermarked or unwatermarked
            else 0
        ),
        "utf8_overhead_mean": (
            sum(int(row["geometry"]["utf8_overhead"]) for row in (*watermarked, *unwatermarked))
            / (len(watermarked) + len(unwatermarked))
            if watermarked or unwatermarked
            else 0
        ),
        "hard_invariant_blocked_mean": (
            sum(int(row["geometry"].get("hard_invariant_blocked_count") or 0) for row in (*watermarked, *unwatermarked))
            / (len(watermarked) + len(unwatermarked))
            if watermarked or unwatermarked
            else 0
        ),
        "fail_closed_identity_count": sum(
            bool(row["geometry"].get("fail_closed_identity")) for row in (*watermarked, *unwatermarked)
        ),
    }


def _topic_for_seed(seed_base: int) -> str:
    role = role_for_seed_base(seed_base)
    if role == CYCLE8_EXPLORATORY_ROLE:
        return CYCLE8_EXPLORATORY_TOPIC
    if role == CYCLE8_REPLICATION_ROLE:
        return CYCLE8_REPLICATION_TOPIC
    if role == CYCLE8_VALIDATION_ROLE:
        return CYCLE8_VALIDATION_TOPIC
    if role == CYCLE8_SCALE_EXPLORATORY_ROLE:
        return CYCLE8_SCALE_EXPLORATORY_TOPIC
    if role == CYCLE8_SCALE_REPLICATION_ROLE:
        return CYCLE8_SCALE_REPLICATION_TOPIC
    if role == CYCLE8_SCALE_VALIDATION_ROLE:
        return CYCLE8_SCALE_VALIDATION_TOPIC
    if role == CYCLE8_DENSITY_EXPLORATORY_ROLE:
        return CYCLE8_DENSITY_EXPLORATORY_TOPIC
    if role == CYCLE8_LETTER_EXPLORATORY_ROLE:
        return CYCLE8_LETTER_EXPLORATORY_TOPIC
    if role == CYCLE8_LETTER_BENCHMARK_PRIMARY_ROLE:
        return CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC
    if role == CYCLE8_LETTER_BENCHMARK_REPLICATION_ROLE:
        return CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC
    raise ValueError("Cycle 8 detector compare only runs exploratory, replication, validation, scale, density, letter, or letter-benchmark seeds")


def _generate_cycle8_samples(
    backend: Any,
    seed_base: int,
    max_attempts: int,
    *,
    pair_count: int | None = None,
) -> tuple[dict[str, object], ...]:
    role = role_for_seed_base(seed_base)
    if role is None:
        raise ValueError("seed_base is not in the Cycle 8 ledger")
    assert_cycle8_development_seed(seed_base, role=role)
    topic = _topic_for_seed(seed_base)
    domains = tuple(CorpusDomain)
    if pair_count is None:
        pair_count = len(domains)
    if not isinstance(pair_count, int) or isinstance(pair_count, bool) or pair_count <= 0:
        raise ValueError("pair_count must be a positive integer")
    if pair_count % len(domains) != 0:
        raise ValueError("pair_count must be a multiple of the Cycle 8 domain count")
    samples: list[dict[str, object]] = []
    for pair_index in range(pair_count):
        domain = domains[pair_index % len(domains)]
        prompt = _CYCLE8_TEMPLATES[domain].format(topic=topic)
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
            raise RuntimeError(f"Cycle 8 failed to generate an ASCII pair for {domain.value} pair {pair_index}")
        seed, control, watermarked = accepted
        for label, generated in (
            (WatermarkLabel.UNWATERMARKED, control),
            (WatermarkLabel.WATERMARKED, watermarked),
        ):
            if pair_count == len(domains):
                sample_id = f"cycle8-{seed_base}-{domain.value}-{label.value}"
            else:
                sample_id = f"cycle8-{seed_base}-{pair_index:02d}-{domain.value}-{label.value}"
            samples.append(
                {
                    "sample_id": sample_id,
                    "domain": domain.value,
                    "label": label.value,
                    "prompt": prompt,
                    "seed": seed,
                    "pair_index": pair_index,
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
    *,
    arm_ids: tuple[str, ...] = CYCLE8_DETECTOR_ARM_IDS,
    sanitizer_ids: tuple[str, ...] = CYCLE7_SANITIZER_VARIANT_IDS,
    sanitize=sanitize_cycle7_variant,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], dict[str, object]]:
    from .cycle7_stage_a_hf import _score_text
    from .tiny_dev_transform_hf import _encode_text

    def encoder(text: str) -> tuple[int, ...]:
        return _encode_text(tokenizer, text)

    scored_rows: list[dict[str, object]] = []
    geometry_rows: list[dict[str, object]] = []
    for sample in samples:
        measurements = {}
        for arm_id in arm_ids:
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
            for variant in sanitizer_ids:
                text = sanitize(variant, str(measurement["transformed_text"]))
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
                    "equals_transformed": text == str(measurement["transformed_text"]),
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
    summaries = {arm_id: _detector_arm_summary(tuple(scored_rows), arm_id) for arm_id in arm_ids}
    return tuple(geometry_rows), tuple(scored_rows), summaries


def _build_detector_artifact(
    samples: tuple[dict[str, object], ...],
    geometry_rows: tuple[dict[str, object], ...],
    scored_rows: tuple[dict[str, object], ...],
    summaries: dict[str, object],
    *,
    seed_base: int,
    algorithm_version: str = CYCLE8_DETECTOR_VERSION,
    arm_ids: tuple[str, ...] = CYCLE8_DETECTOR_ARM_IDS,
    sanitizer_ids: tuple[str, ...] = CYCLE7_SANITIZER_VARIANT_IDS,
    pair_count: int | None = None,
) -> dict[str, object]:
    from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION

    visible_pass = sum(int(summary["visible_pass_count"]) for summary in summaries.values())
    visible_total = sum(int(summary["visible_total_count"]) for summary in summaries.values())
    artifact = {
        "algorithm_version": algorithm_version,
        "seed_base": seed_base,
        "topic": _topic_for_seed(seed_base),
        "pair_count": pair_count if pair_count is not None else len({sample["sample_id"] for sample in samples}) // 2,
        "model": DEFAULT_MODEL_ID,
        "model_revision": DEFAULT_MODEL_REVISION,
        "threshold": CYCLE6_THRESHOLD,
        "sanitizer_ids": sanitizer_ids,
        "arm_ids": arm_ids,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "samples": tuple(
            {
                "sample_id": sample["sample_id"],
                "domain": sample["domain"],
                "label": sample["label"],
                "seed": sample["seed"],
                "pair_index": sample.get("pair_index"),
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


def run_cycle8_detector_compare(
    *,
    device: str = "cpu",
    max_attempts: int = CYCLE8_MAX_ATTEMPTS,
    seed_base: int = CYCLE8_EXPLORATORY_SEED_BASE,
    pair_count: int | None = None,
    arm_ids: tuple[str, ...] = CYCLE8_DETECTOR_ARM_IDS,
    sanitizer_ids: tuple[str, ...] = CYCLE7_SANITIZER_VARIANT_IDS,
    sanitize=sanitize_cycle7_variant,
    algorithm_version: str = CYCLE8_DETECTOR_VERSION,
) -> dict[str, object]:
    from .cycle7_stage_a_hf import _adapter_and_tokenizer

    role = role_for_seed_base(seed_base)
    if role is None:
        raise ValueError("seed_base is not in the Cycle 8 ledger")
    assert_cycle8_development_seed(seed_base, role=role)
    backend, tokenizer, adapter, _identity_hash, eos = _adapter_and_tokenizer(device)
    samples = _generate_cycle8_samples(backend, seed_base, max_attempts, pair_count=pair_count)
    geometry_rows, scored_rows, summaries = _evaluate_samples(
        samples,
        tokenizer,
        adapter,
        eos,
        arm_ids=arm_ids,
        sanitizer_ids=sanitizer_ids,
        sanitize=sanitize,
    )
    return _build_detector_artifact(
        samples,
        geometry_rows,
        scored_rows,
        summaries,
        seed_base=seed_base,
        algorithm_version=algorithm_version,
        arm_ids=arm_ids,
        sanitizer_ids=sanitizer_ids,
        pair_count=pair_count,
    )


def rescore_cycle8_detector_compare(
    previous: dict[str, object],
    *,
    device: str = "cpu",
    arm_ids: tuple[str, ...] | None = None,
    sanitizer_ids: tuple[str, ...] | None = None,
    sanitize=None,
    algorithm_version: str | None = None,
) -> dict[str, object]:
    from .cycle7_stage_a_hf import _adapter_and_tokenizer
    from .cycle8.sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant

    seed_base = int(previous["seed_base"])
    role = role_for_seed_base(seed_base)
    if role is None:
        raise ValueError("seed_base is not in the Cycle 8 ledger")
    assert_cycle8_development_seed(seed_base, role=role)
    _backend, tokenizer, adapter, _identity_hash, eos = _adapter_and_tokenizer(device)
    samples = tuple(previous["samples"])
    resolved_arm_ids = tuple(arm_ids) if arm_ids is not None else tuple(previous.get("arm_ids") or CYCLE8_DETECTOR_ARM_IDS)
    resolved_sanitizer_ids = (
        tuple(sanitizer_ids) if sanitizer_ids is not None else tuple(previous.get("sanitizer_ids") or CYCLE7_SANITIZER_VARIANT_IDS)
    )
    if sanitize is None:
        sanitize = (
            sanitize_cycle8_scale_variant
            if "nfc" in resolved_sanitizer_ids or resolved_sanitizer_ids == CYCLE8_SCALE_SANITIZER_VARIANT_IDS
            else sanitize_cycle7_variant
        )
    geometry_rows, scored_rows, summaries = _evaluate_samples(
        samples,
        tokenizer,
        adapter,
        eos,
        arm_ids=resolved_arm_ids,
        sanitizer_ids=resolved_sanitizer_ids,
        sanitize=sanitize,
    )
    return _build_detector_artifact(
        samples,
        geometry_rows,
        scored_rows,
        summaries,
        seed_base=seed_base,
        algorithm_version=str(algorithm_version or previous.get("algorithm_version") or CYCLE8_DETECTOR_VERSION),
        arm_ids=resolved_arm_ids,
        sanitizer_ids=resolved_sanitizer_ids,
        pair_count=previous.get("pair_count"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, default=CYCLE8_EXPLORATORY_SEED_BASE)
    parser.add_argument("--max-attempts", type=int, default=CYCLE8_MAX_ATTEMPTS)
    parser.add_argument(
        "--detector-json",
        type=Path,
        default=None,
    )
    parser.add_argument("--skip-detector", action="store_true")
    parser.add_argument("--rescore-from", type=Path, default=None)
    args = parser.parse_args(argv)
    from .cycle8.compare import run_fixture_compare
    from .cycle8.tokenizer_screen import load_gpt2_encoder

    if args.detector_json is None:
        args.detector_json = Path(f"evidence/cycle8-{args.seed_base}-2026-08-25/detector-compare.json")
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
            detector = run_cycle8_detector_compare(
                device=args.device,
                max_attempts=args.max_attempts,
                seed_base=args.seed_base,
            )
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
