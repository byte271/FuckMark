from __future__ import annotations

from collections import Counter
from typing import Any

from ..hashing import sha256_json
from ..transforms.protected import ProtectedSpanExtractor


COVERAGE_HOLE_ANALYSIS_VERSION = "coverage-hole-structure-v1"
NGRAM_LEN = 5

_FUNCTION_WORDS = frozenset(
    (
        "is",
        "of",
        "to",
        "the",
        "and",
        "in",
        "for",
        "on",
        "with",
        "as",
        "from",
        "that",
        "this",
        "was",
        "are",
        "be",
        "can",
        "will",
        "have",
        "has",
        "not",
        "but",
        "or",
        "by",
        "at",
        "it",
        "we",
        "you",
        "they",
        "an",
        "he",
        "she",
        "his",
        "her",
        "its",
        "our",
        "their",
        "them",
        "him",
        "us",
        "me",
        "my",
        "your",
        "if",
        "when",
        "where",
        "which",
        "who",
        "what",
        "how",
        "why",
        "because",
        "so",
        "than",
        "then",
        "there",
        "here",
        "all",
        "any",
        "each",
        "more",
        "most",
        "some",
        "such",
        "only",
        "very",
        "just",
        "also",
        "into",
        "about",
        "over",
        "under",
        "after",
        "before",
        "between",
        "during",
        "through",
        "without",
        "while",
        "do",
        "does",
        "been",
        "being",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "were",
        "one",
        "even",
        "still",
        "often",
    )
)


def classify_word(word: str) -> str:
    stripped = word.strip(".,;:!?\"'()")
    if not stripped:
        return "punctuation_or_empty"
    if stripped.isdigit():
        return "numeric"
    lowered = stripped.lower()
    if lowered in _FUNCTION_WORDS:
        return "function_word"
    if stripped[0].isupper():
        return "capitalized_content"
    if stripped.isalpha():
        return "lowercase_content"
    return "other"


def _rule_family(rule_id: str) -> str:
    if rule_id.startswith("contract"):
        return "contraction"
    if rule_id.startswith("surface"):
        return "surface_spacing"
    if rule_id.startswith("lexical"):
        return "lexical"
    if rule_id.startswith("syntax"):
        return "syntax"
    return "other"


def build_coverage_hole_row(
    text: str,
    token_ids: tuple[int, ...],
    offsets: tuple[tuple[int, int], ...],
    enumeration,
    geometry,
    variant,
) -> dict[str, object]:
    token_count = len(token_ids)
    observation_count = max(0, token_count - NGRAM_LEN + 1)
    coverage = geometry.coverage_mapping()
    window_hits = Counter()
    for candidate_id, intervals in coverage.items():
        for interval in intervals:
            for window in range(interval.start, interval.end_exclusive):
                window_hits[window] += 1
    uncovered = tuple(w for w in range(observation_count) if window_hits[w] == 0)
    covered_windows = observation_count - len(uncovered)
    longest_run = 0
    run = 0
    for window in range(observation_count):
        if window_hits[window] == 0:
            run += 1
            longest_run = max(longest_run, run)
        else:
            run = 0
    uncovered_spans = []
    cursor = None
    for window in uncovered:
        if cursor is None or window != cursor[1]:
            if cursor is not None:
                uncovered_spans.append(cursor)
            cursor = [window, window + 1]
        else:
            cursor[1] = window + 1
    if cursor is not None:
        uncovered_spans.append(cursor)
    lexical_categories: Counter[str] = Counter()
    uncovered_word_samples: list[str] = []
    protected = ProtectedSpanExtractor().extract(text)
    protected_char_spans = tuple((span.start, span.end) for span in protected.spans)
    protected_intersections = 0
    for start_window, end_window in uncovered_spans:
        char_start = offsets[start_window][0] if start_window < len(offsets) else len(text)
        char_end = offsets[min(end_window - 1, len(offsets) - 1)][1] if end_window - 1 < len(offsets) else len(text)
        snippet = text[char_start:char_end]
        for token in snippet.split():
            lexical_categories[classify_word(token)] += 1
        if len(uncovered_word_samples) < 5 and snippet.strip():
            uncovered_word_samples.append(snippet.strip()[:60])
        for span_start, span_end in protected_char_spans:
            if span_start < char_end and char_start < span_end:
                protected_intersections += 1
                break
    selected_ids = set(variant["selected_candidate_ids"])
    realized_windows = sum(
        1
        for window in range(observation_count)
        if any(
            interval.start <= window < interval.end_exclusive
            for candidate_id, intervals in coverage.items()
            if candidate_id in selected_ids
            for interval in intervals
        )
    )
    candidate_by_family = Counter(
        _rule_family(candidate.rule_id) for candidate in enumeration.candidates
    )
    redundancy = (
        sum(window_hits.values()) / covered_windows if covered_windows else 0.0
    )
    return {
        "source_sample_id": variant["source_sample_id"],
        "source_label": variant["source_label"],
        "domain": variant["domain"],
        "token_count": token_count,
        "observation_window_count": observation_count,
        "candidate_count": len(enumeration.candidates),
        "candidate_count_by_family": dict(candidate_by_family),
        "candidate_density_per_100_tokens": round(100.0 * len(enumeration.candidates) / token_count, 4) if token_count else 0.0,
        "zero_candidate_source": len(enumeration.candidates) == 0,
        "achievable_coverage_fraction": covered_windows / observation_count if observation_count else 0.0,
        "realized_coverage_fraction": realized_windows / observation_count if observation_count else 0.0,
        "uncovered_window_count": len(uncovered),
        "longest_uncovered_run": longest_run,
        "uncovered_span_count": len(uncovered_spans),
        "uncovered_lexical_categories": dict(lexical_categories),
        "unprotected_word_samples": uncovered_word_samples,
        "protected_span_intersections": protected_intersections,
        "candidate_redundancy_mean_multiplicity": round(redundancy, 4),
    }


def build_coverage_hole_report(corpus: Any, tokenizer: Any, plan: dict[str, object]) -> dict[str, object]:
    from ..experiments.effectiveness_plan import _attack_samples, _encode_with_offsets
    from ..transforms import build_candidate_tokenizer_geometry

    registry = _registry_for_plan(plan)
    profile_budgets = plan["budgets"]
    sources = {sample.sample_id: sample for sample in _attack_samples(corpus)}
    rows = []
    for variant in plan["variants"]:
        if variant["requested_budget"] != profile_budgets[0]:
            continue
        source = sources[variant["source_sample_id"]]
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        enumeration = registry.enumerate(source.text)
        geometry = build_candidate_tokenizer_geometry(
            source.text,
            enumeration,
            token_ids,
            offsets,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=NGRAM_LEN,
        )
        rows.append(
            build_coverage_hole_row(
                source.text,
                token_ids,
                offsets,
                enumeration,
                geometry,
                variant,
            )
        )
    row_tuple = tuple(rows)
    watermarked = tuple(row for row in row_tuple if row["source_label"] == "watermarked")
    aggregated: Counter[str] = Counter()
    for row in watermarked:
        for category, count in row["uncovered_lexical_categories"].items():
            aggregated[category] += count
    payload = {
        "algorithm_version": COVERAGE_HOLE_ANALYSIS_VERSION,
        "analysis_scope": "structural text-geometry diagnosis; no detector information used",
        "plan_hash": plan["plan_hash"],
        "ruleset_hash": plan["ruleset_hash"],
        "rows": row_tuple,
        "watermarked_uncovered_lexical_totals": dict(aggregated),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _registry_for_plan(plan: dict[str, object]):
    from ..transforms import (
        KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
        CONTENT_REGION_COVERAGE_PROFILE_ID,
        content_region_coverage_transform_registry,
        key_blind_coverage_completion_transform_registry,
        key_blind_high_coverage_transform_registry,
    )

    profile_id = plan["profile_id"]
    if profile_id == KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID:
        return key_blind_coverage_completion_transform_registry()
    if profile_id == CONTENT_REGION_COVERAGE_PROFILE_ID:
        return content_region_coverage_transform_registry()
    return key_blind_high_coverage_transform_registry()


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="fuckmark-coverage-holes")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    from ..corpus import load_tiny_dev_corpus_by_version_json

    corpus = load_tiny_dev_corpus_by_version_json(args.corpus_json)
    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
        use_fast=True,
        padding_side="left",
    )
    report = build_coverage_hole_report(corpus, tokenizer, plan)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sys.stdout.write(f"artifact_hash={report['artifact_hash']}\n")
    sys.stdout.write(f"row_count={len(report['rows'])}\n")
    sys.stdout.write(
        f"uncovered_lexical_totals={report['watermarked_uncovered_lexical_totals']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
