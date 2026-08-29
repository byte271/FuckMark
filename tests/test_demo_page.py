import json
import re
import unicodedata
from pathlib import Path

from fuckmark.cli import transform_text
from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS
from fuckmark.product.visible_projection import project_visible_v1


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "demo.html"


def _samples() -> list[dict]:
    html = DEMO.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="demo-samples" type="application/json">\s*(.*?)\s*</script>',
        html,
        flags=re.S,
    )
    assert match is not None
    payload = json.loads(match.group(1))
    assert isinstance(payload, list) and payload
    return payload


def test_demo_page_is_self_contained_and_honest() -> None:
    html = DEMO.read_text(encoding="utf-8")
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "no-install demo" in html.casefold()
    assert "188/192" in html
    assert "0/192" in html
    assert "not a general" in html.casefold() or "not a guarantee" in html.casefold()
    assert "Mn" in html
    assert "Default_Ignorable_Code_Point" in html
    assert "unsupported-domain" in html
    assert "Fhelp@q1z.org" in html
    assert "mailto:Fhelp@q1z.org" in html
    assert "id=\"detector\"" in html
    assert "We did not detect a watermark in this text." in html
    assert "What? You think there is a watermark in this?" in html
    assert "Contact us" in html
    assert "\u6211\u4eec" not in html
    assert "local FuckMark scan" in html or "FuckMark detector" in html
    assert "file://" in html or "file://" in html.casefold()
    assert "GPT-2" in html
    assert "192" in html
    assert '<script src=' not in html.casefold()
    assert 'href="http' not in html or "mark.q1z.org" in html
    assert "four-layer" in html.casefold() or "u+13430" in html.casefold()


def test_demo_samples_match_live_cli_and_reversal() -> None:
    samples = _samples()
    ids = {sample["id"] for sample in samples}
    assert "ascii-eligible" in ids
    assert "curly-apostrophe" in ids
    assert "latin-only" in ids
    assert "han-only" in ids
    assert "emoji-only" in ids
    assert "site-full" in ids
    for sample in samples:
        result = transform_text(sample["source"])
        assert result.output_text == sample["output"]
        assert result.reason == sample["reason"]
        assert result.change_count == sample["insertions"]
        assert result.site_count == sample["sites"]
        assert result.last_source_index == sample["last_index"]
        assert result.capped is sample["capped"]
        assert result.source_length == sample["source_length"]
        assert result.first_unsupported == sample["first_unsupported"]
        assert result.processed is sample["processed"]
        if result.change_count > 0:
            stripped = "".join(
                character
                for character in result.output_text
                if unicodedata.category(character) != "Mn"
            )
            assert stripped != sample["source"]
            assert project_visible_v1(result.output_text, LETTER_MIX_APPROVED_CARRIERS) == sample["source"]
    curly = next(sample for sample in samples if sample["id"] == "curly-apostrophe")
    assert curly["processed"] is True
    assert curly["first_unsupported"].startswith("U+2019@")
    latin_only = next(sample for sample in samples if sample["id"] == "latin-only")
    assert latin_only["processed"] is True
    assert latin_only["sites"] == 3
    assert latin_only["first_unsupported"] == ""
    han_only = next(sample for sample in samples if sample["id"] == "han-only")
    assert han_only["processed"] is True
    assert han_only["sites"] == 2
    assert han_only["first_unsupported"] == ""
    emoji_only = next(sample for sample in samples if sample["id"] == "emoji-only")
    assert emoji_only["processed"] is True
    assert emoji_only["sites"] == 1
    assert emoji_only["first_unsupported"] == ""
    accented = next(sample for sample in samples if sample["id"] == "accented")
    assert accented["first_unsupported"] == ""
    covered = next(sample for sample in samples if sample["id"] == "site-full")
    assert covered["capped"] is False
    assert covered["sites"] == 312
    assert covered["insertions"] == 1560
