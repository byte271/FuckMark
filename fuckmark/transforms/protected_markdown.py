from __future__ import annotations

from bisect import bisect_right

from .protected_patterns import (
    _append,
    _is_escaped,
    _line_content_end,
    _line_starts,
    _skip_reference_whitespace,
)
from .schema import ProtectedSpanKind

_MAX_MARKDOWN_LABEL = 999


def _normalize_markdown_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _markdown_bracket_pairs(text: str) -> tuple[tuple[int, int], ...]:
    stack: list[int] = []
    pairs: list[tuple[int, int]] = []
    for index, character in enumerate(text):
        if character not in "[]" or _is_escaped(text, index):
            continue
        if character == "[":
            stack.append(index)
            continue
        if not stack:
            continue
        start = stack.pop()
        inner = index - start - 1
        if inner > _MAX_MARKDOWN_LABEL:
            continue
        pairs.append((start, index))
    return tuple(pairs)


def _line_index(line_starts: tuple[int, ...], index: int) -> int:
    return bisect_right(line_starts, index) - 1


def _skip_blockquotes(text: str, index: int, limit: int) -> int:
    while True:
        spaces = 0
        cursor = index
        while cursor < limit and spaces < 4 and text[cursor] == " ":
            spaces += 1
            cursor += 1
        if cursor < limit and text[cursor] == ">":
            index = cursor + 1
            if index < limit and text[index] in " \t":
                index += 1
            continue
        return index


def _skip_list_marker(text: str, index: int, limit: int) -> int:
    spaces = 0
    cursor = index
    while cursor < limit and spaces < 4 and text[cursor] == " ":
        spaces += 1
        cursor += 1
    if spaces >= 4:
        return index
    if cursor < limit and text[cursor] in "-+*":
        nxt = cursor + 1
        if nxt < limit and text[nxt] in " \t":
            return nxt + 1
        return index
    digits = 0
    while cursor < limit and text[cursor].isdigit() and digits < 9:
        cursor += 1
        digits += 1
    if digits and cursor < limit and text[cursor] in ".)":
        cursor += 1
        if cursor < limit and text[cursor] in " \t":
            return cursor + 1
    return index


def _is_reference_definition_label(
    text: str,
    start: int,
    end: int,
    line_starts: tuple[int, ...],
) -> bool:
    line_i = _line_index(line_starts, start)
    line_start = line_starts[line_i]
    next_start = line_starts[line_i + 1] if line_i + 1 < len(line_starts) else len(text)
    limit = _line_content_end(text, line_start, next_start)
    cursor = _skip_blockquotes(text, line_start, limit)
    cursor = _skip_list_marker(text, cursor, limit)
    indent = 0
    while cursor < start and indent < 4 and text[cursor] == " ":
        indent += 1
        cursor += 1
    if cursor != start or indent >= 4:
        return False
    after = _skip_reference_whitespace(text, end + 1)
    return after < len(text) and text[after] == ":"


def _parse_link_destination(text: str, start: int) -> tuple[int, int] | None:
    index = start
    length = len(text)
    if index >= length:
        return None
    if text[index] == "<":
        cursor = index + 1
        while cursor < length and text[cursor] not in ">\r\n":
            if text[cursor] == "\\" and cursor + 1 < length:
                cursor += 2
                continue
            cursor += 1
        if cursor < length and text[cursor] == ">":
            return index, cursor + 1
        return None
    cursor = index
    depth = 0
    while cursor < length:
        character = text[cursor]
        if character in " \t\r\n" or ord(character) < 32:
            break
        if character == "\\" and cursor + 1 < length:
            cursor += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                break
            depth -= 1
        cursor += 1
    if cursor <= index:
        return None
    return index, cursor


def _definition_labels(text: str, pairs: tuple[tuple[int, int], ...]) -> dict[str, list[tuple[int, int, int, int]]]:
    found: dict[str, list[tuple[int, int, int, int]]] = {}
    line_starts = _line_starts(text)
    for start, end in pairs:
        if not _is_reference_definition_label(text, start, end, line_starts):
            continue
        after = _skip_reference_whitespace(text, end + 1)
        if after >= len(text) or text[after] != ":":
            continue
        dest_from = _skip_reference_whitespace(text, after + 1)
        destination = _parse_link_destination(text, dest_from)
        if destination is None:
            continue
        dest_start, dest_end = destination
        inner = text[start + 1 : end]
        if not inner.strip():
            continue
        if end - start - 1 > _MAX_MARKDOWN_LABEL:
            continue
        key = _normalize_markdown_label(inner)
        found.setdefault(key, []).append((start + 1, end, dest_start, dest_end))
    return found


def resolve_markdown_reference_hrefs(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    pairs = _markdown_bracket_pairs(text)
    defined = _definition_labels(text, pairs)
    by_start = {start: (start, end) for start, end in pairs}
    hrefs: list[str] = []
    seen_pair_starts: set[int] = set()
    line_starts = _line_starts(text)
    for start, end in pairs:
        if start in seen_pair_starts:
            continue
        if _is_reference_definition_label(text, start, end, line_starts):
            continue
        following = by_start.get(end + 1)
        if following is not None:
            seen_pair_starts.add(following[0])
            label_inner = text[following[0] + 1 : following[1]]
            if label_inner.strip() == "":
                label_inner = text[start + 1 : end]
            key = _normalize_markdown_label(label_inner)
            rows = defined.get(key)
            if not rows:
                continue
            dest_start, dest_end = rows[0][2], rows[0][3]
            hrefs.append(_destination_href(text[dest_start:dest_end]))
            continue
        if end + 1 < len(text) and text[end + 1] == "(":
            continue
        label_inner = text[start + 1 : end]
        key = _normalize_markdown_label(label_inner)
        rows = defined.get(key)
        if not rows:
            continue
        dest_start, dest_end = rows[0][2], rows[0][3]
        hrefs.append(_destination_href(text[dest_start:dest_end]))
    return tuple(hrefs)


def _destination_href(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == "<" and raw[-1] == ">":
        return raw[1:-1]
    return raw


def _add_markdown_reference_spans(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    pairs = _markdown_bracket_pairs(text)
    if not pairs:
        return
    defined = _definition_labels(text, pairs)
    if not defined:
        return
    line_starts = _line_starts(text)
    for _key, rows in defined.items():
        for label_start, label_end, dest_start, dest_end in rows:
            _append(raw, label_start, label_end, ProtectedSpanKind.MARKDOWN_LABEL)
            _append(raw, dest_start, dest_end, ProtectedSpanKind.MARKDOWN_DESTINATION)
    by_start = {start: (start, end) for start, end in pairs}
    seen_pair_starts: set[int] = set()
    for start, end in pairs:
        if start in seen_pair_starts:
            continue
        if _is_reference_definition_label(text, start, end, line_starts):
            continue
        following = by_start.get(end + 1)
        if following is not None:
            seen_pair_starts.add(following[0])
            label_inner = text[following[0] + 1 : following[1]]
            if label_inner.strip() == "":
                inner_start, inner_end = start + 1, end
                label_inner = text[inner_start:inner_end]
            else:
                inner_start, inner_end = following[0] + 1, following[1]
            if _normalize_markdown_label(label_inner) in defined:
                _append(raw, inner_start, inner_end, ProtectedSpanKind.MARKDOWN_LABEL)
            continue
        if end + 1 < len(text) and text[end + 1] == "(":
            continue
        inner_start, inner_end = start + 1, end
        label_inner = text[inner_start:inner_end]
        if _normalize_markdown_label(label_inner) in defined:
            _append(raw, inner_start, inner_end, ProtectedSpanKind.MARKDOWN_LABEL)


def markdown_label_closers(text: str) -> frozenset[int]:
    return frozenset(end for _start, end in _markdown_bracket_pairs(text))
