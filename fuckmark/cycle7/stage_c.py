from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..hashing import sha256_json
from .density import durable_density_table
from .stage_b import INSUFFICIENT_EVIDENCE, PROMISING_DEVELOPMENT, summarize_density_rows


CYCLE7_STAGE_C_DECISION_VERSION = "cycle7-stage-c-decision-v1"


def classify_stage_c_density(
    *,
    density_summary: Mapping[str, object],
    collapsed_intact_mean: float | None = None,
    source_root_mean: float | None = None,
) -> dict[str, object]:
    mean_candidates = float(density_summary["mean_candidate_count"])
    mean_format = float(density_summary["mean_format_candidate_count"])
    mean_clause = float(density_summary.get("mean_format_clause_candidate_count", 0.0))
    mean_quantifier = float(density_summary.get("mean_quantifier_of_candidate_count", 0.0))
    residual_mean = mean_candidates - mean_format
    reasons: list[str] = []
    if mean_candidates >= 8:
        reasons.append("mean durable candidate count is at least 8 per sample")
    elif mean_candidates >= 4:
        reasons.append("mean durable candidate count remains in the Stage B four-site regime")
    else:
        reasons.append("mean durable candidate count remains too low to replace Cycle 6 spacing")
    if mean_format >= 0.6 * mean_candidates and mean_candidates > 0:
        reasons.append("most durable sites are still punctuation-newline layout edits")
    if mean_clause >= 2:
        reasons.append("clause punctuation newlines supply additional layout density")
    if mean_quantifier >= 1:
        reasons.append("quantifier-of-determiner sites fired on this corpus")
    if residual_mean < 2 and mean_format >= 2:
        reasons.append("non-format lexical and syntactic density remains low")
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
    if mean_candidates < 8:
        decision = INSUFFICIENT_EVIDENCE
    elif collapsed_fraction is not None and collapsed_fraction > 0.75:
        decision = INSUFFICIENT_EVIDENCE
        reasons.append("density rose but collapse-surviving geometry still leaves most windows intact")
    else:
        decision = PROMISING_DEVELOPMENT
        reasons.append("this is development evidence, not Cycle 7 formal confirmation")
    payload = {
        "algorithm_version": CYCLE7_STAGE_C_DECISION_VERSION,
        "decision": decision,
        "reasons": tuple(reasons),
        "mean_candidate_count": mean_candidates,
        "mean_format_candidate_count": mean_format,
        "mean_format_clause_candidate_count": mean_clause,
        "mean_quantifier_of_candidate_count": mean_quantifier,
        "mean_nonformat_candidate_count": residual_mean,
        "collapsed_intact_fraction_of_root": collapsed_fraction,
        "notes": (
            "Stage C is development-only. Seeds 830000/840000/850000 were not inspected. "
            "Seed 880000 remains unused validation until a catalog freeze. "
            "Do not retune on 810000, 860000, or 820000."
        ),
    }
    return payload


def density_artifact_stage_c(
    samples: Sequence[Mapping[str, object]],
    *,
    seed_base: int,
    catalog_version: str,
) -> dict[str, object]:
    rows = durable_density_table(samples)
    summary = summarize_density_rows(rows)
    payload = {
        "algorithm_version": "cycle7-stage-c-density-v1",
        "seed_base": seed_base,
        "durable_catalog_version": catalog_version,
        "detector_access_used_for_selection": False,
        "rows": rows,
        "summary": summary,
        "decision": classify_stage_c_density(density_summary=summary),
    }
    return {**payload, "artifact_hash": sha256_json({k: v for k, v in payload.items() if k != "artifact_hash"})}
