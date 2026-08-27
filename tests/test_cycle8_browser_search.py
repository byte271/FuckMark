import pytest

from fuckmark.cycle8.browser_search import compare_chrome_find
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.product.rendering import chrome_executable


def test_chromium_find_hits_visible_do_not_in_mix_payload() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    hit = compare_chrome_find(transformed, "do not")
    if hit["status"] == "UNKNOWN":
        pytest.skip(str(hit["detail"]))
    assert hit["status"] == "VERIFIED"
    assert hit["hit"] is True
    miss = compare_chrome_find(transformed, "zzzzz")
    if miss["status"] == "UNKNOWN":
        pytest.skip(str(miss["detail"]))
    assert miss["status"] == "VERIFIED"
    assert miss["hit"] is False
