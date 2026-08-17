from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .._validation import require_sha256
from ..hashing import sha256_json
from .synthid_geometry import GeometryLabel, GeometryPairStatus, SynthIDGeometryReport


SYNTHID_POSTSELECTION_ALGORITHM_VERSION = "synthid-postselection-audit-v1"


def _pearson(first: tuple[float, ...], second: tuple[float, ...]) -> float | None:
    if len(first) != len(second):
        raise ValueError("correlation inputs must have equal length")
    if len(first) < 2:
        return None
    first_mean = statistics.fmean(first)
    second_mean = statistics.fmean(second)
    first_ss = sum((value - first_mean) ** 2 for value in first)
    second_ss = sum((value - second_mean) ** 2 for value in second)
    if first_ss == 0.0 or second_ss == 0.0:
        return None
    covariance = sum((left - first_mean) * (right - second_mean) for left, right in zip(first, second))
    return covariance / math.sqrt(first_ss * second_ss)


@dataclass(frozen=True, slots=True)
class PostselectionLabelSummary:
    label: GeometryLabel
    matched_pair_count: int
    geometry_positive_pair_count: int
    geometry_positive_score_positive_count: int
    geometry_positive_score_nonpositive_count: int
    mean_score_advantage_when_geometry_positive: float | None
    pearson_geometry_vs_score: float | None


@dataclass(frozen=True, slots=True)
class SynthIDPostselectionAudit:
    algorithm_version: str
    source_report_hash: str
    selection_feedback_used: bool
    summaries: tuple[PostselectionLabelSummary, ...]
    audit_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_POSTSELECTION_ALGORITHM_VERSION:
            raise ValueError("unsupported postselection audit algorithm version")
        require_sha256("source_report_hash", self.source_report_hash)
        if self.selection_feedback_used is not False:
            raise ValueError("postselection audit must remain descriptive")
        if tuple(row.label for row in self.summaries) != (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED):
            raise ValueError("summaries must use canonical label order")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self.payload()):
            raise ValueError("audit_hash does not match postselection audit")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_report_hash": self.source_report_hash,
            "selection_feedback_used": self.selection_feedback_used,
            "summaries": self.summaries,
        }


def _summary(report: SynthIDGeometryReport, label: GeometryLabel) -> PostselectionLabelSummary:
    pairs = tuple(
        pair
        for pair in report.pairs
        if pair.status is GeometryPairStatus.MATCHED and pair.label is label
    )
    geometry_positive = tuple(pair for pair in pairs if float(pair.disruption_advantage) > 0.0)
    positive_score_count = sum(float(pair.score_drop_advantage) > 0.0 for pair in geometry_positive)
    mean_positive = None
    if geometry_positive:
        mean_positive = statistics.fmean(float(pair.score_drop_advantage) for pair in geometry_positive)
    correlation = _pearson(
        tuple(float(pair.disruption_advantage) for pair in pairs),
        tuple(float(pair.score_drop_advantage) for pair in pairs),
    )
    return PostselectionLabelSummary(
        label,
        len(pairs),
        len(geometry_positive),
        positive_score_count,
        len(geometry_positive) - positive_score_count,
        mean_positive,
        correlation,
    )


def build_synthid_postselection_audit(report: SynthIDGeometryReport) -> SynthIDPostselectionAudit:
    if not isinstance(report, SynthIDGeometryReport):
        raise TypeError("report must be a SynthIDGeometryReport")
    summaries = (
        _summary(report, GeometryLabel.CONTROL),
        _summary(report, GeometryLabel.WATERMARKED),
    )
    payload = {
        "algorithm_version": SYNTHID_POSTSELECTION_ALGORITHM_VERSION,
        "source_report_hash": report.report_hash,
        "selection_feedback_used": False,
        "summaries": summaries,
    }
    return SynthIDPostselectionAudit(
        SYNTHID_POSTSELECTION_ALGORITHM_VERSION,
        report.report_hash,
        False,
        summaries,
        sha256_json(payload),
    )
