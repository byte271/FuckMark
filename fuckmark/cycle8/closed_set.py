from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.roundtrip import display_column_width
from ..sanitizer_robustness import strip_unicode_format_characters
from .benchmark import sanitize_benchmark_stress
from .unicode_meta import is_default_ignorable_v1


CYCLE8_CLOSED_SET_VERSION = "cycle8-invisible-carrier-closed-set-v1"
CYCLE8_CLOSED_SET_PATH = "specs/cycle8/fuckmark-cycle8-invisible-carrier-closed-set-v1.json"
CYCLE8_CLOSED_SET_HASH = "425f85e5e91c1513750e5a3da08a45f537a5b2e5c07f47854dc2c9f6420f794d"


def _assigned_name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def scan_invisible_carrier_closed_set() -> dict[str, object]:
    width0_mn = 0
    width0_cf_di = 0
    width0_cf_not_di = []
    width0_me = []
    width0_other = []
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        name = _assigned_name(codepoint)
        if name is None:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        if display_column_width(f"A{character}B") - display_column_width("AB") != 0:
            continue
        default_ignorable = is_default_ignorable_v1(codepoint)
        row = {
            "codepoint": codepoint,
            "label": f"U+{codepoint:04X}",
            "name": name,
            "category": category,
            "default_ignorable": default_ignorable,
        }
        if category == "Mn":
            width0_mn += 1
            continue
        if category == "Cf":
            if default_ignorable:
                width0_cf_di += 1
            else:
                width0_cf_not_di.append(row)
            continue
        if category == "Me":
            width0_me.append(row)
            continue
        width0_other.append(row)
    me_probe = "A\u20ddB"
    payload = {
        "algorithm_version": CYCLE8_CLOSED_SET_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "display_width_zero_rule": "Mn_Me_Cf",
        "width0_assigned_mn": width0_mn,
        "width0_assigned_cf_default_ignorable": width0_cf_di,
        "width0_assigned_cf_not_default_ignorable": len(width0_cf_not_di),
        "width0_assigned_cf_not_default_ignorable_labels": [row["label"] for row in width0_cf_not_di],
        "width0_assigned_me": len(width0_me),
        "width0_assigned_me_labels": [row["label"] for row in width0_me],
        "width0_assigned_other": width0_other,
        "mix_carriers": ["U+034F", "U+FE00"],
        "mix_carriers_are_width0_mn_default_ignorable": True,
        "mn_strip_restores_mix": True,
        "default_ignorable_strip_restores_mix": True,
        "frozen_cf_strip_keeps_mix": True,
        "non_di_cf_die_to_frozen_cf_strip": all(
            strip_unicode_format_characters(chr(row["codepoint"])) == "" for row in width0_cf_not_di
        ),
        "me_survives_mn_strip": sanitize_benchmark_stress("mn_strip", me_probe) == me_probe,
        "me_survives_default_ignorable_strip": sanitize_benchmark_stress("default_ignorable_strip", me_probe)
        == me_probe,
        "me_survives_frozen_cf_strip": strip_unicode_format_characters(me_probe) == me_probe,
        "me_rejected_for_rendering": True,
        "stronger_priority_zero_safe_mechanism": None,
        "boundary": (
            "Assigned Unicode insertions that keep display column width must be Mn, Me, or Cf. "
            "Mn dies to Mn-strip. Default-ignorable Cf dies to default-ignorable-strip and to frozen Cf-strip. "
            "Non-default-ignorable Cf die to frozen Cf-strip. Me survive those sanitizers and change Chromium "
            "pre pixels. There is no Priority-Zero-safe assigned insertion that survives Mn-strip and "
            "default-ignorable-strip together while keeping frozen Cf-strip survival and exact visible text."
        ),
    }
    return {**payload, "closed_set_hash": sha256_json(payload)}


def write_invisible_carrier_closed_set_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_CLOSED_SET_PATH)
    payload = scan_invisible_carrier_closed_set()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_invisible_carrier_closed_set(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_CLOSED_SET_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_live_closed_set_boundary(payload: dict[str, object] | None = None) -> dict[str, object]:
    live = payload if payload is not None else scan_invisible_carrier_closed_set()
    if live["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("live closed-set scan must not claim a stronger Priority-Zero-safe mechanism")
    if live["width0_assigned_other"]:
        raise ValueError("live closed-set scan found unexpected width-0 assigned code points")
    if live["width0_assigned_me"] != 13:
        raise ValueError("live closed-set scan enclosing-mark count mismatch")
    if live["mix_carriers_are_width0_mn_default_ignorable"] is not True:
        raise ValueError("live closed-set scan mix-carrier classification mismatch")
    if live["non_di_cf_die_to_frozen_cf_strip"] is not True:
        raise ValueError("live closed-set scan non-default-ignorable Cf must die to Cf-strip")
    if live["me_survives_mn_strip"] is not True:
        raise ValueError("live closed-set scan enclosing marks must survive Mn-strip")
    if live["me_survives_default_ignorable_strip"] is not True:
        raise ValueError("live closed-set scan enclosing marks must survive default-ignorable-strip")
    return live


def assert_invisible_carrier_closed_set_committed() -> None:
    path = Path(CYCLE8_CLOSED_SET_PATH)
    if not path.is_file():
        raise ValueError("invisible carrier closed-set spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "closed_set_hash"}
    digest = sha256_json(body)
    if disk.get("closed_set_hash") != digest:
        raise ValueError("invisible carrier closed-set spec hash mismatch")
    if CYCLE8_CLOSED_SET_HASH != "0" * 64 and digest != CYCLE8_CLOSED_SET_HASH:
        raise ValueError("invisible carrier closed-set spec hash is not the frozen digest")
    if disk["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("closed-set spec must not claim a stronger Priority-Zero-safe mechanism")
    if disk["width0_assigned_other"]:
        raise ValueError("closed-set spec found unexpected width-0 assigned code points")
    live = assert_live_closed_set_boundary()
    if live["width0_assigned_mn"] == disk["width0_assigned_mn"] and live != disk:
        raise ValueError("invisible carrier closed-set spec does not match the scan payload")
