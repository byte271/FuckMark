from __future__ import annotations

import json
from pathlib import Path

from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from .compare import CYCLE8_LETTER_ALT_ARM_ID
from .mix_freeze import CYCLE8_MIX_FREEZE_VERSION


CYCLE8_MIX_SECOND_MODEL_TRANSFER_VERSION = "cycle8-mix-second-model-transfer-v1"
CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH = "evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/scorecard.json"
CYCLE8_MIX_SECOND_MODEL_TRANSFER_HASH = "1f6c9a6af58e9dd547940a393c7e4115713d6333ab4d5162ad382bf5a91d5156"
CYCLE8_MIX_SECOND_MODEL_ID = "distilbert/distilgpt2"
CYCLE8_MIX_SECOND_MODEL_REVISION = "2290a62682d06624634c1f46a6ad5be0f47f38aa"


def try_load_mix_second_model_transfer_scorecard(path: str | Path | None = None) -> dict[str, object] | None:
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH)
    if not destination.is_file():
        return None
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_mix_second_model_transfer_committed() -> None:
    path = Path(CYCLE8_MIX_SECOND_MODEL_TRANSFER_PATH)
    if not path.is_file():
        raise ValueError("mix second-model transfer scorecard is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    digest = sha256_json(body)
    if disk.get("scorecard_hash") != digest:
        raise ValueError("mix second-model transfer scorecard hash mismatch")
    if CYCLE8_MIX_SECOND_MODEL_TRANSFER_HASH != "0" * 64 and digest != CYCLE8_MIX_SECOND_MODEL_TRANSFER_HASH:
        raise ValueError("mix second-model transfer scorecard hash is not the frozen digest")
    if disk.get("algorithm_version") != CYCLE8_MIX_SECOND_MODEL_TRANSFER_VERSION:
        raise ValueError("mix second-model transfer algorithm version mismatch")
    if disk.get("mechanism_id") not in {None, CYCLE8_LETTER_ALT_ARM_ID}:
        raise ValueError("mix second-model transfer mechanism mismatch")
    if disk.get("freeze_version") not in {None, CYCLE8_MIX_FREEZE_VERSION}:
        raise ValueError("mix second-model transfer freeze version mismatch")
    if disk.get("confirmation_rewritten") is True:
        raise ValueError("second-model transfer must not rewrite confirmation")
    if disk.get("product_authorized") is True:
        raise ValueError("second-model transfer must not product-authorize mix")
    if disk.get("mix_freeze_confirmation") is True:
        raise ValueError("second-model transfer must not claim mix-freeze confirmation")
    if disk.get("second_model") is not True:
        raise ValueError("second-model transfer must claim a second model")
    if disk.get("second_configuration") is True:
        raise ValueError("second-model transfer must not claim a second configuration")
    if disk.get("evidence_label") != "HYPOTHESIS":
        raise ValueError("second-model transfer must remain HYPOTHESIS")
    if disk.get("model") != CYCLE8_MIX_SECOND_MODEL_ID:
        raise ValueError("second-model transfer must use DistilGPT2")
    if disk.get("model_revision") != CYCLE8_MIX_SECOND_MODEL_REVISION:
        raise ValueError("second-model transfer model revision mismatch")
    if int(disk.get("tokenizer_vocab_size") or 0) != 50257:
        raise ValueError("second-model transfer tokenizer vocab mismatch")
    if int(disk.get("pair_count") or 0) != 16:
        raise ValueError("second-model transfer must stay n=16")
    if int(disk.get("seed_base") or 0) != 1090000:
        raise ValueError("second-model transfer seed_base mismatch")
    if disk.get("keys_depth") != 30:
        raise ValueError("second-model transfer must use 30 keys")
    if float(disk.get("threshold") or 0) != CYCLE6_THRESHOLD:
        raise ValueError("second-model transfer threshold mismatch")
    effectiveness = disk["effectiveness"]
    if effectiveness["identity_wm"]["rate"] != "16/16":
        raise ValueError("second-model identity WM rate mismatch")
    if effectiveness["mix_wm"]["rate"] != "0/16":
        raise ValueError("second-model mix WM rate mismatch")
    if effectiveness["identity_uw"]["rate"] != "0/16":
        raise ValueError("second-model identity UW rate mismatch")
    if effectiveness["mix_uw"]["rate"] != "0/16":
        raise ValueError("second-model mix UW rate mismatch")
    if float(effectiveness["mix_wm_max_score"]) != 0.5047997827277791:
        raise ValueError("second-model mix max score mismatch")
    if disk.get("visible_pass") is not True:
        raise ValueError("second-model visible projection must pass")
