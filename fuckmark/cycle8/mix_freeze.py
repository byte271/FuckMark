from __future__ import annotations

import json
from pathlib import Path

from .._validation import require_int
from ..cli import process_text
from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_file, sha256_json
from ..seeds.ledger import (
    CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES,
    CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
    CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
    row_for_seed_base,
)
from ..transforms.registry import release_transform_registry
from .compare import CYCLE8_LETTER_ALT_ARM_ID, CYCLE8_MIX_ARM_IDS
from .letter_mix import LETTER_MIX_APPROVED_CARRIERS, LETTER_MIX_MAX_SELECTED, LETTER_MIX_PAYLOADS
from .sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS


CYCLE8_MIX_FREEZE_VERSION = "cycle8-mix-freeze-v1"
CYCLE8_MIX_FREEZE_PATH = "specs/cycle8/fuckmark-cycle8-mix-freeze-v1.json"
CYCLE8_MIX_CONFIRMATION_DETECTOR_VERSION = "cycle8-mix-confirmation-detector-compare-v1"
CYCLE8_MIX_CONFIRMATION_PAIR_COUNT = 64
_LETTER_MIX_PATH = Path(__file__).resolve().parent / "letter_mix.py"
_DEVELOPMENT_ARTIFACTS = (
    ("1020000", "evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json", "2538c614a73bed360cdeebdaa60c0fa36ad34cf6995c76a120d49bd1da063ce2"),
    ("1030000", "evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json", "142809783554a890cfd68b80b560295605e068b8e0deede8ea81e3e75358eb95"),
    ("1040000", "evidence/cycle8-mix-1040000-n64-2026-08-26/detector-compare.json", "46ddefff3200de9d45c919761d3cb4f842b1ffa7f5404542b0aed571cfbbdf7b"),
    ("1050000", "evidence/cycle8-mix-1050000-n64-2026-08-26/detector-compare.json", "157572031cd0d4cbcc26345f3b33e79b5ca7154cc4365c0d62086c7e03e17575"),
)


def mix_freeze_payload() -> dict[str, object]:
    artifacts = []
    for seed_base, relative, artifact_hash in _DEVELOPMENT_ARTIFACTS:
        path = Path(relative)
        disk = json.loads(path.read_text(encoding="utf-8"))
        if disk["artifact_hash"] != artifact_hash:
            raise ValueError("mix freeze development artifact hash mismatch")
        artifacts.append(
            {
                "seed_base": int(seed_base),
                "path": relative,
                "artifact_hash": artifact_hash,
            }
        )
    payload = {
        "algorithm_version": CYCLE8_MIX_FREEZE_VERSION,
        "freeze": True,
        "confirmation": False,
        "confirmation_generated": False,
        "product_authorized": False,
        "release_registry_empty": release_transform_registry().rules == (),
        "cli_identity": process_text("I do not agree.") == "I do not agree.",
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "carriers": [int(codepoint) for codepoint in LETTER_MIX_APPROVED_CARRIERS],
        "payloads": list(LETTER_MIX_PAYLOADS),
        "even_site_payload": "\u034f",
        "odd_site_payload": "\ufe00",
        "max_selected": LETTER_MIX_MAX_SELECTED,
        "placement": (
            "ASCII letter sites outside raw unmerged hard machine spans; "
            "even selected-site index receives U+034F; odd receives U+FE00"
        ),
        "hard_machine_spans": [
            "fenced_code",
            "inline_code",
            "markdown_destination",
            "url",
            "email",
            "ip",
            "date",
            "currency",
            "percent",
            "number",
            "posix_path",
            "windows_path",
            "cli_flag",
        ],
        "quote_interiors_eligible": True,
        "math_citation_quotation_not_hard": True,
        "visible_projection": "project_visible_v1",
        "carrier_insertion": "is_carrier_insertion_v1",
        "user_visible_invariants": "validate_user_visible_invariants",
        "supported_input_domain": "is_supported_product_domain_v1",
        "letter_mix_source_sha256": sha256_file(_LETTER_MIX_PATH),
        "detector": {
            "model": "openai-community/gpt2",
            "model_revision": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
            "implementation": "Hugging Face SynthID Weighted Mean",
            "threshold": CYCLE6_THRESHOLD,
            "comparison": "score >= threshold",
            "fpr_assumption": "frozen Cycle 6 GPT-2 / Hugging Face SynthID Weighted Mean threshold 0.5570987654320988",
            "device": "cpu",
        },
        "sanitizer_ids": list(CYCLE8_SCALE_SANITIZER_VARIANT_IDS),
        "control_protocol": {
            "arm_ids": list(CYCLE8_MIX_ARM_IDS),
            "pair_count": CYCLE8_MIX_CONFIRMATION_PAIR_COUNT,
            "matched_unwatermarked": True,
            "detector_blind": True,
            "watermark_key_blind": True,
            "non_neural": True,
            "run_once": True,
        },
        "development_evidence": {
            "label": "HYPOTHESIS",
            "rate": "0/256",
            "raw_watermarked_detected": 0,
            "raw_unwatermarked_detected": 0,
            "worst_max_score": 0.5195221445221445,
            "min_gap_below_threshold": CYCLE6_THRESHOLD - 0.5195221445221445,
            "artifacts": artifacts,
        },
        "confirmation_protocol": {
            "preregistered": True,
            "generated": False,
            "seed_bases": list(CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES),
            "topics": {
                "830000": CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
                "840000": CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
                "850000": CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
            },
            "pair_count": CYCLE8_MIX_CONFIRMATION_PAIR_COUNT,
            "algorithm_version": CYCLE8_MIX_CONFIRMATION_DETECTOR_VERSION,
            "target_transformed_wm": "0/192",
            "target_visible": "192/192",
            "do_not_rerun_looking_for_zero": True,
        },
        "do_not_generate_950000": True,
        "weaknesses": [
            "Mn-strip removes U+034F",
            "default-ignorable-strip removes U+034F and U+FE00",
            "latin-1 cannot roundtrip U+034F or U+FE00",
            "low-site rows can remain closer to threshold than high-site rows",
            "token expansion remains large",
        ],
    }
    return payload


def mix_freeze_hash() -> str:
    return sha256_json(mix_freeze_payload())


def assert_mix_freeze_committed() -> None:
    path = Path(CYCLE8_MIX_FREEZE_PATH)
    if not path.is_file():
        raise ValueError("mix freeze spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in disk.items() if key != "freeze_hash"}
    if payload != mix_freeze_payload():
        raise ValueError("mix freeze spec does not match the embedded freeze payload")
    if disk.get("freeze_hash") != mix_freeze_hash():
        raise ValueError("mix freeze spec hash mismatch")
    if disk.get("freeze") is not True:
        raise ValueError("mix freeze spec is not frozen")
    if disk.get("product_authorized") is True:
        raise ValueError("mix freeze must not product-authorize the mechanism")
    if release_transform_registry().rules != ():
        raise ValueError("release_transform_registry must stay empty")


def assert_cycle8_mix_confirmation_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_mix_freeze_committed()
    if seed_base not in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        raise ValueError("seed_base is not a Cycle 8 mix confirmation seed")
    row = row_for_seed_base(seed_base)
    if row["generated"] is True:
        raise ValueError("confirmation seed already generated")
    if row["scored"] is True:
        raise ValueError("confirmation seed already scored")
    if row["eligible_for_confirmation"] is not True:
        raise ValueError("seed is not eligible for confirmation")
