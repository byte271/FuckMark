from __future__ import annotations

from pathlib import Path


CONTEXT_IDENTIFIER = "identifier"
CONTEXT_EMOJI = "emoji"
CONTEXT_STRING = "string"
CONTEXT_COMMENT = "comment"
CONTEXT_PROSE = "prose"

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_INFO = "info"

ROLE_CODE = "code"
ROLE_STRING = "string"
ROLE_COMMENT = "comment"

_ZWJ = 0x200D
_VS = frozenset({*range(0xFE00, 0xFE10)})

_LANGUAGE_ALIASES = {
    "auto": "auto",
    "javascript": "javascript",
    "js": "javascript",
    "ts": "javascript",
    "typescript": "javascript",
    "jsx": "javascript",
    "tsx": "javascript",
    "c": "c",
    "h": "c",
    "cc": "c",
    "cpp": "c",
    "cxx": "c",
    "java": "c",
    "go": "c",
    "rs": "c",
    "rust": "c",
    "cs": "c",
    "css": "c",
    "jsonc": "c",
    "python": "python",
    "py": "python",
    "pyi": "python",
    "hash": "python",
    "sh": "python",
    "bash": "python",
    "zsh": "python",
    "shell": "python",
    "shellscript": "python",
    "yaml": "python",
    "yml": "python",
    "rb": "python",
    "ruby": "python",
    "toml": "python",
    "html": "html",
    "htm": "html",
    "xml": "html",
    "sql": "sql",
}

_LANGUAGE_BY_SUFFIX = {
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",
    ".jsx": "javascript",
    ".tsx": "javascript",
    ".c": "c",
    ".h": "c",
    ".hh": "c",
    ".cc": "c",
    ".cpp": "c",
    ".cxx": "c",
    ".java": "c",
    ".go": "c",
    ".rs": "c",
    ".cs": "c",
    ".css": "c",
    ".py": "python",
    ".pyi": "python",
    ".sh": "python",
    ".bash": "python",
    ".zsh": "python",
    ".yaml": "python",
    ".yml": "python",
    ".rb": "python",
    ".toml": "python",
    ".html": "html",
    ".htm": "html",
    ".xml": "html",
    ".sql": "sql",
}


def normalize_language(language: str | None) -> str:
    if language is None:
        return "auto"
    if not isinstance(language, str):
        raise TypeError("language must be a string")
    key = language.strip().lower()
    if not key:
        return "auto"
    return _LANGUAGE_ALIASES.get(key, "auto")


def language_from_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return _LANGUAGE_BY_SUFFIX.get(suffix, "auto")


def _slash_comments(language: str) -> bool:
    return language in {"auto", "javascript", "c", "sql"}


def _block_comments(language: str) -> bool:
    return language in {"auto", "javascript", "c", "sql"}


def _hash_comments(language: str) -> bool:
    return language == "python"


def _sql_line_comments(language: str) -> bool:
    return language == "sql"


def _html_comments(language: str) -> bool:
    return language == "html"


def _is_url_slash_slash(text: str, index: int) -> bool:
    return index > 0 and text[index - 1] == ":"


def source_roles(text: str, language: str | None = None) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    lang = normalize_language(language)
    roles = [ROLE_CODE] * len(text)
    length = len(text)
    index = 0
    in_string = ""
    escape = False
    while index < length:
        character = text[index]
        if in_string:
            roles[index] = ROLE_STRING
            if escape:
                escape = False
                index += 1
                continue
            if character == "\\" and index + 1 < length:
                escape = True
                index += 1
                continue
            if character == in_string:
                in_string = ""
            index += 1
            continue
        pair = text[index : index + 2]
        if _slash_comments(lang) and pair == "//" and not _is_url_slash_slash(text, index):
            cursor = index
            while cursor < length and text[cursor] not in "\n\r":
                roles[cursor] = ROLE_COMMENT
                cursor += 1
            index = cursor
            continue
        if _sql_line_comments(lang) and pair == "--":
            cursor = index
            while cursor < length and text[cursor] not in "\n\r":
                roles[cursor] = ROLE_COMMENT
                cursor += 1
            index = cursor
            continue
        if _block_comments(lang) and pair == "/*":
            close = text.find("*/", index + 2)
            stop = close + 2 if close >= 0 else length
            cursor = index
            while cursor < stop:
                roles[cursor] = ROLE_COMMENT
                cursor += 1
            index = stop
            continue
        if _hash_comments(lang) and character == "#":
            cursor = index
            while cursor < length and text[cursor] not in "\n\r":
                roles[cursor] = ROLE_COMMENT
                cursor += 1
            index = cursor
            continue
        if _html_comments(lang) and text[index : index + 4] == "<!--":
            close = text.find("-->", index + 4)
            stop = close + 3 if close >= 0 else length
            cursor = index
            while cursor < stop:
                roles[cursor] = ROLE_COMMENT
                cursor += 1
            index = stop
            continue
        if character in {'"', "'", "`"}:
            in_string = character
            roles[index] = ROLE_STRING
            index += 1
            continue
        index += 1
    return tuple(roles)


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


def classify_context(text: str, index: int, role: str = ROLE_CODE) -> str:
    prev = text[index - 1] if index > 0 else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    prev_cp = ord(prev) if prev else -1
    nxt_cp = ord(nxt) if nxt else -1
    if _is_emojiish(prev_cp) or _is_emojiish(nxt_cp) or prev_cp in _VS or nxt_cp in _VS:
        return CONTEXT_EMOJI
    if role == ROLE_COMMENT:
        return CONTEXT_COMMENT
    if role == ROLE_STRING:
        return CONTEXT_STRING
    if _is_ident_char(prev) and _is_ident_char(nxt):
        return CONTEXT_IDENTIFIER
    if _is_ident_char(nxt) or _is_ident_char(prev):
        return CONTEXT_IDENTIFIER
    return CONTEXT_PROSE


def score_severity(category: str, context: str) -> str:
    if category == "tag":
        return SEVERITY_CRITICAL
    if category == "bidi_control":
        if context in {CONTEXT_IDENTIFIER, CONTEXT_COMMENT, CONTEXT_STRING}:
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
    if category == "bidi_control" and context == CONTEXT_COMMENT:
        return (
            "Bidirectional override sits inside a comment, so commented-out code can appear to run (Trojan Source commenting-out).",
            "Strip the bidi control from the comment.",
        )
    if category == "bidi_control" and context == CONTEXT_STRING:
        return (
            "Bidirectional override sits inside a string, so the literal can appear to close early (Trojan Source stretched-string).",
            "Strip the bidi control from the string.",
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


def annotate_finding(
    text: str,
    index: int,
    category: str,
    role: str = ROLE_CODE,
) -> tuple[str, str, str, str]:
    context = classify_context(text, index, role)
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
