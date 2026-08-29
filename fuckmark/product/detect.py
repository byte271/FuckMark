from __future__ import annotations

from dataclasses import dataclass

from ..cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    LETTER_MIX_CF_CODEPOINTS,
    LETTER_MIX_CONTROL_CODEPOINTS,
    LETTER_MIX_IA_CODEPOINTS,
    LETTER_MIX_MARK_PAYLOADS,
    LETTER_MIX_ME_PAYLOADS,
)


DETECT_CONTACT_EMAIL = "Fhelp@q1z.org"
DETECT_MECHANISM_ID = "fuckmark-carrier-scan-v1"
_MARK = frozenset(ord(character) for character in LETTER_MIX_MARK_PAYLOADS)
_CC = frozenset(LETTER_MIX_CONTROL_CODEPOINTS)
_ME = frozenset(ord(character) for character in LETTER_MIX_ME_PAYLOADS)
_CF = frozenset(LETTER_MIX_CF_CODEPOINTS)
_IA = frozenset(LETTER_MIX_IA_CODEPOINTS)
_APPROVED = frozenset(LETTER_MIX_APPROVED_CARRIERS)


@dataclass(frozen=True, slots=True)
class DetectResult:
    detected: bool
    found: int
    mark_count: int
    cc_count: int
    me_count: int
    cf_count: int
    ia_count: int
    first_hit: str
    source_length: int

    @property
    def verdict(self) -> str:
        return "detected" if self.detected else "not-detected"


def detect_fuckmark_insertions(text: str) -> DetectResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    mark = cc = me = cf = ia = 0
    first = ""
    for index, character in enumerate(text):
        code = ord(character)
        if code not in _APPROVED:
            continue
        if not first:
            first = f"U+{code:04X}@{index}"
        if code in _MARK:
            mark += 1
        elif code in _CC:
            cc += 1
        elif code in _ME:
            me += 1
        elif code in _CF:
            cf += 1
        elif code in _IA:
            ia += 1
    total = mark + cc + me + cf + ia
    return DetectResult(
        detected=total > 0,
        found=total,
        mark_count=mark,
        cc_count=cc,
        me_count=me,
        cf_count=cf,
        ia_count=ia,
        first_hit=first,
        source_length=len(text),
    )


def detect_machine_line(result: DetectResult) -> str:
    detected = "yes" if result.detected else "no"
    return (
        "fuckmark-detect "
        f"detected={detected} found={result.found} "
        f"mark={result.mark_count} cc={result.cc_count} me={result.me_count} "
        f"cf={result.cf_count} ia={result.ia_count} "
        f"first={result.first_hit} source_length={result.source_length}"
    )


def detect_human_report(result: DetectResult) -> str:
    if result.detected:
        first = f" first={result.first_hit}" if result.first_hit else ""
        return (
            "FuckMark detector: watermark detected.\n"
            f"Found {result.found} FuckMark insertion characters "
            f"(mark={result.mark_count} cc={result.cc_count} me={result.me_count} "
            f"cf={result.cf_count} ia={result.ia_count}{first}).\n"
            "This is a closed-set scan of FuckMark insertions, not a general AI-watermark detector.\n"
        )
    return (
        "FuckMark detector: no watermark detected.\n"
        "We did not detect a FuckMark watermark in this text.\n"
        f"What? You think there is a watermark in this? Contact us: {DETECT_CONTACT_EMAIL}\n"
    )
