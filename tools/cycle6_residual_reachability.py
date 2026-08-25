from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, ".")


def encode(tokenizer, text: str) -> tuple[int, ...]:
    return tuple(int(value) for value in tokenizer(text, add_special_tokens=False)["input_ids"])


def variants(text: str) -> dict[str, str]:
    return {
        "raw": text,
        "nfkc": unicodedata.normalize("NFKC", text),
        "cf_strip": "".join(
            character
            for character in text
            if not unicodedata.category(character).startswith("Cf")
        ),
        "combined": "".join(
            character
            for character in unicodedata.normalize("NFKC", text)
            if not unicodedata.category(character).startswith("Cf")
        ),
    }


def positional_survivors(root, source_tokens, output_tokens, repetition):
    from fuckmark.alignment import align_tokens
    from fuckmark.geometry.counterfactual import (
        DEFAULT_MAX_ALIGNMENT_CELLS,
        _ambiguous_root_indices,
    )

    alignment = align_tokens(source_tokens, output_tokens)
    ambiguous = _ambiguous_root_indices(
        source_tokens,
        output_tokens,
        alignment.distance,
        max_cells=DEFAULT_MAX_ALIGNMENT_CELLS,
    )
    output_eligibility = repetition.evaluate(output_tokens).eligible_windows
    survivors = set()
    for observation in root.observations:
        if not observation.eligible:
            continue
        indices = range(observation.token_start, observation.token_end_exclusive)
        if any(index in ambiguous for index in indices):
            continue
        mapped = tuple(alignment.original_to_transformed[index] for index in indices)
        if any(value is None for value in mapped):
            continue
        positions = tuple(int(value) for value in mapped)
        if positions != tuple(range(positions[0], positions[0] + len(positions))):
            continue
        if tuple(output_tokens[position] for position in positions) != observation.token_ids:
            continue
        if positions[0] >= len(output_eligibility) or not output_eligibility[positions[0]]:
            continue
        survivors.add(observation.observation_index)
    return survivors, ambiguous, alignment


def _span_inside(start: int, end: int, spans) -> bool:
    return any(start >= span.start and end <= span.end for span in spans)


def _span_intersects(start: int, end: int, spans) -> bool:
    return any(start < span.end and span.start < end for span in spans)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--indices", type=int, nargs="+", default=(8, 10))
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--threshold", type=float, default=0.5570987654320988)
    parser.add_argument("--source-container-hash")
    parser.add_argument("--source-content-hash")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    from fuckmark.adapters import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
    from fuckmark.detectors import weighted_mean_evidence
    from fuckmark.experiments.cover_greedy_v4 import schedule_cover_greedy_v4
    from fuckmark.geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
    from fuckmark.geometry.repetition import PublicRepetitionGeometry
    from fuckmark.hashing import sha256_json
    from fuckmark.native_observations import build_native_observations
    from fuckmark.tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
    from fuckmark.transforms import ProtectedSpanExtractor, ProtectedSpanKind
    from fuckmark.transforms.effectiveness_profile import zrd_destruction_transform_registry

    model_id = "openai-community/gpt2"
    model_revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    keys = (654, 400, 836, 123, 340, 443, 597, 160, 57)
    ngram_len = 5
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=model_revision,
        padding_side="left",
    )
    identity = runtime_tokenizer_identity_public(tokenizer, model_id, model_revision)
    tokenizer_identity_hash = sha256_json(
        {
            "model_id": identity.model_id,
            "model_revision": identity.model_revision,
            "tokenizer_id": identity.tokenizer_id,
            "tokenizer_revision": identity.tokenizer_revision,
        }
    )
    adapter = HuggingFaceSynthIDAdapter.from_torch(
        HuggingFaceSynthIDConfig(ngram_len=ngram_len, keys=keys),
        device="cpu",
    )
    eos = tokenizer.eos_token_id
    repetition = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=1024,
    )
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=GeometryConfig.create(
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
            repetition_mask_policy_id=repetition.policy_id,
        ),
        eligibility_policy=repetition.eligibility_policy,
    )
    registry = zrd_destruction_transform_registry()
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    samples = {int(row["index"]): row for row in corpus["samples"]}

    def batch(sample_id: str, text: str):
        return build_native_observations(sample_id, encode(tokenizer, text), eos, adapter)

    def score(sample_id: str, text: str) -> float:
        return weighted_mean_evidence(batch(sample_id, text)).raw_score

    reports = []
    for index in args.indices:
        source = str(samples[index]["text"])
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
        result = registry.apply(enumeration, plan.selected_candidate_ids)
        output = result.output_text
        source_encoded = tokenizer(
            source,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        source_tokens = tuple(int(value) for value in source_encoded["input_ids"])
        source_offsets = tuple((int(a), int(b)) for a, b in source_encoded["offset_mapping"])
        output_tokens = encode(tokenizer, output)
        root = engine.build_root(source_sample_id=f"dev-{index}", source_text=source)
        survivors, ambiguous, alignment = positional_survivors(
            root.observations,
            source_tokens,
            output_tokens,
            repetition,
        )
        output_windows = {
            tuple(output_tokens[start : start + ngram_len])
            for start in range(max(0, len(output_tokens) - ngram_len + 1))
        }
        quotation_spans = tuple(
            span
            for span in ProtectedSpanExtractor().extract(source).spans
            if ProtectedSpanKind.QUOTATION in span.kinds
        )
        source_batch = batch(f"dev-{index}-source", source)
        source_evidence = weighted_mean_evidence(source_batch)
        weights = source_evidence.normalized_weights
        candidates = enumeration.candidates
        rejections = enumeration.rejections
        observations = []
        for observation, detector_record in zip(
            root.observations.observations,
            source_batch.records,
        ):
            start = source_offsets[observation.token_start][0]
            end = source_offsets[observation.token_end_exclusive - 1][1]
            row_score = sum(
                weight * value for weight, value in zip(weights, detector_record.g_values)
            ) / len(weights)
            available = tuple(
                candidate
                for candidate in candidates
                if start < candidate.end and candidate.start < end
            )
            rejected = tuple(
                rejection
                for rejection in rejections
                if start < rejection.end and rejection.start < end
            )
            inside_quote = _span_inside(start, end, quotation_spans)
            observations.append(
                {
                    "index": observation.observation_index,
                    "token_start": observation.token_start,
                    "token_end_exclusive": observation.token_end_exclusive,
                    "character_start": start,
                    "character_end": end,
                    "text": source[start:end],
                    "eligible": observation.eligible,
                    "repeated_context": not observation.eligible,
                    "g_values": detector_record.g_values,
                    "token_ids": observation.token_ids,
                    "weighted_row_score": row_score,
                    "inside_quote": inside_quote,
                    "intersects_quote": _span_intersects(start, end, quotation_spans),
                    "protection_reason": (
                        "blanket_quotation_exact"
                        if inside_quote
                        else None
                    ),
                    "available_candidate_ids": tuple(
                        candidate.candidate_id for candidate in available
                    ),
                    "available_candidate_families": tuple(
                        sorted({candidate.family.value for candidate in available})
                    ),
                    "rejected_candidate_count": len(rejected),
                    "rejection_reasons": tuple(
                        sorted({rejection.reason.value for rejection in rejected})
                    ),
                    "positional_intact": observation.observation_index in survivors,
                    "tuple_leak": observation.token_ids in output_windows,
                    "ambiguous_alignment": any(
                        token_index in ambiguous
                        for token_index in range(
                            observation.token_start,
                            observation.token_end_exclusive,
                        )
                    ),
                }
            )

        output_encoded = tokenizer(
            output,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        output_offsets = tuple((int(a), int(b)) for a, b in output_encoded["offset_mapping"])
        output_quotes = tuple(
            span
            for span in ProtectedSpanExtractor().extract(output).spans
            if ProtectedSpanKind.QUOTATION in span.kinds
        )
        output_batch = batch(f"dev-{index}-output", output)
        output_evidence = weighted_mean_evidence(output_batch)
        output_rows = []
        for record in output_batch.records:
            start = output_offsets[record.token_start][0]
            end = output_offsets[record.token_end_exclusive - 1][1]
            row_score = sum(
                weight * value
                for weight, value in zip(output_evidence.normalized_weights, record.g_values)
            ) / len(output_evidence.normalized_weights)
            output_rows.append(
                {
                    "index": record.index,
                    "valid": record.valid,
                    "repeated_context": record.repeated,
                    "character_start": start,
                    "character_end": end,
                    "inside_quote": _span_inside(start, end, output_quotes),
                    "g_values": record.g_values,
                    "weighted_row_score": row_score,
                }
            )
        valid_rows = [row for row in output_rows if row["valid"]]
        quote_rows = [row for row in valid_rows if row["inside_quote"]]
        total_mass = sum(float(row["weighted_row_score"]) for row in valid_rows)
        quote_mass = sum(float(row["weighted_row_score"]) for row in quote_rows)
        total_excess = sum(float(row["weighted_row_score"]) - 0.5 for row in valid_rows)
        quote_excess = sum(float(row["weighted_row_score"]) - 0.5 for row in quote_rows)
        intact_inside = sum(
            bool(row["eligible"] and row["positional_intact"] and row["inside_quote"])
            for row in observations
        )
        intact_outside = sum(
            bool(row["eligible"] and row["positional_intact"] and not row["inside_quote"])
            for row in observations
        )
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        sanitizer_scores = {
            name: score(f"dev-{index}-{name}", text)
            for name, text in variants(output).items()
        }
        reports.append(
            {
                "index": index,
                "seed": samples[index]["seed"],
                "source_text": source,
                "output_text": output,
                "source_token_ids": source_tokens,
                "output_token_ids": output_tokens,
                "source_token_count": len(source_tokens),
                "output_token_count": len(output_tokens),
                "quotation_spans": tuple(
                    {
                        "start": span.start,
                        "end": span.end,
                        "text": span.exact_text,
                    }
                    for span in quotation_spans
                ),
                "protected_spans": tuple(
                    {
                        "start": span.start,
                        "end": span.end,
                        "kinds": tuple(kind.value for kind in span.kinds),
                        "text": span.exact_text,
                    }
                    for span in enumeration.protected_manifest.spans
                ),
                "candidate_count": len(candidates),
                "rejected_candidate_count": len(rejections),
                "rejections_by_reason": dict(Counter(row.reason.value for row in rejections)),
                "rejections_by_family": dict(Counter(row.rule_id for row in rejections)),
                "conflict_count": len(enumeration.conflicts),
                "selected_operations": tuple(
                    {
                        "candidate_id": candidate_id,
                        "rule_id": by_id[candidate_id].rule_id,
                        "family": by_id[candidate_id].family.value,
                        "start": by_id[candidate_id].start,
                        "end": by_id[candidate_id].end,
                        "before": by_id[candidate_id].source_text,
                        "after": by_id[candidate_id].replacement_text,
                    }
                    for candidate_id in plan.selection_order
                ),
                "root_window_count": plan.root_window_count,
                "intact_window_count": plan.intact_window_count,
                "intact_windows_inside_quotes": intact_inside,
                "intact_windows_outside_quotes": intact_outside,
                "tuple_leak_window_count": plan.tuple_leak_window_count,
                "repeated_root_window_count": sum(
                    not observation.eligible
                    for observation in root.observations.observations
                ),
                "ambiguous_root_token_indices": tuple(sorted(ambiguous)),
                "alignment_distance": alignment.distance,
                "selected_operation_count": plan.selected_candidate_count,
                "repair_selections": plan.repair_phase_selections,
                "budget_exhausted": plan.budget_exhausted,
                "candidate_exhausted": (
                    plan.selected_candidate_count < args.budget and not plan.achieved_zero
                ),
                "conflict_excluded_candidate_count": len(
                    plan.conflict_excluded_candidate_ids
                ),
                "source_score": source_evidence.raw_score,
                "output_score": output_evidence.raw_score,
                "detected": output_evidence.raw_score >= args.threshold,
                "sanitizer_scores": sanitizer_scores,
                "sanitizer_detections": {
                    name: value >= args.threshold
                    for name, value in sanitizer_scores.items()
                },
                "quote_valid_observation_count": len(quote_rows),
                "valid_observation_count": len(valid_rows),
                "quote_fraction_of_detector_numerator": (
                    quote_mass / total_mass if total_mass else None
                ),
                "quote_fraction_of_signed_excess_above_null": (
                    quote_excess / total_excess if total_excess else None
                ),
                "classification": "protected-region-unreachable",
                "classification_exclusions": {
                    "budget_limited": False,
                    "candidate_density_limited": True,
                    "conflict_limited": False,
                    "search_limited": False,
                    "closure_limited": False,
                    "repetition_mask_limited": False,
                    "statistical_tail": False,
                },
                "root_observation_map": observations,
                "output_observations": output_rows,
            }
        )

    artifact = {
        "algorithm_version": "cycle6-residual-reachability-v1",
        "source_corpus_hash": args.source_container_hash or corpus.get("corpus_hash"),
        "source_corpus_content_hash": args.source_content_hash or corpus.get("content_hash"),
        "threshold": args.threshold,
        "budget": args.budget,
        "registry": "zrd-destruction-extension-v1",
        "scheduler": "cover-greedy-key-blind-v4",
        "reports": reports,
    }
    artifact["artifact_hash"] = sha256_json(artifact)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
    print(output_path)
    print(artifact["artifact_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
