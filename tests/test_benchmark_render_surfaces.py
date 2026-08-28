import pytest

from fuckmark.cycle8.benchmark_render import (
    BENCHMARK_RENDER_FONT,
    BENCHMARK_RENDER_VERSION,
    _html_surface,
    chrome_version,
    compare_chrome_surface,
    displayed_js_property,
)
from fuckmark.product.rendering import chrome_executable


class _FakeElement:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.__dict__.pop("value", None)
        self.textContent = ""
        if kind == "textarea":
            self.value = ""

    def __contains__(self, key: object) -> bool:
        return key in self.__dict__


def _old_buggy_assign(element: _FakeElement, payload: str) -> None:
    element.value = payload
    if "value" not in element:
        element.textContent = payload


def test_generated_contenteditable_script_sets_text_content_not_value() -> None:
    html = _html_surface("AAAA", "contenteditable")
    assert "el.textContent=" in html
    assert "el.value=" not in html
    assert "('value' in" not in html
    assert displayed_js_property("contenteditable") == "textContent"
    textarea = _html_surface("AAAA", "textarea")
    assert "el.value=" in textarea
    assert "el.textContent=" not in textarea.split("<script>", 1)[1]
    assert displayed_js_property("textarea") == "value"
    assert BENCHMARK_RENDER_VERSION == "cycle8-benchmark-render-v2"
    assert BENCHMARK_RENDER_FONT == "DejaVu Sans Mono"


def test_old_value_in_check_leaves_contenteditable_blank() -> None:
    editable = _FakeElement("contenteditable")
    _old_buggy_assign(editable, "AAAA")
    assert editable.value == "AAAA"
    assert editable.textContent == ""
    area = _FakeElement("textarea")
    _old_buggy_assign(area, "BBBB")
    assert area.value == "BBBB"


def test_unavailable_browser_is_unknown_never_verified(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.cycle8.benchmark_render.chrome_executable", lambda: None)
    result = compare_chrome_surface("AAAA", "BBBB", "contenteditable")
    assert result["status"] == "UNKNOWN"
    assert result["equal"] is None
    assert result["status"] != "VERIFIED"
    assert "no chromium" in str(result["detail"]).casefold()


def test_contenteditable_and_textarea_controls_on_chromium() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    different = compare_chrome_surface("AAAA", "BBBB", "contenteditable")
    if different["status"] == "UNKNOWN":
        pytest.skip(str(different["detail"]))
    assert different["status"] == "REJECTED"
    assert different["equal"] is False
    same = compare_chrome_surface("AAAA", "AAAA", "contenteditable")
    if same["status"] == "UNKNOWN":
        pytest.skip(str(same["detail"]))
    assert same["status"] == "VERIFIED"
    assert same["equal"] is True
    nonempty = compare_chrome_surface("AAAA", "", "contenteditable")
    if nonempty["status"] == "UNKNOWN":
        pytest.skip(str(nonempty["detail"]))
    assert nonempty["status"] == "REJECTED"
    textarea_same = compare_chrome_surface("AAAA", "AAAA", "textarea")
    if textarea_same["status"] == "UNKNOWN":
        pytest.skip(str(textarea_same["detail"]))
    assert textarea_same["status"] == "VERIFIED"
    textarea_different = compare_chrome_surface("AAAA", "BBBB", "textarea")
    if textarea_different["status"] == "UNKNOWN":
        pytest.skip(str(textarea_different["detail"]))
    assert textarea_different["status"] == "REJECTED"
    textarea_blank = compare_chrome_surface("AAAA", "", "textarea")
    if textarea_blank["status"] == "UNKNOWN":
        pytest.skip(str(textarea_blank["detail"]))
    assert textarea_blank["status"] == "REJECTED"
    assert chrome_version() is not None
