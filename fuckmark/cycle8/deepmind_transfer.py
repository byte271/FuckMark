from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from .compare import CYCLE8_LETTER_ALT_ARM_ID
from .mix_freeze import CYCLE8_MIX_FREEZE_VERSION


CYCLE8_MIX_DEEPMIND_TRANSFER_VERSION = "cycle8-mix-deepmind-30key-transfer-v1"
CYCLE8_MIX_DEEPMIND_TRANSFER_PATH = "evidence/cycle8-mix-deepmind-transfer-2026-08-27/scorecard.json"
CYCLE8_MIX_DEEPMIND_TRANSFER_HASH = "ed61939e164e4c39277bf385961a95eb239178db84e63959f72948fab7df25e5"
CYCLE8_MIX_DEEPMIND_920000_PATH = "evidence/cycle8-mix-deepmind-30key-920000-n16-2026-08-27/scorecard.json"
CYCLE8_MIX_DEEPMIND_920000_HASH = "ee521a04ab6017134e7aa2b48f07da0612c188f8bf2b353611f33f33a4cbb7bf"
_CORPORA = (
    (1060000, "evidence/cycle8-mix-deepmind-1060000-n64-2026-08-27/scorecard.json", "2c828e6076005b5aa1b94aad145b20a8748766134fea62c2690202a7ded36e52"),
    (1070000, "evidence/cycle8-mix-deepmind-1070000-n64-2026-08-27/scorecard.json", "b05e9e80e41fe8487769bdb2908642d59bc2e753746f02dcd05d8f956fb5cb92"),
    (1080000, "evidence/cycle8-mix-deepmind-1080000-n64-2026-08-27/scorecard.json", "d97f005332d45b93be3588e413055d7ff0035b234f1b4213d3db9e83f85df4d0"),
)


def development_source_path() -> str:
    return CYCLE8_MIX_DEEPMIND_920000_PATH


def transfer_corpus_paths() -> tuple[tuple[int, str, str], ...]:
    return _CORPORA


def load_deepmind_scorecard(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def try_load_mix_deepmind_transfer_scorecard(path: str | Path | None = None) -> dict[str, object] | None:
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_DEEPMIND_TRANSFER_PATH)
    if not destination.is_file():
        return None
    return json.loads(destination.read_text(encoding="utf-8"))


def build_mix_deepmind_transfer_scorecard(artifacts: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise ValueError("DeepMind transfer requires three corpus scorecards")
    identity_wm = mix_wm = identity_uw = mix_uw = 0
    n_wm = n_uw = 0
    mix_wm_max = None
    visible_pass = True
    compact = []
    for artifact in artifacts:
        body = {key: value for key, value in artifact.items() if key != "scorecard_hash"}
        digest = sha256_json(body)
        if artifact.get("scorecard_hash") != digest:
            raise ValueError("DeepMind corpus scorecard hash mismatch")
        if artifact.get("product_authorized") is True:
            raise ValueError("DeepMind transfer must not product-authorize mix")
        if artifact.get("confirmation_rewritten") is True:
            raise ValueError("DeepMind transfer must not rewrite confirmation")
        if artifact.get("second_model") is True:
            raise ValueError("DeepMind transfer must not claim a second model")
        if artifact.get("keys_depth") != 30:
            raise ValueError("DeepMind transfer must use 30 keys")
        effectiveness = artifact["effectiveness"]
        identity_wm += int(effectiveness["identity_wm"]["detected"])
        mix_wm += int(effectiveness["mix_wm"]["detected"])
        identity_uw += int(effectiveness["identity_uw"]["detected"])
        mix_uw += int(effectiveness["mix_uw"]["detected"])
        n_wm += int(effectiveness["identity_wm"]["n"])
        n_uw += int(effectiveness["identity_uw"]["n"])
        score = float(effectiveness["mix_wm_max_score"])
        mix_wm_max = score if mix_wm_max is None else max(mix_wm_max, score)
        visible_pass = visible_pass and bool(artifact["visible_pass"])
        compact.append(
            {
                "seed_base": artifact["seed_base"],
                "topic": artifact["topic"],
                "scorecard_hash": digest,
                "effectiveness": effectiveness,
                "visible_pass": artifact["visible_pass"],
            }
        )
    payload = {
        "algorithm_version": CYCLE8_MIX_DEEPMIND_TRANSFER_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "freeze_version": CYCLE8_MIX_FREEZE_VERSION,
        "product_authorized": False,
        "confirmation_rewritten": False,
        "mix_freeze_confirmation": False,
        "threshold": CYCLE6_THRESHOLD,
        "model": "openai-community/gpt2",
        "generation": "synthid_text.SynthIDGPT2LMHeadModel",
        "detector": "synthid_text.logits_processing.SynthIDLogitsProcessor",
        "keys_depth": 30,
        "second_model": False,
        "second_configuration": True,
        "evidence_label": "HYPOTHESIS",
        "scope": (
            "Independent Google synthid-text 30-key mixin generation and official logits processor "
            "on GPT-2. Not the Hugging Face nine-key adapter. Not a second model. "
            "Not mix-freeze confirmation rewrite."
        ),
        "effectiveness": {
            "identity_wm": {"detected": identity_wm, "n": n_wm, "rate": f"{identity_wm}/{n_wm}"},
            "mix_wm": {"detected": mix_wm, "n": n_wm, "rate": f"{mix_wm}/{n_wm}"},
            "identity_uw": {"detected": identity_uw, "n": n_uw, "rate": f"{identity_uw}/{n_uw}"},
            "mix_uw": {"detected": mix_uw, "n": n_uw, "rate": f"{mix_uw}/{n_uw}"},
            "mix_wm_max_score": mix_wm_max,
        },
        "visible_pass": visible_pass,
        "corpora": compact,
        "exploratory_920000_n16_hash": CYCLE8_MIX_DEEPMIND_920000_HASH,
        "do_not_generate_950000": True,
        "do_not_rerun_looking_for_zero": True,
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}


def write_mix_deepmind_transfer_scorecard(path: str | Path | None = None) -> Path:
    artifacts = [load_deepmind_scorecard(relative) for _seed, relative, _digest in _CORPORA]
    payload = build_mix_deepmind_transfer_scorecard(artifacts)
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_DEEPMIND_TRANSFER_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def assert_mix_deepmind_transfer_committed() -> None:
    path = Path(CYCLE8_MIX_DEEPMIND_TRANSFER_PATH)
    if not path.is_file():
        raise ValueError("mix DeepMind transfer scorecard is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "scorecard_hash"}
    digest = sha256_json(body)
    if disk.get("scorecard_hash") != digest:
        raise ValueError("mix DeepMind transfer scorecard hash mismatch")
    if CYCLE8_MIX_DEEPMIND_TRANSFER_HASH != "0" * 64 and digest != CYCLE8_MIX_DEEPMIND_TRANSFER_HASH:
        raise ValueError("mix DeepMind transfer scorecard hash is not the frozen digest")
    if disk.get("confirmation_rewritten") is True:
        raise ValueError("DeepMind transfer must not rewrite confirmation")
    if disk.get("product_authorized") is True:
        raise ValueError("DeepMind transfer must not product-authorize mix")
    if disk.get("second_model") is True:
        raise ValueError("DeepMind transfer must not claim a second model")
    if disk.get("mix_freeze_confirmation") is True:
        raise ValueError("DeepMind transfer must not claim mix-freeze confirmation")
    if disk.get("evidence_label") != "HYPOTHESIS":
        raise ValueError("DeepMind transfer must remain HYPOTHESIS")
    if disk.get("keys_depth") != 30:
        raise ValueError("DeepMind transfer must use 30 keys")
    exploratory = load_deepmind_scorecard(CYCLE8_MIX_DEEPMIND_920000_PATH)
    exploratory_body = {key: value for key, value in exploratory.items() if key != "scorecard_hash"}
    if sha256_json(exploratory_body) != CYCLE8_MIX_DEEPMIND_920000_HASH:
        raise ValueError("DeepMind 920000 n=16 scorecard hash mismatch")
    for seed_base, relative, expected in _CORPORA:
        artifact = load_deepmind_scorecard(relative)
        body = {key: value for key, value in artifact.items() if key != "scorecard_hash"}
        digest = sha256_json(body)
        if expected != "0" * 64 and digest != expected:
            raise ValueError("DeepMind corpus scorecard hash is not the frozen digest")
        if int(artifact["seed_base"]) != seed_base:
            raise ValueError("DeepMind corpus seed_base mismatch")
        if artifact.get("scorecard_hash") != digest:
            raise ValueError("DeepMind corpus scorecard hash mismatch")
