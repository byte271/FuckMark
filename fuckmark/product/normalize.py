from __future__ import annotations

import argparse
import json
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, TextIO

from ..hashing import sha256_json, sha256_text
from .domain import PRODUCT_MAX_INPUT_CHARS
from .scan import (
    SECURITY_SCAN_CATEGORIES,
    clean_hidden_characters,
    decode_hidden_scan_bytes,
    normalize_scan_categories,
)


NORMALIZE_ALGORITHM_VERSION = "fuckmark-normalize-v1"
NORMALIZE_EXIT_OK = 0
NORMALIZE_EXIT_USAGE = 2

_CONFUSABLE = {
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
    "\u0410": "A",
    "\u0415": "E",
    "\u041e": "O",
    "\u0420": "P",
    "\u0421": "C",
    "\u0425": "X",
    "\u0391": "A",
    "\u0392": "B",
    "\u0395": "E",
    "\u0397": "H",
    "\u0399": "I",
    "\u039a": "K",
    "\u039c": "M",
    "\u039d": "N",
    "\u039f": "O",
    "\u03a1": "P",
    "\u03a4": "T",
    "\u03a7": "X",
    "\u03b1": "a",
    "\u03bf": "o",
    "\u03c1": "p",
    "\u03c5": "y",
    "\u03c7": "x",
    "\u00a0": " ",
    "\u2007": " ",
    "\u202f": " ",
    "\uff01": "!",
    "\uff0e": ".",
    "\uff0f": "/",
    "\uff1a": ":",
    "\uff1f": "?",
}


@dataclass(frozen=True, slots=True)
class NormalizeReceipt:
    nfc: bool
    confusable: bool
    stripped: int
    steps: tuple[str, ...]
    input_sha256: str
    output_sha256: str
    changed: bool


def skeleton_fold(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return "".join(_CONFUSABLE.get(character, character) for character in text)


def normalize_text(
    text: str,
    *,
    nfc: bool = True,
    confusable: bool = False,
    strip: bool = True,
    categories: Iterable[str] | None = None,
) -> tuple[str, NormalizeReceipt]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text) > PRODUCT_MAX_INPUT_CHARS:
        raise ValueError(f"input is too large (max {PRODUCT_MAX_INPUT_CHARS} characters)")
    selected = (
        frozenset(SECURITY_SCAN_CATEGORIES)
        if categories is None
        else normalize_scan_categories(categories)
    )
    original = text
    steps: list[str] = []
    if nfc:
        folded = unicodedata.normalize("NFC", text)
        if folded != text:
            steps.append("nfc")
        text = folded
    if confusable:
        folded = skeleton_fold(text)
        if folded != text:
            steps.append("confusable")
        text = folded
    stripped = 0
    if strip:
        text, stripped = clean_hidden_characters(text, categories=selected)
        if stripped:
            steps.append("strip")
    receipt = NormalizeReceipt(
        nfc=nfc,
        confusable=confusable,
        stripped=stripped,
        steps=tuple(steps),
        input_sha256=sha256_text(original),
        output_sha256=sha256_text(text),
        changed=text != original,
    )
    return text, receipt


def normalize_receipt_dict(receipt: NormalizeReceipt) -> dict[str, object]:
    return {
        "algorithm_version": NORMALIZE_ALGORITHM_VERSION,
        "nfc": receipt.nfc,
        "confusable": receipt.confusable,
        "stripped": receipt.stripped,
        "steps": list(receipt.steps),
        "changed": receipt.changed,
        "input_sha256": receipt.input_sha256,
        "output_sha256": receipt.output_sha256,
        "report_hash": sha256_json(
            {
                "algorithm_version": NORMALIZE_ALGORITHM_VERSION,
                "nfc": receipt.nfc,
                "confusable": receipt.confusable,
                "stripped": receipt.stripped,
                "steps": list(receipt.steps),
                "changed": receipt.changed,
                "input_sha256": receipt.input_sha256,
                "output_sha256": receipt.output_sha256,
            }
        ),
    }


def _normalize_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark normalize",
        description=(
            "NFC-normalize text, optionally fold identifier lookalikes, "
            "and strip hidden Unicode. Emits a receipt of what changed."
        ),
    )
    parser.add_argument("source", nargs="?", metavar="TEXT_OR_FILE")
    parser.add_argument(
        "--confusable",
        action="store_true",
        help="fold a UTS #39-inspired identifier lookalike subset to ASCII skeletons",
    )
    parser.add_argument(
        "--keep-hidden",
        action="store_true",
        help="do not strip hidden characters",
    )
    parser.add_argument(
        "--receipt",
        dest="receipt_output",
        action="store_true",
        help="write the JSON receipt to stderr",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    return parser


def _load_plain(source: str | None, stdin: TextIO) -> str:
    if source in (None, "-", ""):
        buffer = getattr(stdin, "buffer", None)
        if buffer is not None:
            return decode_hidden_scan_bytes(buffer.read())
        return stdin.read()
    from pathlib import Path

    path = Path(source).expanduser()
    if path.is_file():
        return decode_hidden_scan_bytes(path.read_bytes())
    return source


def _emit(stream: TextIO, text: str) -> None:
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        try:
            stream.flush()
        except (OSError, ValueError, UnicodeError):
            pass
        buffer.write(text.encode("utf-8", "surrogatepass"))
        buffer.flush()
        return
    stream.write(text)
    stream.flush()


def run_normalize_argv(argv: list[str], stdin: TextIO, output: TextIO, errors: TextIO) -> int:
    try:
        arguments = _normalize_parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return NORMALIZE_EXIT_OK
        return int(code) if isinstance(code, int) else NORMALIZE_EXIT_USAGE
    try:
        raw = _load_plain(arguments.source, stdin)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return NORMALIZE_EXIT_USAGE
    if not raw:
        errors.write("FuckMark: no input. Pipe text, pass a file, or quote a string.\n")
        errors.flush()
        return NORMALIZE_EXIT_USAGE
    try:
        cleaned, receipt = normalize_text(
            raw,
            confusable=arguments.confusable,
            strip=not arguments.keep_hidden,
        )
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return NORMALIZE_EXIT_USAGE
    _emit(output, cleaned)
    if not arguments.quiet:
        if receipt.changed:
            steps = ",".join(receipt.steps) or "none"
            errors.write(
                f"FuckMark normalize: changed ({steps}); stripped {receipt.stripped} hidden characters.\n"
            )
        else:
            errors.write("FuckMark normalize: already canonical; nothing changed.\n")
        errors.flush()
    if arguments.receipt_output:
        _emit(errors, json.dumps(normalize_receipt_dict(receipt), ensure_ascii=False, indent=2) + "\n")
    return NORMALIZE_EXIT_OK


def normalize_payload(value: Any, *, confusable: bool = False) -> dict[str, object]:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    try:
        cleaned, receipt = normalize_text(value, confusable=confusable)
    except ValueError as error:
        if "too large" in str(error):
            return {
                "ok": False,
                "reason": "too-large",
                "backend": "python",
                "max": PRODUCT_MAX_INPUT_CHARS,
            }
        raise
    return {
        "ok": True,
        "reason": "normalized" if receipt.changed else "unchanged",
        "backend": "python",
        "text": cleaned,
        "receipt": normalize_receipt_dict(receipt),
    }
