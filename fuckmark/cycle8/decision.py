from __future__ import annotations

from collections.abc import Mapping

from .compare import (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U034F_SPACE_RUN_ARM_ID,
    CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
    CYCLE8_U200C_SPACE_ARM_ID,
    CYCLE8_UFE00_SPACE_ARM_ID,
)
from .scoreboard import EvidenceLabel, ProductGate


CYCLE8_DECISION_VERSION = "cycle8-fixture-decision-v1"
PROMISING_DEVELOPMENT = "PROMISING_DEVELOPMENT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
REJECTED = "REJECTED"


def _arm(row: Mapping[str, object], arm_id: str) -> Mapping[str, object]:
    arms = row["arms"]
    if not isinstance(arms, Mapping):
        raise TypeError("row arms must be a mapping")
    value = arms[arm_id]
    if not isinstance(value, Mapping):
        raise TypeError("arm summary must be a mapping")
    return value


def _sanitizer(arm: Mapping[str, object], variant: str) -> Mapping[str, object]:
    sanitizers = arm["sanitizers"]
    if not isinstance(sanitizers, Mapping):
        raise TypeError("arm sanitizers must be a mapping")
    value = sanitizers[variant]
    if not isinstance(value, Mapping):
        raise TypeError("sanitizer summary must be a mapping")
    return value


def classify_fixture_compare(report: Mapping[str, object]) -> dict[str, object]:
    rows = report.get("rows")
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("Cycle 8 fixture report must contain rows")
    reasons: list[str] = []
    visible_failures = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("fixture row must be a mapping")
        arms = row["arms"]
        if not isinstance(arms, Mapping):
            raise TypeError("row arms must be a mapping")
        for arm_id, arm in arms.items():
            if not isinstance(arm, Mapping):
                raise TypeError("arm summary must be a mapping")
            if arm.get("visible_ok") is not True:
                visible_failures += 1
                reasons.append(f"{row.get('source_sample_id')}:{arm_id} failed visible projection")
    screen = next(row for row in rows if row["source_sample_id"] == "gpt2-screen")
    quote = next(row for row in rows if row["source_sample_id"] == "quote-interior")
    identity = _arm(screen, CYCLE8_IDENTITY_ARM_ID)
    u200c = _arm(screen, CYCLE8_U200C_SPACE_ARM_ID)
    u034f = _arm(screen, CYCLE8_U034F_SPACE_ARM_ID)
    u034f_run = _arm(screen, CYCLE8_U034F_SPACE_RUN_ARM_ID)
    ufe00 = _arm(screen, CYCLE8_UFE00_SPACE_ARM_ID) if CYCLE8_UFE00_SPACE_ARM_ID in screen["arms"] else None
    if identity.get("selected_count") != 0:
        reasons.append("identity arm selected a transform")
    if int(u034f["selected_count"]) <= 0:
        reasons.append("U+034F space arm selected no sites on the GPT-2 fixture")
    if _sanitizer(u200c, "cf_strip")["equals_source"] is True:
        reasons.append("U+200C is removed by Cf-strip")
    else:
        reasons.append("U+200C unexpectedly survived Cf-strip")
    if _sanitizer(u034f, "cf_strip")["equals_transformed"] is True:
        reasons.append("U+034F survives Cf-strip on the GPT-2 fixture")
    else:
        reasons.append("U+034F did not survive Cf-strip")
    if _sanitizer(u034f, "nfkc")["equals_transformed"] is True:
        reasons.append("U+034F survives NFKC on the GPT-2 fixture")
    if _sanitizer(u034f, "ws_collapse")["equals_transformed"] is True:
        reasons.append("U+034F survives whitespace-collapse-v1 after ASCII spaces")
    if int(_arm(quote, CYCLE8_U034F_SPACE_ARM_ID)["protected_blocked_count"]) > 0:
        reasons.append("quote interiors block U+034F space carriers as protected spans")
    tokenizer = u034f.get("tokenizer")
    if isinstance(tokenizer, Mapping) and tokenizer.get("ids_equal") is False:
        reasons.append("U+034F space insertion changes GPT-2 token ids")
    if isinstance(tokenizer, Mapping) and int(u034f_run.get("utf8_overhead") or 0) > int(u034f.get("utf8_overhead") or 0):
        reasons.append("U+034F x8 increases hidden payload over x1")
    if ufe00 is not None and _sanitizer(ufe00, "cf_strip").get("equals_transformed") is True:
        reasons.append("U+FE00 survives Cf-strip on the GPT-2 fixture")
    product_gate = ProductGate.DISQUALIFIED if visible_failures else ProductGate.PASS
    detector = report.get("detector")
    detector_signal = None
    if visible_failures:
        decision = REJECTED
        label = EvidenceLabel.PRODUCT_DISQUALIFIED
    elif _sanitizer(u034f, "cf_strip")["equals_transformed"] is not True:
        decision = REJECTED
        label = EvidenceLabel.REJECTED
    elif isinstance(detector, Mapping) and detector.get("available") is True:
        u034f_summary = detector[CYCLE8_U034F_SPACE_ARM_ID]
        identity_summary = detector[CYCLE8_IDENTITY_ARM_ID]
        u200c_summary = detector[CYCLE8_U200C_SPACE_ARM_ID]
        run_summary = detector[CYCLE8_U034F_SPACE_RUN_ARM_ID]
        detector_signal = {
            "identity_raw_watermarked_detected": int(identity_summary["raw_watermarked_detected"]),
            "u200c_raw_watermarked_detected": int(u200c_summary["raw_watermarked_detected"]),
            "u034f_raw_watermarked_detected": int(u034f_summary["raw_watermarked_detected"]),
            "u034f_run_raw_watermarked_detected": int(run_summary["raw_watermarked_detected"]),
            "u034f_ws_collapse_watermarked_detected": int(u034f_summary["ws_collapse_watermarked_detected"]),
            "identity_raw_unwatermarked_detected": int(identity_summary["raw_unwatermarked_detected"]),
            "u034f_raw_unwatermarked_detected": int(u034f_summary["raw_unwatermarked_detected"]),
            "watermarked_row_count": int(u034f_summary["watermarked_row_count"]),
        }
        reasons.append("detector scores are development-only")
        if (
            product_gate is ProductGate.PASS
            and int(u034f_summary["raw_watermarked_detected"]) < int(identity_summary["raw_watermarked_detected"])
            and int(u034f_summary["raw_unwatermarked_detected"]) <= int(identity_summary["raw_unwatermarked_detected"])
        ):
            decision = PROMISING_DEVELOPMENT
            label = EvidenceLabel.HYPOTHESIS
            reasons.append("U+034F reduced raw watermarked detections without raising unwatermarked detections")
        else:
            decision = INSUFFICIENT_EVIDENCE
            label = EvidenceLabel.HYPOTHESIS
            reasons.append("U+034F did not beat identity on this tiny development corpus")
    else:
        decision = INSUFFICIENT_EVIDENCE
        label = EvidenceLabel.HYPOTHESIS
        reasons.append("no Cycle 8 detector scores on seed 890000 in this fixture artifact")
    payload = {
        "algorithm_version": CYCLE8_DECISION_VERSION,
        "decision": decision,
        "product_gate": product_gate.value,
        "evidence_label": label.value,
        "visible_failures": visible_failures,
        "reasons": tuple(reasons),
        "detector_signal": detector_signal,
        "notes": (
            "This is Cycle 8 development classification, not confirmation. "
            "Do not inspect 830000, 840000, or 850000. "
            "Seed 880000 is PUBLICLY_EXPOSED by PR #98 and is not eligible as unseen validation. "
            "U+034F is not product-authorized."
        ),
    }
    return payload


CYCLE8_SCALE_DECISION_VERSION = "cycle8-scale-decision-v1"


def classify_scale_detector_compare(
    artifact: Mapping[str, object],
    transformed_arm_id: str = CYCLE8_U034F_SPACE_ARM_ID,
) -> dict[str, object]:
    summaries = artifact.get("summaries")
    if not isinstance(summaries, Mapping):
        raise ValueError("scale detector artifact must contain summaries")
    identity = summaries[CYCLE8_IDENTITY_ARM_ID]
    u034f = summaries[transformed_arm_id]
    if transformed_arm_id == CYCLE8_U034F_SPACE_ARM_ID:
        arm_label = "U+034F x1"
    elif transformed_arm_id == CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID:
        arm_label = "U+034F space-wordfinal x1"
    else:
        arm_label = transformed_arm_id
    visible_total = int(u034f["visible_total_count"])
    visible_pass = int(u034f["visible_pass_count"])
    visible_failures = visible_total - visible_pass
    identity_wm = int(identity["raw_watermarked_detected"])
    transformed_wm = int(u034f["raw_watermarked_detected"])
    transformed_uw = int(u034f["raw_unwatermarked_detected"])
    cf_wm = int(u034f["cf_strip_watermarked_detected"])
    nfkc_wm = int(u034f["nfkc_watermarked_detected"])
    collapse_wm = int(u034f["ws_collapse_watermarked_detected"])
    nfkc_cf_wm = int(u034f["nfkc_cf_strip_watermarked_detected"])
    combined_wm = int(u034f["ws_collapse_nfkc_cf_strip_watermarked_detected"])
    reasons: list[str] = []
    if visible_failures:
        reasons.append("visible projection failed")
        decision = REJECTED
        label = EvidenceLabel.PRODUCT_DISQUALIFIED
        gate = ProductGate.DISQUALIFIED
    else:
        gate = ProductGate.PASS
        reasons.append(f"visible projection passed on all scored {arm_label} rows")
        if transformed_wm < identity_wm and transformed_uw <= int(identity["raw_unwatermarked_detected"]):
            decision = PROMISING_DEVELOPMENT
            label = EvidenceLabel.HYPOTHESIS
            reasons.append(f"{arm_label} reduced raw watermarked detections without raising unwatermarked detections")
        else:
            decision = INSUFFICIENT_EVIDENCE
            label = EvidenceLabel.HYPOTHESIS
            reasons.append(f"{arm_label} did not beat identity on this scale development corpus")
        if transformed_wm == 0:
            reasons.append("raw transformed watermarked detections are 0 on this corpus")
        if cf_wm == transformed_wm:
            reasons.append("Cf-strip detections match raw transformed detections")
        if nfkc_wm == transformed_wm and collapse_wm == transformed_wm:
            reasons.append("NFKC and whitespace-collapse detections match raw transformed detections")
        if nfkc_cf_wm == transformed_wm and combined_wm == transformed_wm:
            reasons.append("combined sanitizer detections match raw transformed detections")
    payload = {
        "algorithm_version": CYCLE8_SCALE_DECISION_VERSION,
        "decision": decision,
        "product_gate": gate.value,
        "evidence_label": label.value,
        "visible_failures": visible_failures,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "identity_raw_watermarked_detected": identity_wm,
        "u034f_raw_watermarked_detected": transformed_wm,
        "u034f_raw_unwatermarked_detected": transformed_uw,
        "u034f_cf_strip_watermarked_detected": cf_wm,
        "u034f_nfkc_watermarked_detected": nfkc_wm,
        "u034f_ws_collapse_watermarked_detected": collapse_wm,
        "u034f_nfkc_cf_strip_watermarked_detected": nfkc_cf_wm,
        "u034f_ws_collapse_nfkc_cf_strip_watermarked_detected": combined_wm,
        "transformed_arm_id": transformed_arm_id,
        "reasons": tuple(reasons),
        "notes": (
            "This is Cycle 8 scale development classification, not confirmation. "
            "U+034F is not product-authorized. Do not inspect 830000, 840000, or 850000. "
            "Seed 880000 is PUBLICLY_EXPOSED by PR #98. Do not generate 950000 yet."
        ),
    }
    return payload
