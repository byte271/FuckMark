import json
from pathlib import Path

from fuckmark.cli import process_text
from fuckmark.cycle8.closed_set import CYCLE8_CLOSED_SET_HASH
from fuckmark.cycle8.control_carrier import CYCLE8_CONTROL_CARRIER_HASH
from fuckmark.cycle8.feasibility import CYCLE8_FEASIBILITY_HASH
from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.cycle8.post_sanitizer_class import (
    CYCLE8_POST_SANITIZER_CLASS_HASH,
    CYCLE8_POST_SANITIZER_CLASS_PATH,
    CYCLE8_POST_SANITIZER_CLASS_VERSION,
    assert_post_sanitizer_mechanism_class_committed,
    post_sanitizer_mechanism_class_payload,
)
from fuckmark.cycle8.publishability import CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH, mix_is_product_publishable
from fuckmark.hashing import sha256_json
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_POST_SANITIZER_CLASS_PATH).read_text(encoding="utf-8"))


def test_post_sanitizer_mechanism_class_has_no_conjunction_survivor() -> None:
    disk = _load()
    payload = post_sanitizer_mechanism_class_payload()
    body = {key: value for key, value in disk.items() if key != "class_hash"}
    assert disk["class_hash"] == sha256_json(body) == CYCLE8_POST_SANITIZER_CLASS_HASH
    assert disk["algorithm_version"] == CYCLE8_POST_SANITIZER_CLASS_VERSION
    assert disk["does_not_repeat_assigned_width0_scan"] is True
    assert disk["assigned_width0_closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert disk["assigned_width0_feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert disk["control_carrier_hash"] == CYCLE8_CONTROL_CARRIER_HASH
    assert disk["mix_publishability_hash"] == CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH
    assert disk["mix_sanitizer_gate"] == "FAIL"
    assert disk["control_carrier_required_sanitizers_keep"] is True
    assert disk["control_carrier_chromium_pre_pixels"] == "HOST_DEPENDENT"
    assert disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] == []
    assert disk["stronger_priority_zero_safe_mechanism"] is None
    assert disk["product_authorized"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert payload == disk
    assert_post_sanitizer_mechanism_class_committed()
    by_id = {row["id"]: row for row in disk["classes"]}
    assert by_id["mn_default_ignorable_insertion"]["required_sanitizers"] == "FAIL"
    assert by_id["cc_del_c1_insertion"]["required_sanitizers"] == "PASS"
    assert by_id["cc_del_c1_insertion"]["chromium_pre"] == "HOST_DEPENDENT"
    assert by_id["cc_del_c1_insertion"]["ordinary_plain_text"] == "FAIL"
    assert by_id["me_enclosing_insertion"]["chromium_pre"] == "REJECTED"
    assert mix_is_product_publishable() is True
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert product_approved_carriers_v1() == frozenset(LETTER_MIX_APPROVED_CARRIERS)
    assert release_transform_registry().rules == ()
    for row in disk["classes"]:
        conjunction = (
            row["required_sanitizers"] == "PASS"
            and row["chromium_pre"] == "VERIFIED"
            and row["ordinary_plain_text"] == "PASS"
        )
        assert conjunction is False
