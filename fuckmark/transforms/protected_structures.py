from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Sequence

from .protected_patterns import _append, _is_escaped, _line_content_end, _line_end, _line_starts, _trim_terminal_punctuation
from .schema import ProtectedSpanKind

_INLINE_CODE_RUN_RE = re.compile(r"`+")
_FENCE_OPEN_RE = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[^\n]*(?:\n|$)")
_BLANK_LINE_RE = re.compile(r"\r?\n[ \t]*\r?\n")
_CURLY_SINGLE_QUOTE_RE = re.compile(r"‘[^’\n]{2,}’")
_STRAIGHT_SINGLE_QUOTE_RE = re.compile(r"(?<!\w)'[^'\n]{2,}'(?!\w)")
_POSIX_PATH_RE = re.compile(r"(?<![\w:])(?:~?/|\./|\.\./)(?:[A-Za-z0-9._~+@%-]+/)*[A-Za-z0-9._~+@%-]+/?")
_RELATIVE_PATH_RE = re.compile(
    r"(?<![\w:/])(?:[A-Za-z0-9._~+@%-]+/)+[A-Za-z0-9._~+@%-]*\.[A-Za-z][A-Za-z0-9]{0,11}/?"
)
_EXTENSIONLESS_RELATIVE_PATH_RE = re.compile(
    r"(?<![\w:/])(?:[A-Za-z0-9._~+@%-]+/){1,}[A-Za-z0-9._~+@%-]+/?"
)
_FILENAME_TOKEN = r"[A-Za-z0-9._~+@%'-]+"
_SPACED_BASENAME = rf"(?:{_FILENAME_TOKEN} ){{1,3}}{_FILENAME_TOKEN}\.[A-Za-z][A-Za-z0-9]{{0,11}}"
_WINDOWS_SPACED_FILE_RE = re.compile(
    rf"(?i)(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)(?:{_FILENAME_TOKEN}[/\\])+{_SPACED_BASENAME}"
)
_POSIX_SPACED_FILE_RE = re.compile(
    rf"(?<![\w:])(?:~?/|\./|\.\./)(?:{_FILENAME_TOKEN}/)+{_SPACED_BASENAME}"
)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]{0,64}(?:\s[^<>\r\n]{0,1024})?/?>")
_HTML_ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{0,31}|#[0-9]{1,7}|#x[0-9A-Fa-f]{1,6});")
_PROSE_SLASH_PAIRS = frozenset(
    {
        "and/or",
        "or/and",
        "either/or",
        "he/she",
        "she/he",
        "his/her",
        "her/his",
        "yes/no",
        "no/yes",
        "on/off",
        "off/on",
        "true/false",
        "false/true",
        "n/a",
        "w/o",
        "c/o",
        "a/k/a",
        "i/o",
        "input/output",
        "output/input",
        "read/write",
        "write/read",
        "high/low",
        "low/high",
        "left/right",
        "right/left",
        "up/down",
        "down/up",
        "plus/minus",
        "minus/plus",
    }
)
_PATH_ROOTS = frozenset(
    {
        "src",
        "lib",
        "bin",
        "sbin",
        "scripts",
        "tests",
        "docs",
        "dist",
        "tmp",
        "temp",
        "usr",
        "var",
        "opt",
        "etc",
        "include",
        "vendor",
        "pkg",
        "pkgs",
        "tools",
        "assets",
        "static",
        "cmake",
        "modules",
        "third_party",
        "node_modules",
    }
)
_WINDOWS_PATH_RE = re.compile(
    r"(?i)(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)(?:[^\\/:*?\"<>|\s]+[/\\])*[^\\/:*?\"<>|\s]+"
)
_WINDOWS_PREFIX_RE = re.compile(r"(?i)(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)")
_POSIX_PREFIX_RE = re.compile(r"(?<![\w:])(?:~?/|\./|\.\./)")
_EXTENDED_BOUNDARY_RE = re.compile(r"[ \t]+(?=(?ai:https?://|www\.)|(?:/|~/|\./|\.\./)|[A-Za-z]:\\|\\\\|--?[A-Za-z])")
_MAX_EXTENDED_PATH_SCAN = 4096
_CURRENCY_DOLLAR_SUFFIX_RE = re.compile(r"[^\S\r\n]*[-+]?(?:\d|\.\d)")


def _add_fenced_code(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    cursor = 0
    while True:
        opening = _FENCE_OPEN_RE.search(text, cursor)
        if opening is None:
            return
        run = opening.group(1)
        marker = run[0]
        minimum = len(run)
        close_re = re.compile(rf"(?m)^[ \t]{{0,3}}{re.escape(marker)}{{{minimum},}}[ \t]*(?:\n|$)")
        closing = close_re.search(text, opening.end())
        end = len(text) if closing is None else closing.end()
        _append(raw, opening.start(), end, ProtectedSpanKind.CODE)
        if closing is None:
            return
        cursor = end


def _paragraph_end(text: str, start: int) -> int:
    match = _BLANK_LINE_RE.search(text, start)
    return len(text) if match is None else match.start()


def _add_indented_code(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    starts = _line_starts(text)
    count = len(starts)
    for index, start in enumerate(starts):
        next_start = starts[index + 1] if index + 1 < count else len(text)
        limit = _line_content_end(text, start, next_start)
        cursor = start
        while True:
            spaces = 0
            look = cursor
            while look < limit and spaces < 4 and text[look] == " ":
                spaces += 1
                look += 1
            if look < limit and text[look] == ">":
                cursor = look + 1
                if cursor < limit and text[cursor] in " \t":
                    cursor += 1
                continue
            break
        if cursor < limit and text[cursor] == "\t":
            _append(raw, cursor, limit, ProtectedSpanKind.CODE)
            continue
        if cursor + 4 <= limit and text[cursor : cursor + 4] == "    ":
            _append(raw, cursor, limit, ProtectedSpanKind.CODE)


def _add_html_markup(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _HTML_TAG_RE.finditer(text):
        _append(raw, match.start(), match.end(), ProtectedSpanKind.CODE)
    for match in _HTML_ENTITY_RE.finditer(text):
        _append(raw, match.start(), match.end(), ProtectedSpanKind.CODE)


def _add_inline_code(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    runs = tuple(match for match in _INLINE_CODE_RUN_RE.finditer(text) if not _is_escaped(text, match.start()))
    if not runs:
        return
    by_length: dict[int, tuple[int, ...]] = {}
    match_by_start = {match.start(): match for match in runs}
    grouped: dict[int, list[int]] = {}
    for match in runs:
        grouped.setdefault(len(match.group()), []).append(match.start())
    for length, starts in grouped.items():
        by_length[length] = tuple(starts)
    consumed_until = -1
    for opening in runs:
        if opening.start() < consumed_until:
            continue
        starts = by_length[len(opening.group())]
        position = bisect_right(starts, opening.start())
        paragraph_end = _paragraph_end(text, opening.end())
        closing = None
        if position < len(starts) and starts[position] < paragraph_end:
            closing = match_by_start[starts[position]]
        if closing is None:
            end = _line_end(text, opening.end())
        else:
            end = closing.end()
        _append(raw, opening.start(), end, ProtectedSpanKind.CODE)
        consumed_until = max(end, opening.end())


def _add_double_quotations(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    index = 0
    while index < len(text):
        if text[index] == '"' and not _is_escaped(text, index):
            end_of_line = _line_end(text, index + 1)
            cursor = index + 1
            while True:
                closing = text.find('"', cursor, end_of_line)
                if closing < 0:
                    _append(raw, index, end_of_line, ProtectedSpanKind.QUOTATION)
                    index = max(end_of_line, index + 1)
                    break
                if not _is_escaped(text, closing):
                    _append(raw, index, closing + 1, ProtectedSpanKind.QUOTATION)
                    index = closing + 1
                    break
                cursor = closing + 1
            continue
        if text[index] == "“":
            end_of_line = _line_end(text, index + 1)
            closing = text.find("”", index + 1, end_of_line)
            end = end_of_line if closing < 0 else closing + 1
            _append(raw, index, end, ProtectedSpanKind.QUOTATION)
            index = max(end, index + 1)
            continue
        index += 1


def _add_markdown_destinations(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    cursor = 0
    while True:
        marker = text.find("](", cursor)
        if marker < 0:
            return
        if _is_escaped(text, marker):
            cursor = marker + 2
            continue
        start = marker + 2
        depth = 1
        index = start
        escaped = False
        while index < len(text):
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    _append(raw, start, index, ProtectedSpanKind.MARKDOWN_DESTINATION)
                    cursor = index + 1
                    break
            index += 1
        else:
            _append(raw, start, index, ProtectedSpanKind.MARKDOWN_DESTINATION)
            cursor = max(index, start + 1)
            continue
        if depth != 0:
            _append(raw, start, index, ProtectedSpanKind.MARKDOWN_DESTINATION)
            cursor = max(index, start + 1)


def _accept_extensionless_relative(token: str) -> bool:
    compact = token.strip("/").casefold()
    if compact in _PROSE_SLASH_PAIRS:
        return False
    parts = [part for part in token.strip("/").split("/") if part]
    if len(parts) < 2:
        return False
    if len(parts) >= 3:
        return True
    if parts[0].casefold() in _PATH_ROOTS:
        return True
    return any(
        any(character in part for character in "._-") or any(character.isdigit() for character in part)
        for part in parts
    )


def _last_component_has_space(text: str, start: int, end: int, separators: str) -> bool:
    chunk = text[start:end]
    last = -1
    for separator in separators:
        last = max(last, chunk.rfind(separator))
    if last < 0:
        return False
    return " " in chunk[last + 1 :]


def _add_posix_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _POSIX_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        _append(raw, start, end, ProtectedSpanKind.POSIX_PATH)
    for match in _RELATIVE_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        _append(raw, start, end, ProtectedSpanKind.POSIX_PATH)
    for match in _EXTENSIONLESS_RELATIVE_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        token = text[start:end]
        if not _accept_extensionless_relative(token):
            continue
        _append(raw, start, end, ProtectedSpanKind.POSIX_PATH)
    for match in _POSIX_SPACED_FILE_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        if _last_component_has_space(text, start, end, "/"):
            _append(raw, start, end, ProtectedSpanKind.POSIX_PATH)


def _add_windows_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _WINDOWS_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        _append(raw, start, end, ProtectedSpanKind.WINDOWS_PATH)
    for match in _WINDOWS_SPACED_FILE_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        if _last_component_has_space(text, start, end, "/\\"):
            _append(raw, start, end, ProtectedSpanKind.WINDOWS_PATH)


def _path_scan_limit(text: str, start: int, forbidden: str) -> int:
    line_end = _line_end(text, start)
    end = min(line_end, start + _MAX_EXTENDED_PATH_SCAN)
    boundary = _EXTENDED_BOUNDARY_RE.search(text, start, end)
    if boundary is not None:
        end = boundary.start()
    for index in range(start, end):
        if text[index] in forbidden or text[index] == ";":
            return index
    return end


def _extended_path_end(text: str, start: int, prefix_end: int, separator: str, forbidden: str) -> int | None:
    line_end = _line_end(text, prefix_end)
    limit = _path_scan_limit(text, prefix_end, forbidden)
    segment = text[start:limit]
    whitespace_positions = [index for index, character in enumerate(segment) if character in " \t"]
    if not whitespace_positions:
        return None
    if not any(separator in segment[index + 1:] for index in whitespace_positions):
        return None
    end = limit
    for relative in whitespace_positions:
        if separator in segment[relative + 1:]:
            continue
        prefix = segment[:relative].rstrip()
        if re.search(r"\.[A-Za-z0-9]{1,12}$", prefix):
            end = start + relative
            break
    if line_end > prefix_end + _MAX_EXTENDED_PATH_SCAN and limit == prefix_end + _MAX_EXTENDED_PATH_SCAN and end == limit:
        raise ValueError("extended path scan exceeded resource limit")
    _, end = _trim_terminal_punctuation(text, start, end)
    return end if end > prefix_end else None


def _other_protection_index(raw: Sequence[tuple[int, int, ProtectedSpanKind]], own_kind: ProtectedSpanKind) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    ordered = sorted((start, end) for start, end, kind in raw if kind is not own_kind)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    intervals = tuple(merged)
    return tuple(start for start, _ in intervals), intervals


def _starts_inside_other_protection(starts: tuple[int, ...], intervals: tuple[tuple[int, int], ...], start: int) -> bool:
    index = bisect_right(starts, start) - 1
    return index >= 0 and start < intervals[index][1]


def _add_extended_windows_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    starts, intervals = _other_protection_index(raw, ProtectedSpanKind.WINDOWS_PATH)
    for match in _WINDOWS_PREFIX_RE.finditer(text):
        if _starts_inside_other_protection(starts, intervals, match.start()):
            continue
        separator = "/" if match.group().endswith("/") else "\\"
        end = _extended_path_end(text, match.start(), match.end(), separator, '<>"|?*')
        if end is not None:
            _append(raw, match.start(), end, ProtectedSpanKind.WINDOWS_PATH)


def _add_extended_posix_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    starts, intervals = _other_protection_index(raw, ProtectedSpanKind.POSIX_PATH)
    for match in _POSIX_PREFIX_RE.finditer(text):
        if _starts_inside_other_protection(starts, intervals, match.start()):
            continue
        end = _extended_path_end(text, match.start(), match.end(), "/", '<>"|')
        if end is not None:
            _append(raw, match.start(), end, ProtectedSpanKind.POSIX_PATH)


def _looks_like_currency_dollar(text: str, index: int) -> bool:
    return _CURRENCY_DOLLAR_SUFFIX_RE.match(text, index + 1, _line_end(text, index + 1)) is not None




def _find_double_dollar(text: str, start: int) -> int | None:
    cursor = start
    while True:
        index = text.find("$$", cursor)
        if index < 0:
            return None
        if not _is_escaped(text, index) and not (index > 0 and text[index - 1] == "$") and not (index + 2 < len(text) and text[index + 2] == "$"):
            return index
        cursor = index + 1

def _find_single_dollar(text: str, start: int, end: int) -> int | None:
    cursor = start
    while True:
        index = text.find("$", cursor, end)
        if index < 0:
            return None
        if not _is_escaped(text, index) and not (index > 0 and text[index - 1] == "$") and not (index + 1 < len(text) and text[index + 1] == "$"):
            return index
        cursor = index + 1


def _add_dollar_math(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    index = 0
    while index < len(text):
        if text[index] != "$" or _is_escaped(text, index):
            index += 1
            continue
        if text.startswith("$$", index):
            closing = _find_double_dollar(text, index + 2)
            end = len(text) if closing is None else closing + 2
            _append(raw, index, end, ProtectedSpanKind.MATH)
            index = max(end, index + 2)
            continue
        if index > 0 and text[index - 1] == "$":
            index += 1
            continue
        end_of_line = _line_end(text, index + 1)
        closing = _find_single_dollar(text, index + 1, end_of_line)
        if _looks_like_currency_dollar(text, index):
            if closing is None or _looks_like_currency_dollar(text, closing):
                index += 1
                continue
        if closing is None:
            _append(raw, index, end_of_line, ProtectedSpanKind.MATH)
            index = max(end_of_line, index + 1)
            continue
        _append(raw, index, closing + 1, ProtectedSpanKind.MATH)
        index = closing + 1


def _find_unescaped_delimiter(text: str, delimiter: str, start: int, end: int) -> int | None:
    cursor = start
    while True:
        index = text.find(delimiter, cursor, end)
        if index < 0:
            return None
        if not _is_escaped(text, index):
            return index
        cursor = index + 1


def _add_delimited_math(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for opening, closing in ((r"\(", r"\)"), (r"\[", r"\]")):
        cursor = 0
        while True:
            start = text.find(opening, cursor)
            if start < 0:
                break
            if _is_escaped(text, start):
                cursor = start + len(opening)
                continue
            end_of_line = _line_end(text, start + len(opening))
            close = _find_unescaped_delimiter(text, closing, start + len(opening), end_of_line)
            end = end_of_line if close is None else close + len(closing)
            _append(raw, start, end, ProtectedSpanKind.MATH)
            cursor = max(end, start + len(opening))
