from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from ..product.domain import PRODUCT_DOMAIN_ALLOWED_CODEPOINTS
from ..product.invariants import validate_user_visible_invariants
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..transforms.protected import add_hard_machine_spans
from ..transforms.schema import InvariantStatus, ProtectedSpanKind


LETTER_MIX_CONTROL_CODEPOINTS = (0x007F, *range(0x0080, 0x0085), *range(0x0086, 0x00A0))
LETTER_MIX_MARK_PAYLOADS = ("\u034f", "\ufe00")
LETTER_MIX_CONTROL_PAYLOADS = tuple(chr(codepoint) for codepoint in LETTER_MIX_CONTROL_CODEPOINTS)
LETTER_MIX_ME_PAYLOADS = ("\u20dd",)
LETTER_MIX_CF_CODEPOINTS = tuple(range(0x13430, 0x13439))
LETTER_MIX_CF_PAYLOADS = tuple(chr(codepoint) for codepoint in LETTER_MIX_CF_CODEPOINTS)
LETTER_MIX_IA_CODEPOINTS = (0xFFF9, 0xFFFA, 0xFFFB)
LETTER_MIX_IA_PAYLOADS = tuple(chr(codepoint) for codepoint in LETTER_MIX_IA_CODEPOINTS)
LETTER_MIX_APPROVED_CARRIERS = (
    tuple(ord(character) for character in LETTER_MIX_MARK_PAYLOADS)
    + LETTER_MIX_CONTROL_CODEPOINTS
    + tuple(ord(character) for character in LETTER_MIX_ME_PAYLOADS)
    + LETTER_MIX_CF_CODEPOINTS
    + LETTER_MIX_IA_CODEPOINTS
)
LETTER_MIX_PAYLOADS = LETTER_MIX_MARK_PAYLOADS
LETTER_MIX_MAX_SELECTED = 4096
LETTER_MIX_INSERTIONS_PER_SITE = 5
LETTER_MIX_MECHANISM_ID = "u034f-ufe00-cc-me-cf-ia-letter-alt-v1"
HISTORICAL_MARK_MIX_CARRIERS = (0x034F, 0xFE00)
HISTORICAL_MARK_MIX_MAX_SELECTED = 192
HISTORICAL_MARK_MIX_INSERTIONS_PER_SITE = 1
HISTORICAL_MARK_MIX_MECHANISM_ID = "u034f-ufe00-letter-alt-v1"
HISTORICAL_DUAL_LAYER_MIX_CARRIERS = tuple(ord(character) for character in LETTER_MIX_MARK_PAYLOADS) + LETTER_MIX_CONTROL_CODEPOINTS
HISTORICAL_DUAL_LAYER_MIX_MAX_SELECTED = 4096
HISTORICAL_DUAL_LAYER_MIX_INSERTIONS_PER_SITE = 2
HISTORICAL_DUAL_LAYER_MIX_MECHANISM_ID = "u034f-ufe00-cc-letter-alt-v1"
HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS = (
    tuple(ord(character) for character in LETTER_MIX_MARK_PAYLOADS)
    + LETTER_MIX_CONTROL_CODEPOINTS
    + tuple(ord(character) for character in LETTER_MIX_ME_PAYLOADS)
)
HISTORICAL_TRIPLE_LAYER_MIX_MAX_SELECTED = 4096
HISTORICAL_TRIPLE_LAYER_MIX_INSERTIONS_PER_SITE = 3
HISTORICAL_TRIPLE_LAYER_MIX_MECHANISM_ID = "u034f-ufe00-cc-me-letter-alt-v1"
HISTORICAL_QUAD_LAYER_MIX_CARRIERS = (
    tuple(ord(character) for character in LETTER_MIX_MARK_PAYLOADS)
    + LETTER_MIX_CONTROL_CODEPOINTS
    + tuple(ord(character) for character in LETTER_MIX_ME_PAYLOADS)
    + LETTER_MIX_CF_CODEPOINTS
)
HISTORICAL_QUAD_LAYER_MIX_MAX_SELECTED = 4096
HISTORICAL_QUAD_LAYER_MIX_INSERTIONS_PER_SITE = 4
HISTORICAL_QUAD_LAYER_MIX_MECHANISM_ID = "u034f-ufe00-cc-me-cf-letter-alt-v1"
_CLUSTER_EXTEND_CATEGORIES = frozenset({"Mn", "Mc", "Me"})
_VS_CODEPOINTS = frozenset({0xFE0E, 0xFE0F})
_KEYCAP_BASES = frozenset("#*0123456789")
_LIVE_NAME_PREFIXES = (
    "LATIN ",
    "GREEK ",
    "CYRILLIC ",
    "CJK UNIFIED IDEOGRAPH",
    "CJK COMPATIBILITY IDEOGRAPH",
    "HIRAGANA ",
    "KATAKANA ",
    "KATAKANA-HIRAGANA ",
    "HANGUL SYLLABLE ",
    "BOPOMOFO ",
)


def _assigned_name(character: str) -> str:
    try:
        return unicodedata.name(character)
    except ValueError:
        return ""


def _is_regional_indicator(character: str) -> bool:
    code = ord(character)
    return 0x1F1E6 <= code <= 0x1F1FF


def _is_emoji_base(character: str) -> bool:
    code = ord(character)
    if 0x1F1E6 <= code <= 0x1F1FF:
        return True
    if 0x1F000 <= code <= 0x1FAFF:
        return True
    if 0x2600 <= code <= 0x27BF and unicodedata.category(character) == "So":
        return True
    return code in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}


def _is_live_letter_base(character: str) -> bool:
    if not character.isalpha():
        return False
    if character.isascii():
        return True
    name = _assigned_name(character)
    return any(name.startswith(prefix) for prefix in _LIVE_NAME_PREFIXES)


def _is_keycap_base(text: str, index: int) -> bool:
    if text[index] not in _KEYCAP_BASES:
        return False
    nxt = index + 1
    return nxt < len(text) and ord(text[nxt]) in {0xFE0F, 0x20E3}


def _is_live_cluster_base(text: str, index: int) -> bool:
    character = text[index]
    return _is_live_letter_base(character) or _is_emoji_base(character) or _is_keycap_base(text, index)


def _extend_cluster(text: str, start: int) -> int:
    index = start + 1
    length = len(text)
    if _is_regional_indicator(text[start]) and index < length and _is_regional_indicator(text[index]):
        index += 1
    while index < length:
        code = ord(text[index])
        category = unicodedata.category(text[index])
        if category in _CLUSTER_EXTEND_CATEGORIES:
            index += 1
            continue
        if code in _VS_CODEPOINTS:
            index += 1
            continue
        if 0xE0020 <= code <= 0xE007F:
            index += 1
            continue
        if code == 0x200D:
            index += 1
            if index < length:
                index += 1
            continue
        break
    return index


def _range_overlaps_blocked(start: int, end: int, blocked: Sequence[tuple[int, int]]) -> bool:
    for left, right in blocked:
        if start < right and end > left:
            return True
    return False


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


def _source_contains_carriers(text: str, approved: Sequence[int]) -> bool:
    blocked = frozenset(approved)
    return any(ord(character) in blocked for character in text)


def select_letter_mix_sites(
    text: str,
    *,
    max_selected: int | None = LETTER_MIX_MAX_SELECTED,
    approved_carriers: Sequence[int] | None = None,
    ascii_only: bool = False,
) -> tuple[int, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if max_selected is not None:
        if not isinstance(max_selected, int) or isinstance(max_selected, bool):
            raise TypeError("max_selected must be an integer")
        if max_selected <= 0:
            raise ValueError("max_selected must be positive")
    approved = LETTER_MIX_APPROVED_CARRIERS if approved_carriers is None else tuple(approved_carriers)
    if _source_contains_carriers(text, approved):
        return ()
    blocked = hard_machine_intervals(text)
    sites: list[int] = []
    if ascii_only:
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
    index = 0
    length = len(text)
    while index < length:
        if not _is_live_cluster_base(text, index):
            index += 1
            continue
        cluster_end = _extend_cluster(text, index)
        if _range_overlaps_blocked(index, cluster_end, blocked):
            index = cluster_end
            continue
        sites.append(cluster_end - 1)
        if max_selected is not None and len(sites) >= max_selected:
            break
        index = cluster_end
    return tuple(sites)


def compose_letter_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("letter mix sites must be unique and ordered")
    control_count = len(LETTER_MIX_CONTROL_PAYLOADS)
    me_count = len(LETTER_MIX_ME_PAYLOADS)
    cf_count = len(LETTER_MIX_CF_PAYLOADS)
    ia_count = len(LETTER_MIX_IA_PAYLOADS)
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("letter mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(LETTER_MIX_MARK_PAYLOADS[order % 2])
        chunks.append(LETTER_MIX_CONTROL_PAYLOADS[order % control_count])
        chunks.append(LETTER_MIX_ME_PAYLOADS[order % me_count])
        chunks.append(LETTER_MIX_CF_PAYLOADS[order % cf_count])
        chunks.append(LETTER_MIX_IA_PAYLOADS[order % ia_count])
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
            shift += LETTER_MIX_INSERTIONS_PER_SITE
            site_index += 1
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("letter mix mutated a hard machine span")
    return output


def compose_historical_mark_letter_mix(text: str, sites: Sequence[int]) -> str:
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
        chunks.append(LETTER_MIX_MARK_PAYLOADS[order % 2])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, HISTORICAL_MARK_MIX_CARRIERS) != text:
        raise RuntimeError("letter mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, HISTORICAL_MARK_MIX_CARRIERS):
        raise RuntimeError("letter mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, HISTORICAL_MARK_MIX_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("letter mix failed user-visible invariants")
    site_index = 0
    shift = 0
    for start, end in hard_machine_intervals(text):
        while site_index < len(ordered) and ordered[site_index] < start:
            shift += HISTORICAL_MARK_MIX_INSERTIONS_PER_SITE
            site_index += 1
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("letter mix mutated a hard machine span")
    return output


def compose_historical_dual_layer_letter_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("letter mix sites must be unique and ordered")
    control_count = len(LETTER_MIX_CONTROL_PAYLOADS)
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("letter mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(LETTER_MIX_MARK_PAYLOADS[order % 2])
        chunks.append(LETTER_MIX_CONTROL_PAYLOADS[order % control_count])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, HISTORICAL_DUAL_LAYER_MIX_CARRIERS) != text:
        raise RuntimeError("letter mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, HISTORICAL_DUAL_LAYER_MIX_CARRIERS):
        raise RuntimeError("letter mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, HISTORICAL_DUAL_LAYER_MIX_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("letter mix failed user-visible invariants")
    site_index = 0
    shift = 0
    for start, end in hard_machine_intervals(text):
        while site_index < len(ordered) and ordered[site_index] < start:
            shift += HISTORICAL_DUAL_LAYER_MIX_INSERTIONS_PER_SITE
            site_index += 1
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("letter mix mutated a hard machine span")
    return output


def compose_historical_triple_layer_letter_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("letter mix sites must be unique and ordered")
    control_count = len(LETTER_MIX_CONTROL_PAYLOADS)
    me_count = len(LETTER_MIX_ME_PAYLOADS)
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("letter mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(LETTER_MIX_MARK_PAYLOADS[order % 2])
        chunks.append(LETTER_MIX_CONTROL_PAYLOADS[order % control_count])
        chunks.append(LETTER_MIX_ME_PAYLOADS[order % me_count])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS) != text:
        raise RuntimeError("letter mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS):
        raise RuntimeError("letter mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("letter mix failed user-visible invariants")
    site_index = 0
    shift = 0
    for start, end in hard_machine_intervals(text):
        while site_index < len(ordered) and ordered[site_index] < start:
            shift += HISTORICAL_TRIPLE_LAYER_MIX_INSERTIONS_PER_SITE
            site_index += 1
        if output[start + shift : end + shift] != text[start:end]:
            raise RuntimeError("letter mix mutated a hard machine span")
    return output


def compose_historical_quad_layer_letter_mix(text: str, sites: Sequence[int]) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    ordered = tuple(sites)
    if ordered != tuple(sorted(set(ordered))):
        raise ValueError("letter mix sites must be unique and ordered")
    control_count = len(LETTER_MIX_CONTROL_PAYLOADS)
    me_count = len(LETTER_MIX_ME_PAYLOADS)
    cf_count = len(LETTER_MIX_CF_PAYLOADS)
    chunks: list[str] = []
    cursor = 0
    for order, index in enumerate(ordered):
        if index < cursor or index >= len(text):
            raise ValueError("letter mix site is outside the source")
        chunks.append(text[cursor : index + 1])
        chunks.append(LETTER_MIX_MARK_PAYLOADS[order % 2])
        chunks.append(LETTER_MIX_CONTROL_PAYLOADS[order % control_count])
        chunks.append(LETTER_MIX_ME_PAYLOADS[order % me_count])
        chunks.append(LETTER_MIX_CF_PAYLOADS[order % cf_count])
        cursor = index + 1
    chunks.append(text[cursor:])
    output = "".join(chunks)
    if project_visible_v1(output, HISTORICAL_QUAD_LAYER_MIX_CARRIERS) != text:
        raise RuntimeError("letter mix changed the visible projection")
    if not is_carrier_insertion_v1(text, output, HISTORICAL_QUAD_LAYER_MIX_CARRIERS):
        raise RuntimeError("letter mix is not a carrier insertion")
    report = validate_user_visible_invariants(text, output, HISTORICAL_QUAD_LAYER_MIX_CARRIERS)
    if report.status is not InvariantStatus.PASS:
        raise RuntimeError("letter mix failed user-visible invariants")
    site_index = 0
    shift = 0
    for start, end in hard_machine_intervals(text):
        while site_index < len(ordered) and ordered[site_index] < start:
            shift += HISTORICAL_QUAD_LAYER_MIX_INSERTIONS_PER_SITE
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


def apply_historical_mark_letter_mix(
    text: str,
    *,
    max_selected: int | None = HISTORICAL_MARK_MIX_MAX_SELECTED,
) -> str:
    sites = select_letter_mix_sites(
        text,
        max_selected=max_selected,
        approved_carriers=HISTORICAL_MARK_MIX_CARRIERS,
        ascii_only=True,
    )
    return compose_historical_mark_letter_mix(text, sites)


def apply_historical_dual_layer_letter_mix(
    text: str,
    *,
    max_selected: int | None = HISTORICAL_DUAL_LAYER_MIX_MAX_SELECTED,
) -> str:
    sites = select_letter_mix_sites(
        text,
        max_selected=max_selected,
        approved_carriers=HISTORICAL_DUAL_LAYER_MIX_CARRIERS,
        ascii_only=True,
    )
    return compose_historical_dual_layer_letter_mix(text, sites)


def apply_historical_triple_layer_letter_mix(
    text: str,
    *,
    max_selected: int | None = HISTORICAL_TRIPLE_LAYER_MIX_MAX_SELECTED,
) -> str:
    sites = select_letter_mix_sites(
        text,
        max_selected=max_selected,
        approved_carriers=HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS,
        ascii_only=True,
    )
    return compose_historical_triple_layer_letter_mix(text, sites)


def apply_historical_quad_layer_letter_mix(
    text: str,
    *,
    max_selected: int | None = HISTORICAL_QUAD_LAYER_MIX_MAX_SELECTED,
) -> str:
    sites = select_letter_mix_sites(
        text,
        max_selected=max_selected,
        approved_carriers=HISTORICAL_QUAD_LAYER_MIX_CARRIERS,
        ascii_only=True,
    )
    return compose_historical_quad_layer_letter_mix(text, sites)


def first_unmixed_non_ascii(text: str) -> tuple[int, int] | None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    blocked = hard_machine_intervals(text)
    covered: list[tuple[int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        if not _is_live_cluster_base(text, index):
            index += 1
            continue
        cluster_end = _extend_cluster(text, index)
        if not _range_overlaps_blocked(index, cluster_end, blocked):
            covered.append((index, cluster_end))
        index = cluster_end
    covered_index = 0
    covered_count = len(covered)
    for position, character in enumerate(text):
        codepoint = ord(character)
        if codepoint in PRODUCT_DOMAIN_ALLOWED_CODEPOINTS:
            continue
        while covered_index < covered_count and covered[covered_index][1] <= position:
            covered_index += 1
        if covered_index < covered_count and covered[covered_index][0] <= position < covered[covered_index][1]:
            continue
        return position, codepoint
    return None


def letter_mix_protected_blocked_count(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    blocked = hard_machine_intervals(text)
    count = 0
    index = 0
    length = len(text)
    while index < length:
        if not _is_live_cluster_base(text, index):
            index += 1
            continue
        cluster_end = _extend_cluster(text, index)
        if _range_overlaps_blocked(index, cluster_end, blocked):
            count += 1
        index = cluster_end
    return count
