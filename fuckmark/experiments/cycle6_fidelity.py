from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from ..hashing import sha256_json, sha256_text
from ..sanitizer_robustness import introduced_invisible_codepoint_count
from ..transforms.hard_invariants import validate_hard_invariants
from ..transforms.quote_policy import validate_quote_safe_surface_operations
from ..transforms.schema import InvariantStatus


CYCLE6_FIDELITY_MECHANICAL_VERSION = "cycle6-fidelity-mechanical-v1"
CYCLE6_FIDELITY_REPORT_VERSION = "cycle6-full-fidelity-mechanical-report-v1"
_ASCII_SPACE_RUN = re.compile(r" {2,}")
_QUOTE_DELIMITERS = frozenset(('"', "'", "“", "”", "‘", "’"))


def collapse_repeated_ascii_spaces(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _ASCII_SPACE_RUN.sub(" ", text)


def _non_whitespace_text(text: str) -> str:
    return "".join(character for character in text if not character.isspace())


def _quote_delimiters(text: str) -> tuple[str, ...]:
    return tuple(character for character in text if character in _QUOTE_DELIMITERS)


def build_cycle6_fidelity_mechanical_row(
    *,
    sample_index: int,
    source_text: str,
    transformed_text: str,
    operations: Sequence[object],
    geometry: Mapping[str, object],
) -> dict[str, object]:
    operation_tuple = tuple(operations)
    validate_quote_safe_surface_operations(source_text, operation_tuple)
    hard = validate_hard_invariants(
        source_text,
        transformed_text,
        include_quotations=False,
    )
    only_one_ascii_space_added = all(
        operation.after_text
        in (operation.before_text + " ", " " + operation.before_text)
        for operation in operation_tuple
    )
    non_whitespace_preserved = (
        _non_whitespace_text(source_text) == _non_whitespace_text(transformed_text)
    )
    quote_delimiters_preserved = (
        _quote_delimiters(source_text) == _quote_delimiters(transformed_text)
    )
    length_delta = len(transformed_text) - len(source_text)
    operation_count = len(operation_tuple)
    repeated_space_collapse_restores_source = (
        collapse_repeated_ascii_spaces(transformed_text)
        == collapse_repeated_ascii_spaces(source_text)
    )
    payload = {
        "algorithm_version": CYCLE6_FIDELITY_MECHANICAL_VERSION,
        "sample_index": sample_index,
        "source_text_hash": sha256_text(source_text),
        "transformed_text_hash": sha256_text(transformed_text),
        "selected_operation_count": operation_count,
        "hard_invariant_status": hard.status.value,
        "hard_invariant_report_hash": hard.report_hash,
        "protected_content_status": hard.protected_report.status.value,
        "protected_content_report_hash": hard.protected_report.report_hash,
        "non_whitespace_text_preserved": non_whitespace_preserved,
        "non_whitespace_text_hash": sha256_text(_non_whitespace_text(source_text)),
        "quote_delimiter_sequence_preserved": quote_delimiters_preserved,
        "only_one_ascii_space_added_per_operation": only_one_ascii_space_added,
        "character_length_delta": length_delta,
        "length_delta_matches_operation_count": length_delta == operation_count,
        "introduced_invisible_codepoint_count": introduced_invisible_codepoint_count(
            source_text,
            transformed_text,
        ),
        "repeated_ascii_space_collapse_restores_source": (
            repeated_space_collapse_restores_source
        ),
        "root_window_count": geometry["root_window_count"],
        "intact_window_count": geometry["intact_window_count"],
        "tuple_leak_window_count": geometry["tuple_leak_window_count"],
        "closure_free": geometry["closure_free"],
        "budget_exhausted": geometry["budget_exhausted"],
    }
    passed = (
        hard.status is InvariantStatus.PASS
        and non_whitespace_preserved
        and quote_delimiters_preserved
        and only_one_ascii_space_added
        and length_delta == operation_count
        and payload["introduced_invisible_codepoint_count"] == 0
    )
    payload["mechanical_gate_passed"] = passed
    return {**payload, "row_hash": sha256_json(payload)}


def build_cycle6_full_fidelity_mechanical_report(
    rows: Sequence[Mapping[str, object]],
    *,
    source_corpus_content_hash: str,
    ruleset_hash: str,
    packet_hash: str,
) -> dict[str, object]:
    row_tuple = tuple(dict(row) for row in rows)
    if len(row_tuple) != 16:
        raise ValueError("Cycle 6 full fidelity report requires all 16 development samples")
    if tuple(sorted(int(row["sample_index"]) for row in row_tuple)) != tuple(range(16)):
        raise ValueError("Cycle 6 full fidelity rows must cover indices 0 through 15")
    for row in row_tuple:
        row_payload = {key: value for key, value in row.items() if key != "row_hash"}
        if row.get("row_hash") != sha256_json(row_payload):
            raise ValueError("Cycle 6 full fidelity mechanical row hash drifted")
    payload = {
        "algorithm_version": CYCLE6_FIDELITY_REPORT_VERSION,
        "source_corpus_content_hash": source_corpus_content_hash,
        "ruleset_hash": ruleset_hash,
        "budget": 14,
        "packet_hash": packet_hash,
        "row_count": len(row_tuple),
        "all_mechanical_gates_passed": all(
            bool(row["mechanical_gate_passed"]) for row in row_tuple
        ),
        "all_outputs_restored_by_repeated_ascii_space_collapse": all(
            bool(row["repeated_ascii_space_collapse_restores_source"])
            for row in row_tuple
        ),
        "human_review_status": "PENDING_INDEPENDENT_HUMAN_REVIEW",
        "detector_results_disclosed": False,
        "rows": row_tuple,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
