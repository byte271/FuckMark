from __future__ import annotations

import json
from pathlib import Path

from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from .compare import CYCLE8_IDENTITY_ARM_ID, CYCLE8_LETTER_ALT_ARM_ID, CYCLE8_U034F_LETTER_ARM_ID
from .mix_freeze import CYCLE8_MIX_FREEZE_VERSION


CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION = "cycle8-mix-confirmation-scorecard-v1"
_CORPORA = (
    (830000, "evidence/cycle8-mix-confirmation-830000-n64-2026-08-26/detector-compare.json", "b237512f7250b50bfb87c5f2aec60a01689e185533028ac73c3f7ee1201e02eb"),
    (840000, "evidence/cycle8-mix-confirmation-840000-n64-2026-08-26/detector-compare.json", "5fef030650a75b371708b88dee328391db4649ab3bc4f832e30704625582e4b0"),
    (850000, "evidence/cycle8-mix-confirmation-850000-n64-2026-08-26/detector-compare.json", "25b7519c4eba50f0094b5314fe0f8d9b9086b1abb5cb78e2ee24c12a0b9a8b6a"),
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_mix_confirmation_scorecard() -> dict[str, object]:
    artifacts = []
    mix_wm = 0
    mix_uw = 0
    letter_wm = 0
    letter_uw = 0
    identity_wm = 0
    identity_uw = 0
    mix_max = None
    letter_max = None
    visible_wm = 0
    visible_wm_total = 0
    sanitizer_wm = {
        "nfc": 0,
        "cf_strip": 0,
        "nfkc": 0,
        "ws_collapse": 0,
        "nfkc_cf_strip": 0,
        "ws_collapse_nfkc_cf_strip": 0,
    }
    for seed_base, relative, expected_hash in _CORPORA:
        artifact = _load(Path(relative))
        if artifact["artifact_hash"] != expected_hash:
            raise ValueError("mix confirmation artifact hash mismatch")
        mix = artifact["summaries"][CYCLE8_LETTER_ALT_ARM_ID]
        letter = artifact["summaries"][CYCLE8_U034F_LETTER_ARM_ID]
        identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
        mix_wm += int(mix["raw_watermarked_detected"])
        mix_uw += int(mix["raw_unwatermarked_detected"])
        letter_wm += int(letter["raw_watermarked_detected"])
        letter_uw += int(letter["raw_unwatermarked_detected"])
        identity_wm += int(identity["raw_watermarked_detected"])
        identity_uw += int(identity["raw_unwatermarked_detected"])
        mix_score = float(mix["raw_watermarked_max_score"])
        letter_score = float(letter["raw_watermarked_max_score"])
        mix_max = mix_score if mix_max is None else max(mix_max, mix_score)
        letter_max = letter_score if letter_max is None else max(letter_max, letter_score)
        for row in artifact["scored_rows"]:
            if row["arm_id"] != CYCLE8_LETTER_ALT_ARM_ID or row["label"] != "watermarked":
                continue
            visible_wm_total += 1
            visible_wm += int(bool(row["geometry"]["visible_ok"]))
        sanitizer_wm["nfc"] += int(mix["nfc_watermarked_detected"])
        sanitizer_wm["cf_strip"] += int(mix["cf_strip_watermarked_detected"])
        sanitizer_wm["nfkc"] += int(mix["nfkc_watermarked_detected"])
        sanitizer_wm["ws_collapse"] += int(mix["ws_collapse_watermarked_detected"])
        sanitizer_wm["nfkc_cf_strip"] += int(mix["nfkc_cf_strip_watermarked_detected"])
        sanitizer_wm["ws_collapse_nfkc_cf_strip"] += int(mix["ws_collapse_nfkc_cf_strip_watermarked_detected"])
        artifacts.append(
            {
                "seed_base": seed_base,
                "path": relative,
                "artifact_hash": expected_hash,
                "topic": artifact["topic"],
                "mix_raw_watermarked_detected": int(mix["raw_watermarked_detected"]),
                "mix_raw_unwatermarked_detected": int(mix["raw_unwatermarked_detected"]),
                "mix_max_score": mix_score,
                "letter_raw_watermarked_detected": int(letter["raw_watermarked_detected"]),
                "identity_raw_watermarked_detected": int(identity["raw_watermarked_detected"]),
                "visible_pass_count": int(mix["visible_pass_count"]),
            }
        )
    payload = {
        "algorithm_version": CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION,
        "freeze_version": CYCLE8_MIX_FREEZE_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "confirmation": True,
        "run_once": True,
        "rerun_looking_for_zero": False,
        "freeze": True,
        "product_authorized": False,
        "release_registry_empty": True,
        "evidence_label": "VERIFIED",
        "threshold": CYCLE6_THRESHOLD,
        "effectiveness": {
            "transformed_wm": {
                "rate": f"{mix_wm}/192",
                "raw_watermarked_detected": mix_wm,
                "max_score": mix_max,
                "min_gap_below_threshold": CYCLE6_THRESHOLD - float(mix_max),
            },
            "transformed_uw": {
                "rate": f"{mix_uw}/192",
                "raw_unwatermarked_detected": mix_uw,
            },
            "letter_x1_same_corpora": {
                "rate": f"{letter_wm}/192",
                "raw_watermarked_detected": letter_wm,
                "raw_unwatermarked_detected": letter_uw,
                "max_score": letter_max,
            },
            "identity": {
                "raw_watermarked_detected": identity_wm,
                "raw_unwatermarked_detected": identity_uw,
            },
        },
        "visibility": {
            "watermarked_pass_rate": f"{visible_wm}/{visible_wm_total}",
        },
        "durability": {
            "sanitizer_watermarked_detected": sanitizer_wm,
            "frozen_sanitizers_match_raw": all(value == mix_wm for value in sanitizer_wm.values()),
        },
        "corpora": artifacts,
        "do_not_generate_950000": True,
        "notes": (
            "One-shot formal confirmation of cycle8-mix-freeze-v1. "
            "Do not rerun looking for zero. Do not retune on these corpora. "
            "Public CLI remains empty."
        ),
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}
