from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, ".")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-out", required=True)
    parser.add_argument("--private-out", required=True)
    parser.add_argument("--indices", type=int, nargs="+", default=(8, 10))
    parser.add_argument("--budget", type=int, default=14)
    parser.add_argument("--seed", type=int, default=6_720_000)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    from fuckmark.experiments.cover_greedy_v4 import schedule_cover_greedy_v4
    from fuckmark.hashing import sha256_json
    from fuckmark.tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
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
    )
    identity = runtime_tokenizer_identity_public(tokenizer, model_id, revision)
    tokenizer_identity_hash = sha256_json(
        {
            "model_id": identity.model_id,
            "model_revision": identity.model_revision,
            "tokenizer_id": identity.tokenizer_id,
            "tokenizer_revision": identity.tokenizer_revision,
        }
    )
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    by_index = {int(row["index"]): row for row in corpus["samples"]}
    registry = quote_safe_zrd_transform_registry()
    samples = []
    for index in args.indices:
        source = str(by_index[index]["text"])
        enumeration = registry.enumerate(source)
        plan = schedule_cover_greedy_v4(
            source_sample_id=f"dev-{index}",
            source_text=source,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=5,
            budget=args.budget,
        )
        transformed = registry.apply(
            enumeration,
            plan.selected_candidate_ids,
        ).output_text
        samples.append(
            FidelityReviewSample.create(
                registry.ruleset_hash,
                f"fresh16-{index}",
                source,
                transformed,
            )
        )
    packet = build_blind_review_packet(tuple(samples), args.seed)
    public_payload = packet.public_payload()
    public_payload["status"] = "PENDING_INDEPENDENT_HUMAN_REVIEW"
    public_payload["scope"] = "quote-interior surface-spacing residuals only"
    public_payload["detector_results_disclosed"] = False
    public_path = Path(args.public_out)
    private_path = Path(args.private_out)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public_payload, indent=1) + "\n", encoding="utf-8")
    private_path.write_text(
        json.dumps(asdict(packet), indent=1) + "\n",
        encoding="utf-8",
    )
    print(public_path)
    print(private_path)
    print(packet.packet_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
