from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.roundtrip import display_column_width
from ..sanitizer_robustness import strip_unicode_format_characters
from .benchmark import sanitize_benchmark_stress, strip_default_ignorable, strip_nonspacing_marks
from .closed_set import CYCLE8_CLOSED_SET_HASH
from .feasibility import CYCLE8_FEASIBILITY_HASH
from .sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from .unicode_meta import is_default_ignorable_v1


CYCLE8_CONTROL_CARRIER_VERSION = "cycle8-control-carrier-scan-v1"
CYCLE8_CONTROL_CARRIER_PATH = "specs/cycle8/fuckmark-cycle8-control-carrier-scan-v1.json"
CYCLE8_CONTROL_CARRIER_HASH = "1e63bd5d39f04ba1f7d3634c60cea1f218e118590dd8d09b55ffb449908010e4"
LAYOUT_CONTROL_CODEPOINTS = (0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x0085, 0x2028, 0x2029)
HOSTILE_CONTROL_CODEPOINTS = (0x0000,)
ISO6429_DEVICE_CONTROL_CODEPOINTS = (0x0084, 0x008D, 0x008E, 0x008F, 0x0090, 0x0098, 0x009B, 0x009C, 0x009D, 0x009E, 0x009F)
CONTROL_MIX_ELIGIBLE_CODEPOINTS = (0x007F, *range(0x0080, 0x0085), *range(0x0086, 0x00A0))
CONTROL_CLASS_PROBE_CODEPOINTS = tuple(list(range(0x0000, 0x0020)) + [0x007F] + list(range(0x0080, 0x00A0)))
REJECTED_EMPTY_GLYPH_PROBES = (0x1680, 0x2800, 0xFFFD, 0xFFFE, 0xFFFF, 0xFDD0, 0xE000, 0xF8FF)


def iter_cc_probe_codepoints() -> tuple[int, ...]:
    return CONTROL_CLASS_PROBE_CODEPOINTS


def is_layout_control(codepoint: int) -> bool:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    return codepoint in LAYOUT_CONTROL_CODEPOINTS


def is_hostile_control(codepoint: int) -> bool:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    return codepoint in HOSTILE_CONTROL_CODEPOINTS


def is_iso6429_device_control(codepoint: int) -> bool:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    return codepoint in ISO6429_DEVICE_CONTROL_CODEPOINTS


def is_control_mix_eligible(codepoint: int) -> bool:
    if not isinstance(codepoint, int) or isinstance(codepoint, bool):
        raise TypeError("codepoint must be an integer")
    return codepoint in CONTROL_MIX_ELIGIBLE_CODEPOINTS


def control_display_column_width(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    width = 0
    for character in text:
        codepoint = ord(character)
        if codepoint in CONTROL_MIX_ELIGIBLE_CODEPOINTS:
            continue
        if unicodedata.category(character) in {"Mn", "Me", "Cf"}:
            continue
        if character in {"\n", "\r"}:
            continue
        width += 1
    return width


def apply_required_sanitizer_bundle(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = strip_nonspacing_marks(cleaned)
    cleaned = strip_default_ignorable(cleaned)
    cleaned = strip_unicode_format_characters(cleaned)
    return cleaned


def required_sanitizers_keep(text: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if strip_nonspacing_marks(text) != text:
        return False
    if strip_default_ignorable(text) != text:
        return False
    if strip_unicode_format_characters(text) != text:
        return False
    if unicodedata.normalize("NFC", text) != text:
        return False
    if unicodedata.normalize("NFKC", text) != text:
        return False
    if unicodedata.normalize("NFKD", text) != text:
        return False
    if apply_required_sanitizer_bundle(text) != text:
        return False
    if any(sanitize_cycle8_scale_variant(variant, text) != text for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS):
        return False
    if any(sanitize_benchmark_stress(variant, text) != text for variant in ("mn_strip", "default_ignorable_strip", "nfkd")):
        return False
    return True


def _probe_row(codepoint: int) -> dict[str, object]:
    character = chr(codepoint)
    category = unicodedata.category(character)
    width_delta = display_column_width(f"A{character}B") - display_column_width("AB")
    research_width_delta = control_display_column_width(f"A{character}B") - control_display_column_width("AB")
    return {
        "codepoint": codepoint,
        "label": f"U+{codepoint:04X}",
        "category": category,
        "default_ignorable": is_default_ignorable_v1(codepoint),
        "layout_control": is_layout_control(codepoint),
        "hostile_control": is_hostile_control(codepoint),
        "eligible": is_control_mix_eligible(codepoint),
        "required_sanitizers_keep": required_sanitizers_keep(f"A{character}B"),
        "product_display_width_delta": width_delta,
        "research_display_width_delta": research_width_delta,
    }


def scan_control_carrier_class() -> dict[str, object]:
    rows = [_probe_row(codepoint) for codepoint in CONTROL_CLASS_PROBE_CODEPOINTS]
    eligible = [row for row in rows if row["eligible"] is True]
    layout = [row["label"] for row in rows if row["layout_control"] is True]
    hostile = [row["label"] for row in rows if row["hostile_control"] is True]
    tofu = [
        row["label"]
        for row in rows
        if row["category"] == "Cc"
        and row["eligible"] is False
        and row["layout_control"] is False
        and row["hostile_control"] is False
    ]
    empty_glyph = []
    for codepoint in REJECTED_EMPTY_GLYPH_PROBES:
        character = chr(codepoint)
        empty_glyph.append(
            {
                "label": f"U+{codepoint:04X}",
                "category": unicodedata.category(character),
                "default_ignorable": is_default_ignorable_v1(codepoint),
                "required_sanitizers_keep": required_sanitizers_keep(f"A{character}B"),
                "product_display_width_delta": display_column_width(f"A{character}B") - display_column_width("AB"),
            }
        )
    payload = {
        "algorithm_version": CYCLE8_CONTROL_CARRIER_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "search_space": "general_category_Cc_plus_empty_glyph_probes",
        "assigned_width0_class": "cycle8-invisible-carrier-closed-set-v1",
        "assigned_width0_closed_set_hash": CYCLE8_CLOSED_SET_HASH,
        "assigned_width0_feasibility_hash": CYCLE8_FEASIBILITY_HASH,
        "assigned_width0_stronger_mechanism": None,
        "layout_control_codepoints": [f"U+{codepoint:04X}" for codepoint in LAYOUT_CONTROL_CODEPOINTS],
        "hostile_control_codepoints": [f"U+{codepoint:04X}" for codepoint in HOSTILE_CONTROL_CODEPOINTS],
        "iso6429_device_control_codepoints": [f"U+{codepoint:04X}" for codepoint in ISO6429_DEVICE_CONTROL_CODEPOINTS],
        "eligible_codepoints": [f"U+{codepoint:04X}" for codepoint in CONTROL_MIX_ELIGIBLE_CODEPOINTS],
        "eligible_count": len(CONTROL_MIX_ELIGIBLE_CODEPOINTS),
        "cc_probe_count": len(rows),
        "eligible_required_sanitizers_keep": all(row["required_sanitizers_keep"] is True for row in eligible),
        "eligible_are_cc": all(row["category"] == "Cc" for row in eligible),
        "eligible_not_default_ignorable": all(row["default_ignorable"] is False for row in eligible),
        "eligible_product_width_delta_one": all(row["product_display_width_delta"] == 1 for row in eligible),
        "eligible_research_width_delta_zero": all(row["research_display_width_delta"] == 0 for row in eligible),
        "iso6429_device_controls_remain_in_eligible_set": all(
            codepoint in CONTROL_MIX_ELIGIBLE_CODEPOINTS for codepoint in ISO6429_DEVICE_CONTROL_CODEPOINTS
        ),
        "product_display_width_proxy": "FAIL",
        "terminal_pixels": "UNKNOWN",
        "layout_control_labels": layout,
        "hostile_control_labels": hostile,
        "c0_non_layout_non_hostile_not_eligible": tofu,
        "empty_glyph_probes": empty_glyph,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "boundary": (
            "Assigned width-0 insertions remain Mn, Me, or Cf and stay closed. "
            "The next insertion class is general category Cc. Layout controls and NUL "
            "are excluded. DEL and C1 except NEXT LINE survive Mn-strip, "
            "default-ignorable-strip, Cf-strip, NFC, NFKC, NFKD, frozen Cycle 6/7 "
            "sanitizers, and the combination of those arms. Product display width still "
            "counts them. Research width skips the eligible set because Chromium pre, "
            "textarea, and contenteditable pixels match the source. ISO-6429 C1 device "
            "controls including CSI remain in the measured eligible set. That ordinary-text "
            "and terminal risk blocks product authorization and does not rewrite mix "
            "sanitizer FAIL. Terminal pixels stay UNKNOWN."
        ),
    }
    return {**payload, "control_carrier_hash": sha256_json(payload)}


def write_control_carrier_scan_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_CONTROL_CARRIER_PATH)
    payload = scan_control_carrier_class()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_control_carrier_scan(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_CONTROL_CARRIER_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_control_carrier_scan_committed() -> None:
    path = Path(CYCLE8_CONTROL_CARRIER_PATH)
    if not path.is_file():
        raise ValueError("control carrier scan spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "control_carrier_hash"}
    digest = sha256_json(body)
    if disk.get("control_carrier_hash") != digest:
        raise ValueError("control carrier scan spec hash mismatch")
    if CYCLE8_CONTROL_CARRIER_HASH != "0" * 64 and digest != CYCLE8_CONTROL_CARRIER_HASH:
        raise ValueError("control carrier scan spec hash is not the frozen digest")
    if disk["product_authorized"] is True:
        raise ValueError("control carrier scan must not product-authorize the mechanism")
    if disk["assigned_width0_stronger_mechanism"] is not None:
        raise ValueError("control carrier scan must not reopen the assigned width-0 closed set")
    if disk["mix_gate_not_rewritten"] is not True:
        raise ValueError("control carrier scan must not rewrite the mix sanitizer gate")
    live = scan_control_carrier_class()
    if live["control_carrier_hash"] != disk["control_carrier_hash"]:
        raise ValueError("control carrier scan spec does not match the scan payload")
    if live["eligible_required_sanitizers_keep"] is not True:
        raise ValueError("control carrier eligible set must survive required sanitizers")
    if live["iso6429_device_controls_remain_in_eligible_set"] is not True:
        raise ValueError("measured eligible set must keep ISO-6429 device controls")
    if live["product_display_width_proxy"] != "FAIL":
        raise ValueError("product display-width proxy must remain FAIL")
    if live["terminal_pixels"] != "UNKNOWN":
        raise ValueError("terminal pixels must remain UNKNOWN")
