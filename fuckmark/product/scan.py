from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from .._validation import require_int
from .severity import annotate_finding, normalize_language, source_roles
from .visible_projection import product_approved_carriers_v1


SCAN_ALGORITHM_VERSION = "fuckmark-hidden-scan-v1"
SCAN_CONTACT_EMAIL = "Fhelp@q1z.org"
DEFAULT_MAX_FINDINGS = 256

CATEGORY_BIDI_CONTROL = "bidi_control"
CATEGORY_ZERO_WIDTH = "zero_width"
CATEGORY_VARIATION_SELECTOR = "variation_selector"
CATEGORY_TAG = "tag"
CATEGORY_ENCLOSING_MARK = "enclosing_mark"
CATEGORY_LINE_SEPARATOR = "line_separator"
CATEGORY_DEPRECATED = "deprecated"
CATEGORY_FORMAT = "format"
CATEGORY_CONTROL = "control"
CATEGORY_PRIVATE_USE = "private_use"
CATEGORY_NONCHARACTER = "noncharacter"
CATEGORY_SURROGATE = "surrogate"

SCAN_CATEGORIES = (
    CATEGORY_BIDI_CONTROL,
    CATEGORY_ZERO_WIDTH,
    CATEGORY_VARIATION_SELECTOR,
    CATEGORY_TAG,
    CATEGORY_ENCLOSING_MARK,
    CATEGORY_LINE_SEPARATOR,
    CATEGORY_DEPRECATED,
    CATEGORY_FORMAT,
    CATEGORY_CONTROL,
    CATEGORY_PRIVATE_USE,
    CATEGORY_NONCHARACTER,
    CATEGORY_SURROGATE,
)
SECURITY_SCAN_CATEGORIES = (
    CATEGORY_BIDI_CONTROL,
    CATEGORY_ZERO_WIDTH,
    CATEGORY_TAG,
    CATEGORY_CONTROL,
    CATEGORY_NONCHARACTER,
    CATEGORY_SURROGATE,
)
TROJAN_SOURCE_CATEGORIES = (CATEGORY_BIDI_CONTROL,)

CATEGORY_DESCRIPTIONS = {
    CATEGORY_BIDI_CONTROL: "bidirectional override/isolate (Trojan Source reordering)",
    CATEGORY_ZERO_WIDTH: "zero-width or invisible spacing character",
    CATEGORY_VARIATION_SELECTOR: "variation selector (glyph/steganography carrier)",
    CATEGORY_TAG: "Unicode tag character (hidden text / prompt-injection smuggling)",
    CATEGORY_ENCLOSING_MARK: "enclosing combining mark (alters surrounding glyph)",
    CATEGORY_LINE_SEPARATOR: "line/paragraph separator (breaks parsers, invisible)",
    CATEGORY_DEPRECATED: "deprecated format control or interlinear annotation",
    CATEGORY_FORMAT: "general Unicode format control (Cf)",
    CATEGORY_CONTROL: "C0/C1 control character",
    CATEGORY_PRIVATE_USE: "private-use codepoint (renderer-defined)",
    CATEGORY_NONCHARACTER: "Unicode noncharacter or unassigned codepoint",
    CATEGORY_SURROGATE: "lone surrogate codepoint",
}

_ALLOWED_WHITESPACE = frozenset({0x09, 0x0A, 0x0D, 0x20})

_BIDI_CONTROL = frozenset(
    {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
)

_DEPRECATED = frozenset({*range(0x206A, 0x2070), 0xFFF9, 0xFFFA, 0xFFFB})

_ZERO_WIDTH = frozenset(
    {
        0x00AD,
        0x034F,
        0x115F,
        0x1160,
        0x17B4,
        0x17B5,
        0x180E,
        0x200B,
        0x200C,
        0x200D,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
        0x3164,
        0xFEFF,
        0xFFA0,
    }
)

_VARIATION_SELECTOR = frozenset({*range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0)})

_TAG = frozenset(range(0xE0000, 0xE0080))
_FORMAT_RANGES = (
    (0x0600, 0x0605),
    (0x06DD, 0x06DD),
    (0x070F, 0x070F),
    (0x0890, 0x0891),
    (0x08E2, 0x08E2),
    (0x110BD, 0x110BD),
    (0x110CD, 0x110CD),
    (0x13430, 0x1343F),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
)


def _is_noncharacter(codepoint: int) -> bool:
    if 0xFDD0 <= codepoint <= 0xFDEF:
        return True
    return (codepoint & 0xFFFF) in {0xFFFE, 0xFFFF}


def _is_format(codepoint: int) -> bool:
    for start, end in _FORMAT_RANGES:
        if start <= codepoint <= end:
            return True
    return False


def classify_hidden_codepoint(codepoint: int) -> str | None:
    require_int("codepoint", codepoint)
    if codepoint < 0 or codepoint > 0x10FFFF:
        raise ValueError("codepoint must be a Unicode scalar value")
    if codepoint in _ALLOWED_WHITESPACE:
        return None
    if codepoint in _BIDI_CONTROL:
        return CATEGORY_BIDI_CONTROL
    if codepoint in _DEPRECATED:
        return CATEGORY_DEPRECATED
    if codepoint in _ZERO_WIDTH:
        return CATEGORY_ZERO_WIDTH
    if codepoint in _VARIATION_SELECTOR:
        return CATEGORY_VARIATION_SELECTOR
    if codepoint in _TAG:
        return CATEGORY_TAG
    if _is_noncharacter(codepoint):
        return CATEGORY_NONCHARACTER
    if 0xD800 <= codepoint <= 0xDFFF:
        return CATEGORY_SURROGATE
    if _is_format(codepoint):
        return CATEGORY_FORMAT
    category = unicodedata.category(chr(codepoint))
    if category == "Me":
        return CATEGORY_ENCLOSING_MARK
    if category in {"Zl", "Zp"}:
        return CATEGORY_LINE_SEPARATOR
    if category == "Cc":
        return CATEGORY_CONTROL
    if category == "Cf":
        return CATEGORY_FORMAT
    if category == "Co":
        return CATEGORY_PRIVATE_USE
    if category == "Cs":
        return CATEGORY_SURROGATE
    if category == "Cn":
        return CATEGORY_NONCHARACTER
    return None


def codepoint_label(codepoint: int) -> str:
    require_int("codepoint", codepoint)
    if codepoint < 0 or codepoint > 0x10FFFF:
        raise ValueError("codepoint must be a Unicode scalar value")
    try:
        name = unicodedata.name(chr(codepoint))
    except ValueError:
        name = ""
    base = f"U+{codepoint:04X}"
    return f"{base} {name}" if name else base


def normalize_scan_categories(categories: Iterable[str] | None) -> frozenset[str]:
    if categories is None:
        return frozenset(SCAN_CATEGORIES)
    selected = frozenset(categories)
    unknown = selected - frozenset(SCAN_CATEGORIES)
    if unknown:
        raise ValueError(f"unknown scan categories: {sorted(unknown)}")
    return selected


@dataclass(frozen=True, slots=True)
class HiddenFinding:
    index: int
    codepoint: int
    category: str
    context: str = "prose"
    severity: str = "medium"
    why: str = ""
    remedy: str = ""

    @property
    def label(self) -> str:
        return codepoint_label(self.codepoint)


_SEVERITY_RANK = {"info": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True, slots=True)
class ScanResult:
    source_length: int
    total: int
    counts: dict[str, int]
    findings: tuple[HiddenFinding, ...]
    truncated: bool
    fuckmark_carriers: int

    @property
    def detected(self) -> bool:
        return self.total > 0

    @property
    def verdict(self) -> str:
        return "hidden-characters-found" if self.detected else "clean"

    @property
    def first_hit(self) -> str:
        if not self.findings:
            return ""
        first = self.findings[0]
        return f"U+{first.codepoint:04X}@{first.index}({first.category})"

    @property
    def highest_severity(self) -> str:
        if not self.findings:
            return ""
        return max(self.findings, key=lambda item: _SEVERITY_RANK.get(item.severity, 0)).severity

    def active_categories(self) -> tuple[str, ...]:
        return tuple(name for name in SCAN_CATEGORIES if self.counts.get(name, 0) > 0)


def scan_hidden_characters(
    text: str,
    *,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    language: str | None = None,
) -> ScanResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    require_int("max_findings", max_findings)
    if max_findings < 0:
        raise ValueError("max_findings must not be negative")
    lang = normalize_language(language)
    roles = source_roles(text, lang)
    approved = product_approved_carriers_v1()
    counts = {name: 0 for name in SCAN_CATEGORIES}
    findings: list[HiddenFinding] = []
    total = 0
    truncated = False
    carriers = 0
    for index, character in enumerate(text):
        code = ord(character)
        if code in approved:
            carriers += 1
        category = classify_hidden_codepoint(code)
        if category is None:
            continue
        total += 1
        counts[category] += 1
        if len(findings) < max_findings:
            context, severity, why, remedy = annotate_finding(text, index, category, roles[index])
            findings.append(
                HiddenFinding(
                    index=index,
                    codepoint=code,
                    category=category,
                    context=context,
                    severity=severity,
                    why=why,
                    remedy=remedy,
                )
            )
        else:
            truncated = True
    return ScanResult(
        source_length=len(text),
        total=total,
        counts=counts,
        findings=tuple(findings),
        truncated=truncated,
        fuckmark_carriers=carriers,
    )


def extract_tag_payload(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    pieces: list[str] = []
    for character in text:
        code = ord(character)
        if 0xE0020 <= code <= 0xE007E:
            pieces.append(chr(code - 0xE0000))
    return "".join(pieces)


def clean_hidden_characters(
    text: str,
    *,
    categories: Iterable[str] | None = None,
) -> tuple[str, int]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    selected = normalize_scan_categories(categories)
    kept: list[str] = []
    removed = 0
    for character in text:
        category = classify_hidden_codepoint(ord(character))
        if category is not None and category in selected:
            removed += 1
            continue
        kept.append(character)
    return "".join(kept), removed


def autofix_trojan_source(text: str) -> tuple[str, int]:
    return clean_hidden_characters(text, categories=TROJAN_SOURCE_CATEGORIES)


def scan_machine_line(result: ScanResult) -> str:
    found = "yes" if result.detected else "no"
    categories = ",".join(f"{name}={result.counts[name]}" for name in result.active_categories())
    return (
        "fuckmark-scan "
        f"found={found} total={result.total} source_length={result.source_length} "
        f"fuckmark_carriers={result.fuckmark_carriers} truncated={'yes' if result.truncated else 'no'} "
        f"first={result.first_hit} severity={result.highest_severity or 'none'} "
        f"categories={categories or 'none'}"
    )


def scan_human_report(result: ScanResult, *, max_lines: int = 20) -> str:
    require_int("max_lines", max_lines)
    if max_lines < 0:
        raise ValueError("max_lines must not be negative")
    if not result.detected:
        return (
            "FuckMark scan: no hidden characters found.\n"
            f"Scanned {result.source_length} characters; the text is clean.\n"
        )
    lines = [
        "FuckMark scan: hidden characters found.",
        f"Found {result.total} hidden or suspicious codepoints "
        f"across {len(result.active_categories())} categories "
        f"in {result.source_length} characters.",
    ]
    for name in result.active_categories():
        lines.append(f"  {name}: {result.counts[name]} ({CATEGORY_DESCRIPTIONS[name]})")
    shown = result.findings[:max_lines]
    if shown:
        lines.append("First locations:")
        for finding in shown:
            extra = f" {finding.severity}/{finding.context}" if finding.severity else ""
            lines.append(f"  @{finding.index} {finding.label} [{finding.category}]{extra}")
            if finding.why:
                lines.append(f"    {finding.why}")
                lines.append(f"    {finding.remedy}")
    if result.truncated or len(result.findings) > len(shown):
        lines.append("  ... more locations not listed.")
    if result.fuckmark_carriers:
        lines.append(f"{result.fuckmark_carriers} of these are FuckMark carrier codepoints.")
    lines.append("Use --clean to strip these characters, keeping the visible text.")
    return "\n".join(lines) + "\n"


def scan_dict(result: ScanResult) -> dict[str, object]:
    return {
        "algorithm_version": SCAN_ALGORITHM_VERSION,
        "found": result.detected,
        "total": result.total,
        "source_length": result.source_length,
        "fuckmark_carriers": result.fuckmark_carriers,
        "truncated": result.truncated,
        "first": result.first_hit,
        "highest_severity": result.highest_severity,
        "counts": {name: result.counts[name] for name in result.active_categories()},
        "findings": [
            {
                "index": finding.index,
                "codepoint": f"U+{finding.codepoint:04X}",
                "category": finding.category,
                "label": finding.label,
                "context": finding.context,
                "severity": finding.severity,
                "why": finding.why,
                "remedy": finding.remedy,
            }
            for finding in result.findings
        ],
    }
