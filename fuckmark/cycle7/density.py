from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..transforms.registry import TransformRegistry
from .registry import cycle7_durable_transform_registry


def _prefix_ids(rule_ids: Sequence[str], prefixes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(rule_id for rule_id in rule_ids if rule_id.startswith(prefixes))


def durable_candidate_rule_ids(text: str, *, registry: TransformRegistry | None = None) -> tuple[str, ...]:
    active = cycle7_durable_transform_registry() if registry is None else registry
    enumeration = active.enumerate(text)
    return tuple(candidate.rule_id for candidate in enumeration.candidates)


def durable_density_row(
    sample_id: str,
    text: str,
    *,
    registry: TransformRegistry | None = None,
) -> dict[str, object]:
    active = cycle7_durable_transform_registry() if registry is None else registry
    enumeration = active.enumerate(text)
    rule_ids = tuple(candidate.rule_id for candidate in enumeration.candidates)
    conflict_ids = {item.first_candidate_id for item in enumeration.conflicts} | {
        item.second_candidate_id for item in enumeration.conflicts
    }
    isolated = tuple(
        candidate.rule_id for candidate in enumeration.candidates if candidate.candidate_id not in conflict_ids
    )
    compound_ids = _prefix_ids(rule_ids, ("lexical-compound-",))
    contraction_ids = _prefix_ids(
        rule_ids,
        ("contract-", "expand-", "cycle7-contract-", "cycle7-expand-"),
    )
    apostrophe_ids = _prefix_ids(rule_ids, ("lexical-apostrophe-",))
    format_ids = _prefix_ids(rule_ids, ("cycle7-format-",))
    format_sentence_ids = _prefix_ids(rule_ids, ("cycle7-format-sentence-",))
    format_clause_ids = _prefix_ids(rule_ids, ("cycle7-format-clause-",))
    discourse_ids = _prefix_ids(rule_ids, ("lexical-discourse-",))
    prenominal_ids = _prefix_ids(rule_ids, ("lexical-prenominal-",))
    complementizer_ids = _prefix_ids(
        rule_ids,
        ("cycle7-syntax-complementizer-", "cycle7-syntax-relative-"),
    )
    parenthetical_ids = _prefix_ids(rule_ids, ("cycle7-syntax-parenthetical-",))
    coord_comma_ids = _prefix_ids(rule_ids, ("cycle7-syntax-coord-comma-",))
    quantifier_ids = _prefix_ids(rule_ids, ("lexical-quantifier-",))
    word_boundary_ids = _prefix_ids(rule_ids, ("cycle7-word-boundary-",))
    tokenish = max(1, len(text.split()))
    return {
        "sample_id": sample_id,
        "candidate_count": len(rule_ids),
        "isolated_candidate_count": len(isolated),
        "conflict_pair_count": len(enumeration.conflicts),
        "candidates_per_64_tokens": round(64.0 * len(rule_ids) / tokenish, 4),
        "compound_candidate_count": len(compound_ids),
        "contraction_candidate_count": len(contraction_ids),
        "apostrophe_candidate_count": len(apostrophe_ids),
        "format_candidate_count": len(format_ids),
        "format_sentence_candidate_count": len(format_sentence_ids),
        "format_clause_candidate_count": len(format_clause_ids),
        "discourse_comma_candidate_count": len(discourse_ids),
        "prenominal_candidate_count": len(prenominal_ids),
        "complementizer_candidate_count": len(complementizer_ids),
        "parenthetical_candidate_count": len(parenthetical_ids),
        "coord_comma_candidate_count": len(coord_comma_ids),
        "quantifier_of_candidate_count": len(quantifier_ids),
        "word_boundary_candidate_count": len(word_boundary_ids),
        "protected_blocked_count": sum(
            1 for rejection in enumeration.rejections if rejection.reason.value == "protected_overlap"
        ),
        "quote_blocked_count": sum(
            1 for rejection in enumeration.rejections if rejection.reason.value == "quote_policy_blocked"
        ),
        "precondition_failed_count": sum(
            1 for rejection in enumeration.rejections if rejection.reason.value == "precondition_failed"
        ),
        "rule_ids": rule_ids,
        "compound_rule_ids": compound_ids,
        "apostrophe_rule_ids": apostrophe_ids,
        "format_rule_ids": format_ids,
        "format_sentence_rule_ids": format_sentence_ids,
        "format_clause_rule_ids": format_clause_ids,
        "discourse_rule_ids": discourse_ids,
        "prenominal_rule_ids": prenominal_ids,
        "complementizer_rule_ids": complementizer_ids,
        "parenthetical_rule_ids": parenthetical_ids,
        "coord_comma_rule_ids": coord_comma_ids,
        "quantifier_of_rule_ids": quantifier_ids,
        "word_boundary_rule_ids": word_boundary_ids,
    }


def durable_density_table(
    samples: Sequence[Mapping[str, object]],
    *,
    registry: TransformRegistry | None = None,
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for sample in samples:
        rows.append(
            durable_density_row(str(sample["sample_id"]), str(sample["text"]), registry=registry)
        )
    return tuple(rows)
