from __future__ import annotations

import argparse
import json
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

PROMPTS = (
    ("general_explanatory", "Explain why regular sleep schedules matter for concentration."),
    ("technical_explanation", "Describe how a refrigerator keeps food cold using a compressor."),
    ("conversational_prose", "Tell me about your favorite way to spend a rainy afternoon."),
    ("structured_instructional", "Give step-by-step instructions for watering an orchid."),
    ("general_explanatory", "Explain how public libraries choose which books to buy."),
    ("technical_explanation", "Describe what happens inside a microwave oven when it runs."),
    ("conversational_prose", "Talk about the challenges of moving to a new city alone."),
    ("structured_instructional", "List practical steps for organizing a small home office."),
    ("general_explanatory", "Explain why some birds migrate thousands of kilometers."),
    ("technical_explanation", "Explain how water towers maintain pressure in a town."),
    ("conversational_prose", "Describe learning to ride a bicycle as an adult."),
    ("structured_instructional", "Outline safe practices for hanging pictures on a wall."),
    ("general_explanatory", "Discuss why farmers rotate crops between fields each year."),
    ("technical_explanation", "Explain how elevators know where to stop on each floor."),
    ("conversational_prose", "Talk about keeping in touch with friends across time zones."),
    ("structured_instructional", "Provide instructions for cleaning and storing winter boots."),
)


def encode(tokenizer, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return tuple(int(value) for value in ids)


def sanitizer_variants(text: str) -> dict[str, str]:
    return {
        "raw": text,
        "nfkc": unicodedata.normalize("NFKC", text),
        "cf_strip": "".join(ch for ch in text if not unicodedata.category(ch).startswith("Cf")),
        "combined": "".join(
            ch for ch in unicodedata.normalize("NFKC", text)
            if not unicodedata.category(ch).startswith("Cf")
        ),
    }


def _load_texts(args, tokenizer) -> list[dict[str, object]]:
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if corpus.get("prompt_count") != len(PROMPTS[: args.samples]):
        raise ValueError("corpus does not bind this prompt set")
    if corpus.get("seed_base") != args.seed_base:
        raise ValueError("corpus seed base does not match requested seed base")
    rows = []
    seen = 0
    for entry in corpus["samples"]:
        text = entry["text"]
        if len(encode(tokenizer, text)) < 21:
            continue
        rows.append({"index": entry["index"], "domain": entry["domain"], "seed": entry["seed"], "text": text})
        seen += 1
    if not rows:
        raise ValueError("frozen corpus produced no usable samples")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--seed-base", type=int, default=710_000)
    parser.add_argument("--threshold", type=float, default=0.5570987654320988)
    parser.add_argument("--registry", type=str, choices=("coverage", "zrd"), default="coverage")
    parser.add_argument("--corpus", type=str, default=None)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--out", type=str, default="artifacts/cycle5-dev-paired-run.json")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, SynthIDTextWatermarkingConfig

    from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
    from fuckmark.detectors import weighted_mean_evidence
    from fuckmark.experiments.cover_greedy_v3 import schedule_cover_greedy_v3
    from fuckmark.experiments.cover_greedy_v4 import schedule_cover_greedy_v4
    from fuckmark.geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
    from fuckmark.geometry.repetition import PublicRepetitionGeometry
    from fuckmark.geometry.tuple_closure import compute_tuple_closure
    from fuckmark.hashing import sha256_json, sha256_text
    from fuckmark.native_observations import build_native_observations
    from fuckmark.tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
    from fuckmark.transforms import content_region_coverage_transform_registry
    from fuckmark.transforms.effectiveness_profile import zrd_destruction_transform_registry

    model_id = "openai-community/gpt2"
    model_revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    keys = (654, 400, 836, 123, 340, 443, 597, 160, 57)
    ngram_len = 5

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=model_revision, padding_side="left")
    identity = runtime_tokenizer_identity_public(tokenizer, model_id, model_revision)
    tokenizer_identity_hash = sha256_json(
        {
            "model_id": identity.model_id,
            "model_revision": identity.model_revision,
            "tokenizer_id": identity.tokenizer_id,
            "tokenizer_revision": identity.tokenizer_revision,
        }
    )

    if args.generate_only:
        model = AutoModelForCausalLM.from_pretrained(model_id, revision=model_revision)
        model.eval()
        eos = tokenizer.eos_token_id
        watermark_config = SynthIDTextWatermarkingConfig(ngram_len=ngram_len, keys=list(keys))
        samples = []
        for index in range(min(args.samples, len(PROMPTS))):
            domain, prompt = PROMPTS[index]
            seed = args.seed_base + index + 1
            torch.manual_seed(seed)
            encoded = tokenizer(prompt, return_tensors="pt")
            with torch.inference_mode():
                output = model.generate(
                    **encoded,
                    do_sample=True,
                    temperature=0.8,
                    top_k=50,
                    top_p=0.95,
                    min_new_tokens=64,
                    max_new_tokens=64,
                    pad_token_id=tokenizer.pad_token_id or eos,
                    watermarking_config=watermark_config,
                )
            continuation = tuple(int(v) for v in output[0, encoded["input_ids"].shape[1]:])
            text = tokenizer.decode(continuation, skip_special_tokens=True)
            samples.append({"index": index, "domain": domain, "seed": seed, "text": text, "text_sha256": sha256_text(text)})
        artifact = {
            "algorithm_version": "cycle5-dev-corpus-freeze-v1",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "model": model_id,
            "model_revision": model_revision,
            "seed_base": args.seed_base,
            "prompt_count": min(args.samples, len(PROMPTS)),
            "sample_count": len(samples),
            "generation_note": "single-process generation; cross-process byte-reproducibility is NOT claimed",
            "samples": samples,
        }
        artifact["corpus_hash"] = sha256_json({k: v for k, v in artifact.items() if k != "corpus_hash"})
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
        print(f"frozen corpus: {out_path} ({len(samples)} samples)")
        return 0

    if not args.corpus:
        raise SystemExit("scoring mode requires --corpus pointing at a frozen cycle5-dev-corpus file")

    model = AutoModelForCausalLM.from_pretrained(model_id, revision=model_revision)
    model.eval()
    eos = tokenizer.eos_token_id
    watermark_config = SynthIDTextWatermarkingConfig(ngram_len=ngram_len, keys=list(keys))
    adapter_config = HuggingFaceSynthIDConfig(ngram_len=ngram_len, keys=keys)
    adapter = HuggingFaceSynthIDAdapter.from_torch(adapter_config, device="cpu")

    repetition = PublicRepetitionGeometry.create(ngram_len=ngram_len, context_history_size=1024)
    geometry_config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=repetition.policy_id,
    )
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=geometry_config,
        eligibility_policy=repetition.eligibility_policy,
    )
    registry = zrd_destruction_transform_registry() if args.registry == "zrd" else content_region_coverage_transform_registry()

    def score_text(sample_id: str, text: str) -> float:
        tokens = encode(tokenizer, text)
        batch = build_native_observations(sample_id, tokens, eos, adapter)
        return weighted_mean_evidence(batch).raw_score

    frozen_rows = _load_texts(args, tokenizer)
    rows = []
    for entry in frozen_rows:
        index, domain, text = entry["index"], entry["domain"], entry["text"]

        pristine_score = score_text(f"dev-{index}-pristine", text)
        enumeration = registry.enumerate(text)
        if not enumeration.candidates:
            continue

        common = dict(
            source_sample_id=f"dev-{index}",
            source_text=text,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
        )
        plan_v3 = schedule_cover_greedy_v3(budget=args.budget, **common)
        out_v3 = registry.apply(enumeration, plan_v3.selected_candidate_ids).output_text
        plan_v4 = schedule_cover_greedy_v4(budget=args.budget, **common)
        out_v4 = registry.apply(enumeration, plan_v4.selected_candidate_ids).output_text

        root_obs = engine.build_root(source_sample_id=f"dev-{index}", source_text=text).observations
        closure_v3 = compute_tuple_closure(root=root_obs, transformed_tokens=encode(tokenizer, out_v3))
        closure_v4 = compute_tuple_closure(root=root_obs, transformed_tokens=encode(tokenizer, out_v4))

        row = {
            "index": index,
            "domain": domain,
            "seed": entry["seed"],
            "text_sha256": sha256_text(text)[:16],
            "pristine_score": round(pristine_score, 6),
            "v3": {
                "score": round(score_text(f"dev-{index}-v3", out_v3), 6),
                "selected": plan_v3.selected_candidate_count,
                "repair_used": plan_v3.repair_phase_selections,
                "intact_windows": plan_v3.intact_window_count,
                "closure_leaks": closure_v3.leaked_window_count,
            },
            "v4": {
                "score": round(score_text(f"dev-{index}-v4", out_v4), 6),
                "selected": plan_v4.selected_candidate_count,
                "repair_used": plan_v4.repair_phase_selections,
                "intact_windows": plan_v4.intact_window_count,
                "closure_leaks": plan_v4.tuple_leak_window_count,
            },
        }
        row["v3"]["detected"] = row["v3"]["score"] >= args.threshold
        row["v4"]["detected"] = row["v4"]["score"] >= args.threshold
        variants = {"v3": sanitizer_variants(out_v3), "v4": sanitizer_variants(out_v4)}
        row["sanitizers"] = {
            arm: {
                variant: {
                    "score": round(score_text(f"dev-{index}-{arm}-{variant}", value), 6),
                    "detected": score_text(f"dev-{index}-{arm}-{variant}", value) >= args.threshold,
                }
                for variant, value in pair.items()
            }
            for arm, pair in variants.items()
        }
        rows.append(row)
        print(
            f"[{index:02d}] pristine={row['pristine_score']:.4f} "
            f"v3={row['v3']['score']:.4f} (sel={row['v3']['selected']} rep={row['v3']['repair_used']}) "
            f"v4={row['v4']['score']:.4f} (sel={row['v4']['selected']} rep={row['v4']['repair_used']} "
            f"leak={row['v4']['closure_leaks']})"
        )

    summary = {}
    for arm in ("v3", "v4"):
        scores = [r[f"{arm}"]["score"] for r in rows]
        drops = [r["pristine_score"] - r[f"{arm}"]["score"] for r in rows]
        summary[arm] = {
            "detected": sum(1 for r in rows if r[f"{arm}"]["detected"]),
            "mean_score": round(statistics.mean(scores), 6) if scores else None,
            "mean_drop": round(statistics.mean(drops), 6) if drops else None,
            "mean_selected": round(statistics.mean(r[f"{arm}"]["selected"] for r in rows), 2) if rows else None,
            "closure_free_rate": (
                round(sum(1 for r in rows if r[arm]["closure_leaks"] == 0) / len(rows), 4) if rows else None
            ),
            "sanitizer_detection_counts": {
                variant: sum(1 for r in rows if r["sanitizers"][arm][variant]["detected"])
                for variant in ("raw", "nfkc", "cf_strip", "combined")
            },
        }

    artifact = {
        "algorithm_version": "cycle5-dev-paired-scored-v2",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model_id,
        "model_revision": model_revision,
        "frozen_corpus": Path(args.corpus).name,
        "registry": args.registry,
        "budget": args.budget,
        "threshold": args.threshold,
        "threshold_note": "frozen confirmation measurement identity; unchanged",
        "row_count": len(rows),
        "summary": summary,
        "rows": rows,
    }
    artifact["artifact_hash"] = sha256_json({k: v for k, v in artifact.items() if k != "artifact_hash"})
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")

    print("\n=== SUMMARY (threshold unchanged) ===")
    print(json.dumps(summary, indent=1))
    print(f"artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
