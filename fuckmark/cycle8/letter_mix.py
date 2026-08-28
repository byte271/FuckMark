from __future__ import annotations

from collections.abc import Sequence

from ..product.invariants import validate_user_visible_invariants
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..transforms.protected import add_hard_machine_spans
from ..transforms.schema import InvariantStatus, ProtectedSpanKind

LETTER_MIX_APPROVED_CARRIERS = (0x034F, 0xFE00)
LETTER_MIX_PAYLOADS = ("\u034f", "\ufe00")
LETTER_MIX_MAX_SELECTED = 192


def hard_machine_intervals(text: str) -> tuple[tuple[int, int], ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    raw: list[tuple[int, int, ProtectedSpanKind]] = []
    add_hard_machine_spans(raw, text)
    ordered = sorted((start, end) for start, end, _kind in raw)
    merged: list[list[int]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
            continue
        merged[-1][1] = max(merged[-1][1], end)
    return tuple((start, end) for start, end in merged)


def _source_contains_approved_carriers(text: str) -> bool:
    approved = LETTER_MIX_APPROVED_CARRIERS
    return any(ord(character) in approved for character in text)


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
    if _source_contains_approved_carriers(text):
        return ()
    blocked = hard_machine_intervals(text)
    sites: list[int] = []
    interval_index = 0
    blocked_count = len(blocked)
    for index, character in enumerate(text):
        while interval_index < blocked_count and blocked[interval_index][1] <= index:
            interval_index += 1
        if interval_index < blocked_count and blocked[interval_index][0] <= index:
            continue
        if character.isascii() and character.isalpha():
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
    site_index = 0
    shift = 0
    for start, end in hard_machine_intervals(text):
        while site_index < len(ordered) and ordered[site_index] < start:
            shift += 1
            site_index += 1
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
    count = 0
    interval_index = 0
    blocked_count = len(blocked)
    for index, character in enumerate(text):
        while interval_index < blocked_count and blocked[interval_index][1] <= index:
            interval_index += 1
        if not (character.isascii() and character.isalpha()):
            continue
        if interval_index < blocked_count and blocked[interval_index][0] <= index:
            count += 1
    return count
