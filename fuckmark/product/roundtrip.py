from __future__ import annotations

import io
import unicodedata

from ..hashing import sha256_json, sha256_text
from .visible_projection import is_carrier_insertion_v1, project_visible_v1


ROUNDTRIP_HARNESS_VERSION = "product-text-roundtrip-v1"


def nfc_normalize(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return unicodedata.normalize("NFC", text)


def display_column_width(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    width = 0
    for character in text:
        if unicodedata.category(character) in {"Mn", "Me", "Cf"}:
            continue
        if character in {"\n", "\r"}:
            continue
        width += 1
    return width


def utf8_file_roundtrip(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    encoded = text.encode("utf-8")
    return encoded.decode("utf-8")


def stdin_stdout_roundtrip(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    buffer = io.StringIO()
    buffer.write(text)
    return buffer.getvalue()


def latin1_roundtrip_survives(text: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    try:
        return text.encode("latin-1").decode("latin-1") == text
    except UnicodeEncodeError:
        return False


def roundtrip_report(original: str, transformed: str, approved_carriers: tuple[int, ...]) -> dict[str, object]:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    utf8 = utf8_file_roundtrip(transformed)
    stdout = stdin_stdout_roundtrip(transformed)
    nfc = nfc_normalize(transformed)
    payload = {
        "algorithm_version": ROUNDTRIP_HARNESS_VERSION,
        "original_sha256": sha256_text(original),
        "transformed_sha256": sha256_text(transformed),
        "visible_ok": is_carrier_insertion_v1(original, transformed, approved_carriers),
        "projected_equals_source": project_visible_v1(transformed, approved_carriers) == original,
        "utf8_roundtrip_equals_transformed": utf8 == transformed,
        "stdin_stdout_equals_transformed": stdout == transformed,
        "nfc_equals_transformed": nfc == transformed,
        "latin1_roundtrip_survives": latin1_roundtrip_survives(transformed),
        "display_column_width_equal": display_column_width(original) == display_column_width(transformed),
        "newline_count_equal": original.count("\n") == transformed.count("\n"),
        "ascii_space_count_equal": original.count(" ") == transformed.count(" "),
    }
    return {**payload, "report_hash": sha256_json(payload)}
