from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .config import canonical_json_text
from .corpus.schema import CorpusDomain, WatermarkLabel
from .corpus.tiny_dev import TINY_DEV_TARGET_LENGTH
from .corpus.tiny_dev_generation import TINY_DEV_DEFAULT_MAX_ATTEMPTS, TINY_DEV_PAIR_SEED_STRIDE
from .cycle7.compare import (
    CYCLE6_SPACING_ARM_ID,
    CYCLE7_COMBINED_ARM_ID,
    CYCLE7_DURABLE_ARM_ID,
    compare_arms_on_text,
    run_fixture_stage_a,
    summarize_arm,
)
from .cycle7.decision import classify_fixture_stage_a
from .cycle7.ledger import (
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_EXPLORATORY_SEED_BASE,
    assert_development_seed,
)
from .cycle7.whitespace_collapse import CYCLE7_SANITIZER_VARIANT_IDS, sanitize_cycle7_variant
from .detectors import weighted_mean_evidence
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_BUDGET, CYCLE6_THRESHOLD
from .hashing import sha256_json, sha256_text
from .native_observations import build_native_observations
from .tiny_dev_context_survival_plan_hf import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION
from .tiny_dev_corpus_hf import HuggingFaceTinyDevBackend
from .tiny_dev_detector_hf import default_watermark_payload
from .tiny_dev_transform_hf import _encode_text


CYCLE7_STAGE_A_DETECTOR_VERSION = "cycle7-stage-a-detector-compare-v1"

_STAGE_A_TEMPLATES = {
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

_STAGE_A_TOPIC = "reproducibility"


class _OffsetTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode("utf-8"))

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        data = text.encode("utf-8")
        result = {"input_ids": list(data)}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(data))]
        return result


def _score_text(sample_id: str, text: str, tokenizer: Any, adapter: HuggingFaceSynthIDAdapter, eos_token_id: int) -> float:
    tokens = _encode_text(tokenizer, text)
    batch = build_native_observations(sample_id, tokens, eos_token_id, adapter)
    return weighted_mean_evidence(batch).raw_score


def _generate_stage_a_samples(backend: HuggingFaceTinyDevBackend, seed_base: int) -> tuple[dict[str, object], ...]:
    assert_development_seed(seed_base, role=CYCLE7_EXPLORATORY_ROLE)
    samples: list[dict[str, object]] = []
    for pair_index, domain in enumerate(CorpusDomain):
        prompt = _STAGE_A_TEMPLATES[domain].format(topic=_STAGE_A_TOPIC)
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = None
        for attempt in range(TINY_DEV_DEFAULT_MAX_ATTEMPTS):
            seed = pair_seed_base + attempt
            control = backend.generate(prompt, seed, watermarked=False)
            watermarked = backend.generate(prompt, seed, watermarked=True)
            if len(control.continuation_token_ids) != TINY_DEV_TARGET_LENGTH:
                continue
            if len(watermarked.continuation_token_ids) != TINY_DEV_TARGET_LENGTH:
                continue
            if control.text == watermarked.text:
                continue
            accepted = (seed, control, watermarked)
            break
        if accepted is None:
            raise RuntimeError(f"Cycle 7 Stage A failed to generate a pair for {domain.value}")
        seed, control, watermarked = accepted
        for label, generated in (
            (WatermarkLabel.UNWATERMARKED, control),
            (WatermarkLabel.WATERMARKED, watermarked),
        ):
            sample_id = f"cycle7-stage-a-{domain.value}-{label.value}"
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


def _detector_arm_summary(rows: tuple[dict[str, object], ...], arm_id: str) -> dict[str, object]:
    watermarked = tuple(row for row in rows if row["label"] == WatermarkLabel.WATERMARKED.value and row["arm_id"] == arm_id)
    unwatermarked = tuple(row for row in rows if row["label"] == WatermarkLabel.UNWATERMARKED.value and row["arm_id"] == arm_id)
    def _count(selected, variant, field):
        return sum(bool(row["sanitizers"][variant][field]) for row in selected)
    def _mean(selected, variant):
        return sum(float(row["sanitizers"][variant]["score"]) for row in selected) / len(selected)
    payload = {
        "arm_id": arm_id,
        "watermarked_row_count": len(watermarked),
        "unwatermarked_row_count": len(unwatermarked),
        "pristine_watermarked_detected": sum(bool(row["pristine_detected"]) for row in watermarked),
        "pristine_unwatermarked_detected": sum(bool(row["pristine_detected"]) for row in unwatermarked),
        "raw_watermarked_detected": _count(watermarked, "raw", "detected"),
        "raw_unwatermarked_detected": _count(unwatermarked, "raw", "detected"),
        "ws_collapse_watermarked_detected": _count(watermarked, "ws_collapse", "detected"),
        "ws_collapse_unwatermarked_detected": _count(unwatermarked, "ws_collapse", "detected"),
        "raw_watermarked_mean_score": _mean(watermarked, "raw"),
        "ws_collapse_watermarked_mean_score": _mean(watermarked, "ws_collapse"),
        "median_raw_watermarked_score": sorted(float(row["sanitizers"]["raw"]["score"]) for row in watermarked)[len(watermarked) // 2],
        "worst_raw_watermarked_score": max(float(row["sanitizers"]["raw"]["score"]) for row in watermarked),
    }
    return payload


def _evaluate_samples(
    samples: tuple[dict[str, object], ...],
    tokenizer: Any,
    identity_hash: str,
    adapter: HuggingFaceSynthIDAdapter,
    eos: int,
    *,
    registries: dict[str, Any] | None = None,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], dict[str, object]]:
    scored_rows: list[dict[str, object]] = []
    geometry_rows: list[dict[str, object]] = []
    for sample in samples:
        arms = compare_arms_on_text(
            source_sample_id=str(sample["sample_id"]),
            source_text=str(sample["text"]),
            tokenizer=tokenizer,
            tokenizer_identity_hash=identity_hash,
            budget=CYCLE6_BUDGET,
            registries=registries,
        )
        geometry_rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "arms": {arm_id: summarize_arm(measurement) for arm_id, measurement in arms.items()},
            }
        )
        pristine = _score_text(
            f"{sample['sample_id']}-pristine",
            str(sample["text"]),
            tokenizer,
            adapter,
            eos,
        )
        for arm_id, measurement in arms.items():
            sanitizers = {}
            for variant in CYCLE7_SANITIZER_VARIANT_IDS:
                text = sanitize_cycle7_variant(variant, measurement.transformed_text)
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
        arm_id: _detector_arm_summary(tuple(scored_rows), arm_id)
        for arm_id in (CYCLE6_SPACING_ARM_ID, CYCLE7_DURABLE_ARM_ID, CYCLE7_COMBINED_ARM_ID)
    }
    return tuple(geometry_rows), tuple(scored_rows), summaries


def _adapter_and_tokenizer(device: str) -> tuple[Any, Any, HuggingFaceSynthIDAdapter, str, int]:
    backend = HuggingFaceTinyDevBackend(
        DEFAULT_MODEL_ID,
        DEFAULT_MODEL_REVISION,
        device=device,
        temperature=0.8,
        top_k=50,
        top_p=0.95,
    )
    tokenizer = backend._tokenizer
    tokenizer.padding_side = "left"
    payload = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=int(payload["ngram_len"]),
            keys=tuple(payload["keys"]),
            context_history_size=int(payload["context_history_size"]),
            sampling_table_seed=int(payload["sampling_table_seed"]),
            sampling_table_size=int(payload["sampling_table_size"]),
            skip_first_ngram_calls=bool(payload["skip_first_ngram_calls"]),
            debug_mode=bool(payload["debug_mode"]),
        )
    )
    eos = tokenizer.eos_token_id
    if eos is None:
        raise RuntimeError("GPT-2 tokenizer must define eos_token_id")
    return backend, tokenizer, adapter, backend.model_identity.identity_hash, int(eos)


def _build_detector_artifact(
    samples: tuple[dict[str, object], ...],
    geometry_rows: tuple[dict[str, object], ...],
    scored_rows: tuple[dict[str, object], ...],
    summaries: dict[str, object],
    *,
    catalog_version: str,
) -> dict[str, object]:
    artifact = {
        "algorithm_version": CYCLE7_STAGE_A_DETECTOR_VERSION,
        "seed_base": CYCLE7_EXPLORATORY_SEED_BASE,
        "durable_catalog_version": catalog_version,
        "model": DEFAULT_MODEL_ID,
        "model_revision": DEFAULT_MODEL_REVISION,
        "threshold": CYCLE6_THRESHOLD,
        "budget": CYCLE6_BUDGET,
        "sanitizer_ids": CYCLE7_SANITIZER_VARIANT_IDS,
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
    return {**artifact, "artifact_hash": sha256_json({k: v for k, v in artifact.items() if k != "artifact_hash"})}


def run_stage_a_detector_compare(*, device: str = "cpu") -> dict[str, object]:
    from .cycle7.durable_rules import CYCLE7_DURABLE_RULE_CATALOG_VERSION

    assert_development_seed(CYCLE7_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    backend, tokenizer, adapter, identity_hash, eos = _adapter_and_tokenizer(device)
    samples = _generate_stage_a_samples(backend, CYCLE7_EXPLORATORY_SEED_BASE)
    geometry_rows, scored_rows, summaries = _evaluate_samples(
        samples, tokenizer, identity_hash, adapter, eos
    )
    return _build_detector_artifact(
        samples,
        geometry_rows,
        scored_rows,
        summaries,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )


def rescore_stage_a_detector_compare(previous: dict[str, object], *, device: str = "cpu") -> dict[str, object]:
    from .cycle7.durable_rules import CYCLE7_DURABLE_RULE_CATALOG_VERSION
    from .tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
    from transformers import AutoTokenizer

    assert_development_seed(CYCLE7_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    samples = tuple(previous["samples"])
    tokenizer = AutoTokenizer.from_pretrained(
        DEFAULT_MODEL_ID,
        revision=DEFAULT_MODEL_REVISION,
        padding_side="left",
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    identity = runtime_tokenizer_identity_public(tokenizer, DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION)
    payload = default_watermark_payload()
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(
            ngram_len=int(payload["ngram_len"]),
            keys=tuple(payload["keys"]),
            context_history_size=int(payload["context_history_size"]),
            sampling_table_seed=int(payload["sampling_table_seed"]),
            sampling_table_size=int(payload["sampling_table_size"]),
            skip_first_ngram_calls=bool(payload["skip_first_ngram_calls"]),
            debug_mode=bool(payload["debug_mode"]),
        )
    )
    eos = tokenizer.eos_token_id
    if eos is None:
        raise RuntimeError("GPT-2 tokenizer must define eos_token_id")
    geometry_rows, scored_rows, summaries = _evaluate_samples(
        samples, tokenizer, identity.identity_hash, adapter, int(eos)
    )
    return _build_detector_artifact(
        samples,
        geometry_rows,
        scored_rows,
        summaries,
        catalog_version=CYCLE7_DURABLE_RULE_CATALOG_VERSION,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle7-stage-a")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--fixture-json",
        type=Path,
        default=Path("evidence/cycle7-stage-a-2026-08-25/fixture-geometry.json"),
    )
    parser.add_argument(
        "--detector-json",
        type=Path,
        default=Path("evidence/cycle7-stage-a-2026-08-25/detector-compare.json"),
    )
    parser.add_argument("--skip-detector", action="store_true")
    parser.add_argument(
        "--rescore-from",
        type=Path,
        default=None,
        help="Reuse previously generated Stage A texts; do not regenerate.",
    )
    args = parser.parse_args(argv)
    fixture = run_fixture_stage_a(_OffsetTokenizer())
    write_canonical_json_fsynced(args.fixture_json, fixture)
    detector = None
    if not args.skip_detector:
        if args.rescore_from is not None:
            previous = json.loads(args.rescore_from.read_text(encoding="utf-8"))
            detector = rescore_stage_a_detector_compare(previous, device=args.device)
        else:
            detector = run_stage_a_detector_compare(device=args.device)
        write_canonical_json_fsynced(args.detector_json, detector)
        fixture = {
            **{k: v for k, v in fixture.items() if k != "artifact_hash"},
            "detector": {
                "available": True,
                "cycle6_spacing": detector["summaries"][CYCLE6_SPACING_ARM_ID],
                "durable": detector["summaries"][CYCLE7_DURABLE_ARM_ID],
                "combined": detector["summaries"][CYCLE7_COMBINED_ARM_ID],
            },
        }
        fixture = {**fixture, "artifact_hash": sha256_json({k: v for k, v in fixture.items() if k != "artifact_hash"})}
        write_canonical_json_fsynced(args.fixture_json, fixture)
    decision = classify_fixture_stage_a(fixture)
    args.fixture_json.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(args.fixture_json.parent / "decision.json", decision)
    print(canonical_json_text(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
