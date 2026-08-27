from __future__ import annotations

from collections.abc import Sequence

from ..product.invariants import validate_user_visible_invariants
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..transforms.schema import InvariantStatus
from .control_carrier import CONTROL_MIX_ELIGIBLE_CODEPOINTS
from .letter_mix import hard_machine_intervals


CONTROL_MIX_APPROVED_CARRIERS = CONTROL_MIX_ELIGIBLE_CODEPOINTS
CONTROL_MIX_PAYLOADS = tuple(chr(codepoint) for codepoint in CONTROL_MIX_APPROVED_CARRIERS)
CONTROL_MIX_MAX_SELECTED = 192
CYCLE8_CONTROL_MIX_ARM_ID = "cc-del-c1-letter-alt-v1"


def _index_blocked(index: int, intervals: Sequence[tuple[int, int]]) -> bool:
    for start, end in intervals:
        if start <= index < end:
            return True
        if start > index:
            return False
    return False


def select_control_mix_sites(
    text: str,
    *,
    max_selected: int | None = CONTROL_MIX_MAX_SELECTED,
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
            payload = CONTROL_MIX_PAYLOADS[len(sites) % len(CONTROL_MIX_PAYLOADS)]
            trial = text[: index + 1] + payload + text[index + 1 :]
            if not is_carrier_insertion_v1(text, trial, CONTROL_MIX_APPROVED_CARRIERS):
                continue
            if project_visible_v1(trial, CONTROL_MIX_APPROVED_CARRIERS) != text:
                continue
            report = validate_user_visible_invariants(text, trial, CONTROL_MIX_APPROVED_CARRIERS)
            if report.status is not InvariantStatus.PASS:
                continue
            sites.append(index)
            if max_selected is not None and len(sites) >= max_selected:
                break
    return tuple(sites)


def compose_control_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("control mix sites must be unique and ordered")
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("control mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(CONTROL_MIX_PAYLOADS[order % len(CONTROL_MIX_PAYLOADS)])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, CONTROL_MIX_APPROVED_CARRIERS) != text:
        raise RuntimeError("control mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, CONTROL_MIX_APPROVED_CARRIERS):
        raise RuntimeError("control mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, CONTROL_MIX_APPROVED_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("control mix failed user-visible invariants")
    for start, end in hard_machine_intervals(text):
        shift = sum(1 for index in ordered if index < start)
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("control mix mutated a hard machine span")
    return output


def apply_control_alternating_mix(
    text: str,
    *,
    max_selected: int | None = CONTROL_MIX_MAX_SELECTED,
) -> str:
    return compose_control_mix(text, select_control_mix_sites(text, max_selected=max_selected))


def control_mix_inserted_count(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return sum(text.count(payload) for payload in CONTROL_MIX_PAYLOADS)
