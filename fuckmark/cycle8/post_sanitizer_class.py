from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from .closed_set import CYCLE8_CLOSED_SET_HASH
from .control_carrier import CYCLE8_CONTROL_CARRIER_HASH, scan_control_carrier_class
from .feasibility import CYCLE8_FEASIBILITY_HASH
from .publishability import CYCLE8_MIX_PUBLISHABILITY_HASH


CYCLE8_POST_SANITIZER_CLASS_VERSION = "cycle8-post-sanitizer-mechanism-class-v1"
CYCLE8_POST_SANITIZER_CLASS_PATH = "specs/cycle8/fuckmark-cycle8-post-sanitizer-mechanism-class-v1.json"
CYCLE8_POST_SANITIZER_CLASS_HASH = "a13f935834b399bd2dda6c543ad4cf646bcfc2f6426ca866b08ae8cf51346bf3"


def _class_row(
    class_id: str,
    *,
    required_sanitizers: str,
    chromium_pre: str,
    ordinary_plain_text: str,
    product: str,
    reason: str,
    examples: tuple[str, ...],
) -> dict[str, object]:
    return {
        "id": class_id,
        "examples": list(examples),
        "required_sanitizers": required_sanitizers,
        "chromium_pre": chromium_pre,
        "ordinary_plain_text": ordinary_plain_text,
        "product": product,
        "reason": reason,
    }


def post_sanitizer_mechanism_class_payload() -> dict[str, object]:
    control = scan_control_carrier_class()
    classes = (
        _class_row(
            "mn_default_ignorable_insertion",
            required_sanitizers="FAIL",
            chromium_pre="VERIFIED_ON_RESEARCH_HOST",
            ordinary_plain_text="PASS",
            product="FAIL",
            reason="Mix lives here. Mn-strip and default-ignorable-strip restore the source.",
            examples=("U+034F", "U+FE00"),
        ),
        _class_row(
            "cf_format_insertion",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="PASS",
            product="FAIL",
            reason="Frozen Cf-strip restores the source.",
            examples=("U+200C",),
        ),
        _class_row(
            "me_enclosing_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="All 13 enclosing marks change Chromium pre pixels.",
            examples=("U+20DD",),
        ),
        _class_row(
            "cc_del_c1_insertion",
            required_sanitizers="PASS",
            chromium_pre="HOST_DEPENDENT",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="GitHub Actions Chromium rejected the full apply. ISO-6429 device controls remain in the measured set.",
            examples=("U+007F", "U+0080", "U+009B"),
        ),
        _class_row(
            "cc_layout_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED_OR_LAYOUT",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="TAB, LF, VT, FF, CR, NEXT LINE, and line or paragraph separators change layout.",
            examples=("U+0009", "U+000A", "U+0085"),
        ),
        _class_row(
            "cc_nul_insertion",
            required_sanitizers="PASS",
            chromium_pre="VERIFIED_ON_RESEARCH_HOST",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="NUL is hostile to ordinary C-string text.",
            examples=("U+0000",),
        ),
        _class_row(
            "cc_c0_tofu_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="Most remaining C0 controls change Chromium pre pixels.",
            examples=("U+0001",),
        ),
        _class_row(
            "empty_glyph_or_pua_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="Braille blank, Ogham space, noncharacters, and BMP private-use probes change Chromium pre pixels.",
            examples=("U+2800", "U+1680", "U+E000"),
        ),
        _class_row(
            "homoglyph_or_compatibility_substitution",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="Homoglyphs are forbidden. NFKC collapses compatibility lookalikes.",
            examples=(),
        ),
        _class_row(
            "whitespace_or_visible_layout",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="Visible whitespace, punctuation, and letter changes are forbidden.",
            examples=("U+00A0",),
        ),
    )
    conjunction = [
        row["id"]
        for row in classes
        if row["required_sanitizers"] == "PASS"
        and row["chromium_pre"] == "VERIFIED"
        and row["ordinary_plain_text"] == "PASS"
    ]
    payload = {
        "algorithm_version": CYCLE8_POST_SANITIZER_CLASS_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "search_space": "post_required_sanitizer_unicode_string_transforms",
        "does_not_repeat_assigned_width0_scan": True,
        "assigned_width0_closed_set_hash": CYCLE8_CLOSED_SET_HASH,
        "assigned_width0_feasibility_hash": CYCLE8_FEASIBILITY_HASH,
        "control_carrier_hash": CYCLE8_CONTROL_CARRIER_HASH,
        "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_HASH,
        "mix_sanitizer_gate": "FAIL",
        "control_carrier_required_sanitizers_keep": control["eligible_required_sanitizers_keep"],
        "control_carrier_chromium_pre_pixels": control["chromium_pre_pixels"],
        "classes": list(classes),
        "conjunction_sanitizer_pass_chromium_verified_ordinary_text": conjunction,
        "stronger_priority_zero_safe_mechanism": None,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "boundary": (
            "Required sanitizers are Mn-strip, default-ignorable-strip, Cf-strip, NFC, NFKC, "
            "and combinations. Assigned width-0 insertions remain Mn, Me, or Cf. Mix lives in "
            "Mn plus default-ignorable and dies to those stress sanitizers. The measured "
            "sanitizer-surviving insertion classes are enclosing marks, control codes, empty "
            "glyphs, and private use. Enclosing marks and empty glyphs change Chromium pre "
            "pixels. Control-code insertion survives the required sanitizers and is Chromium "
            "host-dependent, with ISO-6429 device controls remaining in the measured set. "
            "No measured class is simultaneously sanitizer-surviving, Chromium-portable, "
            "ordinary plain text, and Priority-Zero safe. This does not rewrite mix sanitizer FAIL."
        ),
    }
    return {**payload, "class_hash": sha256_json(payload)}


def write_post_sanitizer_mechanism_class_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_CLASS_PATH)
    payload = post_sanitizer_mechanism_class_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_post_sanitizer_mechanism_class(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_CLASS_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_post_sanitizer_mechanism_class_committed() -> None:
    path = Path(CYCLE8_POST_SANITIZER_CLASS_PATH)
    if not path.is_file():
        raise ValueError("post-sanitizer mechanism class spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "class_hash"}
    digest = sha256_json(body)
    if disk.get("class_hash") != digest:
        raise ValueError("post-sanitizer mechanism class spec hash mismatch")
    if CYCLE8_POST_SANITIZER_CLASS_HASH != "0" * 64 and digest != CYCLE8_POST_SANITIZER_CLASS_HASH:
        raise ValueError("post-sanitizer mechanism class spec hash is not the frozen digest")
    if disk["product_authorized"] is True:
        raise ValueError("post-sanitizer class must not product-authorize a mechanism")
    if disk["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("post-sanitizer class must not claim a stronger Priority-Zero mechanism")
    if disk["mix_gate_not_rewritten"] is not True:
        raise ValueError("post-sanitizer class must not rewrite the mix sanitizer gate")
    if disk["mix_sanitizer_gate"] != "FAIL":
        raise ValueError("post-sanitizer class must keep mix sanitizer FAIL")
    if disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] != []:
        raise ValueError("post-sanitizer class must not claim a conjunction survivor")
    live = post_sanitizer_mechanism_class_payload()
    if live["class_hash"] != disk["class_hash"]:
        raise ValueError("post-sanitizer mechanism class spec does not match the live payload")
