from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.roundtrip import display_column_width
from .closed_set import CYCLE8_CLOSED_SET_HASH
from .control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from .feasibility import CYCLE8_FEASIBILITY_HASH
from .post_sanitizer_class import CYCLE8_POST_SANITIZER_CLASS_HASH
from .publishability import CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH
from .unicode_meta import DEFAULT_IGNORABLE_RANGES_V1, is_default_ignorable_v1


CYCLE8_POST_SANITIZER_EXTENDED_VERSION = "cycle8-post-sanitizer-extended-class-v1"
CYCLE8_POST_SANITIZER_EXTENDED_PATH = "specs/cycle8/fuckmark-cycle8-post-sanitizer-extended-class-v1.json"
CYCLE8_POST_SANITIZER_EXTENDED_HASH = "b1ca728142a217887ad327ddb226869b4343c898452240d731ab4c7d07f6f918"

UCD15_DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)
MC_CHROMIUM_PROBES = (0x302E, 0x302F, 0x093E, 0x09BE, 0x0BBE, 0x1B35, 0x09D7)
LM_CHROMIUM_PROBES = (0x02B9, 0x02BC, 0x02C0, 0xA71D)
DESIGNED_BLANK_PROBES = (0x1680, 0x2422, 0x2800, 0xA8F9, 0xFFFC, 0x1144E, 0x11C44, 0x11F48, 0x13441, 0x13442)
NFKC_COLLAPSE_PROBES = (0x00A0, 0x02B0, 0xFF9E, 0xFF9F)
HANGUL_JAMO_FILLER_SEQUENCE = "\u115f\u1160"
TRUE_TYPE_SIMPLE_EMPTY_CONTOUR_COUNT = 0
TRUE_TYPE_COMPOSITE_CONTOUR_COUNT = -1
H14_RESEARCH_EXTRA_INSTALL = 'pip install -e ".[research]"'


def is_simple_empty_true_type_glyph(contour_count: object) -> bool:
    if type(contour_count) is not int:
        raise TypeError("contour_count")
    return contour_count == TRUE_TYPE_SIMPLE_EMPTY_CONTOUR_COUNT


def _assigned_name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def _label(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


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


def _width_delta(character: str) -> int:
    return display_column_width(f"A{character}B") - display_column_width("AB")


def scan_spacing_mark_and_modifier_survivors() -> dict[str, object]:
    mc_keep = 0
    lm_keep = 0
    mc_width0: list[str] = []
    lm_width0: list[str] = []
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        if _assigned_name(codepoint) is None:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        if category not in {"Mc", "Lm"}:
            continue
        inserted = f"A{character}B"
        if not required_sanitizers_keep(inserted):
            continue
        delta = _width_delta(character)
        if category == "Mc":
            mc_keep += 1
            if delta == 0:
                mc_width0.append(_label(codepoint))
        else:
            lm_keep += 1
            if delta == 0:
                lm_width0.append(_label(codepoint))
    return {
        "mc_sanitizer_survivor_count": mc_keep,
        "lm_sanitizer_survivor_count": lm_keep,
        "mc_width0_survivor_labels": mc_width0,
        "lm_width0_survivor_labels": lm_width0,
    }


def designed_blank_probe_rows() -> tuple[dict[str, object], ...]:
    rows = []
    for codepoint in DESIGNED_BLANK_PROBES:
        character = chr(codepoint)
        inserted = f"A{character}B"
        rows.append(
            {
                "label": _label(codepoint),
                "name": _assigned_name(codepoint),
                "category": unicodedata.category(character),
                "required_sanitizers_keep": required_sanitizers_keep(inserted),
                "width_delta": _width_delta(character),
                "default_ignorable": is_default_ignorable_v1(codepoint),
            }
        )
    return tuple(rows)


def nfkc_collapse_probe_rows() -> tuple[dict[str, object], ...]:
    rows = []
    for codepoint in NFKC_COLLAPSE_PROBES:
        character = chr(codepoint)
        rows.append(
            {
                "label": _label(codepoint),
                "name": _assigned_name(codepoint),
                "category": unicodedata.category(character),
                "nfkc": unicodedata.normalize("NFKC", character),
                "required_sanitizers_keep": required_sanitizers_keep(f"A{character}B"),
            }
        )
    return tuple(rows)


def post_sanitizer_extended_class_payload() -> dict[str, object]:
    survivors = scan_spacing_mark_and_modifier_survivors()
    blanks = designed_blank_probe_rows()
    nfkc_rows = nfkc_collapse_probe_rows()
    hangul_seq_keep = required_sanitizers_keep(f"A{HANGUL_JAMO_FILLER_SEQUENCE}B")
    di_complete = DEFAULT_IGNORABLE_RANGES_V1 == UCD15_DEFAULT_IGNORABLE_RANGES
    classes = (
        _class_row(
            "mc_spacing_combining_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Spacing combining marks survive Mn-strip, default-ignorable-strip, Cf-strip, "
                "NFC, and NFKC. H9 skipped Mc as a visible category. Measured Mc probes, "
                "including Hangul tone marks and Indic vowel signs, change Chromium pre pixels."
            ),
            examples=tuple(_label(codepoint) for codepoint in MC_CHROMIUM_PROBES),
        ),
        _class_row(
            "lm_modifier_letter_insertion",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "NFKC-stable modifier letters survive the required sanitizers and take display "
                "width. Measured probes change Chromium pre pixels. Compatibility modifier "
                "letters such as U+02B0 die to NFKC."
            ),
            examples=tuple(_label(codepoint) for codepoint in LM_CHROMIUM_PROBES),
        ),
        _class_row(
            "designed_blank_or_gap_filler",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Egyptian hieroglyph blanks, Indic gap fillers, Braille blank, Ogham space, "
                "blank symbol, and object replacement survive the required sanitizers with "
                "nonzero display width and change Chromium pre pixels."
            ),
            examples=tuple(_label(codepoint) for codepoint in DESIGNED_BLANK_PROBES),
        ),
        _class_row(
            "font_zero_advance_empty_glyph",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "DejaVu Sans Mono has no sanitizer-surviving simple empty zero-advance glyph. "
                "Empty Mono glyphs are spaces, Cf annotation, or U+FFFC with full cell advance. "
                "U+FFFC is zero-advance in DejaVu Sans and full-cell in Mono; Chromium pre uses "
                "Mono and rejects it. Remaining system-font zero-advance empties are Cc or layout."
            ),
            examples=("U+FFFC",),
        ),
        _class_row(
            "hangul_filler_sequence",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason="U+115F plus U+1160 is default-ignorable. Default-ignorable-strip restores the source.",
            examples=("U+115F", "U+1160"),
        ),
        _class_row(
            "nfkc_compatibility_lookalike",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "NBSP, modifier letter small h, and halfwidth katakana voiced marks are not "
                "NFKC-stable. Homoglyph substitution remains forbidden."
            ),
            examples=tuple(_label(codepoint) for codepoint in NFKC_COLLAPSE_PROBES),
        ),
        _class_row(
            "cc_csi_filtered_subset",
            required_sanitizers="PASS",
            chromium_pre="HOST_DEPENDENT",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Removing ISO-6429 device controls from H12 does not leave the Cc class. "
                "DEL and remaining C1 are still controls, still not ordinary plain text, and "
                "Chromium remains host-dependent."
            ),
            examples=("U+007F", "U+0080"),
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
        "algorithm_version": CYCLE8_POST_SANITIZER_EXTENDED_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "search_space": (
            "sanitizer_surviving_non_width0_unicode_string_transforms_including_mc_lm_blanks_"
            "sequences_and_font_metrics"
        ),
        "does_not_repeat_assigned_width0_scan": True,
        "does_not_reopen_h13_classification": True,
        "assigned_width0_closed_set_hash": CYCLE8_CLOSED_SET_HASH,
        "assigned_width0_feasibility_hash": CYCLE8_FEASIBILITY_HASH,
        "control_carrier_hash": CYCLE8_CONTROL_CARRIER_HASH,
        "post_sanitizer_class_hash": CYCLE8_POST_SANITIZER_CLASS_HASH,
        "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH,
        "mix_sanitizer_gate": "FAIL",
        "di_list_complete_vs_ucd15": di_complete,
        "mc_sanitizer_survivor_count": survivors["mc_sanitizer_survivor_count"],
        "lm_sanitizer_survivor_count": survivors["lm_sanitizer_survivor_count"],
        "mc_width0_survivor_labels": survivors["mc_width0_survivor_labels"],
        "lm_width0_survivor_labels": survivors["lm_width0_survivor_labels"],
        "mc_chromium_probe_labels": [_label(codepoint) for codepoint in MC_CHROMIUM_PROBES],
        "lm_chromium_probe_labels": [_label(codepoint) for codepoint in LM_CHROMIUM_PROBES],
        "designed_blank_probes": list(blanks),
        "nfkc_collapse_probes": list(nfkc_rows),
        "hangul_jamo_filler_sequence_required_sanitizers_keep": hangul_seq_keep,
        "dejavu_sans_mono_zero_advance_empty_assigned_survivors": [],
        "classes": list(classes),
        "conjunction_sanitizer_pass_chromium_verified_ordinary_text": conjunction,
        "stronger_priority_zero_safe_mechanism": None,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "spent_confirmation_corpora_not_reused": True,
        "boundary": (
            "After Mn-strip, default-ignorable-strip, Cf-strip, NFC, and NFKC, a surviving "
            "string difference must use a non-Mn, non-default-ignorable, non-Cf character. "
            "Unicode treats those characters as graphic. H9 closed width-0 assigned insertions "
            "at Mn, Me, or Cf. H14 measured the next classes: Mc, NFKC-stable Lm, designed "
            "blanks and gap fillers, Hangul filler sequences, font-metric empty glyphs, and a "
            "CSI-filtered Cc subset. Mc, Lm, and designed blanks survive the required sanitizers "
            "and change Chromium pre pixels. Hangul fillers and NFKC lookalikes die to the "
            "required sanitizers. DejaVu Sans Mono has no sanitizer-surviving zero-advance empty "
            "glyph. Control codes remain the only measured sanitizer-surviving pixel-equal class "
            "on one research host, and they are Chromium host-dependent and not ordinary text. "
            "No measured class is simultaneously sanitizer-surviving, Chromium-portable, ordinary "
            "plain text, and Priority-Zero safe. This does not rewrite mix sanitizer FAIL."
        ),
    }
    return {**payload, "extended_class_hash": sha256_json(payload)}


def write_post_sanitizer_extended_class_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_EXTENDED_PATH)
    payload = post_sanitizer_extended_class_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_post_sanitizer_extended_class(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_EXTENDED_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_post_sanitizer_extended_class_committed() -> None:
    path = Path(CYCLE8_POST_SANITIZER_EXTENDED_PATH)
    if not path.is_file():
        raise ValueError("post-sanitizer extended class spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "extended_class_hash"}
    digest = sha256_json(body)
    if disk.get("extended_class_hash") != digest:
        raise ValueError("post-sanitizer extended class spec hash mismatch")
    if CYCLE8_POST_SANITIZER_EXTENDED_HASH != "0" * 64 and digest != CYCLE8_POST_SANITIZER_EXTENDED_HASH:
        raise ValueError("post-sanitizer extended class spec hash is not the frozen digest")
    if disk["product_authorized"] is True:
        raise ValueError("extended class must not product-authorize a mechanism")
    if disk["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("extended class must not claim a stronger Priority-Zero mechanism")
    if disk["mix_gate_not_rewritten"] is not True:
        raise ValueError("extended class must not rewrite the mix sanitizer gate")
    if disk["mix_sanitizer_gate"] != "FAIL":
        raise ValueError("extended class must keep mix sanitizer FAIL")
    if disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] != []:
        raise ValueError("extended class must not claim a conjunction survivor")
    if disk["mc_width0_survivor_labels"] != []:
        raise ValueError("extended class found width-0 Mc sanitizer survivors")
    if disk["lm_width0_survivor_labels"] != []:
        raise ValueError("extended class found width-0 Lm sanitizer survivors")
    if disk["hangul_jamo_filler_sequence_required_sanitizers_keep"] is not False:
        raise ValueError("Hangul filler sequence must die to required sanitizers")
    if disk["di_list_complete_vs_ucd15"] is not True:
        raise ValueError("project default-ignorable list must match Unicode 15.0")
    live = post_sanitizer_extended_class_payload()
    if live["mc_sanitizer_survivor_count"] == disk["mc_sanitizer_survivor_count"] and live != disk:
        raise ValueError("post-sanitizer extended class spec does not match the live payload")
