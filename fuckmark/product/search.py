from __future__ import annotations

from collections.abc import Iterable

from .visible_projection import product_approved_carriers_v1, project_visible_v1


PRODUCT_SEARCH_ALGORITHM_VERSION = "product-visible-search-v1"


def visible_contains(
    haystack: str,
    needle: str,
    approved_carriers: Iterable[int] | None = None,
) -> bool:
    if not isinstance(haystack, str) or not isinstance(needle, str):
        raise TypeError("haystack and needle must be strings")
    carriers = product_approved_carriers_v1() if approved_carriers is None else approved_carriers
    return needle in project_visible_v1(haystack, carriers)


def raw_codepoint_contains(haystack: str, needle: str) -> bool:
    if not isinstance(haystack, str) or not isinstance(needle, str):
        raise TypeError("haystack and needle must be strings")
    return needle in haystack
