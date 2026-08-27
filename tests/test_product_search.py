from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.product.search import raw_codepoint_contains, visible_contains
from fuckmark.product.visible_projection import product_approved_carriers_v1, project_visible_v1


def test_visible_search_finds_do_not_after_letter_mix() -> None:
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    assert raw_codepoint_contains(source, "do not") is True
    assert raw_codepoint_contains(transformed, "do not") is False
    assert visible_contains(transformed, "do not", LETTER_MIX_APPROVED_CARRIERS) is True
    assert visible_contains(transformed, "zzzzz", LETTER_MIX_APPROVED_CARRIERS) is False
    assert project_visible_v1(transformed, LETTER_MIX_APPROVED_CARRIERS) == source


def test_product_authorized_search_strips_mix_carriers_by_default() -> None:
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    assert product_approved_carriers_v1() == frozenset(LETTER_MIX_APPROVED_CARRIERS)
    assert visible_contains(transformed, "do not") is True
    assert visible_contains(source, "do not") is True
    assert raw_codepoint_contains(transformed, "do not") is False
