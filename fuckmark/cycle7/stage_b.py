from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..hashing import sha256_json
from .density import durable_density_table
from .instrumentation import measure_arm
from .registry import cycle7_durable_transform_registry, cycle7_stage_b_durable_transform_registry


CYCLE7_STAGE_B_DECISION_VERSION = "cycle7-stage-b-decision-v1"
PROMISING_DEVELOPMENT = "PROMISING_DEVELOPMENT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
REJECTED = "REJECTED"


def summarize_density_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not rows:
        raise ValueError("density rows must not be empty")
    counts = tuple(int(row["candidate_count"]) for row in rows)
    format_counts = tuple(int(row["format_candidate_count"]) for row in rows)
    format_clause_counts = tuple(int(row.get("format_clause_candidate_count", 0)) for row in rows)
    complementizer_counts = tuple(int(row["complementizer_candidate_count"]) for row in rows)
    discourse_counts = tuple(int(row["discourse_comma_candidate_count"]) for row in rows)
    prenominal_counts = tuple(int(row["prenominal_candidate_count"]) for row in rows)
    parenthetical_counts = tuple(int(row["parenthetical_candidate_count"]) for row in rows)
    coord_comma_counts = tuple(int(row["coord_comma_candidate_count"]) for row in rows)
    quantifier_counts = tuple(int(row.get("quantifier_of_candidate_count", 0)) for row in rows)
    word_boundary_counts = tuple(int(row.get("word_boundary_candidate_count", 0)) for row in rows)
    return {
        "sample_count": len(rows),
        "mean_candidate_count": sum(counts) / len(counts),
        "min_candidate_count": min(counts),
        "max_candidate_count": max(counts),
        "mean_format_candidate_count": sum(format_counts) / len(format_counts),
        "mean_format_clause_candidate_count": sum(format_clause_counts) / len(format_clause_counts),
        "mean_complementizer_candidate_count": sum(complementizer_counts) / len(complementizer_counts),
        "mean_discourse_comma_candidate_count": sum(discourse_counts) / len(discourse_counts),
        "mean_prenominal_candidate_count": sum(prenominal_counts) / len(prenominal_counts),
        "mean_parenthetical_candidate_count": sum(parenthetical_counts) / len(parenthetical_counts),
        "mean_coord_comma_candidate_count": sum(coord_comma_counts) / len(coord_comma_counts),
        "mean_quantifier_of_candidate_count": sum(quantifier_counts) / len(quantifier_counts),
        "mean_word_boundary_candidate_count": sum(word_boundary_counts) / len(word_boundary_counts),
        "zero_candidate_rows": sum(count == 0 for count in counts),
    }


def classify_stage_b_density(
    *,
    density_summary: Mapping[str, object],
    collapsed_intact_mean: float | None = None,
    source_root_mean: float | None = None,
) -> dict[str, object]:
    mean_candidates = float(density_summary["mean_candidate_count"])
    mean_format = float(density_summary["mean_format_candidate_count"])
    mean_coord = float(density_summary.get("mean_coord_comma_candidate_count", 0.0))
    residual_mean = mean_candidates - mean_format
    punctuation_mean = mean_format + mean_coord
    reasons: list[str] = []
    if mean_candidates >= 8:
        reasons.append("mean durable candidate count is at least 8 per sample")
    elif mean_candidates >= 4:
        reasons.append("mean durable candidate count rose above the Stage A one-to-three site regime")
    else:
        reasons.append("mean durable candidate count remains too low to replace Cycle 6 spacing")
    if residual_mean < 2 and mean_format >= 2:
        reasons.append(
            "most of the new density is sentence-boundary formatting rather than lexical/syntactic sites"
        )
    if mean_coord >= 2 and mean_coord >= residual_mean * 0.5:
        reasons.append(
            "coordinating-conjunction commas supply a large share of non-format density"
        )
    collapsed_fraction = None
    if collapsed_intact_mean is not None and source_root_mean is not None:
        if source_root_mean <= 0:
            raise ValueError("source_root_mean must be positive")
        collapsed_fraction = collapsed_intact_mean / source_root_mean
        if collapsed_fraction <= 0.5:
            reasons.append("collapsed intact root windows dropped by at least half versus the source root")
        elif collapsed_fraction <= 0.75:
            reasons.append("collapsed intact root windows dropped, but more than half of the source windows remain")
        else:
            reasons.append("collapsed intact root windows remain high relative to the source root")
    if mean_candidates < 4:
        decision = INSUFFICIENT_EVIDENCE
    elif collapsed_fraction is not None and collapsed_fraction > 0.75:
        decision = INSUFFICIENT_EVIDENCE
        reasons.append("density rose but collapse-surviving geometry still leaves most windows intact")
    else:
        decision = PROMISING_DEVELOPMENT
        reasons.append("this is development evidence, not Cycle 7 formal confirmation")
    payload = {
        "algorithm_version": CYCLE7_STAGE_B_DECISION_VERSION,
        "decision": decision,
        "reasons": tuple(reasons),
        "mean_candidate_count": mean_candidates,
        "mean_format_candidate_count": mean_format,
        "mean_coord_comma_candidate_count": mean_coord,
        "mean_nonformat_candidate_count": residual_mean,
        "mean_punctuation_candidate_count": punctuation_mean,
        "collapsed_intact_fraction_of_root": collapsed_fraction,
        "notes": (
            "Stage B is development-only. Seeds 830000/840000/850000 were not inspected. "
            "Do not promote exploratory or validation seeds into confirmation after seeing scores."
        ),
    }
    return payload


def density_artifact(
    samples: Sequence[Mapping[str, object]],
    *,
    seed_base: int,
    catalog_version: str,
) -> dict[str, object]:
    rows = durable_density_table(samples, registry=cycle7_stage_b_durable_transform_registry())
    summary = summarize_density_rows(rows)
    payload = {
        "algorithm_version": "cycle7-stage-b-density-v1",
        "seed_base": seed_base,
        "durable_catalog_version": catalog_version,
        "detector_access_used_for_selection": False,
        "rows": rows,
        "summary": summary,
        "decision": classify_stage_b_density(density_summary=summary),
    }
    return {**payload, "artifact_hash": sha256_json({k: v for k, v in payload.items() if k != "artifact_hash"})}


def geometry_intact_means(
    samples: Sequence[Mapping[str, object]],
    tokenizer,
    tokenizer_identity_hash: str,
    *,
    registry=None,
) -> dict[str, float]:
    active = cycle7_durable_transform_registry() if registry is None else registry
    intact = []
    collapsed_intact = []
    selected = []
    roots = []
    for sample in samples:
        measurement = measure_arm(
            arm_id="cycle7_durable",
            source_sample_id=str(sample["sample_id"]),
            source_text=str(sample["text"]),
            registry=active,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
        )
        intact.append(measurement.intact_window_count)
        collapsed_intact.append(measurement.collapsed_intact_window_count)
        selected.append(measurement.selected_count)
        roots.append(measurement.root_window_count)
    n = len(samples)
    root_mean = sum(roots) / n
    collapsed_mean = sum(collapsed_intact) / n
    return {
        "mean_selected_count": sum(selected) / n,
        "mean_root_window_count": root_mean,
        "mean_intact_window_count": sum(intact) / n,
        "mean_collapsed_intact_window_count": collapsed_mean,
        "collapsed_intact_fraction_of_root": collapsed_mean / root_mean if root_mean else 1.0,
    }
