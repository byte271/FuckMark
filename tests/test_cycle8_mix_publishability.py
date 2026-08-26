import json
from pathlib import Path

from fuckmark.cli import RELEASE_CLI_ALGORITHM_VERSION, process_text
from fuckmark.cycle8.compare import CYCLE8_LETTER_ALT_ARM_ID
from fuckmark.cycle8.mix_confirmation import CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
from fuckmark.cycle8.mix_freeze import CYCLE8_MIX_FREEZE_VERSION, mix_freeze_hash
from fuckmark.cycle8.publishability import (
    CYCLE8_MIX_PUBLISHABILITY_HASH,
    CYCLE8_MIX_PUBLISHABILITY_PATH,
    CYCLE8_MIX_PUBLISHABILITY_VERSION,
    assert_mix_publishability_committed,
    mix_is_product_publishable,
    mix_publishability_hash,
    mix_publishability_payload,
)
from fuckmark.hashing import sha256_json
from fuckmark.product.contract import FROZEN_PRODUCT_CONTRACT_HASH
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


_FREEZE_HASH = "2286aa201bd9cb70136f2895740489136aa1ba7cfd9471c6e233fe201af41986"
_SCORECARD_HASH = "a4911189af7f38d34252452821d90df1188bfe05025fe33c028c4b670eecbcce"


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_MIX_PUBLISHABILITY_PATH).read_text(encoding="utf-8"))


def test_mix_publishability_spec_fail_closes_product_promotion() -> None:
    disk = _load()
    body = {key: value for key, value in disk.items() if key != "report_hash"}
    payload = mix_publishability_payload()
    assert body == payload
    assert disk["report_hash"] == mix_publishability_hash() == sha256_json(payload) == CYCLE8_MIX_PUBLISHABILITY_HASH
    assert disk["algorithm_version"] == CYCLE8_MIX_PUBLISHABILITY_VERSION
    assert disk["mechanism_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert disk["freeze_version"] == CYCLE8_MIX_FREEZE_VERSION
    assert disk["confirmation_scorecard_version"] == CYCLE8_MIX_CONFIRMATION_SCORECARD_VERSION
    assert disk["cli_algorithm_version"] == RELEASE_CLI_ALGORITHM_VERSION
    assert disk["product_publishable"] is False
    assert disk["product_authorized"] is False
    assert disk["release_registry_empty"] is True
    assert disk["product_approved_carriers_v1"] == []
    assert disk["do_not_generate_950000"] is True
    assert disk["do_not_retag_v030"] is True
    assert mix_is_product_publishable() is False
    assert_mix_publishability_committed()
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset()
    assert process_text("I do not agree.") == "I do not agree."


def test_mix_publishability_gates_match_measured_evidence() -> None:
    payload = mix_publishability_payload()
    gates = {gate["id"]: gate for gate in payload["gates"]}
    assert tuple(gates) == (
        "reproducibility",
        "visibility_invariance",
        "software_compatibility",
        "sanitizer_weaknesses",
        "cross_detector_generalization",
    )
    assert gates["reproducibility"]["verdict"] == "PASS"
    assert gates["visibility_invariance"]["verdict"] == "PASS"
    assert gates["software_compatibility"]["verdict"] == "FAIL"
    assert gates["sanitizer_weaknesses"]["verdict"] == "FAIL"
    assert gates["cross_detector_generalization"]["verdict"] == "FAIL"
    assert all(gate["product_blocking"] is True for gate in payload["gates"])
    checks = {gate["id"]: {check["id"]: check["verdict"] for check in gate["checks"]} for gate in payload["gates"]}
    assert checks["reproducibility"]["confirmation_zero_of_192"] == "PASS"
    assert checks["visibility_invariance"]["visible_projection"] == "PASS"
    assert checks["visibility_invariance"]["webkit_safari"] == "UNKNOWN"
    assert checks["software_compatibility"]["utf8_and_json"] == "PASS"
    assert checks["software_compatibility"]["latin1"] == "FAIL"
    assert checks["software_compatibility"]["literal_search"] == "FAIL"
    assert checks["software_compatibility"]["protected_url_email"] == "PASS"
    assert checks["sanitizer_weaknesses"]["frozen_sanitizers"] == "PASS"
    assert checks["sanitizer_weaknesses"]["mn_strip"] == "FAIL"
    assert checks["sanitizer_weaknesses"]["default_ignorable_strip"] == "FAIL"
    assert checks["sanitizer_weaknesses"]["nfkd"] == "PASS"
    assert checks["cross_detector_generalization"]["confirmed_families"] == "FAIL"
    assert checks["cross_detector_generalization"]["second_model"] == "FAIL"
    assert payload["identities"]["mix_freeze_hash"] == mix_freeze_hash() == _FREEZE_HASH
    assert payload["identities"]["confirmation_scorecard_hash"] == _SCORECARD_HASH
    assert payload["identities"]["product_contract_hash"] == FROZEN_PRODUCT_CONTRACT_HASH
    assert payload["confirmation"]["transformed_wm"] == "0/192"
    assert payload["confirmation"]["transformed_uw"] == "0/192"
    assert payload["confirmation"]["visible"] == "192/192"
