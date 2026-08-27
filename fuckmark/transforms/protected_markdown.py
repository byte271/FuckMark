from __future__ import annotations

from .protected_patterns import _append, _is_escaped
from .schema import ProtectedSpanKind


def _normalize_markdown_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _markdown_bracket_pairs(text: str) -> tuple[tuple[int, int], ...]:
    stack: list[int] = []
    pairs: list[tuple[int, int]] = []
    for index, character in enumerate(text):
        if character == "\n":
            stack.clear()
            continue
        if character not in "[]" or _is_escaped(text, index):
            continue
        if character == "[":
            stack.append(index)
        elif stack:
            pairs.append((stack.pop(), index))
    return tuple(pairs)


def _line_start(text: str, index: int) -> int:
    newline = text.rfind("\n", 0, index)
    return 0 if newline < 0 else newline + 1


def _is_reference_definition_label(text: str, start: int, end: int) -> bool:
    prefix = text[_line_start(text, start) : start]
    if len(prefix) > 3 or any(character not in " \t" for character in prefix):
        return False
    return end + 1 < len(text) and text[end + 1] == ":"


def _parse_link_destination(text: str, start: int) -> tuple[int, int] | None:
    index = start
    length = len(text)
    while index < length and text[index] in " \t":
        index += 1
    if index >= length or text[index] in "\r\n":
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
        if character in " \t\r\n":
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
    for start, end in pairs:
        if not _is_reference_definition_label(text, start, end):
            continue
        destination = _parse_link_destination(text, end + 2)
        if destination is None:
            continue
        dest_start, dest_end = destination
        inner = text[start + 1 : end]
        if not inner.strip():
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
    for start, end in pairs:
        if start in seen_pair_starts:
            continue
        if _is_reference_definition_label(text, start, end):
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
    for _key, rows in defined.items():
        for label_start, label_end, dest_start, dest_end in rows:
            _append(raw, label_start, label_end, ProtectedSpanKind.MARKDOWN_LABEL)
            _append(raw, dest_start, dest_end, ProtectedSpanKind.MARKDOWN_DESTINATION)
    by_start = {start: (start, end) for start, end in pairs}
    seen_pair_starts: set[int] = set()
    for start, end in pairs:
        if start in seen_pair_starts:
            continue
        if _is_reference_definition_label(text, start, end):
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
