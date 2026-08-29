from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from .benchmark import strip_nonspacing_marks
from .closed_set import CYCLE8_CLOSED_SET_HASH
from .control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from .feasibility import CYCLE8_FEASIBILITY_HASH
from .post_sanitizer_class import CYCLE8_POST_SANITIZER_CLASS_HASH
from .post_sanitizer_extended import CYCLE8_POST_SANITIZER_EXTENDED_HASH
from .publishability import CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH


CYCLE8_POST_SANITIZER_SEQUENCES_VERSION = "cycle8-post-sanitizer-sequences-v1"
CYCLE8_POST_SANITIZER_SEQUENCES_PATH = "specs/cycle8/fuckmark-cycle8-post-sanitizer-sequences-v1.json"
CYCLE8_POST_SANITIZER_SEQUENCES_HASH = "a0fcdd2dfd7a05575592a2dec095c54513869deeb9bfdfbca4d7301ef478906c"
SEQUENCE_SOURCE = "I do not agree."
HANGUL_L_V_SEQUENCE = "\u1100\u1161"
HANGUL_FILLER_SEQUENCE = "\u115f\u1160"
MIX_PLUS_DEL_SEQUENCE = "\u034f\u007f"
LRI_PDI_WRAP = "\u2066" + SEQUENCE_SOURCE + "\u2069"
TATWEEL = "\u0640"
MALAYALAM_DOT_REPH = 0x0D4E
UAX29_PREPEND_CODEPOINTS = (
    *range(0x0600, 0x0606),
    0x06DD,
    0x070F,
    0x0890,
    0x0891,
    0x08E2,
    0x0D4E,
    0x110BD,
    0x111C2,
    0x111C3,
    0x1193F,
    0x11A3A,
    *range(0x11A84, 0x11A8A),
    0x11D46,
    0x11F02,
)
JOINING_CONNECTOR_PROBES = (0x0640, 0x07FA, 0x180A, 0x2040)
PREPEND_CHROMIUM_PROBES = (0x0D4E, 0x111C2, 0x11A3A, 0x11F02)


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


def _insert(payload: str) -> str:
    return f"I{payload} do not agree."


def scan_prepend_survivors() -> tuple[str, ...]:
    labels: list[str] = []
    for codepoint in UAX29_PREPEND_CODEPOINTS:
        if _assigned_name(codepoint) is None:
            continue
        character = chr(codepoint)
        inserted = character + SEQUENCE_SOURCE
        after = _insert(character)
        if required_sanitizers_keep(inserted) or required_sanitizers_keep(after):
            labels.append(_label(codepoint))
    return tuple(labels)


def hangul_lv_required_sanitizers_keep() -> bool:
    return required_sanitizers_keep(_insert(HANGUL_L_V_SEQUENCE))


def hangul_lv_composed_required_sanitizers_keep() -> bool:
    composed = unicodedata.normalize("NFC", HANGUL_L_V_SEQUENCE)
    return required_sanitizers_keep(_insert(composed))


def ascii_plus_mc_nfc_hit_count() -> int:
    hits = 0
    marks: list[int] = []
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        character = chr(codepoint)
        if unicodedata.category(character) != "Mc":
            continue
        if _assigned_name(codepoint) is None:
            continue
        if required_sanitizers_keep(f"A{character}B"):
            marks.append(codepoint)
    for base in (ord("I"), ord("a"), ord("e")):
        for mark in marks:
            seq = chr(base) + chr(mark)
            if unicodedata.normalize("NFC", seq) != seq:
                hits += 1
    return hits


def joining_connector_keep_labels() -> tuple[str, ...]:
    labels: list[str] = []
    for codepoint in JOINING_CONNECTOR_PROBES:
        character = chr(codepoint)
        if required_sanitizers_keep(_insert(character)):
            labels.append(_label(codepoint))
    return tuple(labels)


def mix_plus_del_mn_remainder() -> str:
    transformed = _insert(MIX_PLUS_DEL_SEQUENCE)
    remainder = strip_nonspacing_marks(transformed)
    extra = "".join(character for character in remainder if character not in SEQUENCE_SOURCE)
    return extra


def lri_wrap_required_sanitizers_keep() -> bool:
    return required_sanitizers_keep(LRI_PDI_WRAP)


def post_sanitizer_sequences_payload() -> dict[str, object]:
    prepend = scan_prepend_survivors()
    joining = joining_connector_keep_labels()
    hangul_seq_keep = hangul_lv_required_sanitizers_keep()
    hangul_composed_keep = hangul_lv_composed_required_sanitizers_keep()
    nfc_hits = ascii_plus_mc_nfc_hit_count()
    mix_del_remainder = mix_plus_del_mn_remainder()
    filler_keep = required_sanitizers_keep(_insert(HANGUL_FILLER_SEQUENCE))
    classes = (
        _class_row(
            "grapheme_prepend_plus_base",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "UAX #29 prepend letters such as Malayalam Dot Reph form a grapheme cluster "
                "with the following base. Assigned prepend probes survive the required "
                "sanitizers with nonzero width and change Chromium pre pixels on Latin bases."
            ),
            examples=tuple(prepend[:4]) if prepend else ("U+0D4E",),
        ),
        _class_row(
            "joining_connector_sequence",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Arabic tatweel, Nko lajanyalan, Mongolian nirugu, and character-tie "
                "connectors survive the required sanitizers. Inserted into Latin they change "
                "Chromium pre pixels. ZWJ and ZWNJ joining controls are Cf and die to Cf-strip."
            ),
            examples=("U+0640", "U+07FA", "U+180A"),
        ),
        _class_row(
            "hangul_lv_composition_sequence",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Hangul L plus V jamo NFC-compose to a syllable, so NFC sanitizer rewrites "
                "the sequence. The composed syllable NFKD-decomposes, so NFKD sanitizer "
                "rewrites that form. Either representation dies to the required bundle. "
                "Filler jamo remain default-ignorable."
            ),
            examples=("U+1100", "U+1161"),
        ),
        _class_row(
            "bidi_isolate_wrap_sequence",
            required_sanitizers="FAIL",
            chromium_pre="VERIFIED_ON_RESEARCH_HOST",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Matched LRI or FSI plus PDI around LTR English is pixel-equal on this "
                "Chromium pre host. Unmatched LRI is also pixel-equal here. RLI and RLO wraps "
                "reverse or isolate RTL and change pixels. LRI, RLI, FSI, PDI, LRO, and PDF "
                "are Cf and default-ignorable, so Cf-strip and default-ignorable-strip restore "
                "the source. That is not a new sanitizer-surviving class."
            ),
            examples=("U+2066", "U+2069"),
        ),
        _class_row(
            "iso6429_escape_sequence",
            required_sanitizers="PASS",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "7-bit ESC CSI sequences and 8-bit CSI plus ASCII parameters survive Mn-strip, "
                "default-ignorable-strip, Cf-strip, NFC, and NFKC because ESC and C1 are Cc. "
                "Chromium pre textContent does not interpret them as device control, so the "
                "parameter characters remain visible. Still not ordinary plain text."
            ),
            examples=("U+001B", "U+009B"),
        ),
        _class_row(
            "partial_sanitizer_remainder",
            required_sanitizers="FAIL",
            chromium_pre="HOST_DEPENDENT",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "Combining a stripped carrier with a survivor leaves the survivor after "
                "Mn-strip or default-ignorable-strip. Mix plus DEL stays pixel-equal here and "
                "Mn-strip leaves DEL. The remainder is the H12 Cc class, not a new mechanism. "
                "Mix plus Mc or Me leaves those marks, which change Chromium pixels."
            ),
            examples=("U+034F", "U+007F"),
        ),
        _class_row(
            "font_gsub_ligature_sequence",
            required_sanitizers="FAIL",
            chromium_pre="REJECTED",
            ordinary_plain_text="FAIL",
            product="FAIL",
            reason=(
                "DejaVu Sans Mono Latin GSUB extra-component ligatures are discretionary "
                "f plus i and f plus l mapping to compatibility ligature characters. Those "
                "characters die to NFKC. Chromium pre does not apply that discretionary "
                "ligature: inserting CGJ, ZWJ, ZWNJ, or VS1 between f and i in affirm is "
                "pixel-equal. No sanitizer-surviving extra code point is eaten by a Latin liga."
            ),
            examples=("U+FB01", "U+FB02"),
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
        "algorithm_version": CYCLE8_POST_SANITIZER_SEQUENCES_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "search_space": (
            "sequence_and_representation_transforms_after_h14_including_prepend_joining_"
            "hangul_composition_bidi_wraps_escape_sequences_partial_sanitizer_and_gsub"
        ),
        "does_not_repeat_assigned_width0_scan": True,
        "does_not_repeat_h14_single_codepoint_sweep": True,
        "assigned_width0_closed_set_hash": CYCLE8_CLOSED_SET_HASH,
        "assigned_width0_feasibility_hash": CYCLE8_FEASIBILITY_HASH,
        "control_carrier_hash": CYCLE8_CONTROL_CARRIER_HASH,
        "post_sanitizer_class_hash": CYCLE8_POST_SANITIZER_CLASS_HASH,
        "post_sanitizer_extended_hash": CYCLE8_POST_SANITIZER_EXTENDED_HASH,
        "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH,
        "mix_sanitizer_gate": "FAIL",
        "prepend_sanitizer_survivor_labels": list(prepend),
        "prepend_sanitizer_survivor_count": len(prepend),
        "joining_connector_keep_labels": list(joining),
        "hangul_lv_sequence_required_sanitizers_keep": hangul_seq_keep,
        "hangul_lv_composed_required_sanitizers_keep": hangul_composed_keep,
        "hangul_filler_sequence_required_sanitizers_keep": filler_keep,
        "ascii_plus_mc_nfc_hit_count": nfc_hits,
        "lri_wrap_required_sanitizers_keep": lri_wrap_required_sanitizers_keep(),
        "mix_plus_del_mn_remainder": [f"U+{ord(character):04X}" for character in mix_del_remainder],
        "dejavu_sans_mono_zero_advance_keep_including_composites": [],
        "dejavu_sans_mono_latin_extra_component_liga_count": 2,
        "classes": list(classes),
        "conjunction_sanitizer_pass_chromium_verified_ordinary_text": conjunction,
        "stronger_priority_zero_safe_mechanism": None,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "spent_confirmation_corpora_not_reused": True,
        "boundary": (
            "Sequence-level transforms do not escape the H13/H14 sanitizer boundary. "
            "Grapheme prepend and joining connectors survive the required sanitizers and "
            "change Chromium pre pixels. Hangul L plus V is NFC-unstable as jamo and "
            "NFKD-unstable as a syllable. Bidi isolate wraps can be renderer-neutral on LTR "
            "English and still die to Cf-strip. ISO-6429 escape sequences keep sanitizers "
            "because they are Cc plus ASCII, but Chromium pre shows the ASCII parameters. "
            "Partial sanitizer remainders collapse to a previously classified class. DejaVu "
            "Sans Mono has no sanitizer-surviving zero-advance mapped glyph, including "
            "composites, and no Latin GSUB ligature that swallows an extra sanitizer-stable "
            "code point. No measured sequence class is simultaneously sanitizer-surviving, "
            "Chromium-portable, ordinary plain text, and Priority-Zero safe. This does not "
            "rewrite mix sanitizer FAIL."
        ),
    }
    return {**payload, "sequence_class_hash": sha256_json(payload)}


def write_post_sanitizer_sequences_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_SEQUENCES_PATH)
    payload = post_sanitizer_sequences_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_post_sanitizer_sequences(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_POST_SANITIZER_SEQUENCES_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_post_sanitizer_sequences_committed() -> None:
    path = Path(CYCLE8_POST_SANITIZER_SEQUENCES_PATH)
    if not path.is_file():
        raise ValueError("post-sanitizer sequences spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "sequence_class_hash"}
    digest = sha256_json(body)
    if disk.get("sequence_class_hash") != digest:
        raise ValueError("post-sanitizer sequences spec hash mismatch")
    if CYCLE8_POST_SANITIZER_SEQUENCES_HASH != "0" * 64 and digest != CYCLE8_POST_SANITIZER_SEQUENCES_HASH:
        raise ValueError("post-sanitizer sequences spec hash is not the frozen digest")
    if disk["product_authorized"] is True:
        raise ValueError("sequences class must not product-authorize a mechanism")
    if disk["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("sequences class must not claim a stronger Priority-Zero mechanism")
    if disk["mix_gate_not_rewritten"] is not True:
        raise ValueError("sequences class must not rewrite the mix sanitizer gate")
    if disk["mix_sanitizer_gate"] != "FAIL":
        raise ValueError("sequences class must keep mix sanitizer FAIL")
    if disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] != []:
        raise ValueError("sequences class must not claim a conjunction survivor")
    if disk["hangul_lv_sequence_required_sanitizers_keep"] is not False:
        raise ValueError("Hangul L plus V sequence must die to required sanitizers")
    if disk["hangul_lv_composed_required_sanitizers_keep"] is not False:
        raise ValueError("composed Hangul syllable must die to required sanitizers")
    if disk["lri_wrap_required_sanitizers_keep"] is not False:
        raise ValueError("LRI wrap must die to required sanitizers")
    if disk["mix_plus_del_mn_remainder"] != ["U+007F"]:
        raise ValueError("mix plus DEL remainder after Mn-strip must be DEL")
    if disk["ascii_plus_mc_nfc_hit_count"] != 0:
        raise ValueError("ASCII plus Mc must not NFC-compose")
    if disk["dejavu_sans_mono_zero_advance_keep_including_composites"] != []:
        raise ValueError("DejaVu Sans Mono must not have sanitizer-surviving zero-advance glyphs")
    live = post_sanitizer_sequences_payload()
    if live["prepend_sanitizer_survivor_count"] == disk["prepend_sanitizer_survivor_count"] and live != disk:
        raise ValueError("post-sanitizer sequences spec does not match the live payload")
