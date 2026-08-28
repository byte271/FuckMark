from pathlib import Path

from fuckmark.cli import RELEASE_CLI_ALGORITHM_VERSION, process_text
from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.gate_v2 import (
    CYCLE8_PUBLISHABILITY_GATE_V2_HASH,
    GATE_V2_STATUS_AUTHORIZED,
    assert_gate_v2_committed,
    load_gate_v2,
)
from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, LETTER_MIX_MECHANISM_ID, apply_letter_alternating_mix
from fuckmark.hashing import sha256_json
from fuckmark.product.authorization import (
    PRODUCT_AUTHORIZATION_HASH,
    PRODUCT_AUTHORIZATION_PATH,
    PRODUCT_AUTHORIZATION_VERSION,
    assert_product_authorization_committed,
    load_product_authorization,
    product_authorization_payload,
)
from fuckmark.product.visible_projection import product_approved_carriers_v1, project_visible_v1
from fuckmark.transforms.registry import release_transform_registry


def test_product_authorization_spec_is_committed_and_live() -> None:
    assert Path(PRODUCT_AUTHORIZATION_PATH).is_file()
    assert_product_authorization_committed()
    disk = load_product_authorization()
    live = product_authorization_payload()
    assert disk == live
    body = {key: value for key, value in disk.items() if key != "authorization_hash"}
    assert disk["authorization_hash"] == sha256_json(body) == PRODUCT_AUTHORIZATION_HASH
    assert disk["algorithm_version"] == PRODUCT_AUTHORIZATION_VERSION
    assert disk["product_authorized"] is True
    assert disk["mechanism_id"] == LETTER_MIX_MECHANISM_ID
    assert disk["cli_algorithm_version"] == RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v6"
    assert disk["mix_sanitizer_gate_v1"] == "PASS"
    assert disk["required_sanitizer_bundle_not_weakened"] is True
    assert disk["release_registry_empty"] is True
    assert disk["identities"]["gate_v2_hash"] == CYCLE8_PUBLISHABILITY_GATE_V2_HASH
    assert disk["live"]["process_text_equals_mix"] is True
    assert disk["live"]["mn_strip_does_not_restore_source"] is True
    assert disk["live"]["di_strip_does_not_restore_source"] is True
    assert disk["live"]["mixed_unicode_processed"] is True
    assert_gate_v2_committed()
    gate = load_gate_v2()
    assert gate["status"] == GATE_V2_STATUS_AUTHORIZED
    assert gate["product_authorized"] is True
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset(LETTER_MIX_APPROVED_CARRIERS)
    source = "I do not agree."
    applied = process_text(source)
    assert applied == apply_letter_alternating_mix(source)
    assert project_visible_v1(applied) == source
    assert strip_nonspacing_marks(applied) != source
    assert strip_default_ignorable(applied) != source
    assert process_text("123.") == "123."
    assert process_text("I do not agree " + chr(0x00E9) + ".") != "I do not agree " + chr(0x00E9) + "."
    assert process_text(applied) == applied
