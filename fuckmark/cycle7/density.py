from __future__ import annotations

from collections.abc import Mapping, Sequence

from .registry import cycle7_durable_transform_registry


def durable_candidate_rule_ids(text: str) -> tuple[str, ...]:
    enumeration = cycle7_durable_transform_registry().enumerate(text)
    return tuple(candidate.rule_id for candidate in enumeration.candidates)


def durable_density_row(sample_id: str, text: str) -> dict[str, object]:
    rule_ids = durable_candidate_rule_ids(text)
    compound_ids = tuple(rule_id for rule_id in rule_ids if rule_id.startswith("lexical-compound-"))
    contraction_ids = tuple(
        rule_id
        for rule_id in rule_ids
        if rule_id.startswith(("contract-", "expand-", "cycle7-contract-", "cycle7-expand-"))
    )
    apostrophe_ids = tuple(rule_id for rule_id in rule_ids if rule_id.startswith("lexical-apostrophe-"))
    return {
        "sample_id": sample_id,
        "candidate_count": len(rule_ids),
        "compound_candidate_count": len(compound_ids),
        "contraction_candidate_count": len(contraction_ids),
        "apostrophe_candidate_count": len(apostrophe_ids),
        "rule_ids": rule_ids,
        "compound_rule_ids": compound_ids,
        "apostrophe_rule_ids": apostrophe_ids,
    }


def durable_density_table(samples: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for sample in samples:
        rows.append(durable_density_row(str(sample["sample_id"]), str(sample["text"])))
    return tuple(rows)
