from __future__ import annotations

import re
from collections.abc import Sequence

from .protected_patterns import _append, _is_escaped, _line_end, _trim_terminal_punctuation
from .schema import ProtectedSpanKind


_INLINE_CODE_RUN_RE = re.compile(r"`+")


_FENCE_OPEN_RE = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[^\n]*(?:\n|$)")


_CURLY_SINGLE_QUOTE_RE = re.compile(r"‘[^’\n]{2,}’")


_STRAIGHT_SINGLE_QUOTE_RE = re.compile(r"(?<!\w)'[^'\n]{2,}'(?!\w)")


_POSIX_PATH_RE = re.compile(r"(?<![\w:])(?:~?/|\./|\.\./)(?:[A-Za-z0-9._~+@%-]+/)*[A-Za-z0-9._~+@%-]+/?")


_WINDOWS_PATH_RE = re.compile(r"(?i)(?<![A-Z0-9_])(?:[A-Z]:\\|\\\\[A-Z0-9._$-]+\\)(?:[^\\/:*?\"<>|\s]+\\)*[^\\/:*?\"<>|\s]+")


_WINDOWS_PREFIX_RE = re.compile(r"(?i)(?<![A-Z0-9_])(?:[A-Z]:\\|\\\\[A-Z0-9._$-]+\\)")


_POSIX_PREFIX_RE = re.compile(r"(?<![\w:])(?:~?/|\./|\.\./)")


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


def _add_inline_code(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    cursor = 0
    while True:
        opening = _INLINE_CODE_RUN_RE.search(text, cursor)
        if opening is None:
            return
        run = opening.group()
        if _is_escaped(text, opening.start()):
            cursor = opening.end()
            continue
        if len(run) >= 3 and (opening.start() == 0 or text[opening.start() - 1] == "\n"):
            cursor = opening.end()
            continue
        end_of_line = _line_end(text, opening.end())
        closing = text.find(run, opening.end(), end_of_line)
        end = end_of_line if closing < 0 else closing + len(run)
        _append(raw, opening.start(), end, ProtectedSpanKind.CODE)
        cursor = max(end, opening.end())


def _add_double_quotations(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    index = 0
    while index < len(text):
        if text[index] == "\"" and not _is_escaped(text, index):
            end_of_line = _line_end(text, index + 1)
            cursor = index + 1
            while True:
                closing = text.find("\"", cursor, end_of_line)
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
        while index < len(text) and text[index] != "\n":
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


def _add_posix_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _POSIX_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        _append(raw, start, end, ProtectedSpanKind.POSIX_PATH)


def _add_windows_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _WINDOWS_PATH_RE.finditer(text):
        start, end = _trim_terminal_punctuation(text, match.start(), match.end())
        _append(raw, start, end, ProtectedSpanKind.WINDOWS_PATH)


def _path_scan_limit(text: str, start: int, forbidden: str) -> int:
    end = _line_end(text, start)
    for index in range(start, end):
        if text[index] in forbidden:
            return index
    return end


def _extended_path_end(text: str, start: int, prefix_end: int, separator: str, forbidden: str) -> int | None:
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
    _, end = _trim_terminal_punctuation(text, start, end)
    return end if end > prefix_end else None


def _starts_inside_other_protection(
    raw: Sequence[tuple[int, int, ProtectedSpanKind]],
    start: int,
    own_kind: ProtectedSpanKind,
) -> bool:
    return any(left <= start < right and kind is not own_kind for left, right, kind in raw)


def _add_extended_windows_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _WINDOWS_PREFIX_RE.finditer(text):
        if _starts_inside_other_protection(raw, match.start(), ProtectedSpanKind.WINDOWS_PATH):
            continue
        end = _extended_path_end(text, match.start(), match.end(), "\\", '<>"|?*')
        if end is not None:
            _append(raw, match.start(), end, ProtectedSpanKind.WINDOWS_PATH)


def _add_extended_posix_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _POSIX_PREFIX_RE.finditer(text):
        if _starts_inside_other_protection(raw, match.start(), ProtectedSpanKind.POSIX_PATH):
            continue
        end = _extended_path_end(text, match.start(), match.end(), "/", '<>"|')
        if end is not None:
            _append(raw, match.start(), end, ProtectedSpanKind.POSIX_PATH)


def _looks_like_currency_dollar(text: str, index: int) -> bool:
    suffix = text[index + 1:_line_end(text, index + 1)]
    return re.match(r"\s*[-+]?(?:\d|\.\d)", suffix) is not None


def _add_dollar_math(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    index = 0
    while index < len(text):
        if text[index] != "$" or _is_escaped(text, index):
            index += 1
            continue
        if text.startswith("$$", index):
            closing = text.find("$$", index + 2)
            end = len(text) if closing < 0 else closing + 2
            _append(raw, index, end, ProtectedSpanKind.MATH)
            index = max(end, index + 2)
            continue
        if _looks_like_currency_dollar(text, index):
            index += 1
            continue
        end_of_line = _line_end(text, index + 1)
        closing = index + 1
        while True:
            closing = text.find("$", closing, end_of_line)
            if closing < 0:
                _append(raw, index, end_of_line, ProtectedSpanKind.MATH)
                index = max(end_of_line, index + 1)
                break
            if not _is_escaped(text, closing):
                _append(raw, index, closing + 1, ProtectedSpanKind.MATH)
                index = closing + 1
                break
            closing += 1


def _add_delimited_math(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for opening, closing in ((r"\(", r"\)"), (r"\[", r"\]")):
        cursor = 0
        while True:
            start = text.find(opening, cursor)
            if start < 0:
                break
            end_of_line = _line_end(text, start + len(opening))
            close = text.find(closing, start + len(opening), end_of_line)
            end = end_of_line if close < 0 else close + len(closing)
            _append(raw, start, end, ProtectedSpanKind.MATH)
            cursor = max(end, start + len(opening))
