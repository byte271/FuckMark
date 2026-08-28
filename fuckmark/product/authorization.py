from __future__ import annotations

import json
from pathlib import Path

from ..cli import RELEASE_CLI_ALGORITHM_VERSION, process_text
from ..config import canonical_json_text
from ..cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from ..cycle8.gate_v2 import (
    CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH,
    CYCLE8_PUBLISHABILITY_GATE_V2_HASH,
    assert_gate_v2_committed,
)
from ..cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    LETTER_MIX_MAX_SELECTED,
    LETTER_MIX_MECHANISM_ID,
    apply_letter_alternating_mix,
)
from ..cycle8.mix_confirmation import CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
from ..cycle8.mix_freeze import CYCLE8_MIX_FREEZE_VERSION, mix_freeze_hash
from ..cycle8.publishability import CYCLE8_MIX_PUBLISHABILITY_HASH
from ..hashing import sha256_json
from ..product.contract import FROZEN_PRODUCT_CONTRACT_HASH
from ..product.domain import is_supported_product_domain_v1
from ..product.visible_projection import product_approved_carriers_v1, project_visible_v1
from ..transforms.registry import release_transform_registry


PRODUCT_AUTHORIZATION_VERSION = "cycle8-product-authorization-v2"
PRODUCT_AUTHORIZATION_PATH = "specs/cycle8/fuckmark-cycle8-product-authorization-v2.json"
PRODUCT_AUTHORIZATION_HASH = "38b84bb79c3430e62fe27bff3a9325ef91f56b93385f3d360f87f4b4981c8afb"
_MIX_FREEZE_HASH = "2286aa201bd9cb70136f2895740489136aa1ba7cfd9471c6e233fe201af41986"
_MIX_CONFIRMATION_SCORECARD_HASH = "a4911189af7f38d34252452821d90df1188bfe05025fe33c028c4b670eecbcce"
_AUDIT_SOURCE = "I do not agree."


def product_authorization_payload() -> dict[str, object]:
    transformed = apply_letter_alternating_mix(_AUDIT_SOURCE)
    mixed = "I do not agree " + chr(0x00E9) + "."
    payload = {
        "algorithm_version": PRODUCT_AUTHORIZATION_VERSION,
        "product_authorized": True,
        "mechanism_id": LETTER_MIX_MECHANISM_ID,
        "carriers": [int(codepoint) for codepoint in LETTER_MIX_APPROVED_CARRIERS],
        "max_selected": LETTER_MIX_MAX_SELECTED,
        "cli_algorithm_version": RELEASE_CLI_ALGORITHM_VERSION,
        "release_registry_empty": release_transform_registry().rules == (),
        "apply_path": "apply_letter_alternating_mix",
        "fail_closed": [
            "source_already_contains_approved_carriers",
            "visible_projection_mismatch",
            "carrier_insertion_mismatch",
            "apply_error",
            "no_eligible_ascii_letter_sites",
        ],
        "mix_sanitizer_gate_v1": "PASS",
        "required_sanitizer_bundle_not_weakened": True,
        "do_not_generate_950000": True,
        "do_not_retag_v030": True,
        "identities": {
            "mix_freeze_version": CYCLE8_MIX_FREEZE_VERSION,
            "mix_freeze_hash": mix_freeze_hash(),
            "mix_confirmation_scorecard_version": CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION,
            "mix_confirmation_scorecard_hash": _MIX_CONFIRMATION_SCORECARD_HASH,
            "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_HASH,
            "gate_v2_hash": CYCLE8_PUBLISHABILITY_GATE_V2_HASH,
            "gate_v2_confirmation_scorecard_hash": CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH,
            "product_contract_hash": FROZEN_PRODUCT_CONTRACT_HASH,
        },
        "live": {
            "process_text_equals_mix": process_text(_AUDIT_SOURCE) == transformed,
            "visible_projection_equals_source": project_visible_v1(transformed) == _AUDIT_SOURCE,
            "approved_carriers": sorted(product_approved_carriers_v1()),
            "supported_domain": is_supported_product_domain_v1(_AUDIT_SOURCE),
            "mixed_unicode_processed": process_text(mixed) != mixed,
            "no_letter_identity": process_text("123.") == "123.",
            "already_mixed_identity": process_text(transformed) == transformed,
            "mn_strip_does_not_restore_source": strip_nonspacing_marks(transformed) != _AUDIT_SOURCE,
            "di_strip_does_not_restore_source": strip_default_ignorable(transformed) != _AUDIT_SOURCE,
        },
        "notes": (
            "Product authorization of dual-layer u034f-ufe00-cc-letter-alt-v1. "
            "Mark carriers plus Cc residuals keep Mn-strip and default-ignorable-strip from restoring the source. "
            "ASCII letter sites are processed even when the surrounding text contains non-ASCII. "
            "Historical Gate v2 confirmation remains the frozen GPT-2 evidence for the prior mark-only arm."
        ),
    }
    return {**payload, "authorization_hash": sha256_json(payload)}


def write_product_authorization_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(PRODUCT_AUTHORIZATION_PATH)
    payload = product_authorization_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_product_authorization(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(PRODUCT_AUTHORIZATION_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_product_authorization_committed() -> None:
    path = Path(PRODUCT_AUTHORIZATION_PATH)
    if not path.is_file():
        raise ValueError("product authorization spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "authorization_hash"}
    digest = sha256_json(body)
    if disk.get("authorization_hash") != digest:
        raise ValueError("product authorization spec hash mismatch")
    if PRODUCT_AUTHORIZATION_HASH == "0" * 64:
        raise ValueError("product authorization spec hash is not frozen")
    if digest != PRODUCT_AUTHORIZATION_HASH:
        raise ValueError("product authorization spec hash is not the frozen digest")
    live = product_authorization_payload()
    if live != disk:
        raise ValueError("product authorization spec does not match the live payload")
    if disk["product_authorized"] is not True:
        raise ValueError("product authorization spec must authorize")
    if disk["cli_algorithm_version"] != "release-cli-v6":
        raise ValueError("product authorization must use release-cli-v6")
    if disk["mix_sanitizer_gate_v1"] != "PASS":
        raise ValueError("product authorization must record the durable sanitizer gate PASS")
    if disk["identities"]["mix_freeze_hash"] != _MIX_FREEZE_HASH:
        raise ValueError("product authorization must pin the mix freeze hash")
    if disk["identities"]["gate_v2_hash"] != CYCLE8_PUBLISHABILITY_GATE_V2_HASH:
        raise ValueError("product authorization must pin Gate v2")
    if release_transform_registry().rules != ():
        raise ValueError("release_transform_registry must stay empty")
    if product_approved_carriers_v1() != frozenset(LETTER_MIX_APPROVED_CARRIERS):
        raise ValueError("product_approved_carriers_v1 must be the durable mix carriers")
    if process_text(_AUDIT_SOURCE) != apply_letter_alternating_mix(_AUDIT_SOURCE):
        raise ValueError("authorized CLI must equal apply_letter_alternating_mix")
    if disk["live"]["mn_strip_does_not_restore_source"] is not True:
        raise ValueError("authorized mix must resist Mn-strip source restoration")
    if disk["live"]["di_strip_does_not_restore_source"] is not True:
        raise ValueError("authorized mix must resist default-ignorable-strip source restoration")
    assert_gate_v2_committed()
