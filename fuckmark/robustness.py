from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .cycle8.letter_mix import LETTER_MIX_MECHANISM_ID, apply_letter_alternating_mix
from .cycle8.unicode_meta import is_default_ignorable_v1
from .hashing import sha256_file, sha256_json, sha256_text
from .product.detect import detect_fuckmark_insertions
from .product.scan import scan_hidden_characters
from .product.visible_projection import project_visible_v1
from .sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters


ROBUSTNESS_ALGORITHM_VERSION = "fuckmark-robustness-bench-v1"
ROBUSTNESS_EXIT_OK = 0
ROBUSTNESS_EXIT_MISMATCH = 1
ROBUSTNESS_EXIT_USAGE = 2
SPEC_DIR = Path(__file__).resolve().parents[1] / "specs"
PROTOCOL_PATH = SPEC_DIR / "fuckmark-robustness-bench-v1.protocol.md"
VECTORS_PATH = SPEC_DIR / "fuckmark-robustness-bench-v1.vectors.json"
FREEZE_PATH = SPEC_DIR / "fuckmark-robustness-bench-v1.freeze.json"
SEALED_DETECTOR_SCORECARD_PATH = "specs/cycle8/fuckmark-cycle8-gate-v2-confirmation-scorecard-v1.json"
SEALED_DETECTOR_SCORECARD_HASH = "3df98598fa1f9fb3951029f105b43dfd5f3e83a9ec69fd5c160b31686b0ad6c9"
_UNICODE_SANITIZER_PATTERN = re.compile(
    "[\u00a0\u1680\u180e\u2000-\u200b\u200c\u200d\u200e\u200f\u2060\u2063\u202f\u205f\u3000"
    "\ufeff\uffa0\ufff9\ufffa\ufffb\ufe00\ufe01\ufe02\ufe03\ufe04\ufe05\ufe06\ufe07\ufe08\ufe09"
    "\ufe0a\ufe0b\ufe0c\ufe0d\ufe0e\ufe0f\u3164\u202a\u202b\u202c\u202d\u202e\u202f]"
)

ATTACK_IDS = (
    "identity",
    "mn_strip",
    "default_ignorable_strip",
    "nfc",
    "nfkc",
    "nfkd",
    "cf_strip",
    "me_strip",
    "cc_strip",
    "unicode_sanitizer",
    "mn_then_us",
    "di_then_us",
    "us_then_mn",
    "required_bundle",
    "required_bundle_then_us",
    "mn_me_us",
    "mn_me_us_cf",
    "di_me_us_cf",
)

_FIXTURES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("ascii_prose", tuple(ord(ch) for ch in "I do not agree.")),
    ("ascii_clause", tuple(ord(ch) for ch in "We cannot continue.")),
    ("nfd_latin", (0x65, 0x0301)),
    ("emoji", (0x1F600,)),
    ("greek", (0x03B1, 0x03B2)),
    ("cyrillic", (0x0430, 0x0431)),
    ("han", (0x4E2D,)),
    ("hangul", (0xAC00,)),
    ("url_mixed", tuple(ord(ch) for ch in "See https://example.com/x I do not agree.")),
    ("digits", tuple(ord(ch) for ch in "123.")),
)


@dataclass(frozen=True, slots=True)
class RobustnessCell:
    fixture_id: str
    attack_id: str
    source: str
    mixed: str
    attacked: str
    restores_source: bool
    mix_projection_equals_source: bool
    projection_equals_source: bool
    carrier_detected: bool
    residual_categories: tuple[str, ...]
    mix_sha256: str
    output_sha256: str


def fixture_ids() -> tuple[str, ...]:
    return tuple(item[0] for item in _FIXTURES)


def fixture_source(fixture_id: str) -> str:
    for name, codes in _FIXTURES:
        if name == fixture_id:
            return "".join(chr(code) for code in codes)
    raise ValueError(f"unknown robustness fixture: {fixture_id}")


def _strip_category(text: str, category: str) -> str:
    return "".join(character for character in text if unicodedata.category(character) != category)


def strip_nonspacing_marks(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _strip_category(text, "Mn")


def strip_enclosing_marks(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _strip_category(text, "Me")


def strip_other_controls(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _strip_category(text, "Cc")


def strip_default_ignorable(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return "".join(character for character in text if not is_default_ignorable_v1(ord(character)))


def unicode_sanitizer(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = _UNICODE_SANITIZER_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(" +", " ", cleaned)
    return _strip_category(cleaned, "Cc")


def apply_required_sanitizer_bundle(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = strip_nonspacing_marks(cleaned)
    cleaned = strip_default_ignorable(cleaned)
    return strip_unicode_format_characters(cleaned)


def apply_attack(attack_id: str, text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if attack_id == "identity":
        return text
    if attack_id == "mn_strip":
        return strip_nonspacing_marks(text)
    if attack_id == "default_ignorable_strip":
        return strip_default_ignorable(text)
    if attack_id == "nfc":
        return unicodedata.normalize("NFC", text)
    if attack_id == "nfkc":
        return nfkc_normalize(text)
    if attack_id == "nfkd":
        return unicodedata.normalize("NFKD", text)
    if attack_id == "cf_strip":
        return strip_unicode_format_characters(text)
    if attack_id == "me_strip":
        return strip_enclosing_marks(text)
    if attack_id == "cc_strip":
        return strip_other_controls(text)
    if attack_id == "unicode_sanitizer":
        return unicode_sanitizer(text)
    if attack_id == "mn_then_us":
        return unicode_sanitizer(strip_nonspacing_marks(text))
    if attack_id == "di_then_us":
        return unicode_sanitizer(strip_default_ignorable(text))
    if attack_id == "us_then_mn":
        return strip_nonspacing_marks(unicode_sanitizer(text))
    if attack_id == "required_bundle":
        return apply_required_sanitizer_bundle(text)
    if attack_id == "required_bundle_then_us":
        return unicode_sanitizer(apply_required_sanitizer_bundle(text))
    if attack_id == "mn_me_us":
        return unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(text)))
    if attack_id == "mn_me_us_cf":
        return strip_unicode_format_characters(
            unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(text)))
        )
    if attack_id == "di_me_us_cf":
        return strip_unicode_format_characters(
            unicode_sanitizer(strip_enclosing_marks(strip_default_ignorable(text)))
        )
    raise ValueError(f"unknown robustness attack: {attack_id}")


def measure_cell(fixture_id: str, attack_id: str) -> RobustnessCell:
    if attack_id not in ATTACK_IDS:
        raise ValueError(f"unknown robustness attack: {attack_id}")
    source = fixture_source(fixture_id)
    mixed = apply_letter_alternating_mix(source)
    attacked = apply_attack(attack_id, mixed)
    scan = scan_hidden_characters(attacked, max_findings=max(len(attacked), 1))
    return RobustnessCell(
        fixture_id=fixture_id,
        attack_id=attack_id,
        source=source,
        mixed=mixed,
        attacked=attacked,
        restores_source=attacked == source,
        mix_projection_equals_source=project_visible_v1(mixed) == source,
        projection_equals_source=project_visible_v1(attacked) == source,
        carrier_detected=detect_fuckmark_insertions(attacked).detected,
        residual_categories=scan.active_categories(),
        mix_sha256=sha256_text(mixed),
        output_sha256=sha256_text(attacked),
    )


def cell_expect(cell: RobustnessCell) -> dict[str, object]:
    return {
        "restores_source": cell.restores_source,
        "mix_projection_equals_source": cell.mix_projection_equals_source,
        "projection_equals_source": cell.projection_equals_source,
        "carrier_detected": cell.carrier_detected,
        "residual_categories": list(cell.residual_categories),
        "mix_sha256": cell.mix_sha256,
        "output_sha256": cell.output_sha256,
    }


def cell_dict(cell: RobustnessCell) -> dict[str, object]:
    return {
        "id": f"{cell.fixture_id}/{cell.attack_id}",
        "fixture": cell.fixture_id,
        "attack": cell.attack_id,
        "expect": cell_expect(cell),
    }


def sealed_detector_track() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / SEALED_DETECTOR_SCORECARD_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "id": "cycle8-gate-v2-confirmation-scorecard-v1",
        "path": SEALED_DETECTOR_SCORECARD_PATH,
        "file_sha256": sha256_file(path),
        "scorecard_hash": payload["scorecard_hash"],
        "expected_scorecard_hash": SEALED_DETECTOR_SCORECARD_HASH,
        "identity_watermarked_detected": payload["identity_watermarked_detected"],
        "identity_watermarked_of": 192,
        "mix_watermarked_detected_by_required_sanitizer": payload["mix_watermarked_detected_by_required_sanitizer"],
        "visible_pass_rate": payload["visible_pass_rate"],
        "notes": (
            "Sealed historical GPT-2 / SynthID Gate v2 scorecard. "
            "This bench does not rerun detectors. Do not rewrite the scorecard."
        ),
    }


def iter_cells(
    *,
    fixtures: Sequence[str] | None = None,
    attacks: Sequence[str] | None = None,
) -> list[RobustnessCell]:
    selected_fixtures = tuple(fixtures) if fixtures is not None else fixture_ids()
    selected_attacks = tuple(attacks) if attacks is not None else ATTACK_IDS
    unknown_fixtures = [name for name in selected_fixtures if name not in fixture_ids()]
    if unknown_fixtures:
        raise ValueError(f"unknown robustness fixtures: {unknown_fixtures}")
    unknown_attacks = [name for name in selected_attacks if name not in ATTACK_IDS]
    if unknown_attacks:
        raise ValueError(f"unknown robustness attacks: {unknown_attacks}")
    return [measure_cell(fixture_id, attack_id) for fixture_id in selected_fixtures for attack_id in selected_attacks]


def build_vectors_payload() -> dict[str, object]:
    cells = iter_cells()
    fixtures = []
    for fixture_id, codes in _FIXTURES:
        sample = next(cell for cell in cells if cell.fixture_id == fixture_id)
        fixtures.append(
            {
                "id": fixture_id,
                "source": list(codes),
                "mix_sha256": sample.mix_sha256,
                "mix_projection_equals_source": sample.mix_projection_equals_source,
                "mixed": sample.mixed != sample.source,
            }
        )
    return {
        "algorithm_version": ROBUSTNESS_ALGORITHM_VERSION,
        "mix_mechanism_id": LETTER_MIX_MECHANISM_ID,
        "attacks": list(ATTACK_IDS),
        "fixtures": fixtures,
        "cells": [cell_dict(cell) for cell in cells],
    }


def load_vectors() -> dict[str, object]:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


def compare_to_vectors(cells: Sequence[RobustnessCell], vectors: dict[str, object]) -> list[dict[str, object]]:
    expected = {item["id"]: item["expect"] for item in vectors["cells"]}
    mismatches: list[dict[str, object]] = []
    for cell in cells:
        key = f"{cell.fixture_id}/{cell.attack_id}"
        want = expected.get(key)
        got = cell_expect(cell)
        if want != got:
            mismatches.append({"id": key, "expected": want, "actual": got})
    return mismatches


def summary_dict(cells: Sequence[RobustnessCell], mismatches: Sequence[dict[str, object]]) -> dict[str, object]:
    restores = sum(1 for cell in cells if cell.restores_source)
    mix_ok = sum(1 for cell in cells if cell.mix_projection_equals_source)
    return {
        "fixtures": len({cell.fixture_id for cell in cells}),
        "attacks": len({cell.attack_id for cell in cells}),
        "cells": len(cells),
        "restores_source": restores,
        "mix_projection_equals_source": mix_ok,
        "mismatches": len(mismatches),
    }


def run_robustness_bench(
    *,
    fixtures: Sequence[str] | None = None,
    attacks: Sequence[str] | None = None,
) -> dict[str, object]:
    cells = iter_cells(fixtures=fixtures, attacks=attacks)
    vectors = load_vectors()
    mismatches = compare_to_vectors(cells, vectors)
    sealed = sealed_detector_track()
    sealed_ok = sealed["scorecard_hash"] == sealed["expected_scorecard_hash"]
    return {
        "algorithm_version": ROBUSTNESS_ALGORITHM_VERSION,
        "mix_mechanism_id": LETTER_MIX_MECHANISM_ID,
        "summary": summary_dict(cells, mismatches),
        "sealed_detector_track": sealed,
        "sealed_detector_ok": sealed_ok,
        "mismatches": mismatches,
        "cells": [cell_dict(cell) for cell in cells],
    }


def freeze_bindings() -> dict[str, object]:
    vectors = load_vectors()
    return {
        "algorithm_version": ROBUSTNESS_ALGORITHM_VERSION,
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "vectors_file_sha256": sha256_file(VECTORS_PATH),
        "vectors_canonical_sha256": sha256_json(vectors),
        "sealed_detector_scorecard_path": SEALED_DETECTOR_SCORECARD_PATH,
        "sealed_detector_scorecard_hash": SEALED_DETECTOR_SCORECARD_HASH,
        "sealed_detector_scorecard_file_sha256": sha256_file(
            Path(__file__).resolve().parents[1] / SEALED_DETECTOR_SCORECARD_PATH
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark robustness",
        description=(
            "Run the public sanitizer-restore robustness bench "
            "(fuckmark-robustness-bench-v1). Does not rerun GPT-2 or SynthID."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="json_mode")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="fixture id; repeatable. Default: all public fixtures.",
    )
    parser.add_argument(
        "--attack",
        action="append",
        dest="attacks",
        help="attack id; repeatable. Default: the frozen attack catalog.",
    )
    return parser


def _emit(stream: TextIO, text: str) -> None:
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")
    stream.flush()


def run_robustness_argv(argv: list[str], output: TextIO, errors: TextIO) -> int:
    try:
        arguments = _parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return ROBUSTNESS_EXIT_OK
        return int(code) if isinstance(code, int) else ROBUSTNESS_EXIT_USAGE
    try:
        report = run_robustness_bench(fixtures=arguments.fixtures, attacks=arguments.attacks)
    except ValueError as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return ROBUSTNESS_EXIT_USAGE
    summary = report["summary"]
    assert isinstance(summary, dict)
    mismatches = report["mismatches"]
    assert isinstance(mismatches, list)
    if arguments.json_mode:
        _emit(output, json.dumps(report, ensure_ascii=False))
    elif not arguments.quiet:
        _emit(
            errors,
            (
                f"FuckMark robustness: {summary['cells']} cells, "
                f"{summary['restores_source']} restore the source, "
                f"{summary['mismatches']} mismatches versus frozen vectors."
            ),
        )
        _emit(
            errors,
            (
                "Sealed detector track is Gate v2 confirmation "
                f"({report['sealed_detector_track']['identity_watermarked_detected']}/192 identity; "
                "mix required-sanitizer detections stay 0). Detectors were not rerun."
            ),
        )
        if mismatches:
            for item in mismatches[:12]:
                _emit(errors, f"  mismatch {item['id']}")
    failed = bool(mismatches) or not report["sealed_detector_ok"]
    return ROBUSTNESS_EXIT_MISMATCH if failed else ROBUSTNESS_EXIT_OK
