from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.cycle8.benchmark_render import _html_surface
from fuckmark.product.rendering import RENDERING_HARNESS_VERSION, _html_page, compare_chrome_pre_screenshots, render_window_size


def test_render_window_covers_below_fold_text() -> None:
    short = "AAAA\n"
    long = ("AAAA\n" * 40) + "BBBB\n"
    width, height, complete, content_height = render_window_size(long, min_height=200)
    assert complete is True
    assert content_height > 240
    assert height >= content_height
    below = render_window_size(short, min_height=200)
    assert below[1] == 200 or below[3] <= 200


def test_html_page_contains_actual_mix_payload() -> None:
    source = "I do not agree."
    mixed = apply_letter_alternating_mix(source)
    assert "\u034f" in mixed or "\ufe00" in mixed
    page = _html_page(mixed)
    assert mixed in page
    surface = _html_surface(mixed, "contenteditable", box_height=400)
    assert "textContent=" in surface
    assert "el.value=" not in surface
    unknown = compare_chrome_pre_screenshots(source, mixed)
    assert unknown.status in {"UNKNOWN", "VERIFIED", "REJECTED", "INCOMPLETE"}
    if unknown.status == "VERIFIED":
        assert unknown.equal is True
    assert RENDERING_HARNESS_VERSION == "product-reference-render-v2"


def test_payload_render_artifact_keeps_controls_and_does_not_promote_unknown() -> None:
    from json import loads
    from pathlib import Path

    from fuckmark.hashing import sha256_json

    folder = Path(__file__).resolve().parents[1] / "evidence/audit-fixes-2026-08-28"
    payload = loads((folder / "render-payload-v2.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["webkit_safari"] == "UNKNOWN"
    assert payload["terminal_pixels"] == "UNKNOWN"
    by_key = {(row["surface"], row["pair"]): row["result"]["status"] for row in payload["rows"]}
    assert by_key[("pre", "mix_payload")] == "VERIFIED"
    assert by_key[("textarea", "mix_payload")] == "VERIFIED"
    assert by_key[("contenteditable", "mix_payload")] == "VERIFIED"
    assert by_key[("contenteditable", "negative")] == "REJECTED"
    assert by_key[("textarea", "positive")] == "VERIFIED"
    assert by_key[("pre", "below_fold")] == "INCOMPLETE"
    frozen = Path(__file__).resolve().parents[1] / "evidence/audit-fixes-2026-08-27/render-v2.json"
    frozen_payload = loads(frozen.read_text(encoding="utf-8"))
    frozen_body = {key: value for key, value in frozen_payload.items() if key != "artifact_hash"}
    assert frozen_payload["artifact_hash"] == sha256_json(frozen_body)
    assert frozen_payload["artifact_hash"] == "79f45bfa0914d673c919beba70b15e9c00191630c61ef82fb9703b7ff9da4ff2"
