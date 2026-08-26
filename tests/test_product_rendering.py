import json
from pathlib import Path

import pytest

from fuckmark.cycle8_hf import main as cycle8_hf_main
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


def test_cycle8_hf_writes_fixture_compare_without_gpt2_encoder(monkeypatch, tmp_path: Path) -> None:
    import fuckmark.cycle8.tokenizer_screen as module

    monkeypatch.setattr(module, "load_gpt2_encoder", lambda: None)
    destination = tmp_path / "detector-compare.json"
    assert cycle8_hf_main(["--skip-detector", "--detector-json", str(destination)]) == 0
    fixture = json.loads((tmp_path / "fixture-compare.json").read_text(encoding="utf-8"))
    assert fixture["visible_pass_rate"] == "20/20"
    assert fixture["encoder"] == "unavailable"
    assert (tmp_path / "decision.json").is_file()
    assert not destination.is_file()


def test_pinned_cycle8_spec_writers_require_gpt2_encoder() -> None:
    root = Path(__file__).resolve().parents[1]
    fixture_tool = (root / "tools" / "cycle8_fixture_compare.py").read_text(encoding="utf-8")
    screen_tool = (root / "tools" / "cycle8_carrier_screen.py").read_text(encoding="utf-8")
    harness = (root / "fuckmark" / "cycle8_hf.py").read_text(encoding="utf-8")
    assert "require_gpt2_encoder()" in fixture_tool
    assert "require_gpt2_encoder()" in screen_tool
    assert "require_gpt2_encoder()" not in harness
    assert "load_gpt2_encoder()" in harness
