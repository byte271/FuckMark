from __future__ import annotations

from collections.abc import Mapping

from .compare import (
    CYCLE6_SPACING_ARM_ID,
    CYCLE7_COMBINED_ARM_ID,
    CYCLE7_DURABLE_ARM_ID,
)


CYCLE7_DECISION_VERSION = "cycle7-stage-a-decision-v1"
PROMISING_DEVELOPMENT = "PROMISING_DEVELOPMENT"
REJECTED = "REJECTED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def _arm(row: Mapping[str, object], arm_id: str) -> Mapping[str, object]:
    arms = row["arms"]
    if not isinstance(arms, Mapping):
        raise TypeError("row arms must be a mapping")
    value = arms[arm_id]
    if not isinstance(value, Mapping):
        raise TypeError("arm summary must be a mapping")
    return value


def classify_fixture_stage_a(report: Mapping[str, object]) -> dict[str, object]:
    rows = report.get("rows")
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("Stage A report must contain rows")
    rich = next(row for row in rows if row["source_sample_id"] == "contraction-rich")
    sparse = next(row for row in rows if row["source_sample_id"] == "contraction-sparse")
    spacing_rich = _arm(rich, CYCLE6_SPACING_ARM_ID)
    durable_rich = _arm(rich, CYCLE7_DURABLE_ARM_ID)
    combined_rich = _arm(rich, CYCLE7_COMBINED_ARM_ID)
    durable_sparse = _arm(sparse, CYCLE7_DURABLE_ARM_ID)

    quote = next(row for row in rows if row["source_sample_id"] == "quote-interior")
    spacing_quote = _arm(quote, CYCLE6_SPACING_ARM_ID)
    durable_quote = _arm(quote, CYCLE7_DURABLE_ARM_ID)
    collapse_survives = durable_rich["collapsed_equals_collapsed_source"] is False
    spacing_undone = spacing_rich["collapsed_equals_collapsed_source"] is True
    durable_has_ops = int(durable_rich["selected_count"]) > 0
    sparse_density = int(durable_sparse["candidate_count"])
    combined_has_ops = int(combined_rich["selected_count"]) > 0

    reasons: list[str] = []
    if durable_has_ops and collapse_survives:
        reasons.append("durable edits remain after ASCII whitespace collapse on contraction-rich text")
    if spacing_undone and int(spacing_rich["selected_count"]) > 0:
        reasons.append("Cycle 6 spacing edits are removed by the same collapse sanitizer")
    if (
        spacing_quote["collapsed_equals_collapsed_source"] is True
        and durable_quote["collapsed_equals_collapsed_source"] is False
        and int(durable_quote["selected_count"]) > 0
    ):
        reasons.append(
            "inside quotes, Cycle 6 spacing collapses away while Cycle 7 durable edits remain"
        )
    if sparse_density == 0:
        reasons.append("durable candidate density is zero on contraction-sparse text")
    if combined_has_ops:
        reasons.append("combined durable+spacing still enumerates a non-empty candidate set")

    detector = report.get("detector")
    detector_signal = None
    if isinstance(detector, Mapping) and detector.get("available") is True:
        durable_collapse_detected = int(detector["durable"]["ws_collapse_watermarked_detected"])
        spacing_collapse_detected = int(detector["cycle6_spacing"]["ws_collapse_watermarked_detected"])
        durable_raw_detected = int(detector["durable"]["raw_watermarked_detected"])
        spacing_raw_detected = int(detector["cycle6_spacing"]["raw_watermarked_detected"])
        n_watermarked = int(detector["durable"]["watermarked_row_count"])
        detector_signal = {
            "durable_raw_detected": durable_raw_detected,
            "spacing_raw_detected": spacing_raw_detected,
            "durable_ws_collapse_detected": durable_collapse_detected,
            "spacing_ws_collapse_detected": spacing_collapse_detected,
            "watermarked_row_count": n_watermarked,
        }
        if spacing_raw_detected < n_watermarked and spacing_collapse_detected == n_watermarked:
            reasons.append(
                "Cycle 6 spacing reduced raw detections and those detections returned after whitespace collapse"
            )
        if durable_raw_detected == n_watermarked:
            reasons.append("durable family did not reduce raw detections on the Stage A corpus")
        elif durable_collapse_detected < spacing_collapse_detected:
            reasons.append("durable arm has fewer ws_collapse detections than Cycle 6 spacing on the same corpus")
        elif durable_collapse_detected == spacing_collapse_detected:
            reasons.append("durable and Cycle 6 spacing ws_collapse detection counts are tied")
        else:
            reasons.append("durable arm did not beat Cycle 6 spacing on ws_collapse detections")

    if not durable_has_ops:
        decision = REJECTED
        reasons.append("durable family selected no operations on contraction-rich text")
    elif not collapse_survives:
        decision = REJECTED
        reasons.append("durable family did not survive whitespace collapse")
    elif detector is None:
        decision = PROMISING_DEVELOPMENT
        reasons.append("geometry-only Stage A; detector scoring was not attached")
    elif isinstance(detector, Mapping) and detector.get("available") is not True:
        decision = PROMISING_DEVELOPMENT
        reasons.append("geometry collapse-survival demonstrated; detector scoring unavailable")
    else:
        durable_collapse_detected = int(detector["durable"]["ws_collapse_watermarked_detected"])
        spacing_collapse_detected = int(detector["cycle6_spacing"]["ws_collapse_watermarked_detected"])
        durable_raw_detected = int(detector["durable"]["raw_watermarked_detected"])
        n_watermarked = int(detector["durable"]["watermarked_row_count"])
        if durable_collapse_detected < spacing_collapse_detected:
            decision = PROMISING_DEVELOPMENT
            reasons.append("this tiny corpus is not a formal confirmation")
        elif durable_raw_detected == n_watermarked:
            decision = INSUFFICIENT_EVIDENCE
            reasons.append(
                "durable collapse-survival is real on fixtures, but density is too low to replace Cycle 6 spacing"
            )
        elif durable_has_ops and collapse_survives:
            decision = PROMISING_DEVELOPMENT
            reasons.append(
                "collapse-survival is demonstrated, but this tiny corpus is not a formal confirmation"
            )
        else:
            decision = INSUFFICIENT_EVIDENCE

    payload = {
        "algorithm_version": CYCLE7_DECISION_VERSION,
        "decision": decision,
        "reasons": tuple(reasons),
        "detector_signal": detector_signal,
        "notes": (
            "This is a development classification, not a Cycle 7 formal confirmation. "
            "Confirmation seeds 830000/840000/850000 were not inspected."
        ),
    }
    return payload
