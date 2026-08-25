from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


def _intersects(start: int, end: int, spans) -> bool:
    return any(start < span.end and span.start < end for span in spans)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--source-container-hash", required=True)
    parser.add_argument("--source-content-hash", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    from fuckmark.experiments.cover_greedy_v4 import schedule_cover_greedy_v4
    from fuckmark.geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
    from fuckmark.geometry.repetition import PublicRepetitionGeometry
    from fuckmark.hashing import sha256_json
    from fuckmark.tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
    from fuckmark.transforms import ProtectedSpanExtractor, ProtectedSpanKind
    from fuckmark.transforms.effectiveness_profile import quote_safe_zrd_transform_registry
    from tools.cycle6_residual_reachability import encode, positional_survivors

    model_id = "openai-community/gpt2"
    revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    ngram_len = 5
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, padding_side="left")
    identity = runtime_tokenizer_identity_public(tokenizer, model_id, revision)
    tokenizer_identity_hash = sha256_json(
        {
            "model_id": identity.model_id,
            "model_revision": identity.model_revision,
            "tokenizer_id": identity.tokenizer_id,
            "tokenizer_revision": identity.tokenizer_revision,
        }
    )
    repetition = PublicRepetitionGeometry.create(ngram_len=ngram_len, context_history_size=1024)
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=GeometryConfig.create(
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
            repetition_mask_policy_id=repetition.policy_id,
        ),
        eligibility_policy=repetition.eligibility_policy,
    )
    registry = quote_safe_zrd_transform_registry()
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    rows = []
    for sample in corpus["samples"]:
        index = int(sample["index"])
        source = str(sample["text"])
        enumeration = registry.enumerate(source)
        plan = schedule_cover_greedy_v4(
            source_sample_id=f"dev-{index}",
            source_text=source,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
            budget=args.budget,
        )
        output = registry.apply(enumeration, plan.selected_candidate_ids).output_text
        encoded = tokenizer(source, add_special_tokens=False, return_offsets_mapping=True)
        source_tokens = tuple(int(value) for value in encoded["input_ids"])
        source_offsets = tuple((int(a), int(b)) for a, b in encoded["offset_mapping"])
        output_tokens = encode(tokenizer, output)
        root = engine.build_root(source_sample_id=f"dev-{index}", source_text=source)
        survivors, ambiguous, alignment = positional_survivors(
            root.observations, source_tokens, output_tokens, repetition
        )
        quote_spans = tuple(
            span
            for span in ProtectedSpanExtractor().extract(source).spans
            if ProtectedSpanKind.QUOTATION in span.kinds
        )
        exact_spans = enumeration.protected_manifest.spans
        exact_residual = 0
        quote_residual = 0
        for observation in root.observations.observations:
            if not observation.eligible or observation.observation_index not in survivors:
                continue
            start = source_offsets[observation.token_start][0]
            end = source_offsets[observation.token_end_exclusive - 1][1]
            exact_residual += _intersects(start, end, exact_spans)
            quote_residual += _intersects(start, end, quote_spans)
        rows.append(
            {
                "index": index,
                "seed": sample["seed"],
                "candidate_count": plan.candidate_count,
                "selected_operation_count": plan.selected_candidate_count,
                "static_selections": plan.static_phase_selections,
                "repair_selections": plan.repair_phase_selections,
                "root_window_count": plan.root_window_count,
                "intact_window_count": plan.intact_window_count,
                "intact_fraction": (
                    plan.intact_window_count / plan.root_window_count
                    if plan.root_window_count
                    else 0.0
                ),
                "tuple_leak_window_count": plan.tuple_leak_window_count,
                "closure_free": plan.closure_free,
                "achieved_geometry_zero": plan.achieved_zero,
                "budget_exhausted": plan.budget_exhausted,
                "candidate_exhausted": (
                    plan.selected_candidate_count < args.budget and not plan.achieved_zero
                ),
                "conflict_excluded_candidate_count": len(plan.conflict_excluded_candidate_ids),
                "protected_exact_intact_window_count": exact_residual,
                "quote_container_intact_window_count": quote_residual,
                "repeated_root_window_count": sum(
                    not observation.eligible for observation in root.observations.observations
                ),
                "ambiguous_root_token_count": len(ambiguous),
                "alignment_distance": alignment.distance,
                "source_token_count": len(source_tokens),
                "output_token_count": len(output_tokens),
            }
        )
    artifact = {
        "algorithm_version": "cycle6-quote-safe-geometry-report-v1",
        "source_corpus_container_hash": args.source_container_hash,
        "source_corpus_content_hash": args.source_content_hash,
        "model": model_id,
        "model_revision": revision,
        "registry": "quote-safe-zrd",
        "ruleset_hash": registry.ruleset_hash,
        "scheduler": "cover-greedy-key-blind-v4",
        "budget": args.budget,
        "rows": rows,
    }
    artifact["artifact_hash"] = sha256_json(artifact)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
    print(output)
    print(artifact["artifact_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
