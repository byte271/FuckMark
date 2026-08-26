from __future__ import annotations

from collections.abc import Sequence

from ..product.invariants import validate_user_visible_invariants
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..transforms.protected import _add_valid_markdown_destinations
from ..transforms.protected_patterns import (
    _CLI_FLAG_RE,
    _CURRENCY_RE,
    _EMAIL_RE,
    _NUMBER_RE,
    _PERCENT_RE,
    _add_dates,
    _add_ip_addresses,
    _add_regex,
    _add_urls,
)
from ..transforms.protected_structures import (
    _add_extended_posix_paths,
    _add_extended_windows_paths,
    _add_fenced_code,
    _add_inline_code,
    _add_posix_paths,
    _add_windows_paths,
)
from ..transforms.schema import InvariantStatus, ProtectedSpanKind

LETTER_MIX_APPROVED_CARRIERS = (0x034F, 0xFE00)
LETTER_MIX_PAYLOADS = ("\u034f", "\ufe00")
LETTER_MIX_MAX_SELECTED = 192


def hard_machine_intervals(text: str) -> tuple[tuple[int, int], ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    raw: list[tuple[int, int, ProtectedSpanKind]] = []
    _add_fenced_code(raw, text)
    _add_inline_code(raw, text)
    _add_valid_markdown_destinations(raw, text)
    _add_urls(raw, text)
    _add_regex(raw, text, _EMAIL_RE, ProtectedSpanKind.EMAIL)
    _add_ip_addresses(raw, text)
    _add_dates(raw, text)
    _add_regex(raw, text, _CURRENCY_RE, ProtectedSpanKind.CURRENCY)
    _add_regex(raw, text, _PERCENT_RE, ProtectedSpanKind.PERCENTAGE)
    _add_regex(raw, text, _NUMBER_RE, ProtectedSpanKind.NUMBER)
    _add_posix_paths(raw, text)
    _add_extended_posix_paths(raw, text)
    _add_windows_paths(raw, text)
    _add_extended_windows_paths(raw, text)
    _add_regex(raw, text, _CLI_FLAG_RE, ProtectedSpanKind.CLI_FLAG)
    ordered = sorted((start, end) for start, end, _kind in raw)
    merged: list[list[int]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
            continue
        merged[-1][1] = max(merged[-1][1], end)
    return tuple((start, end) for start, end in merged)


def _index_blocked(index: int, intervals: Sequence[tuple[int, int]]) -> bool:
    for start, end in intervals:
        if start <= index < end:
            return True
        if start > index:
            return False
    return False


def select_letter_mix_sites(
    text: str,
    *,
    max_selected: int | None = LETTER_MIX_MAX_SELECTED,
) -> tuple[int, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if max_selected is not None:
        if not isinstance(max_selected, int) or isinstance(max_selected, bool):
            raise TypeError("max_selected must be an integer")
        if max_selected <= 0:
            raise ValueError("max_selected must be positive")
    blocked = hard_machine_intervals(text)
    sites: list[int] = []
    for index, character in enumerate(text):
        if character.isascii() and character.isalpha() and not _index_blocked(index, blocked):
            payload = LETTER_MIX_PAYLOADS[len(sites) % 2]
            trial = text[: index + 1] + payload + text[index + 1 :]
            if not is_carrier_insertion_v1(text, trial, LETTER_MIX_APPROVED_CARRIERS):
                continue
            if project_visible_v1(trial, LETTER_MIX_APPROVED_CARRIERS) != text:
                continue
            report = validate_user_visible_invariants(text, trial, LETTER_MIX_APPROVED_CARRIERS)
            if report.status is not InvariantStatus.PASS:
                continue
            sites.append(index)
            if max_selected is not None and len(sites) >= max_selected:
                break
    return tuple(sites)


def compose_letter_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("letter mix sites must be unique and ordered")
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("letter mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(LETTER_MIX_PAYLOADS[order % 2])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, LETTER_MIX_APPROVED_CARRIERS) != text:
        raise RuntimeError("letter mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, LETTER_MIX_APPROVED_CARRIERS):
        raise RuntimeError("letter mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, LETTER_MIX_APPROVED_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("letter mix failed user-visible invariants")
    for start, end in hard_machine_intervals(text):
        shift = sum(1 for index in ordered if index < start)
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("letter mix mutated a hard machine span")
    return output


def apply_letter_alternating_mix(
    text: str,
    *,
    max_selected: int | None = LETTER_MIX_MAX_SELECTED,
) -> str:
    return compose_letter_mix(text, select_letter_mix_sites(text, max_selected=max_selected))


def letter_mix_protected_blocked_count(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    blocked = hard_machine_intervals(text)
    return sum(
        1
        for index, character in enumerate(text)
        if character.isascii() and character.isalpha() and _index_blocked(index, blocked)
    )
