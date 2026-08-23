from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from .corpus import load_tiny_dev_corpus_by_version_json
from .experiments.mid_dev_quality import protected_span_violation_count, word_edit_rate
from .hashing import sha256_json, sha256_text
from .transforms import validate_hard_invariants, InvariantStatus


BUDGET_SCALED_ROBUSTNESS_VERSION = "budget-scaled-robustness-v1"
FORBIDDEN_CATEGORIES = ("Cc", "Cf", "Mn", "Mc", "Me", "Zl", "Zp")
WORD_EDIT_RATE_MAX = 0.30


def _forbidden_codepoints(text: str) -> tuple[str, ...]:
    return tuple(
        f"U+{ord(character):04X}({unicodedata.category(character)})"
        for character in sorted(set(text))
        if unicodedata.category(character) in FORBIDDEN_CATEGORIES
        or (unicodedata.category(character) == "Zs" and character != " ")
    )


def _introduced_forbidden_codepoints(source_text: str, transformed_text: str) -> tuple[str, ...]:
    source_alphabet = set(source_text)
    return tuple(
        f"U+{ord(character):04X}({unicodedata.category(character)})"
        for character in sorted(set(transformed_text) - source_alphabet)
        if unicodedata.category(character) in FORBIDDEN_CATEGORIES
        or (unicodedata.category(character) == "Zs" and character != " ")
    )


def _introduced_non_ascii(source_text: str, transformed_text: str) -> tuple[str, ...]:
    source_alphabet = set(source_text)
    return tuple(
        f"U+{ord(character):04X}"
        for character in sorted(set(transformed_text) - source_alphabet)
        if not character.isascii()
    )


def _cf_stripped(text: str) -> str:
    return "".join(
        character
        for character in text
        if unicodedata.category(character) != "Cf"
    )


def _robustness_row(source_text: str, transformed_text: str) -> dict[str, object]:
    normalization_noops = {
        "nfc": unicodedata.normalize("NFC", transformed_text) == transformed_text,
        "nfd": unicodedata.normalize("NFD", transformed_text) == transformed_text,
        "nfkc": unicodedata.normalize("NFKC", transformed_text) == transformed_text,
        "nfkd": unicodedata.normalize("NFKD", transformed_text) == transformed_text,
    }
    invariant_status = validate_hard_invariants(source_text, transformed_text).status
    row = {
        "source_text_hash": sha256_text(source_text),
        "transformed_text_hash": sha256_text(transformed_text),
        "transformed_is_ascii": transformed_text.isascii(),
        "preexisting_forbidden_codepoints": _forbidden_codepoints(transformed_text),
        "introduced_forbidden_codepoints": _introduced_forbidden_codepoints(source_text, transformed_text),
        "introduced_non_ascii_codepoints": _introduced_non_ascii(source_text, transformed_text),
        "normalization_noops": normalization_noops,
        "cf_strip_noop": _cf_stripped(transformed_text) == transformed_text,
        "word_edit_rate": word_edit_rate(source_text, transformed_text),
        "protected_span_violation_count": protected_span_violation_count(source_text, transformed_text),
        "hard_invariant_status": invariant_status.value,
    }
    gates_pass = (
        not row["introduced_forbidden_codepoints"]
        and not row["introduced_non_ascii_codepoints"]
        and all(normalization_noops.values())
        and row["cf_strip_noop"]
        and row["word_edit_rate"] <= WORD_EDIT_RATE_MAX
        and row["protected_span_violation_count"] == 0
        and invariant_status is InvariantStatus.PASS
    )
    return {**row, "gates_pass": gates_pass}


def build_budget_scaled_robustness_report(
    corpora: tuple[object, ...],
    plans: tuple[dict[str, object], ...],
) -> dict[str, object]:
    sources: dict[str, object] = {}
    for corpus in corpora:
        for sample in corpus.manifest.samples:
            sources[sample.sample_id] = sample
    corpus_text_hashes: list[set[str]] = [
        {sample.text_sha256 for sample in corpus.manifest.samples} for corpus in corpora
    ]
    pairwise_overlaps = {}
    for left in range(len(corpora)):
        for right in range(left + 1, len(corpora)):
            pairwise_overlaps[f"{left}-{right}"] = len(
                corpus_text_hashes[left] & corpus_text_hashes[right]
            )
    rows: list[dict[str, object]] = []
    for plan in plans:
        for variant in plan["variants"]:
            sample = sources[variant["source_sample_id"]]
            rows.append(
                {
                    "plan_hash": plan["plan_hash"],
                    "source_sample_id": variant["source_sample_id"],
                    "requested_budget": variant["requested_budget"],
                    **_robustness_row(sample.text, variant["transformed_text"]),
                }
            )
    row_tuple = tuple(rows)
    summary = {
        "row_count": len(row_tuple),
        "gate_pass_fraction": sum(1 for row in row_tuple if row["gates_pass"]) / len(row_tuple) if row_tuple else 1.0,
        "all_introduced_codepoints_clean": all(
            not row["introduced_forbidden_codepoints"] and not row["introduced_non_ascii_codepoints"]
            for row in row_tuple
        ),
        "all_normalization_noops": all(all(row["normalization_noops"].values()) for row in row_tuple),
        "all_cf_strip_noop": all(row["cf_strip_noop"] for row in row_tuple),
        "max_word_edit_rate": max((row["word_edit_rate"] for row in row_tuple), default=0.0),
        "total_protected_span_violations": sum(
            row["protected_span_violation_count"] for row in row_tuple
        ),
        "all_hard_invariants_pass": all(
            row["hard_invariant_status"] == InvariantStatus.PASS.value for row in row_tuple
        ),
        "corpus_pairwise_text_hash_overlaps": pairwise_overlaps,
    }
    payload = {
        "algorithm_version": BUDGET_SCALED_ROBUSTNESS_VERSION,
        "word_edit_rate_max": WORD_EDIT_RATE_MAX,
        "forbidden_categories": FORBIDDEN_CATEGORIES,
        "corpus_artifact_hashes": tuple(corpus.artifact_hash for corpus in corpora),
        "plan_hashes": tuple(plan["plan_hash"] for plan in plans),
        "rows": row_tuple,
        "summary": summary,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _load_plan(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-budget-scaled-robustness")
    parser.add_argument("--corpus-json", type=Path, action="append", required=True)
    parser.add_argument("--plan-json", type=Path, action="append", required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpora = tuple(
        load_tiny_dev_corpus_by_version_json(path) for path in args.corpus_json
    )
    plans = tuple(_load_plan(path) for path in args.plan_json)
    report = build_budget_scaled_robustness_report(corpora, plans)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"artifact_hash={report['artifact_hash']}\n")
    sys.stdout.write(f"row_count={report['summary']['row_count']}\n")
    sys.stdout.write(f"gate_pass_fraction={report['summary']['gate_pass_fraction']}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
