from __future__ import annotations

import json
from pathlib import Path

from ..cli import RELEASE_CLI_ALGORITHM_VERSION, process_text
from ..config import canonical_json_text
from ..detectors.bayesian_evidence import BAYESIAN_EVIDENCE_ALGORITHM_VERSION
from ..detectors.mean import MEAN_ALGORITHM_VERSION, WEIGHTED_MEAN_ALGORITHM_VERSION
from ..detectors.types import DetectorFamily
from ..hashing import sha256_json, sha256_text
from ..product.contract import FROZEN_PRODUCT_CONTRACT_HASH
from ..product.domain import is_supported_product_domain_v1
from ..product.roundtrip import latin1_roundtrip_survives, roundtrip_report
from ..product.visible_projection import (
    is_carrier_insertion_v1,
    product_approved_carriers_v1,
    project_visible_v1,
)
from ..transforms.registry import release_transform_registry
from .benchmark import (
    CYCLE8_BENCHMARK_STRESS_SANITIZER_IDS,
    benchmark_fixtures,
    sanitize_benchmark_stress,
)
from .compare import CYCLE8_LETTER_ALT_ARM_ID
from .letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from .mix_confirmation import CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION, build_mix_confirmation_scorecard
from .mix_freeze import (
    CYCLE8_MIX_FREEZE_VERSION,
    assert_mix_freeze_committed,
    mix_freeze_hash,
    mix_freeze_payload,
)
from .sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant


CYCLE8_MIX_PUBLISHABILITY_VERSION = "cycle8-mix-publishability-v1"
CYCLE8_MIX_PUBLISHABILITY_PATH = "specs/cycle8/fuckmark-cycle8-mix-publishability-v1.json"
CYCLE8_MIX_PUBLISHABILITY_HASH = "918513f0a9260f1bbcc66cd0cfe097a4df38cfc218aa61ff26fba9f08e7334b5"
_CONFIRMATION_SCORECARD_HASH = "a4911189af7f38d34252452821d90df1188bfe05025fe33c028c4b670eecbcce"
_MIX_FREEZE_HASH = "2286aa201bd9cb70136f2895740489136aa1ba7cfd9471c6e233fe201af41986"
_PRODUCT_CONTRACT_HASH = "5afd79586f82e31d0d673acbebebf0ac00804cff74b9f644f000bddfd3dc07d1"
_GATE_IDS = (
    "reproducibility",
    "visibility_invariance",
    "software_compatibility",
    "sanitizer_weaknesses",
    "cross_detector_generalization",
)
_LITERAL = "do not"
_URL = "https://example.com/do-not-touch"
_EMAIL = "docs@example.com"


def _check(check_id: str, verdict: str, **evidence: object) -> dict[str, object]:
    if verdict not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ValueError("unknown check verdict")
    return {"id": check_id, "verdict": verdict, **evidence}


def _gate(
    gate_id: str,
    verdict: str,
    *,
    product_blocking: bool,
    summary: str,
    checks: list[dict[str, object]],
) -> dict[str, object]:
    if gate_id not in _GATE_IDS:
        raise ValueError("unknown publishability gate")
    if verdict not in {"PASS", "FAIL"}:
        raise ValueError("unknown gate verdict")
    return {
        "id": gate_id,
        "verdict": verdict,
        "product_blocking": product_blocking,
        "summary": summary,
        "checks": checks,
    }


def _json_roundtrip(text: str) -> bool:
    return json.loads(json.dumps(text, ensure_ascii=False)) == text


def _frozen_carriers_survive(text: str) -> bool:
    return all(sanitize_cycle8_scale_variant(variant, text) == text for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS)


def _stress_kills_carriers(text: str) -> dict[str, bool]:
    rows = {}
    for variant in CYCLE8_BENCHMARK_STRESS_SANITIZER_IDS:
        cleaned = sanitize_benchmark_stress(variant, text)
        rows[variant] = "\u034f" not in cleaned and "\ufe00" not in cleaned
    return rows


def measure_mix_fixtures() -> dict[str, object]:
    visible_pass = 0
    supported = 0
    unsupported = 0
    utf8_pass = 0
    nfc_pass = 0
    stdio_pass = 0
    width_pass = 0
    latin1_survive = 0
    json_pass = 0
    search_candidates = 0
    search_breaks = 0
    frozen_survive = 0
    frozen_total = 0
    mn_kills = 0
    di_kills = 0
    nfkd_kills = 0
    stress_total = 0
    url_preserved = 0
    url_total = 0
    email_preserved = 0
    email_total = 0
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    hashes = tuple(sha256_text(apply_letter_alternating_mix(source)) for _ in range(5))
    for _fixture_id, _category, text in benchmark_fixtures():
        if not is_supported_product_domain_v1(text):
            unsupported += 1
            continue
        supported += 1
        applied = apply_letter_alternating_mix(text)
        visible = is_carrier_insertion_v1(text, applied, LETTER_MIX_APPROVED_CARRIERS) and project_visible_v1(
            applied, LETTER_MIX_APPROVED_CARRIERS
        ) == text
        visible_pass += int(visible)
        report = roundtrip_report(text, applied, LETTER_MIX_APPROVED_CARRIERS)
        utf8_pass += int(bool(report["utf8_roundtrip_equals_transformed"]))
        nfc_pass += int(bool(report["nfc_equals_transformed"]))
        stdio_pass += int(bool(report["stdin_stdout_equals_transformed"]))
        width_pass += int(bool(report["display_column_width_equal"]))
        latin1_survive += int(latin1_roundtrip_survives(applied))
        json_pass += int(_json_roundtrip(applied))
        if _LITERAL in text:
            search_candidates += 1
            search_breaks += int(_LITERAL not in applied)
        if _URL in text:
            url_total += 1
            url_preserved += int(_URL in applied)
        if _EMAIL in text:
            email_total += 1
            email_preserved += int(_EMAIL in applied)
        if applied == text:
            continue
        frozen_total += 1
        frozen_survive += int(_frozen_carriers_survive(applied))
        stress = _stress_kills_carriers(applied)
        stress_total += 1
        mn_kills += int(stress["mn_strip"])
        di_kills += int(stress["default_ignorable_strip"])
        nfkd_kills += int(stress["nfkd"])
    return {
        "determinism_unique_hashes": len(set(hashes)),
        "deterministic": len(set(hashes)) == 1,
        "supported_fixtures": supported,
        "unsupported_fixtures": unsupported,
        "visible_projection_pass": visible_pass,
        "utf8_roundtrip_pass": utf8_pass,
        "nfc_pass": nfc_pass,
        "stdio_pass": stdio_pass,
        "display_width_pass": width_pass,
        "latin1_survive": latin1_survive,
        "json_roundtrip_pass": json_pass,
        "search_literal_candidates": search_candidates,
        "search_literal_breaks": search_breaks,
        "frozen_sanitizer_survive": frozen_survive,
        "frozen_sanitizer_total": frozen_total,
        "mn_strip_kills": mn_kills,
        "default_ignorable_strip_kills": di_kills,
        "nfkd_kills": nfkd_kills,
        "stress_total": stress_total,
        "url_preserved": url_preserved,
        "url_total": url_total,
        "email_preserved": email_preserved,
        "email_total": email_total,
        "cli_identity": process_text(source) == source,
        "cli_preserves_transformed": process_text(transformed) == transformed,
        "short_paragraph_search_breaks": _LITERAL in source and _LITERAL not in transformed,
        "short_paragraph_latin1_fails": latin1_roundtrip_survives(transformed) is False,
        "short_paragraph_frozen_survives": _frozen_carriers_survive(transformed),
        "short_paragraph_mn_kills": _stress_kills_carriers(transformed)["mn_strip"],
        "short_paragraph_di_kills": _stress_kills_carriers(transformed)["default_ignorable_strip"],
        "short_paragraph_nfkd_kills": _stress_kills_carriers(transformed)["nfkd"],
    }


def mix_publishability_payload() -> dict[str, object]:
    assert_mix_freeze_committed()
    freeze = mix_freeze_payload()
    freeze_hash = mix_freeze_hash()
    scorecard = build_mix_confirmation_scorecard()
    measured = measure_mix_fixtures()
    registry_empty = release_transform_registry().rules == ()
    approved = tuple(sorted(product_approved_carriers_v1()))
    reproducibility_pass = (
        freeze_hash == _MIX_FREEZE_HASH
        and scorecard["scorecard_hash"] == _CONFIRMATION_SCORECARD_HASH
        and FROZEN_PRODUCT_CONTRACT_HASH == _PRODUCT_CONTRACT_HASH
        and measured["deterministic"] is True
        and measured["cli_identity"] is True
        and measured["cli_preserves_transformed"] is True
        and registry_empty
        and approved == ()
        and freeze["product_authorized"] is False
        and scorecard["product_authorized"] is False
        and scorecard["effectiveness"]["transformed_wm"]["rate"] == "0/192"
        and scorecard["effectiveness"]["transformed_uw"]["rate"] == "0/192"
        and scorecard["visibility"]["watermarked_pass_rate"] == "192/192"
    )
    visibility_pass = (
        measured["supported_fixtures"] == measured["visible_projection_pass"]
        and measured["utf8_roundtrip_pass"] == measured["supported_fixtures"]
        and measured["nfc_pass"] == measured["supported_fixtures"]
        and measured["stdio_pass"] == measured["supported_fixtures"]
        and measured["display_width_pass"] == measured["supported_fixtures"]
        and measured["supported_fixtures"] > 0
    )
    latin1_fail = measured["latin1_survive"] == 0 and measured["short_paragraph_latin1_fails"] is True
    search_fail = measured["search_literal_breaks"] > 0 and measured["short_paragraph_search_breaks"] is True
    protected_pass = (
        measured["url_total"] > 0
        and measured["email_total"] > 0
        and measured["url_preserved"] == measured["url_total"]
        and measured["email_preserved"] == measured["email_total"]
    )
    json_pass = measured["json_roundtrip_pass"] == measured["supported_fixtures"]
    software_pass = latin1_fail is False and search_fail is False and json_pass and protected_pass
    frozen_pass = (
        measured["frozen_sanitizer_survive"] == measured["frozen_sanitizer_total"]
        and measured["frozen_sanitizer_total"] > 0
        and scorecard["durability"]["frozen_sanitizers_match_raw"] is True
    )
    stress_still_kills = (
        measured["mn_strip_kills"] == measured["stress_total"]
        and measured["default_ignorable_strip_kills"] == measured["stress_total"]
        and measured["stress_total"] > 0
        and measured["nfkd_kills"] == 0
    )
    sanitizer_product_pass = frozen_pass and stress_still_kills is False
    confirmed_families = ("huggingface-synthid-weighted-mean-gpt2",)
    detector_pass = len(confirmed_families) >= 2
    gates = [
        _gate(
            "reproducibility",
            "PASS" if reproducibility_pass else "FAIL",
            product_blocking=True,
            summary="Frozen mix hashes, confirmation 0/192, identity CLI, and deterministic letter-mix apply replay locally.",
            checks=[
                _check("mix_freeze_hash", "PASS" if freeze_hash == _MIX_FREEZE_HASH else "FAIL", digest=freeze_hash),
                _check(
                    "confirmation_scorecard_hash",
                    "PASS" if scorecard["scorecard_hash"] == _CONFIRMATION_SCORECARD_HASH else "FAIL",
                    digest=scorecard["scorecard_hash"],
                ),
                _check(
                    "product_contract_hash",
                    "PASS" if FROZEN_PRODUCT_CONTRACT_HASH == _PRODUCT_CONTRACT_HASH else "FAIL",
                    digest=FROZEN_PRODUCT_CONTRACT_HASH,
                ),
                _check(
                    "letter_mix_deterministic",
                    "PASS" if measured["deterministic"] else "FAIL",
                    unique_hashes=measured["determinism_unique_hashes"],
                ),
                _check("cli_identity", "PASS" if measured["cli_identity"] else "FAIL"),
                _check("release_registry_empty", "PASS" if registry_empty else "FAIL"),
                _check("product_carriers_empty", "PASS" if approved == () else "FAIL", carriers=list(approved)),
                _check(
                    "confirmation_zero_of_192",
                    "PASS" if scorecard["effectiveness"]["transformed_wm"]["rate"] == "0/192" else "FAIL",
                    rate=scorecard["effectiveness"]["transformed_wm"]["rate"],
                ),
            ],
        ),
        _gate(
            "visibility_invariance",
            "PASS" if visibility_pass else "FAIL",
            product_blocking=True,
            summary="Mix keeps exact visible projection, NFC, UTF-8, stdio, and display width on supported ASCII fixtures. WebKit and terminal pixels stay UNKNOWN.",
            checks=[
                _check(
                    "visible_projection",
                    "PASS" if measured["visible_projection_pass"] == measured["supported_fixtures"] else "FAIL",
                    pass_count=measured["visible_projection_pass"],
                    total=measured["supported_fixtures"],
                ),
                _check(
                    "utf8_nfc_stdio_width",
                    "PASS" if visibility_pass else "FAIL",
                    utf8=measured["utf8_roundtrip_pass"],
                    nfc=measured["nfc_pass"],
                    stdio=measured["stdio_pass"],
                    display_width=measured["display_width_pass"],
                ),
                _check("webkit_safari", "UNKNOWN"),
                _check("terminal_pixels", "UNKNOWN"),
            ],
        ),
        _gate(
            "software_compatibility",
            "PASS" if software_pass else "FAIL",
            product_blocking=True,
            summary="UTF-8 and JSON preserve mix. Latin-1 cannot encode the carriers. Literal search for ordinary English phrases breaks on most short texts.",
            checks=[
                _check(
                    "utf8_and_json",
                    "PASS" if json_pass else "FAIL",
                    json_roundtrip_pass=measured["json_roundtrip_pass"],
                    total=measured["supported_fixtures"],
                ),
                _check(
                    "latin1",
                    "FAIL" if latin1_fail else "PASS",
                    survive_count=measured["latin1_survive"],
                    short_paragraph_fails=measured["short_paragraph_latin1_fails"],
                ),
                _check(
                    "literal_search",
                    "FAIL" if search_fail else "PASS",
                    breaks=measured["search_literal_breaks"],
                    candidates=measured["search_literal_candidates"],
                    short_paragraph_breaks=measured["short_paragraph_search_breaks"],
                ),
                _check(
                    "protected_url_email",
                    "PASS" if protected_pass else "FAIL",
                    url_preserved=measured["url_preserved"],
                    url_total=measured["url_total"],
                    email_preserved=measured["email_preserved"],
                    email_total=measured["email_total"],
                ),
            ],
        ),
        _gate(
            "sanitizer_weaknesses",
            "PASS" if sanitizer_product_pass else "FAIL",
            product_blocking=True,
            summary="Frozen Cycle 6/7 sanitizers keep mix. Mn-strip and default-ignorable-strip remove U+034F and U+FE00. NFKD keeps them.",
            checks=[
                _check(
                    "frozen_sanitizers",
                    "PASS" if frozen_pass else "FAIL",
                    survive=measured["frozen_sanitizer_survive"],
                    total=measured["frozen_sanitizer_total"],
                    confirmation_frozen_match_raw=scorecard["durability"]["frozen_sanitizers_match_raw"],
                ),
                _check(
                    "mn_strip",
                    "FAIL" if measured["short_paragraph_mn_kills"] else "PASS",
                    kills=measured["mn_strip_kills"],
                    total=measured["stress_total"],
                    category="stress_only_not_frozen",
                ),
                _check(
                    "default_ignorable_strip",
                    "FAIL" if measured["short_paragraph_di_kills"] else "PASS",
                    kills=measured["default_ignorable_strip_kills"],
                    total=measured["stress_total"],
                    category="stress_only_not_frozen",
                ),
                _check(
                    "nfkd",
                    "PASS" if measured["nfkd_kills"] == 0 else "FAIL",
                    kills=measured["nfkd_kills"],
                    total=measured["stress_total"],
                ),
            ],
        ),
        _gate(
            "cross_detector_generalization",
            "PASS" if detector_pass else "FAIL",
            product_blocking=True,
            summary="Confirmation is one open GPT-2 Hugging Face SynthID Weighted Mean detector. Mean and Bayesian families exist in-tree and were not confirmed on the mix freeze.",
            checks=[
                _check(
                    "confirmed_families",
                    "FAIL" if len(confirmed_families) < 2 else "PASS",
                    families=list(confirmed_families),
                    count=len(confirmed_families),
                ),
                _check(
                    "in_tree_unconfirmed_families",
                    "FAIL",
                    families=[item.value for item in DetectorFamily],
                    mean_algorithm=MEAN_ALGORITHM_VERSION,
                    weighted_mean_algorithm=WEIGHTED_MEAN_ALGORITHM_VERSION,
                    bayesian_evidence_algorithm=BAYESIAN_EVIDENCE_ALGORITHM_VERSION,
                    confirmation_implementation=freeze["detector"]["implementation"],
                    confirmation_model=freeze["detector"]["model"],
                ),
                _check("second_model", "FAIL"),
                _check("closed_or_proprietary_detector", "UNKNOWN"),
            ],
        ),
    ]
    product_publishable = all(gate["verdict"] == "PASS" or gate["product_blocking"] is False for gate in gates)
    return {
        "algorithm_version": CYCLE8_MIX_PUBLISHABILITY_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "freeze_version": CYCLE8_MIX_FREEZE_VERSION,
        "confirmation_scorecard_version": CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION,
        "cli_algorithm_version": RELEASE_CLI_ALGORITHM_VERSION,
        "product_publishable": product_publishable,
        "product_authorized": False,
        "release_registry_empty": registry_empty,
        "product_approved_carriers_v1": list(approved),
        "do_not_generate_950000": True,
        "do_not_retag_v030": True,
        "gates": gates,
        "identities": {
            "mix_freeze_hash": freeze_hash,
            "confirmation_scorecard_hash": scorecard["scorecard_hash"],
            "product_contract_hash": FROZEN_PRODUCT_CONTRACT_HASH,
        },
        "confirmation": {
            "transformed_wm": scorecard["effectiveness"]["transformed_wm"]["rate"],
            "transformed_uw": scorecard["effectiveness"]["transformed_uw"]["rate"],
            "visible": scorecard["visibility"]["watermarked_pass_rate"],
            "worst_max_score": scorecard["effectiveness"]["transformed_wm"]["max_score"],
            "min_gap_below_threshold": scorecard["effectiveness"]["transformed_wm"]["min_gap_below_threshold"],
            "detector": freeze["detector"]["implementation"],
        },
        "weaknesses": list(freeze["weaknesses"])
        + [
            "literal search for ordinary English phrases can miss after letter-mix insertion",
            "confirmation is a single open SynthID Weighted Mean detector on GPT-2",
        ],
    }


def mix_publishability_hash() -> str:
    return sha256_json(mix_publishability_payload())


def mix_is_product_publishable() -> bool:
    return bool(mix_publishability_payload()["product_publishable"])


def assert_mix_publishability_committed() -> None:
    path = Path(CYCLE8_MIX_PUBLISHABILITY_PATH)
    if not path.is_file():
        raise ValueError("mix publishability spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in disk.items() if key != "report_hash"}
    if payload != mix_publishability_payload():
        raise ValueError("mix publishability spec does not match the embedded payload")
    digest = mix_publishability_hash()
    if disk.get("report_hash") != digest:
        raise ValueError("mix publishability spec hash mismatch")
    if CYCLE8_MIX_PUBLISHABILITY_HASH != "0" * 64 and digest != CYCLE8_MIX_PUBLISHABILITY_HASH:
        raise ValueError("mix publishability spec hash is not the frozen digest")
    if disk.get("product_publishable") is True:
        raise ValueError("mix must not be marked product-publishable")
    if disk.get("product_authorized") is True:
        raise ValueError("mix must not be product-authorized")
    if product_approved_carriers_v1():
        raise ValueError("product_approved_carriers_v1 must stay empty")
    if release_transform_registry().rules != ():
        raise ValueError("release_transform_registry must stay empty")
    if process_text("I do not agree.") != "I do not agree.":
        raise ValueError("identity CLI changed")


def write_mix_publishability_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_MIX_PUBLISHABILITY_PATH)
    payload = mix_publishability_payload()
    report = {**payload, "report_hash": sha256_json(payload)}
    destination.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    return destination
