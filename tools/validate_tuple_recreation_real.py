from __future__ import annotations

import argparse
import statistics
import sys

sys.path.insert(0, ".")

from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from fuckmark.alignment import align_tokens
from fuckmark.detectors import weighted_mean_evidence, weighted_mean_score
from fuckmark.experiments.cover_greedy_v3 import schedule_cover_greedy_v3
from fuckmark.geometry.counterfactual import (
    DEFAULT_MAX_ALIGNMENT_CELLS,
    CounterfactualGeometryEngine,
    GeometryConfig,
    _ambiguous_root_indices,
)
from fuckmark.geometry.repetition import PublicRepetitionGeometry
from fuckmark.geometry.tuple_closure import compute_tuple_closure
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import content_region_coverage_transform_registry

MODEL_ID = "openai-community/gpt2"
MODEL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
KEYS = (654, 400, 836, 123, 340, 443, 597, 160, 57)
NGRAM_LEN = 5
TARGET_FPR_THRESHOLD = 0.5570987654320988
BUDGET = 16
TEMPERATURE = 0.8
TOP_K = 50
TOP_P = 0.95
SEED_BASE = 700_000

PROMPTS = (
    "The city council debated the new library proposal for hours.",
    "Modern batteries store energy through chemical reactions.",
    "She walked along the beach collecting shells at dawn.",
    "The recipe requires flour, butter, eggs, and patience.",
    "Astronomers discovered a planet orbiting a distant star.",
    "The train arrived late because of heavy fog on the tracks.",
    "Learning a musical instrument demands steady practice.",
    "The garden bloomed after weeks of gentle rain.",
)


def encode(tokenizer, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return tuple(int(value) for value in ids)


def positional_survivor_starts(
    root_observations,
    source_tokens: tuple[int, ...],
    out_tokens: tuple[int, ...],
    repetition: PublicRepetitionGeometry,
) -> set[int]:
    alignment = align_tokens(source_tokens, out_tokens)
    ambiguous_original_indices = _ambiguous_root_indices(
        source_tokens,
        out_tokens,
        alignment.distance,
        max_cells=DEFAULT_MAX_ALIGNMENT_CELLS,
    )
    output_eligibility = repetition.evaluate(out_tokens).eligible_windows
    positional_starts: set[int] = set()
    for obs in root_observations.observations:
        if not obs.eligible:
            continue
        if any(
            index in ambiguous_original_indices
            for index in range(obs.token_start, obs.token_end_exclusive)
        ):
            continue
        mapped = tuple(
            alignment.original_to_transformed[index]
            for index in range(obs.token_start, obs.token_end_exclusive)
        )
        if any(position is None for position in mapped):
            continue
        positions = tuple(int(position) for position in mapped if position is not None)
        if positions != tuple(range(positions[0], positions[0] + len(positions))):
            continue
        if positions[-1] >= len(out_tokens):
            continue
        if tuple(out_tokens[position] for position in positions) != obs.token_ids:
            continue
        mapped_start = positions[0]
        if mapped_start >= len(output_eligibility) or not output_eligibility[mapped_start]:
            continue
        positional_starts.add(mapped_start)
    return positional_starts


def subset_score(rows_list):
    if not rows_list:
        return None
    return weighted_mean_score(tuple(rows_list), (True,) * len(rows_list))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, SynthIDTextWatermarkingConfig

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model.eval()
    eos = tokenizer.eos_token_id

    from fuckmark.hashing import sha256_json
    from fuckmark.tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public

    identity = runtime_tokenizer_identity_public(tokenizer, MODEL_ID, MODEL_REVISION)
    tokenizer_identity_hash = sha256_json(
        {
            "model_id": identity.model_id,
            "model_revision": identity.model_revision,
            "tokenizer_id": identity.tokenizer_id,
            "tokenizer_revision": identity.tokenizer_revision,
        }
    )

    watermark_config = SynthIDTextWatermarkingConfig(ngram_len=NGRAM_LEN, keys=list(KEYS))
    adapter_config = HuggingFaceSynthIDConfig(
        ngram_len=NGRAM_LEN,
        keys=KEYS,
        context_history_size=1024,
        sampling_table_seed=0,
        sampling_table_size=65536,
        skip_first_ngram_calls=False,
        debug_mode=False,
    )
    adapter = HuggingFaceSynthIDAdapter.from_torch(adapter_config, device="cpu")

    repetition = PublicRepetitionGeometry.create(ngram_len=NGRAM_LEN, context_history_size=1024)
    geometry_config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=NGRAM_LEN,
        repetition_mask_policy_id=repetition.policy_id,
    )
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=geometry_config,
        eligibility_policy=repetition.eligibility_policy,
    )
    registry = content_region_coverage_transform_registry()

    rows = []
    for index in range(min(args.samples, len(PROMPTS))):
        seed = SEED_BASE + index + 1
        torch.manual_seed(seed)
        encoded = tokenizer(PROMPTS[index], return_tensors="pt")
        with torch.inference_mode():
            output = model.generate(
                **encoded,
                do_sample=True,
                temperature=TEMPERATURE,
                top_k=TOP_K,
                top_p=TOP_P,
                min_new_tokens=64,
                max_new_tokens=64,
                pad_token_id=tokenizer.pad_token_id or eos,
                watermarking_config=watermark_config,
            )
        continuation = tuple(int(v) for v in output[0, encoded["input_ids"].shape[1]:])
        text = tokenizer.decode(continuation, skip_special_tokens=True)
        source_tokens = encode(tokenizer, text)
        if len(source_tokens) < NGRAM_LEN + 8:
            continue

        root_obs = engine.build_root(source_sample_id=f"val-{index}", source_text=text).observations
        root_tuple_set = {
            tuple(obs.token_ids) for obs in root_obs.observations if obs.eligible
        }

        pristine_batch = build_native_observations(f"val-{index}-pristine", source_tokens, eos, adapter)
        pristine_score = weighted_mean_evidence(pristine_batch).raw_score

        enumeration = registry.enumerate(text)
        if not enumeration.candidates:
            continue
        result = schedule_cover_greedy_v3(
            source_sample_id=f"val-{index}",
            source_text=text,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=NGRAM_LEN,
            budget=BUDGET,
        )
        transformed_text = registry.apply(enumeration, result.selected_candidate_ids).output_text
        out_tokens = encode(tokenizer, transformed_text)

        closure = compute_tuple_closure(
            root=root_obs,
            transformed_tokens=out_tokens,
        )

        batch = build_native_observations(f"val-{index}-transformed", out_tokens, eos, adapter)
        transformed_score = weighted_mean_evidence(batch).raw_score

        positional_starts = positional_survivor_starts(
            root_obs,
            source_tokens,
            out_tokens,
            repetition,
        )
        if len(positional_starts) != result.intact_window_count:
            raise RuntimeError("validation positional taxonomy disagrees with geometry survival count")

        surv_rows, rec_rows, new_rows = [], [], []
        seen_recreated: set[tuple[int, ...]] = set()
        for record in batch.records:
            if not record.valid:
                continue
            ngram = record.ngram
            if record.index in positional_starts and ngram in root_tuple_set:
                surv_rows.append(record.g_values)
            elif ngram in root_tuple_set and ngram not in seen_recreated:
                seen_recreated.add(ngram)
                rec_rows.append(record.g_values)
            elif ngram in root_tuple_set:
                pass
            else:
                new_rows.append(record.g_values)

        rows.append(
            {
                "index": index,
                "pristine": pristine_score,
                "transformed": transformed_score,
                "detected": transformed_score >= TARGET_FPR_THRESHOLD,
                "positional_survivors": len(surv_rows),
                "survivor_mean_g": subset_score(surv_rows),
                "recreated_distinct": len(rec_rows),
                "recreated_mean_g": subset_score(rec_rows),
                "new_windows": len(new_rows),
                "new_mean_g": subset_score(new_rows),
                "closure_leak": closure.leaked_window_count,
                "selected": result.selected_candidate_count,
                "repair": result.repair_phase_selections,
            }
        )
        print(
            f"[{index:02d}] pristine={pristine_score:.4f} transformed={transformed_score:.4f} "
            f"detected={rows[-1]['detected']} | pos_surv={len(surv_rows)} "
            f"(g={rows[-1]['survivor_mean_g']}) rec_created={len(rec_rows)} "
            f"(g={rows[-1]['recreated_mean_g']}) new={len(new_rows)} "
            f"(g={rows[-1]['new_mean_g']}) | repair_used={result.repair_phase_selections}"
        )

    if rows:
        rec_samples = [r for r in rows if r["recreated_distinct"] > 0]
        above_null_rec = [
            r for r in rec_samples if r["recreated_mean_g"] is not None and r["recreated_mean_g"] > 0.5
        ]
        print("\n=== SUMMARY ===")
        print(f"samples scored: {len(rows)}")
        print(f"detected at frozen threshold: {sum(r['detected'] for r in rows)}")
        print(f"samples containing recreated root tuples: {len(rec_samples)}")
        print(
            "recreated-tuple weighted mean g > 0.5 (above-null evidence): "
            f"{len(above_null_rec)}/{len(rec_samples)}"
        )
        if rec_samples:
            means = [r["recreated_mean_g"] for r in rec_samples]
            print(f"recreated weighted mean-g distribution: mean={statistics.mean(means):.4f}")
        survivors = [r for r in rows if r["positional_survivors"] > 0]
        print(f"samples with positional survivors: {len(survivors)}")
    return 0


def root_observations(engine, sample_id, text):
    return engine.build_root(source_sample_id=sample_id, source_text=text).observations


if __name__ == "__main__":
    raise SystemExit(main())
