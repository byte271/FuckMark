import re
from pathlib import Path

from fuckmark.cli import process_text
from fuckmark.product.detect import DETECT_CONTACT_EMAIL, detect_fuckmark_insertions


ROOT = Path(__file__).resolve().parents[1]
MARK = ROOT / "docs" / "mark.html"
REC = ROOT / "docs" / "rec.html"


def test_mark_page_is_closed_set_detector_with_contact() -> None:
    html = MARK.read_text(encoding="utf-8")
    assert "FM_CARRIER_SET" in html
    assert "detectFuckMark" in html
    assert "0x13430" in html
    assert "length: 9" in html
    assert "\\uFFF9" in html
    assert "\\u20DD" in html
    assert "FE00-\\uFE0F" not in html
    assert "\\u200B-\\u200D" not in html
    assert DETECT_CONTACT_EMAIL in html
    assert f"mailto:{DETECT_CONTACT_EMAIL}" in html
    assert "Fmark@q1z.org" not in html
    assert "We did not detect a watermark in this text." in html
    assert "What? You think there is a watermark in this?" in html
    assert "Contact us" in html
    assert "\u6211\u4eec" not in html
    assert "closed-set" in html.casefold()
    assert "not a general" in html.casefold()
    assert "markedSample" in html
    assert "FM_CCS" in html
    assert "FM_CFS" in html
    assert "No CLI needed" in html
    assert "/api/health" in html
    assert "/api/remove-marks" in html
    assert "scanViaPython" in html
    assert "scanLocal" in html


def test_mark_page_demo_sample_is_detectable_by_python_detector() -> None:
    source = "Hello from Q1z. Visible text stays."
    mixed = process_text(source)
    hit = detect_fuckmark_insertions(mixed)
    assert hit.detected is True
    assert hit.found > 0
    miss = detect_fuckmark_insertions(source)
    assert miss.detected is False


def test_rec_page_redirects_to_mark_demo() -> None:
    html = REC.read_text(encoding="utf-8")
    assert "mark.html" in html
    assert "demo=1" in html
    assert "go.txt" in html
    assert re.search(r"location\.replace\(\s*[\"']mark\.html", html)
