from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


FROZEN_CONTENT_HASH = "b114cf4d869c5a5d78ac52855a1a480b1f0e605137aee2cb269062880fcc22d3"
FROZEN_TOKENIZER_HASH = "1be91dc38048d8f69fc45d5fb8175b0edb7c6ec807af1f6b85aa657343dbb95e"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--public-out", required=True, type=Path)
    parser.add_argument("--private-out", required=True, type=Path)
    parser.add_argument("--mechanical-out", required=True, type=Path)
    parser.add_argument("--budget", type=int, default=14)
    parser.add_argument("--seed", type=int, default=6_720_001)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.budget != 14:
        raise ValueError("Cycle 6 full fidelity review is frozen at B14")

    from transformers import AutoTokenizer

    from fuckmark.durable_io import write_canonical_json_fsynced
    from fuckmark.experiments.cover_greedy_v4 import schedule_cover_greedy_v4
    from fuckmark.experiments.cycle6_fidelity import (
        build_cycle6_fidelity_mechanical_row,
        build_cycle6_full_fidelity_mechanical_report,
    )
    from fuckmark.tiny_dev_context_survival_plan_hf import (
        runtime_tokenizer_identity_public,
    )
    from fuckmark.transforms import (
        FidelityReviewSample,
        build_blind_review_packet,
        quote_safe_zrd_transform_registry,
    )

    model_id = "openai-community/gpt2"
    revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=revision,
        padding_side="left",
        use_fast=True,
    )
    identity = runtime_tokenizer_identity_public(tokenizer, model_id, revision)
    if identity.identity_hash != FROZEN_TOKENIZER_HASH:
        raise ValueError("Cycle 6 fidelity tokenizer identity drifted")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if corpus.get("content_hash") != FROZEN_CONTENT_HASH:
        raise ValueError("Cycle 6 fidelity corpus content hash drifted")
    source_rows = tuple(sorted(corpus["samples"], key=lambda row: int(row["index"])))
    if tuple(int(row["index"]) for row in source_rows) != tuple(range(16)):
        raise ValueError("Cycle 6 full fidelity corpus must cover indices 0 through 15")

    registry = quote_safe_zrd_transform_registry()
    review_samples = []
    mechanical_rows = []
    for row in source_rows:
        index = int(row["index"])
        source = str(row["text"])
        enumeration = registry.enumerate(source)
        plan = schedule_cover_greedy_v4(
            source_sample_id=f"fresh16-{index}",
            source_text=source,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=identity.identity_hash,
            ngram_len=5,
            budget=args.budget,
        )
        result = registry.apply(enumeration, plan.selected_candidate_ids)
        review_samples.append(
            FidelityReviewSample.create(
                registry.ruleset_hash,
                f"fresh16-{index}",
                source,
                result.output_text,
            )
        )
        mechanical_rows.append(
            build_cycle6_fidelity_mechanical_row(
                sample_index=index,
                source_text=source,
                transformed_text=result.output_text,
                operations=result.trace.operations,
                geometry={
                    "root_window_count": plan.root_window_count,
                    "intact_window_count": plan.intact_window_count,
                    "tuple_leak_window_count": plan.tuple_leak_window_count,
                    "closure_free": plan.closure_free,
                    "budget_exhausted": plan.budget_exhausted,
                },
            )
        )

    packet = build_blind_review_packet(tuple(review_samples), args.seed)
    public_payload = {
        **packet.public_payload(),
        "status": "PENDING_INDEPENDENT_HUMAN_REVIEW",
        "scope": "all 16 frozen Cycle 6 B14 development outputs",
        "detector_results_disclosed": False,
        "review_instructions": {
            "labels": (
                "equivalent_or_minor",
                "material_change",
                "cannot_judge",
            ),
            "judge": (
                "meaning, attribution, names, facts, numbers, protected entities, "
                "quote intent, readability, punctuation, and repeated-space naturalness"
            ),
            "minimum_reviewers": 2,
            "tiebreak_reviewer_on_disagreement": True,
        },
    }
    private_payload = {
        **packet.private_manifest_payload(),
        "status": "PRIVATE_ORIENTATION_KEY",
        "detector_results_disclosed": False,
    }
    mechanical = build_cycle6_full_fidelity_mechanical_report(
        mechanical_rows,
        source_corpus_content_hash=FROZEN_CONTENT_HASH,
        ruleset_hash=registry.ruleset_hash,
        packet_hash=packet.packet_hash,
    )
    if mechanical["all_mechanical_gates_passed"] is not True:
        raise ValueError("Cycle 6 full fidelity mechanical gate failed")
    write_canonical_json_fsynced(args.public_out, public_payload)
    write_canonical_json_fsynced(args.private_out, private_payload)
    write_canonical_json_fsynced(args.mechanical_out, mechanical)
    print(f"packet_hash={packet.packet_hash}")
    print(f"mechanical_artifact_hash={mechanical['artifact_hash']}")
    print("human_review_status=PENDING_INDEPENDENT_HUMAN_REVIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
