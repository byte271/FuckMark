from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .detectors.mean import weighted_mean_score
from .experiments.exact_survival_greedy import schedule_exact_survival_greedy
from .experiments.exact_survival_greedy_v2 import schedule_exact_survival_greedy_v2
from .hashing import sha256_json, sha256_text
from .sanitizer_robustness import (
    SANITIZER_VARIANT_IDS,
    introduced_invisible_codepoint_count,
)
from .transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    build_candidate_tokenizer_geometry,
    content_region_coverage_transform_registry,
    content_region_destruction_transform_registry,
)
from .transforms.visible_projection_registry import visible_projection_experimental_registry


DESTRUCTION_DEV_RUN_VERSION = "destruction-dev-run-v1"
DEV_THRESHOLD = 0.5570987654320988

PROMPTS = (
    "Write a formal paragraph with no contractions explaining why careful testing matters before making a scientific claim.",
    "Write a formal paragraph with no contractions explaining why a map can be useful but cannot replace direct observation.",
    "Write a formal paragraph with no contractions about why software should not silently ignore invalid data.",
    "Write a formal paragraph with no contractions describing what a student should do when an experiment does not match a prediction.",
    "Write a formal paragraph with no contractions explaining why a measurement may fail even when an idea is reasonable.",
    "Write a formal paragraph with no contractions about why repeated results are more convincing than one surprising result.",
    "Write a formal paragraph with no contractions explaining why a detector should not be judged from only one example.",
    "Write a formal paragraph with no contractions about why preserving numbers and quotations matters when editing text.",
    "Write a formal paragraph with no contractions explaining why a control group is necessary in an experiment.",
    "Write a formal paragraph with no contractions about why researchers cannot assume that one model represents every model.",
    "Write a formal paragraph with no contractions explaining why a low false positive rate matters for a detector.",
    "Write a formal paragraph with no contractions about why an experiment should not change its rules after seeing the result.",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_offsets(tokenizer, text):
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    token_ids = tuple(int(value) for value in encoded["input_ids"])
    offsets = tuple((int(start), int(end)) for start, end in encoded["offset_mapping"])
    return token_ids, offsets


def _plan_proxy(registry, tokenizer_identity_hash, text, budget, seed, ngram_len=5):
    enumeration = registry.enumerate(text)
    if not enumeration.candidates:
        return {"text": text, "selected": (), "pool": 0, "scheduler": "none"}
    token_ids, offsets = _encode_offsets(_TOKENIZER, text)
    geometry = build_candidate_tokenizer_geometry(
        text, enumeration, token_ids, offsets,
        tokenizer_identity_hash=tokenizer_identity_hash, ngram_len=ngram_len,
    )
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration, coverage_intervals=geometry.coverage_mapping(),
        budget_unit="operation", geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    schedule = CandidateScheduler().schedule(scheduler_input, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND, budget, seed)
    applied = registry.apply(enumeration, schedule.selected_candidate_ids, seed=seed)
    return {
        "text": applied.output_text,
        "text_hash": sha256_text(applied.output_text),
        "selected": schedule.selected_candidate_ids,
        "pool": len(enumeration.candidates),
        "scheduler": "COVERAGE_GREEDY_KEY_BLIND",
    }


def _plan_exact(registry, tokenizer_identity_hash, text, budget, sample_id, version, ngram_len=5):
    enumeration = registry.enumerate(text)
    kwargs = dict(
        source_sample_id=sample_id,
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=_TOKENIZER,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        budget=budget,
    )
    if version == "v1":
        result = schedule_exact_survival_greedy(**kwargs)
    else:
        result = schedule_exact_survival_greedy_v2(**kwargs)
    applied = registry.apply(enumeration, result.selected_candidate_ids)
    return {
        "text": applied.output_text,
        "text_hash": sha256_text(applied.output_text),
        "selected": result.selected_candidate_ids,
        "pool": len(enumeration.candidates),
        "scheduler": result.algorithm_version,
        "policy_saturated": result.policy_saturated,
        "pairwise_completion_used": getattr(result, "pairwise_completion_used", False),
        "exact_destroyed": result.exact_destroyed_observation_count,
        "root_observations": result.root_observation_count,
    }


_TOKENIZER = None


def main(argv=None) -> int:
    global _TOKENIZER
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-destruction-dev-hf")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--model-revision", default="607a30d783dfa663caf39e06633721c8d4cfcd7e")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--sources", type=int, default=12)
    parser.add_argument("--seed-base", type=int, default=560000)
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, SynthIDTextWatermarkingConfig
    except ImportError as error:
        raise RuntimeError("Install the pinned TinyDev Transformers dependencies first") from error

    started = _now()
    torch_device = "cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.model_revision, use_fast=True, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    _TOKENIZER = tokenizer
    model = AutoModelForCausalLM.from_pretrained(args.model, revision=args.model_revision)
    model.to(torch_device)
    model.eval()
    watermark_config = SynthIDTextWatermarkingConfig(ngram_len=5, keys=[654, 400, 836, 123, 340, 443, 597, 160, 57])
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(ngram_len=5, keys=(654, 400, 836, 123, 340, 443, 597, 160, 57)),
        device=torch_device,
    )

    def generate(prompt: str, seed: int) -> str:
        torch.manual_seed(seed)
        encoded = tokenizer(prompt, return_tensors="pt").to(torch_device)
        with torch.inference_mode():
            output = model.generate(
                **encoded,
                do_sample=True,
                temperature=0.8,
                top_k=50,
                top_p=0.95,
                max_new_tokens=args.max_new_tokens,
                pad_token_id=tokenizer.pad_token_id,
                watermarking_config=watermark_config,
            )
        return tokenizer.decode(output[0, encoded["input_ids"].shape[1]:], skip_special_tokens=True)

    def score(text: str) -> float:
        tokens = tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) < 5:
            raise ValueError("text too short to score")
        signals = adapter.signals(tokens, tokenizer.eos_token_id)
        return float(weighted_mean_score(signals.g_values, signals.valid_mask))

    identity_hash = sha256_json({"model": args.model, "revision": args.model_revision})
    cycle3 = content_region_coverage_transform_registry()
    destruction = content_region_destruction_transform_registry()
    diagnostic_u200c = visible_projection_experimental_registry()

    print(f"[corpus] generating {args.sources} watermarked sources", flush=True)
    sources = []
    for index in range(args.sources):
        prompt = PROMPTS[index % len(PROMPTS)]
        text = ""
        for attempt in range(3):
            text = generate(prompt, args.seed_base + 13 * index + attempt)
            if len(text.strip()) >= 40:
                break
        if len(text.strip()) < 40:
            raise RuntimeError(f"degenerate generation at source {index}")
        sources.append({"source_sample_id": f"dev-{index:03d}", "prompt_index": index % len(PROMPTS), "text": text})
        print(f"[corpus] {index + 1}/{args.sources}", flush=True)

    arms = {
        "A_cycle3_proxy": lambda s: _plan_proxy(cycle3, identity_hash, s["text"], args.budget, args.seed_base + s.__len__() * 0 + 1_160_000),
        "B_cycle3_exact_v1": lambda s: _plan_exact(cycle3, identity_hash, s["text"], args.budget, s["source_sample_id"], "v1"),
        "C_destruction_exact_v2": lambda s: _plan_exact(destruction, identity_hash, s["text"], args.budget, s["source_sample_id"], "v2"),
    }
    diagnostic_arm = {
        "D_u200c_exact_v2_diagnostic": lambda s: _plan_exact(diagnostic_u200c, identity_hash, s["text"], args.budget, s["source_sample_id"], "v2"),
    }

    plans = {}
    for name, planner in (*arms.items(), *diagnostic_arm.items()):
        plans[name] = []
        print(f"[plan] {name}", flush=True)
        for source in sources:
            plan = planner(source)
            invisible = introduced_invisible_codepoint_count(source["text"], plan["text"])
            plans[name].append({
                **plan,
                "source_sample_id": source["source_sample_id"],
                "invisible_introduced": invisible,
            })

    rows = []
    for index, source in enumerate(sources):
        row = {"source_sample_id": source["source_sample_id"], "pristine_score": round(score(source["text"]), 8)}
        row["pristine_detected"] = row["pristine_score"] >= DEV_THRESHOLD
        for name in plans:
            entry = plans[name][index]
            row[f"{name}_score"] = round(score(entry["text"]), 8)
            row[f"{name}_detected"] = row[f"{name}_score"] >= DEV_THRESHOLD
            row[f"{name}_edits"] = len(entry["selected"])
            row[f"{name}_invisible"] = entry.get("invisible_introduced", 0)
            if "exact_destroyed" in entry:
                row[f"{name}_exact_destroyed"] = entry["exact_destroyed"]
                row[f"{name}_root_observations"] = entry["root_observations"]
                row[f"{name}_pairwise_used"] = entry.get("pairwise_completion_used", False)
                row[f"{name}_policy_saturated"] = entry.get("policy_saturated", False)
        rows.append(row)
        print(f"[score] {index + 1}/{len(sources)} scored", flush=True)

    def _summary(prefix):
        detected = sum(1 for row in rows if row.get(f"{prefix}_detected"))
        scores = [row[f"{prefix}_score"] for row in rows]
        pristine = [row["pristine_score"] for row in rows]
        return {
            "detected": detected,
            "mean_score": round(sum(scores) / len(scores), 6),
            "mean_drop_vs_pristine": round(sum(p - s for p, s in zip(pristine, scores)) / len(scores), 6),
            "mean_edits": round(sum(row.get(f"{prefix}_edits", 0) for row in rows) / len(rows), 3),
            "mean_invisible_introduced": round(sum(row.get(f"{prefix}_invisible", 0) for row in rows) / len(rows), 3),
        }

    summaries = {"pristine": {
        "detected": sum(1 for row in rows if row["pristine_detected"]),
        "mean_score": round(sum(row["pristine_score"] for row in rows) / len(rows), 6),
        "mean_drop_vs_pristine": 0.0,
        "mean_edits": 0.0,
        "mean_invisible_introduced": 0.0,
    }}
    for name in plans:
        summaries[name] = _summary(name)

    payload = {
        "algorithm_version": DESTRUCTION_DEV_RUN_VERSION,
        "scientific_scope": (
            "Development-only paired comparison of proxy coverage scheduling, frozen exact-survival "
            "greedy v1, and the Cycle-4 destruction pool with pairwise-completed greedy v2; the "
            "quarantined U+200C mechanism appears only as a labeled diagnostic upper-bound arm and "
            "is excluded from every development or release profile"
        ),
        "recorded_at_utc": started,
        "completed_at_utc": _now(),
        "model": args.model,
        "model_revision": args.model_revision,
        "seed_base": args.seed_base,
        "budget": args.budget,
        "threshold": DEV_THRESHOLD,
        "sanitizer_variants_note": "per-variant raw/NFKC/Cf-strip evaluation is reported by fuckmark.sanitizer_robustness consumers of these plans",
        "cycle3_ruleset_hash": cycle3.ruleset_hash,
        "destruction_ruleset_hash": destruction.ruleset_hash,
        "diagnostic_u200c_ruleset_hash": diagnostic_u200c.ruleset_hash,
        "rows": tuple(rows),
        "summaries": summaries,
    }
    payload = {**payload, "artifact_hash": sha256_json(payload)}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sys.stdout.write(f"artifact_hash={payload['artifact_hash']}\n")
    for name, values in summaries.items():
        sys.stdout.write(
            f"{name}: detected={values['detected']}/{len(rows)} mean_score={values['mean_score']:.4f} "
            f"drop={values['mean_drop_vs_pristine']:.4f} edits={values['mean_edits']:.2f} invisible={values['mean_invisible_introduced']:.2f}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
