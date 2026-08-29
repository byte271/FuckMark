from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from .letter_mix import LETTER_MIX_MECHANISM_ID


CYCLE8_COMBO_STRESS_N192_VERSION = "cycle8-combo-stress-exploratory-n192-v1"
CYCLE8_COMBO_STRESS_N192_PATH = "evidence/cycle8-combo-stress-exploratory-n192-2026-08-28/scorecard.json"
CYCLE8_COMBO_STRESS_N192_HASH = "140fc0e33ab45579d7e7c7561a69f65a32f05763377482751fe912873b35e86d"
CYCLE8_DISTIL_COMBO_STRESS_PATH = "evidence/cycle8-distilgpt2-combo-stress-exploratory-2026-08-28/scorecard.json"
CYCLE8_DISTIL_COMBO_STRESS_HASH = "3b0d11a3ae783ca0af34ac2c6bba969528c9ec07ed33bc4bf1cb0ae7f087b2ff"
LIVE_TRIPLE_ARMS = (
    "triple_raw",
    "triple_mn_strip",
    "triple_di_strip",
    "triple_us",
    "triple_mn_us",
    "triple_di_us",
    "triple_us_mn",
    "triple_bundle",
    "triple_bundle_us",
)
HISTORICAL_ARMS = (
    "identity",
    "historical_mark_mn_us",
    "historical_dual_mn_us",
)
COMBO_STRESS_ARMS = HISTORICAL_ARMS + LIVE_TRIPLE_ARMS
_CORPORA = (
    (
        1200000,
        "evidence/cycle8-combo-stress-exploratory-2026-08-28/scorecard.json",
        "3a23b5c4e25af052440c8761b5e7f24a7d8c4133393b503817ac01473481032a",
    ),
    (
        1210000,
        "evidence/cycle8-combo-stress-exploratory-1210000-n64-2026-08-28/scorecard.json",
        "45400cd01ab94ea70959f58448a478519609831b3873ca65ec7bdff4ae46b3d3",
    ),
    (
        1220000,
        "evidence/cycle8-combo-stress-exploratory-1220000-n64-2026-08-28/scorecard.json",
        "98469a54e7feaf0b7781e39f9b3bc28fd52208a217d0ca3df1ab94ca7ec34b99",
    ),
)


def combo_stress_corpus_paths() -> tuple[tuple[int, str, str], ...]:
    return _CORPORA


def load_combo_stress_scorecard(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _scorecard_body_hash(artifact: dict[str, object]) -> str:
    body = {key: value for key, value in artifact.items() if key != "scorecard_hash"}
    return sha256_json(body)


def build_combo_stress_n192_scorecard(artifacts: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise ValueError("combo stress n=192 requires three corpus scorecards")
    totals = {
        arm: {"detected": 0, "n": 0, "restores_source": 0} for arm in COMBO_STRESS_ARMS
    }
    compact = []
    for artifact in artifacts:
        digest = _scorecard_body_hash(artifact)
        if artifact.get("scorecard_hash") != digest:
            raise ValueError("combo stress corpus scorecard hash mismatch")
        if artifact.get("confirmation_rewritten") is True:
            raise ValueError("combo stress must not rewrite confirmation")
        if artifact.get("mechanism_id") != LETTER_MIX_MECHANISM_ID:
            raise ValueError("combo stress must use live triple-layer mechanism")
        if artifact.get("role") != "exploratory_rescore_of_frozen_sources":
            raise ValueError("combo stress must remain an exploratory rescore")
        effectiveness = artifact["effectiveness"]
        for arm in COMBO_STRESS_ARMS:
            row = effectiveness[arm]
            totals[arm]["detected"] += int(row["detected"])
            totals[arm]["n"] += int(artifact["watermarked_rows"])
            totals[arm]["restores_source"] += int(row["restores_source"])
        compact.append(
            {
                "seed_base": artifact["seed_base"],
                "scorecard_hash": digest,
                "watermarked_rows": artifact["watermarked_rows"],
                "effectiveness": {
                    arm: {
                        "detected": int(effectiveness[arm]["detected"]),
                        "rate": effectiveness[arm]["rate"],
                        "restores_source": int(effectiveness[arm]["restores_source"]),
                    }
                    for arm in COMBO_STRESS_ARMS
                },
            }
        )
    payload = {
        "algorithm_version": CYCLE8_COMBO_STRESS_N192_VERSION,
        "role": "exploratory_rescore_of_frozen_sources",
        "confirmation_rewritten": False,
        "spent_confirmation_corpora_not_reused_for_generation": True,
        "mechanism_id": LETTER_MIX_MECHANISM_ID,
        "watermarked_rows": 192,
        "threshold": CYCLE6_THRESHOLD,
        "detector": "huggingface-synthid-weighted-mean-gpt2",
        "evidence_label": "HYPOTHESIS",
        "scope": (
            "Exploratory GPT-2 / SynthID rescore of frozen Gate v2 confirmation watermarked sources "
            "from seeds 1200000, 1210000, and 1220000. Confirmation artifacts were not rewritten."
        ),
        "effectiveness": {
            arm: {
                "detected": totals[arm]["detected"],
                "n": totals[arm]["n"],
                "rate": f"{totals[arm]['detected']}/{totals[arm]['n']}",
                "restores_source": totals[arm]["restores_source"],
            }
            for arm in COMBO_STRESS_ARMS
        },
        "corpora": compact,
        "do_not_generate_950000": True,
        "do_not_rerun_looking_for_zero": True,
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}


def write_combo_stress_n192_scorecard(path: str | Path | None = None) -> Path:
    artifacts = [load_combo_stress_scorecard(relative) for _seed, relative, _digest in _CORPORA]
    payload = build_combo_stress_n192_scorecard(artifacts)
    destination = Path(path) if path is not None else Path(CYCLE8_COMBO_STRESS_N192_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def assert_combo_stress_n192_committed() -> None:
    path = Path(CYCLE8_COMBO_STRESS_N192_PATH)
    if not path.is_file():
        raise ValueError("combo stress n=192 scorecard is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    digest = sha256_json(body)
    if disk.get("scorecard_hash") != digest:
        raise ValueError("combo stress n=192 scorecard hash mismatch")
    if CYCLE8_COMBO_STRESS_N192_HASH != "0" * 64 and digest != CYCLE8_COMBO_STRESS_N192_HASH:
        raise ValueError("combo stress n=192 scorecard hash is not the frozen digest")
    if disk.get("confirmation_rewritten") is True:
        raise ValueError("combo stress must not rewrite confirmation")
    if disk.get("evidence_label") != "HYPOTHESIS":
        raise ValueError("combo stress must remain HYPOTHESIS")
    effectiveness = disk["effectiveness"]
    if effectiveness["identity"]["rate"] != "188/192":
        raise ValueError("combo stress identity must remain 188/192")
    for arm in LIVE_TRIPLE_ARMS:
        if effectiveness[arm]["rate"] != "0/192":
            raise ValueError(f"live triple-layer {arm} must stay 0/192")
        if int(effectiveness[arm]["restores_source"]) != 0:
            raise ValueError(f"live triple-layer {arm} must not restore source")
    if int(effectiveness["historical_dual_mn_us"]["detected"]) < 180:
        raise ValueError("historical dual-layer Mn then UnicodeSanitizer must remain detected")
    if int(effectiveness["historical_mark_mn_us"]["detected"]) < 180:
        raise ValueError("historical mark-only Mn then UnicodeSanitizer must remain detected")
    for seed_base, relative, expected in _CORPORA:
        artifact = load_combo_stress_scorecard(relative)
        corpus_digest = _scorecard_body_hash(artifact)
        if artifact.get("scorecard_hash") != corpus_digest or corpus_digest != expected:
            raise ValueError(f"combo stress corpus {seed_base} hash mismatch")
        if artifact.get("confirmation_rewritten") is True:
            raise ValueError("combo stress corpus must not rewrite confirmation")
        live = artifact["effectiveness"]
        for arm in LIVE_TRIPLE_ARMS:
            if live[arm]["rate"] != "0/64":
                raise ValueError(f"live triple-layer {arm} on {seed_base} must stay 0/64")


def assert_distil_combo_stress_committed() -> None:
    path = Path(CYCLE8_DISTIL_COMBO_STRESS_PATH)
    if not path.is_file():
        raise ValueError("DistilGPT2 combo stress scorecard is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    digest = sha256_json(body)
    if disk.get("scorecard_hash") != digest or digest != CYCLE8_DISTIL_COMBO_STRESS_HASH:
        raise ValueError("DistilGPT2 combo stress scorecard hash mismatch")
    if disk.get("confirmation_rewritten") is True:
        raise ValueError("DistilGPT2 combo stress must not rewrite confirmation")
    if disk.get("frozen_second_model_scorecard_not_rewritten") is not True:
        raise ValueError("DistilGPT2 combo stress must not rewrite the frozen second-model scorecard")
    if disk.get("evidence_label") != "HYPOTHESIS":
        raise ValueError("DistilGPT2 combo stress must remain HYPOTHESIS")
    effectiveness = disk["effectiveness"]
    if effectiveness["identity"]["rate"] != "16/16":
        raise ValueError("DistilGPT2 combo stress identity must remain 16/16")
    if effectiveness["historical_dual_mn_us"]["rate"] != "16/16":
        raise ValueError("DistilGPT2 historical dual-layer Mn then UnicodeSanitizer must remain 16/16")
    for arm in ("triple_raw", "triple_mn_us", "triple_di_us", "triple_bundle_us"):
        if effectiveness[arm]["rate"] != "0/16":
            raise ValueError(f"DistilGPT2 live triple-layer {arm} must stay 0/16")
        if int(effectiveness[arm]["restores_source"]) != 0:
            raise ValueError(f"DistilGPT2 live triple-layer {arm} must not restore source")
