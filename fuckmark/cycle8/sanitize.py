from __future__ import annotations

import unicodedata

from .._validation import require_clean_string
from ..cycle7.whitespace_collapse import CYCLE7_SANITIZER_VARIANT_IDS, sanitize_cycle7_variant


CYCLE8_SCALE_SANITIZER_VARIANT_IDS = (*CYCLE7_SANITIZER_VARIANT_IDS, "nfc")


def sanitize_cycle8_scale_variant(variant_id: str, text: str) -> str:
    require_clean_string("variant_id", variant_id)
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if variant_id == "nfc":
        return unicodedata.normalize("NFC", text)
    return sanitize_cycle7_variant(variant_id, text)
