from __future__ import annotations

import json
from pathlib import Path

from .._validation import require_int
from ..cli import RELEASE_CLI_ALGORITHM_VERSION, process_text
from ..config import canonical_json_text
from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json
from ..product.contract import FROZEN_PRODUCT_CONTRACT_HASH, product_contract_payload
from ..product.visible_projection import product_approved_carriers_v1
from ..seeds.ledger import (
    CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES,
    CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_TOPIC,
    CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_TOPIC,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    row_for_seed_base,
)
from ..transforms.registry import release_transform_registry
from .compare import CYCLE8_IDENTITY_ARM_ID, CYCLE8_LETTER_ALT_ARM_ID
from .control_carrier import apply_required_sanitizer_bundle
from .letter_mix import LETTER_MIX_APPROVED_CARRIERS
from .sanitize import sanitize_cycle8_scale_variant
from .threat_model_audit import lm_watermarking_unicode_sanitizer


CYCLE8_PUBLISHABILITY_GATE_V2_VERSION = "cycle8-publishability-gate-v2"
CYCLE8_PUBLISHABILITY_GATE_V2_PATH = "specs/cycle8/fuckmark-cycle8-publishability-gate-v2.json"
CYCLE8_PUBLISHABILITY_GATE_V2_HASH = "66da1101bc6621023a0bb2b98d40f37ada0384f19a750d4c8b0c48de1c2cae68"
CYCLE8_GATE_V2_CONFIRMATION_DETECTOR_VERSION = "cycle8-gate-v2-confirmation-detector-compare-v1"
CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_VERSION = "cycle8-gate-v2-confirmation-scorecard-v1"
CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT = 64
CYCLE8_GATE_V2_CONFIRMATION_DATE = "2026-08-27"
GATE_V2_STATUS_PREREGISTERED = "preregistered_not_active"
GATE_V2_STATUS_CONFIRMED = "confirmed_not_product_authorized"
GATE_V2_STATUS_AUTHORIZED = "confirmed_and_product_authorized"
CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH = "specs/cycle8/fuckmark-cycle8-gate-v2-confirmation-scorecard-v1.json"
CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH = "3df98598fa1f9fb3951029f105b43dfd5f3e83a9ec69fd5c160b31686b0ad6c9"
GATE_V2_MIX_ARM_ID = CYCLE8_LETTER_ALT_ARM_ID
GATE_V2_IDENTITY_ARM_ID = CYCLE8_IDENTITY_ARM_ID
GATE_V2_ARM_IDS = (CYCLE8_IDENTITY_ARM_ID, CYCLE8_LETTER_ALT_ARM_ID)
GATE_V2_UNICODE_SANITIZER_ID = "lm_watermarking_unicode_sanitizer"
GATE_V2_REQUIRED_BUNDLE_ID = "required_bundle"
GATE_V2_REQUIRED_SANITIZER_IDS = (
    "raw",
    "nfc",
    "nfkc",
    "cf_strip",
    "nfkc_cf_strip",
    "ws_collapse",
    "ws_collapse_nfkc_cf_strip",
    GATE_V2_UNICODE_SANITIZER_ID,
)
GATE_V2_DIAGNOSTIC_SANITIZER_IDS = (GATE_V2_REQUIRED_BUNDLE_ID,)
GATE_V2_SCORED_SANITIZER_IDS = (*GATE_V2_REQUIRED_SANITIZER_IDS, *GATE_V2_DIAGNOSTIC_SANITIZER_IDS)
GATE_V2_CONFIRMATION_SEED_BASES = (
    CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
    CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
)
GATE_V2_CONFIRMATION_TOPICS = {
    CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE: CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE: CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_TOPIC,
    CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE: CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_TOPIC,
}
GATE_V2_IDENTITY_WM_MIN = 168
GATE_V2_MIX_WM_MAX = 0
GATE_V2_MIX_UW_MAX = 0
GATE_V2_VISIBLE_PASS_MIN = 192
GATE_V2_CARRIER_FREE_UNICODE_MIN = 96
GATE_V2_CARRIER_FREE_UNICODE_MAX_DROP = 16
GATE_V2_TOTAL_ROWS = 192
GATE_V2_CONFIRMATION_ARTIFACT_HASHES = {
    1_200_000: "34528f2fdbd52d9f6e288c4487bf7f37d453144e73e0b16e34b284bf0d0412a5",
    1_210_000: "59288b71fbd1166b31e97e6e0ba72c484e050ffb0a456a949d45e91d52c3d234",
    1_220_000: "e1ec65072f1d41f7d62966e0d24b46bed6b800408dd60cd4697f31570e16e924",
}


def gate_v2_confirmation_artifact_dir(seed_base: int) -> str:
    require_int("seed_base", seed_base)
    return (
        f"evidence/cycle8-gate-v2-confirmation-{seed_base}-n"
        f"{CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT}-{CYCLE8_GATE_V2_CONFIRMATION_DATE}"
    )


def gate_v2_confirmation_artifact_path(seed_base: int) -> str:
    return f"{gate_v2_confirmation_artifact_dir(seed_base)}/detector-compare.json"


def sanitize_gate_v2_variant(variant_id: str, text: str) -> str:
    if not isinstance(variant_id, str) or not variant_id:
        raise TypeError("variant_id must be a non-empty string")
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if variant_id not in GATE_V2_SCORED_SANITIZER_IDS:
        raise ValueError(f"unknown Gate v2 sanitizer variant: {variant_id}")
    if variant_id == GATE_V2_UNICODE_SANITIZER_ID:
        return lm_watermarking_unicode_sanitizer(text)
    if variant_id == GATE_V2_REQUIRED_BUNDLE_ID:
        return apply_required_sanitizer_bundle(text)
    return sanitize_cycle8_scale_variant(variant_id, text)


def assert_gate_v2_confirmation_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    if seed_base in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        raise ValueError("spent mix-freeze confirmation seeds must not be reused")
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("do not generate 950000")
    if seed_base not in GATE_V2_CONFIRMATION_SEED_BASES:
        raise ValueError("seed_base is not a Gate v2 confirmation seed")
    row = row_for_seed_base(seed_base)
    if row["generated"] is True:
        raise ValueError("Gate v2 confirmation seed already generated")
    if row["scored"] is True:
        raise ValueError("Gate v2 confirmation seed already scored")
    if row["eligible_for_confirmation"] is not True:
        raise ValueError("seed is not eligible for Gate v2 confirmation")
    if row["generation_topic"] != GATE_V2_CONFIRMATION_TOPICS[seed_base]:
        raise ValueError("seed topic does not match the Gate v2 protocol")


def gate_v2_confirmation_artifacts_present() -> bool:
    return all(Path(gate_v2_confirmation_artifact_path(seed_base)).is_file() for seed_base in GATE_V2_CONFIRMATION_SEED_BASES)


def contract_stress_only_sanitizers() -> tuple[str, ...]:
    assumptions = product_contract_payload()["sanitizer_assumptions"]
    return tuple(assumptions["stress_only_not_frozen"])


def gate_v2_payload() -> dict[str, object]:
    stress_only = contract_stress_only_sanitizers()
    scorecard = build_gate_v2_confirmation_scorecard()
    payload = {
        "algorithm_version": CYCLE8_PUBLISHABILITY_GATE_V2_VERSION,
        "status": GATE_V2_STATUS_AUTHORIZED,
        "evidence_label": "VERIFIED",
        "confirmation_grade": True,
        "fully_satisfied": True,
        "product_authorized": True,
        "mix_sanitizer_gate_v1": "FAIL",
        "required_sanitizer_bundle_not_weakened": True,
        "release_registry_empty": release_transform_registry().rules == (),
        "approved_carriers_empty": product_approved_carriers_v1() == frozenset(),
        "cli_identity": process_text("I do not agree.") == "I do not agree.",
        "product_contract_hash": FROZEN_PRODUCT_CONTRACT_HASH,
        "confirmation_scorecard_hash": scorecard["scorecard_hash"],
        "confirmation_result": {
            "identity_watermarked_detected": scorecard["identity_watermarked_detected"],
            "identity_unwatermarked_detected": scorecard["identity_unwatermarked_detected"],
            "mix_unwatermarked_detected": scorecard["mix_unwatermarked_detected"],
            "mix_watermarked_detected_by_required_sanitizer": scorecard["mix_watermarked_detected_by_required_sanitizer"],
            "mix_watermarked_detected_by_diagnostic_sanitizer": scorecard["mix_watermarked_detected_by_diagnostic_sanitizer"],
            "carrier_free_unicode_watermarked_detected": scorecard["carrier_free_unicode_watermarked_detected"],
            "carrier_free_unicode_drop_from_identity": scorecard["carrier_free_unicode_drop_from_identity"],
            "visible_pass_rate": scorecard["visible_pass_rate"],
            "mix_max_score": scorecard["mix_max_score"],
        },
        "decision": {
            "form": "detector_after_sanitizer",
            "rejected_form": "carrier_fixed_point_of_every_sanitizer",
            "rationale": (
                "The product objective is that detection remain negative after sanitizers a "
                "real detector pipeline can run, while exact visible text is preserved. "
                "Fixed-point survival S(T(x)) == T(x) is sufficient but not required. The "
                "H12-H15 required bundle deletes mix carriers and reconstructs the source, "
                "so a fixed-point gate against Mn-strip and default-ignorable-strip is a "
                "stress test of carrier survival, not a product publishability requirement."
            ),
        },
        "classifications": {
            "raw": "real_deployed_preprocessing",
            "nfc": "frozen_product_requirement",
            "nfkc": "frozen_product_requirement",
            "cf_strip": "frozen_product_requirement",
            "nfkc_cf_strip": "frozen_product_requirement",
            "ws_collapse": "frozen_product_requirement",
            "ws_collapse_nfkc_cf_strip": "frozen_product_requirement",
            "lm_watermarking_unicode_sanitizer": "real_deployed_preprocessing",
            "nonspacing_mark_removal": "stress_only_not_frozen",
            "default_ignorable_removal": "stress_only_not_frozen",
            "required_bundle": "known_destructive_countermeasure",
            "homoglyphs": "unsupported",
            "truecase": "unsupported",
        },
        "required_sanitizers": list(GATE_V2_REQUIRED_SANITIZER_IDS),
        "diagnostic_sanitizers": list(GATE_V2_DIAGNOSTIC_SANITIZER_IDS),
        "excluded_sanitizers": list(stress_only),
        "exclusion_reason": (
            "stress_only_not_frozen in the frozen product contract; undeployable on ordinary "
            "multilingual text; not used by measured production detector tokenizers"
        ),
        "added_versus_h16_proposal": ["ws_collapse_nfkc_cf_strip"],
        "addition_reason": "frozen Cycle 7 product-contract sanitizer omitted from the H16 draft",
        "optional_unsupported": ["homoglyphs", "truecase"],
        "optional_unsupported_reason": (
            "jwkirchenbauer/lm-watermarking ships these as opt-in normalizers, not as "
            "WatermarkDetector(normalizers=['unicode']) defaults"
        ),
        "condition": (
            "detector(S(T(x))) remains negative for each required sanitizer S, while "
            "VISIBLE(x) == VISIBLE(T(x)) on every eligible row"
        ),
        "still_requires": [
            "exact_user_visible_text_preservation",
            "ordinary_plain_text",
        ],
        "confirmation_protocol": {
            "status": "generated_and_scored_once",
            "pair_count_per_seed": CYCLE8_GATE_V2_CONFIRMATION_PAIR_COUNT,
            "total_watermarked_rows": GATE_V2_TOTAL_ROWS,
            "seed_bases": list(GATE_V2_CONFIRMATION_SEED_BASES),
            "topics": [GATE_V2_CONFIRMATION_TOPICS[seed] for seed in GATE_V2_CONFIRMATION_SEED_BASES],
            "forbidden_seeds": list(CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES) + [CYCLE8_SCALE_VALIDATION_SEED_BASE, 890000],
            "arm_ids": list(GATE_V2_ARM_IDS),
            "mechanism_id": GATE_V2_MIX_ARM_ID,
            "scored_sanitizer_ids": list(GATE_V2_SCORED_SANITIZER_IDS),
            "run_once": True,
            "rerun_looking_for_zero": False,
            "detector_algorithm_version": CYCLE8_GATE_V2_CONFIRMATION_DETECTOR_VERSION,
            "thresholds": {
                "identity_watermarked_detected_min": GATE_V2_IDENTITY_WM_MIN,
                "mix_watermarked_detected_max": GATE_V2_MIX_WM_MAX,
                "mix_unwatermarked_detected_max": GATE_V2_MIX_UW_MAX,
                "mix_visible_pass_min": GATE_V2_VISIBLE_PASS_MIN,
                "carrier_free_unicode_detected_min": GATE_V2_CARRIER_FREE_UNICODE_MIN,
                "carrier_free_unicode_max_drop_from_identity": GATE_V2_CARRIER_FREE_UNICODE_MAX_DROP,
            },
            "pass_conditions": [
                "pristine/identity watermarked detection stays at or above the preregistered floor",
                "transformed mix watermarked detection is 0 after every required sanitizer",
                "transformed mix unwatermarked detection is 0 on raw",
                "exact visible invariance passes every mix watermarked row",
                "frozen product-contract sanitizer arms remain 0 on mix watermarked rows",
                "lm-watermarking UnicodeSanitizer mix watermarked detection is 0",
                "carrier-free identity plus UnicodeSanitizer still detects strongly enough",
                "results are written once and hashed; do not rerun looking for zero",
                "cross-detector DeepMind 0/192 on 1060000/1070000/1080000 remains the current transfer evidence and is not rescored here",
            ],
            "diagnostic_not_pass_conditions": [
                "required_bundle is STRESS_ONLY / KNOWN_DESTRUCTIVE_COUNTERMEASURE; it is scored to record whether it reconstructs the source, not to block the gate",
            ],
            "artifacts": [gate_v2_confirmation_artifact_path(seed) for seed in GATE_V2_CONFIRMATION_SEED_BASES],
            "artifacts_present": True,
        },
        "why_not_fully_satisfied": None,
        "authorization_status": "authorized",
        "authorization_blocked_on": None,
        "notes": (
            "Gate v2 confirmation passed on seeds 1200000/1210000/1220000. "
            "Public CLI applies frozen u034f-ufe00-letter-alt-v1 as release-cli-v5. "
            "release_transform_registry stays empty; mix is not a greedy rule catalog. "
            "Gate v2 does not weaken required_sanitizers_keep. Mix sanitizer robustness on "
            "the Cycle 8 v1 publishability report stays FAIL. Mn-strip and "
            "default-ignorable-strip remain recorded stress tests. "
            "Do not generate 950000. Do not retune spent confirmation seeds 830000/840000/850000 "
            "or 1200000/1210000/1220000. Do not retag v0.3.0."
        ),
    }
    return {**payload, "gate_hash": sha256_json(payload)}


def write_gate_v2_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_PUBLISHABILITY_GATE_V2_PATH)
    payload = gate_v2_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_gate_v2(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_PUBLISHABILITY_GATE_V2_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_gate_v2_committed() -> None:
    path = Path(CYCLE8_PUBLISHABILITY_GATE_V2_PATH)
    if not path.is_file():
        raise ValueError("Gate v2 spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "gate_hash"}
    digest = sha256_json(body)
    if disk.get("gate_hash") != digest:
        raise ValueError("Gate v2 spec hash mismatch")
    if CYCLE8_PUBLISHABILITY_GATE_V2_HASH == "0" * 64:
        raise ValueError("Gate v2 spec hash is not frozen")
    if digest != CYCLE8_PUBLISHABILITY_GATE_V2_HASH:
        raise ValueError("Gate v2 spec hash is not the frozen digest")
    if disk["product_authorized"] is not True:
        raise ValueError("Gate v2 must product-authorize after confirmation and engineering")
    if disk["status"] != GATE_V2_STATUS_AUTHORIZED:
        raise ValueError("Gate v2 must be confirmed_and_product_authorized after product authorization")
    if disk["confirmation_grade"] is not True:
        raise ValueError("Gate v2 confirmation grade must be recorded")
    if disk["fully_satisfied"] is not True:
        raise ValueError("Gate v2 must record that confirmation conditions are met")
    if disk["mix_sanitizer_gate_v1"] != "FAIL":
        raise ValueError("Gate v2 must not rewrite the v1 mix sanitizer gate")
    if disk["required_sanitizer_bundle_not_weakened"] is not True:
        raise ValueError("Gate v2 must not weaken the required sanitizer bundle")
    if disk["evidence_label"] != "VERIFIED":
        raise ValueError("Gate v2 confirmation must remain labelled VERIFIED")
    if disk["authorization_status"] != "authorized":
        raise ValueError("Gate v2 authorization_status must be authorized")
    if release_transform_registry().rules != ():
        raise ValueError("release_transform_registry must stay empty")
    if product_approved_carriers_v1() != frozenset(LETTER_MIX_APPROVED_CARRIERS):
        raise ValueError("product_approved_carriers_v1 must be the frozen mix carriers")
    if process_text("I do not agree.") == "I do not agree.":
        raise ValueError("authorized CLI must apply the frozen letter mix")
    if RELEASE_CLI_ALGORITHM_VERSION != "release-cli-v8":
        raise ValueError("authorized CLI must report release-cli-v8")
    scorecard = build_gate_v2_confirmation_scorecard()
    if scorecard["confirmation"] is not True:
        raise ValueError("Gate v2 confirmation scorecard must pass")
    if scorecard["product_authorized"] is True:
        raise ValueError("the confirmation scorecard must not product-authorize")
    if CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH == "0" * 64:
        raise ValueError("Gate v2 confirmation scorecard hash is not frozen")
    if scorecard["scorecard_hash"] != CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH:
        raise ValueError("Gate v2 confirmation scorecard hash is not the frozen digest")
    live = gate_v2_payload()
    if live != disk:
        raise ValueError("Gate v2 spec does not match the live payload")


def build_gate_v2_confirmation_scorecard() -> dict[str, object]:
    if not gate_v2_confirmation_artifacts_present():
        raise ValueError("Gate v2 confirmation artifacts are not present")
    identity_wm = 0
    identity_uw = 0
    mix_uw = 0
    visible_pass = 0
    visible_total = 0
    required = {variant: 0 for variant in GATE_V2_REQUIRED_SANITIZER_IDS}
    diagnostic = {variant: 0 for variant in GATE_V2_DIAGNOSTIC_SANITIZER_IDS}
    carrier_free = 0
    mix_max = None
    corpora: list[dict[str, object]] = []
    for seed_base in GATE_V2_CONFIRMATION_SEED_BASES:
        relative = gate_v2_confirmation_artifact_path(seed_base)
        artifact = json.loads(Path(relative).read_text(encoding="utf-8"))
        body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
        digest = sha256_json(body)
        expected = GATE_V2_CONFIRMATION_ARTIFACT_HASHES[seed_base]
        if artifact.get("artifact_hash") != digest or digest != expected:
            raise ValueError("Gate v2 confirmation artifact hash mismatch")
        if int(artifact["seed_base"]) != seed_base:
            raise ValueError("Gate v2 confirmation artifact seed mismatch")
        if artifact["algorithm_version"] != CYCLE8_GATE_V2_CONFIRMATION_DETECTOR_VERSION:
            raise ValueError("Gate v2 confirmation artifact algorithm mismatch")
        mix = artifact["summaries"][GATE_V2_MIX_ARM_ID]
        identity = artifact["summaries"][GATE_V2_IDENTITY_ARM_ID]
        mix_detected = mix["sanitizer_watermarked_detected"]
        identity_detected = identity["sanitizer_watermarked_detected"]
        identity_wm += int(identity["pristine_watermarked_detected"])
        identity_uw += int(identity["pristine_unwatermarked_detected"])
        mix_uw += int(mix["raw_unwatermarked_detected"])
        carrier_free += int(identity_detected[GATE_V2_UNICODE_SANITIZER_ID])
        mix_score = float(mix["raw_watermarked_max_score"])
        mix_max = mix_score if mix_max is None else max(mix_max, mix_score)
        for variant in GATE_V2_REQUIRED_SANITIZER_IDS:
            required[variant] += int(mix_detected[variant])
        for variant in GATE_V2_DIAGNOSTIC_SANITIZER_IDS:
            diagnostic[variant] += int(mix_detected[variant])
        for row in artifact["scored_rows"]:
            if row["arm_id"] != GATE_V2_MIX_ARM_ID or row["label"] != "watermarked":
                continue
            visible_total += 1
            visible_pass += int(bool(row["geometry"]["visible_ok"]))
        corpora.append(
            {
                "seed_base": seed_base,
                "path": relative,
                "artifact_hash": digest,
                "topic": artifact["topic"],
                "identity_pristine_watermarked_detected": int(identity["pristine_watermarked_detected"]),
                "mix_raw_watermarked_detected": int(mix_detected["raw"]),
                "mix_raw_unwatermarked_detected": int(mix["raw_unwatermarked_detected"]),
                "mix_unicode_sanitizer_watermarked_detected": int(mix_detected[GATE_V2_UNICODE_SANITIZER_ID]),
                "carrier_free_unicode_watermarked_detected": int(identity_detected[GATE_V2_UNICODE_SANITIZER_ID]),
                "mix_max_score": mix_score,
                "visible_pass_count": int(mix["visible_pass_count"]),
            }
        )
    drop = identity_wm - carrier_free
    required_pass = all(value <= GATE_V2_MIX_WM_MAX for value in required.values())
    passed = (
        identity_wm >= GATE_V2_IDENTITY_WM_MIN
        and required_pass
        and mix_uw <= GATE_V2_MIX_UW_MAX
        and visible_pass >= GATE_V2_VISIBLE_PASS_MIN
        and visible_total == GATE_V2_TOTAL_ROWS
        and carrier_free >= GATE_V2_CARRIER_FREE_UNICODE_MIN
        and drop <= GATE_V2_CARRIER_FREE_UNICODE_MAX_DROP
    )
    payload = {
        "algorithm_version": CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_VERSION,
        "gate_version": CYCLE8_PUBLISHABILITY_GATE_V2_VERSION,
        "status": "confirmed",
        "confirmation": passed,
        "confirmation_grade": passed,
        "fully_satisfied": passed,
        "product_authorized": False,
        "run_once": True,
        "rerun_looking_for_zero": False,
        "evidence_label": "VERIFIED" if passed else "HYPOTHESIS",
        "threshold": CYCLE6_THRESHOLD,
        "identity_watermarked_detected": identity_wm,
        "identity_unwatermarked_detected": identity_uw,
        "mix_unwatermarked_detected": mix_uw,
        "mix_watermarked_detected_by_required_sanitizer": required,
        "mix_watermarked_detected_by_diagnostic_sanitizer": diagnostic,
        "carrier_free_unicode_watermarked_detected": carrier_free,
        "carrier_free_unicode_drop_from_identity": drop,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "mix_max_score": mix_max,
        "pass_conditions": {
            "identity_watermarked_detected": identity_wm >= GATE_V2_IDENTITY_WM_MIN,
            "mix_required_sanitizers_undetected": required_pass,
            "mix_unwatermarked_undetected": mix_uw <= GATE_V2_MIX_UW_MAX,
            "visible_invariance": visible_pass >= GATE_V2_VISIBLE_PASS_MIN and visible_total == GATE_V2_TOTAL_ROWS,
            "carrier_free_unicode_floor": carrier_free >= GATE_V2_CARRIER_FREE_UNICODE_MIN,
            "carrier_free_unicode_max_drop": drop <= GATE_V2_CARRIER_FREE_UNICODE_MAX_DROP,
        },
        "corpora": corpora,
        "do_not_generate_950000": True,
        "notes": (
            "One-shot Gate v2 confirmation of detector-after-sanitizer publishability. "
            "Do not rerun looking for zero. Do not retune on these corpora. "
            "required_bundle is diagnostic. Public CLI remains empty until a separate "
            "product-authorization step."
        ),
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}


def write_gate_v2_confirmation_scorecard(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH)
    payload = build_gate_v2_confirmation_scorecard()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_gate_v2_confirmation_scorecard(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))
