import pytest

from fuckmark.product.rendering import _html_page


def test_html_page_does_not_close_script_on_ascii_terminator() -> None:
    page = _html_page("ok</script><img src=x>more")
    _, script = page.split("<script>", 1)
    body, suffix = script.rsplit("</script>", 1)
    assert suffix.startswith("</body>")
    assert "</script>" not in body
    assert "<img" not in body
    assert "\\u003c/script\\u003e" in body
    assert "textContent=" in body


def test_require_gpt2_encoder_fails_closed_when_tiktoken_missing(monkeypatch) -> None:
    import fuckmark.cycle8.tokenizer_screen as module

    monkeypatch.setattr(module, "load_gpt2_encoder", lambda: None)
    with pytest.raises(RuntimeError, match="gpt2 encoder is required"):
        module.require_gpt2_encoder()
