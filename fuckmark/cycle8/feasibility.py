from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.roundtrip import display_column_width
from ..sanitizer_robustness import strip_unicode_format_characters
from .unicode_meta import _BIDI_OVERRIDE, _VISIBLE_CATEGORIES, is_default_ignorable_v1


CYCLE8_FEASIBILITY_VERSION = "cycle8-invisible-carrier-feasibility-v1"
CYCLE8_FEASIBILITY_PATH = "specs/cycle8/fuckmark-cycle8-invisible-carrier-feasibility-v1.json"
CYCLE8_FEASIBILITY_HASH = "edaa10a576def25a4e0edcdd23b74fecc97dca650835e538ad5c7ff14eb31483"
ENCLOSING_MARK_PROBE = 0x20DD


def _assigned_name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def scan_invisible_carrier_feasibility() -> dict[str, object]:
    visible_or_control = 0
    format_count = 0
    nonspacing_count = 0
    enclosing = []
    other = []
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        name = _assigned_name(codepoint)
        if name is None:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        bidirectional = unicodedata.bidirectional(character)
        if (
            category in _VISIBLE_CATEGORIES
            or category in {"Cc", "Cs"}
            or bidirectional in _BIDI_OVERRIDE
        ):
            visible_or_control += 1
            continue
        if category == "Cf":
            format_count += 1
            continue
        if category == "Mn":
            nonspacing_count += 1
            continue
        width_delta = display_column_width(f"A{character}B") - display_column_width("AB")
        nfc_stable = unicodedata.normalize("NFC", character) == character
        nfkc_stable = unicodedata.normalize("NFKC", character) == character
        cf_survives = strip_unicode_format_characters(character) == character
        default_ignorable = is_default_ignorable_v1(codepoint)
        row = {
            "codepoint": codepoint,
            "label": f"U+{codepoint:04X}",
            "name": name,
            "category": category,
            "default_ignorable": default_ignorable,
            "nfc_stable": nfc_stable,
            "nfkc_stable": nfkc_stable,
            "cf_strip_survives": cf_survives,
            "display_width_delta": width_delta,
        }
        if category == "Me":
            enclosing.append(row)
            continue
        other.append(row)
    payload = {
        "algorithm_version": CYCLE8_FEASIBILITY_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "search_space": "assigned_unicode_scalar_values",
        "assigned_visible_or_control": visible_or_control,
        "assigned_format_cf": format_count,
        "assigned_nonspacing_mn": nonspacing_count,
        "assigned_enclosing_me": len(enclosing),
        "enclosing_me_labels": [row["label"] for row in enclosing],
        "other_non_mn_cf_count": len(other),
        "other_non_mn_cf": other,
        "survives_mn_cf_and_default_ignorable_while_invisible": False,
        "enclosing_marks_rejected_rendering": True,
        "enclosing_mark_probe": f"U+{ENCLOSING_MARK_PROBE:04X}",
        "mix_carriers_are_mn_and_default_ignorable": True,
        "stronger_invisible_product_mechanism": None,
        "boundary": (
            "Tokenizer-disruptive invisible insertions that keep exact visible English text "
            "live in Mn or Cf default-ignorable code points. Cf dies to frozen Cf-strip. "
            "Mn default-ignorables survive frozen Cycle 6/7 sanitizers and die to Mn-strip "
            "and default-ignorable-strip. Enclosing marks survive those stress sanitizers "
            "but change rendered pixels."
        ),
    }
    return {**payload, "feasibility_hash": sha256_json(payload)}


def load_invisible_carrier_feasibility(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_FEASIBILITY_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def write_invisible_carrier_feasibility_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_FEASIBILITY_PATH)
    payload = scan_invisible_carrier_feasibility()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def assert_invisible_carrier_feasibility_committed() -> None:
    path = Path(CYCLE8_FEASIBILITY_PATH)
    if not path.is_file():
        raise ValueError("invisible carrier feasibility spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = scan_invisible_carrier_feasibility()
    if disk != payload:
        raise ValueError("invisible carrier feasibility spec does not match the scan payload")
    digest = str(payload["feasibility_hash"])
    if CYCLE8_FEASIBILITY_HASH != "0" * 64 and digest != CYCLE8_FEASIBILITY_HASH:
        raise ValueError("invisible carrier feasibility spec hash is not the frozen digest")
    if payload["stronger_invisible_product_mechanism"] is not None:
        raise ValueError("feasibility spec must not claim a stronger invisible product mechanism")
    if payload["other_non_mn_cf_count"] != 0:
        raise ValueError("feasibility spec found unexpected non-Mn non-Cf assigned code points")
    if payload["survives_mn_cf_and_default_ignorable_while_invisible"] is not False:
        raise ValueError("feasibility spec must not claim an invisible Mn-strip survivor")
