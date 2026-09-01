import json
import unicodedata
from io import StringIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fuckmark import NORMALIZE_ALGORITHM_VERSION, normalize_receipt_dict, normalize_text, skeleton_fold
from fuckmark.cli import main
from fuckmark.hashing import sha256_text
from fuckmark.product.normalize import NORMALIZE_EXIT_OK, NORMALIZE_EXIT_USAGE, run_normalize_argv
from fuckmark.web import normalize_payload, serve_mark_web


CYRILLIC_A = "\u0430"


def _post_json(url: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_nfc_composes_combining_mark() -> None:
    cleaned, receipt = normalize_text("e\u0301", strip=False)
    assert cleaned == unicodedata.normalize("NFC", "e\u0301")
    assert cleaned == "\u00e9"
    assert receipt.changed is True
    assert receipt.steps == ("nfc",)
    assert receipt.stripped == 0


def test_skeleton_fold_maps_cyrillic_lookalike() -> None:
    assert skeleton_fold(CYRILLIC_A) == "a"
    cleaned, receipt = normalize_text(CYRILLIC_A, confusable=True, strip=False)
    assert cleaned == "a"
    assert receipt.steps == ("confusable",)
    assert receipt.changed is True


def test_normalize_strips_hidden_and_emits_receipt_hashes() -> None:
    source = "a\u200bb"
    cleaned, receipt = normalize_text(source)
    assert cleaned == "ab"
    assert receipt.stripped == 1
    assert receipt.steps == ("strip",)
    assert receipt.input_sha256 == sha256_text(source)
    assert receipt.output_sha256 == sha256_text("ab")
    payload = normalize_receipt_dict(receipt)
    assert payload["algorithm_version"] == NORMALIZE_ALGORITHM_VERSION
    assert payload["report_hash"]
    assert payload["changed"] is True


def test_normalize_plain_ascii_is_unchanged() -> None:
    cleaned, receipt = normalize_text("plain ascii")
    assert cleaned == "plain ascii"
    assert receipt.changed is False
    assert receipt.steps == ()


def test_cli_normalize_strips_and_can_emit_receipt() -> None:
    out, err = StringIO(), StringIO()
    code = run_normalize_argv(["--receipt", "a\u200bb"], StringIO(""), out, err)
    assert code == NORMALIZE_EXIT_OK
    assert out.getvalue() == "ab"
    assert "stripped 1 hidden characters" in err.getvalue()
    receipt = json.loads(err.getvalue().split("\n", 1)[1])
    assert receipt["stripped"] == 1
    assert receipt["steps"] == ["strip"]


def test_cli_normalize_via_main_confusable() -> None:
    out, err = StringIO(), StringIO()
    status = main(StringIO(""), out, error_stream=err, argv=("normalize", "--confusable", CYRILLIC_A))
    assert status == 0
    assert out.getvalue() == "a"


def test_cli_normalize_rejects_empty() -> None:
    out, err = StringIO(), StringIO()
    code = run_normalize_argv([], StringIO(""), out, err)
    assert code == NORMALIZE_EXIT_USAGE
    assert "no input" in err.getvalue()


def test_normalize_payload_and_endpoint() -> None:
    payload = normalize_payload("a\u200bb")
    assert payload["ok"] is True
    assert payload["reason"] == "normalized"
    assert payload["text"] == "ab"
    assert payload["receipt"]["stripped"] == 1

    folded = normalize_payload(CYRILLIC_A, confusable=True)
    assert folded["text"] == "a"

    seen: dict[str, object] = {}

    def on_ready(url: str, port: int) -> None:
        status, data = _post_json(f"http://127.0.0.1:{port}/api/normalize", {"text": "a\u200bb"})
        seen["status"] = status
        seen["data"] = data
        fold_status, fold_data = _post_json(
            f"http://127.0.0.1:{port}/api/normalize",
            {"text": CYRILLIC_A, "confusable": True},
        )
        seen["fold_status"] = fold_status
        seen["fold_data"] = fold_data

    serve_mark_web(host="127.0.0.1", port=0, open_browser=False, serve_seconds=0.05, on_ready=on_ready)
    assert seen["status"] == 200
    data = seen["data"]
    assert isinstance(data, dict)
    assert data["text"] == "ab"
    fold_data = seen["fold_data"]
    assert isinstance(fold_data, dict)
    assert fold_data["text"] == "a"
