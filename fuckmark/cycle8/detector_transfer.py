from __future__ import annotations

import json
from pathlib import Path

from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from .compare import CYCLE8_LETTER_ALT_ARM_ID
from .mix_confirmation import CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
from .mix_freeze import CYCLE8_MIX_FREEZE_VERSION


CYCLE8_MIX_DETECTOR_TRANSFER_VERSION = "cycle8-mix-mean-transfer-v1"
CYCLE8_MIX_DETECTOR_TRANSFER_PATH = "evidence/cycle8-mix-mean-transfer-2026-08-26/scorecard.json"
CYCLE8_MIX_DETECTOR_TRANSFER_HASH = "1b13209f53dcb18e1e93938f22c39bcb510eb4292c1d841db6fbe51052d8e620"
_CORPORA = (
    (830000, "evidence/cycle8-mix-confirmation-830000-n64-2026-08-26/detector-compare.json"),
    (840000, "evidence/cycle8-mix-confirmation-840000-n64-2026-08-26/detector-compare.json"),
    (850000, "evidence/cycle8-mix-confirmation-850000-n64-2026-08-26/detector-compare.json"),
)


def confirmation_source_paths() -> tuple[tuple[int, str], ...]:
    return _CORPORA


def build_mix_mean_transfer_scorecard(rows: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("transfer rows must be a non-empty list")
    mix_wm_mean = 0
    mix_wm_weighted = 0
    mix_uw_mean = 0
    mix_uw_weighted = 0
    identity_wm_mean = 0
    identity_wm_weighted = 0
    identity_uw_mean = 0
    identity_uw_weighted = 0
    mix_wm_n = 0
    mix_uw_n = 0
    identity_wm_n = 0
    identity_uw_n = 0
    mix_wm_max_mean = None
    mix_wm_max_weighted = None
    compact = []
    for row in rows:
        label = str(row["label"])
        identity = row["identity"]
        mix = row["mix"]
        if label == "watermarked":
            mix_wm_n += 1
            identity_wm_n += 1
            mix_wm_mean += int(bool(mix["mean_detected"]))
            mix_wm_weighted += int(bool(mix["weighted_mean_detected"]))
            identity_wm_mean += int(bool(identity["mean_detected"]))
            identity_wm_weighted += int(bool(identity["weighted_mean_detected"]))
            mix_score = float(mix["mean_score"])
            weighted_score = float(mix["weighted_mean_score"])
            mix_wm_max_mean = mix_score if mix_wm_max_mean is None else max(mix_wm_max_mean, mix_score)
            mix_wm_max_weighted = (
                weighted_score if mix_wm_max_weighted is None else max(mix_wm_max_weighted, weighted_score)
            )
        elif label == "unwatermarked":
            mix_uw_n += 1
            identity_uw_n += 1
            mix_uw_mean += int(bool(mix["mean_detected"]))
            mix_uw_weighted += int(bool(mix["weighted_mean_detected"]))
            identity_uw_mean += int(bool(identity["mean_detected"]))
            identity_uw_weighted += int(bool(identity["weighted_mean_detected"]))
        else:
            raise ValueError("unknown transfer label")
        compact.append(
            {
                "sample_id": row["sample_id"],
                "seed_base": row["seed_base"],
                "label": label,
                "domain": row["domain"],
                "source_sha256": row["source_sha256"],
                "identity": {
                    "mean_score": identity["mean_score"],
                    "weighted_mean_score": identity["weighted_mean_score"],
                    "mean_detected": identity["mean_detected"],
                    "weighted_mean_detected": identity["weighted_mean_detected"],
                },
                "mix": {
                    "mean_score": mix["mean_score"],
                    "weighted_mean_score": mix["weighted_mean_score"],
                    "mean_detected": mix["mean_detected"],
                    "weighted_mean_detected": mix["weighted_mean_detected"],
                    "text_sha256": mix["text_sha256"],
                },
            }
        )
    payload = {
        "algorithm_version": CYCLE8_MIX_DETECTOR_TRANSFER_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "freeze_version": CYCLE8_MIX_FREEZE_VERSION,
        "confirmation_scorecard_version": CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION,
        "product_authorized": False,
        "confirmation_rewritten": False,
        "threshold": CYCLE6_THRESHOLD,
        "model": "openai-community/gpt2",
        "adapter": "HuggingFaceSynthIDAdapter",
        "families": ["mean", "weighted_mean"],
        "second_model": False,
        "evidence_label": "HYPOTHESIS",
        "scope": (
            "Same frozen mix apply on spent confirmation source texts. "
            "Mean versus Weighted Mean on one Hugging Face GPT-2 SynthID observation adapter. "
            "Not a second model. Not proprietary-detector transfer."
        ),
        "effectiveness": {
            "mix_mean_wm": {"detected": mix_wm_mean, "n": mix_wm_n, "rate": f"{mix_wm_mean}/{mix_wm_n}"},
            "mix_weighted_mean_wm": {
                "detected": mix_wm_weighted,
                "n": mix_wm_n,
                "rate": f"{mix_wm_weighted}/{mix_wm_n}",
            },
            "mix_mean_uw": {"detected": mix_uw_mean, "n": mix_uw_n, "rate": f"{mix_uw_mean}/{mix_uw_n}"},
            "mix_weighted_mean_uw": {
                "detected": mix_uw_weighted,
                "n": mix_uw_n,
                "rate": f"{mix_uw_weighted}/{mix_uw_n}",
            },
            "identity_mean_wm": {
                "detected": identity_wm_mean,
                "n": identity_wm_n,
                "rate": f"{identity_wm_mean}/{identity_wm_n}",
            },
            "identity_weighted_mean_wm": {
                "detected": identity_wm_weighted,
                "n": identity_wm_n,
                "rate": f"{identity_wm_weighted}/{identity_wm_n}",
            },
            "identity_mean_uw": {
                "detected": identity_uw_mean,
                "n": identity_uw_n,
                "rate": f"{identity_uw_mean}/{identity_uw_n}",
            },
            "identity_weighted_mean_uw": {
                "detected": identity_uw_weighted,
                "n": identity_uw_n,
                "rate": f"{identity_uw_weighted}/{identity_uw_n}",
            },
            "mix_mean_wm_max_score": mix_wm_max_mean,
            "mix_weighted_mean_wm_max_score": mix_wm_max_weighted,
        },
        "rows": compact,
        "do_not_generate_950000": True,
        "do_not_rerun_looking_for_zero": True,
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}


def load_mix_mean_transfer_scorecard(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_DETECTOR_TRANSFER_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def try_load_mix_mean_transfer_scorecard(path: str | Path | None = None) -> dict[str, object] | None:
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_DETECTOR_TRANSFER_PATH)
    if not destination.is_file():
        return None
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_mix_mean_transfer_committed() -> None:
    path = Path(CYCLE8_MIX_DETECTOR_TRANSFER_PATH)
    if not path.is_file():
        raise ValueError("mix mean transfer scorecard is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    digest = sha256_json(body)
    if disk.get("scorecard_hash") != digest:
        raise ValueError("mix mean transfer scorecard hash mismatch")
    if CYCLE8_MIX_DETECTOR_TRANSFER_HASH != "0" * 64 and digest != CYCLE8_MIX_DETECTOR_TRANSFER_HASH:
        raise ValueError("mix mean transfer scorecard hash is not the frozen digest")
    if disk.get("confirmation_rewritten") is True:
        raise ValueError("mean transfer must not rewrite confirmation")
    if disk.get("product_authorized") is True:
        raise ValueError("mean transfer must not product-authorize mix")
    if disk.get("second_model") is True:
        raise ValueError("mean transfer must not claim a second model")
    if disk.get("evidence_label") != "HYPOTHESIS":
        raise ValueError("mean transfer must remain HYPOTHESIS")
    effectiveness = disk["effectiveness"]
    if effectiveness["mix_weighted_mean_wm"]["rate"] != "0/192":
        raise ValueError("mean transfer weighted-mean mix WM is not 0/192")
    if effectiveness["mix_mean_wm"]["n"] != 192:
        raise ValueError("mean transfer mix WM n is not 192")
