from __future__ import annotations


CONTEXT_IDENTIFIER = "identifier"
CONTEXT_EMOJI = "emoji"
CONTEXT_STRING = "string"
CONTEXT_PROSE = "prose"

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_INFO = "info"

_ZWJ = 0x200D
_VS = frozenset({*range(0xFE00, 0xFE10)})


def _is_emojiish(codepoint: int) -> bool:
    if codepoint < 0:
        return False
    if 0x1F1E6 <= codepoint <= 0x1F1FF:
        return True
    if 0x1F000 <= codepoint <= 0x1FAFF:
        return True
    if 0x2600 <= codepoint <= 0x27BF:
        return True
    return codepoint in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299, _ZWJ}


def _is_ident_char(character: str) -> bool:
    if not character:
        return False
    return character == "_" or character.isalnum()


def classify_context(text: str, index: int, in_string: bool) -> str:
    prev = text[index - 1] if index > 0 else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    prev_cp = ord(prev) if prev else -1
    nxt_cp = ord(nxt) if nxt else -1
    if _is_emojiish(prev_cp) or _is_emojiish(nxt_cp) or prev_cp in _VS or nxt_cp in _VS:
        return CONTEXT_EMOJI
    if _is_ident_char(prev) and _is_ident_char(nxt):
        return CONTEXT_IDENTIFIER
    if _is_ident_char(nxt) or _is_ident_char(prev):
        return CONTEXT_IDENTIFIER
    if in_string:
        return CONTEXT_STRING
    return CONTEXT_PROSE


def score_severity(category: str, context: str) -> str:
    if category == "tag":
        return SEVERITY_CRITICAL
    if category == "bidi_control":
        if context == CONTEXT_IDENTIFIER:
            return SEVERITY_CRITICAL
        return SEVERITY_HIGH
    if category == "zero_width":
        if context == CONTEXT_EMOJI:
            return SEVERITY_INFO
        if context == CONTEXT_IDENTIFIER:
            return SEVERITY_HIGH
        return SEVERITY_MEDIUM
    if category == "variation_selector":
        if context == CONTEXT_EMOJI:
            return SEVERITY_INFO
        return SEVERITY_MEDIUM
    if category in {"control", "noncharacter", "surrogate"}:
        return SEVERITY_HIGH
    if category == "enclosing_mark":
        return SEVERITY_MEDIUM
    return SEVERITY_MEDIUM


def explain_finding(category: str, context: str, severity: str) -> tuple[str, str]:
    if category == "bidi_control" and context == CONTEXT_IDENTIFIER:
        return (
            "Bidirectional override sits inside an identifier, so the glyphs can read differently than the bytes (Trojan Source).",
            "Strip the bidi control and keep the identifier left-to-right.",
        )
    if category == "bidi_control":
        return (
            "Bidirectional override can reorder nearby glyphs (Trojan Source class, CVE-2021-42574).",
            "Strip U+202A-U+202E / U+2066-U+2069 and rewrite the text left-to-right.",
        )
    if category == "tag":
        return (
            "Unicode tag characters encode a second ASCII string that models read and humans do not.",
            "Strip U+E0020-U+E007F; inspect tag_payload for the smuggled text.",
        )
    if category == "zero_width" and context == CONTEXT_EMOJI:
        return (
            "Zero-width joiner or invisible mark inside an emoji cluster; usually a legitimate emoji sequence.",
            "Leave emoji ZWJ sequences unless you are sanitizing for a security boundary.",
        )
    if category == "zero_width" and context == CONTEXT_IDENTIFIER:
        return (
            "Zero-width character splits an identifier, breaking search and some compilers while looking unchanged.",
            "Strip the zero-width character from the identifier.",
        )
    if category == "zero_width":
        return (
            "Invisible spacing or joining character that changes the byte stream without changing the glyphs.",
            "Strip the zero-width character.",
        )
    if category == "variation_selector" and context == CONTEXT_EMOJI:
        return (
            "Variation selector tunes an emoji glyph; usually benign.",
            "Keep emoji variation selectors unless you are stripping all hidden marks.",
        )
    if severity == SEVERITY_HIGH:
        return (
            "Hidden or non-text codepoint that should not appear in ordinary source or prompts.",
            "Strip the character.",
        )
    return (
        "Hidden or format codepoint that is invisible or renderer-defined.",
        "Strip the character if this text crosses a trust boundary.",
    )


def annotate_finding(text: str, index: int, category: str, in_string: bool) -> tuple[str, str, str, str]:
    context = classify_context(text, index, in_string)
    severity = score_severity(category, context)
    why, remedy = explain_finding(category, context, severity)
    return context, severity, why, remedy


def advance_string_state(state: str, character: str) -> str:
    if state:
        if character == state:
            return ""
        return state
    if character in {'"', "'", "`"}:
        return character
    return ""
