import json
from io import StringIO

import pytest

from fuckmark.cli import main
from fuckmark.clipboard_watch import (
    CLIPBOARD_EXIT_FINDINGS,
    CLIPBOARD_EXIT_OK,
    CLIPBOARD_EXIT_UNAVAILABLE,
    CLIPBOARD_EXIT_USAGE,
    WATCH_ALGORITHM_VERSION,
    ClipboardUnavailableError,
    clean_clipboard_text,
    evaluate_clipboard_text,
    read_clipboard,
    run_clipboard_argv,
    snapshot_text,
    watch_clipboard,
    write_clipboard,
)
from fuckmark.product.scan import SCAN_CATEGORIES, SECURITY_SCAN_CATEGORIES


FAMILY = "\U0001F468\u200d\U0001F469"
ZWJ = "\u200d"
TROJAN = "if (x != \u202eadmin\u202c)"
TAGGED = "visible" + "".join(chr(0xE0000 + ord(ch)) for ch in "PWN")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _run(argv: list[str], reader=None, writer=None, monkeypatch=None) -> tuple[int, str, str]:
    if reader is not None:
        monkeypatch.setattr("fuckmark.clipboard_watch.read_clipboard", reader)
    if writer is not None:
        monkeypatch.setattr("fuckmark.clipboard_watch.write_clipboard", writer)
    out, err = StringIO(), StringIO()
    code = run_clipboard_argv(argv, out, err)
    return code, out.getvalue(), err.getvalue()


def test_evaluate_flags_trojan_and_tags_not_plain() -> None:
    plain = evaluate_clipboard_text("ordinary clipboard")
    assert plain.result.detected is False
    assert plain.removed == 0
    assert plain.cleaned == "ordinary clipboard"
    hidden = evaluate_clipboard_text(TROJAN)
    assert hidden.result.detected is True
    assert hidden.result.counts["bidi_control"] == 2
    assert hidden.cleaned == "if (x != admin)"
    tagged = evaluate_clipboard_text(TAGGED)
    assert tagged.result.detected is True
    assert tagged.result.counts["tag"] == 3
    assert tagged.cleaned == "visible"


def test_evaluate_keeps_emoji_zwj_and_strips_lone_zwj() -> None:
    kept = evaluate_clipboard_text(FAMILY)
    assert kept.result.detected is False
    assert kept.removed == 0
    assert kept.cleaned == FAMILY
    cleaned, removed, _full = clean_clipboard_text("a" + ZWJ + "b")
    assert cleaned == "ab"
    assert removed == 1
    lone = evaluate_clipboard_text("a" + ZWJ + "b")
    assert lone.result.detected is True
    assert lone.cleaned == "ab"


def test_evaluate_keeps_emoji_variation_selector_when_all_selected() -> None:
    text = "\u2764\ufe0f"
    default = evaluate_clipboard_text(text)
    assert default.result.detected is False
    assert default.cleaned == text
    selected = evaluate_clipboard_text(text, categories=frozenset(SCAN_CATEGORIES))
    assert selected.result.detected is False
    assert selected.removed == 0
    assert selected.cleaned == text
    prose = evaluate_clipboard_text("star\ufe0f", categories=frozenset(SCAN_CATEGORIES))
    assert prose.result.detected is True
    assert prose.cleaned == "star"


def test_evaluate_select_can_ignore_zero_width() -> None:
    text = "a" + ZWJ + "b"
    alert = evaluate_clipboard_text(text, categories=frozenset({"bidi_control"}))
    assert alert.result.detected is False
    assert alert.removed == 0
    assert alert.cleaned == text


def test_default_categories_match_security_set() -> None:
    alert = evaluate_clipboard_text("x")
    assert set(SECURITY_SCAN_CATEGORIES) <= {
        "bidi_control",
        "zero_width",
        "tag",
        "control",
        "noncharacter",
        "surrogate",
    }
    assert alert.result.total == 0


def test_snapshot_digest_changes_with_hidden_payload() -> None:
    visible = snapshot_text("admin")
    hidden = snapshot_text("\u202eadmin")
    assert visible.digest != hidden.digest
    assert len(visible.digest) == 64


def test_snapshot_and_watch_accept_lone_surrogates() -> None:
    lone = "\ud800"
    snap = snapshot_text(lone)
    assert len(snap.digest) == 64
    assert snap.digest != snapshot_text("").digest
    alert = evaluate_clipboard_text(lone)
    assert alert.result.detected is True
    assert alert.result.counts["surrogate"] == 1
    assert alert.cleaned == ""
    writes: list[str] = []
    code = watch_clipboard(once=True, clean=True, reader=lambda: lone, writer=writes.append)
    assert code == CLIPBOARD_EXIT_FINDINGS
    assert writes == [""]


def test_linux_clipboard_read_keeps_wl_paste_newlines(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.clipboard_watch.sys.platform", "linux")
    from fuckmark.clipboard_watch import _read_commands

    commands = _read_commands()
    assert commands[0] == ("wl-paste",)
    assert all(command != ("wl-paste", "--no-newline") for command in commands)


def test_watch_clean_does_not_overwrite_newer_clipboard() -> None:
    texts = ["a" + ZWJ, "fresh"]
    idx = {"i": 0}
    writes: list[str] = []

    def reader() -> str:
        i = min(idx["i"], len(texts) - 1)
        idx["i"] += 1
        return texts[i]

    code = watch_clipboard(once=True, clean=True, reader=reader, writer=writes.append)
    assert writes == []
    assert code == CLIPBOARD_EXIT_OK
    assert idx["i"] >= 2


def test_watch_once_clean_and_findings() -> None:
    assert watch_clipboard(once=True, reader=lambda: "hello") == CLIPBOARD_EXIT_OK
    assert watch_clipboard(once=True, reader=lambda: "a" + ZWJ) == CLIPBOARD_EXIT_FINDINGS


def test_watch_clean_rewrites_and_keeps_emoji() -> None:
    store = {"text": "ok" + ZWJ}
    writes: list[str] = []

    def writer(text: str) -> None:
        writes.append(text)
        store["text"] = text

    code = watch_clipboard(
        once=True,
        clean=True,
        reader=lambda: store["text"],
        writer=writer,
    )
    assert code == CLIPBOARD_EXIT_FINDINGS
    assert store["text"] == "ok"
    assert writes == ["ok"]
    family_store = {"text": FAMILY}
    family_writes: list[str] = []
    family_code = watch_clipboard(
        once=True,
        clean=True,
        reader=lambda: family_store["text"],
        writer=lambda text: family_writes.append(text),
    )
    assert family_code == CLIPBOARD_EXIT_OK
    assert family_writes == []
    assert family_store["text"] == FAMILY


def test_watch_alerts_once_per_digest_then_stops_on_find() -> None:
    texts = ["plain", "plain", "a" + ZWJ, "a" + ZWJ]
    idx = {"i": 0}
    alerts: list[int] = []
    clock = FakeClock()

    def reader() -> str:
        i = min(idx["i"], len(texts) - 1)
        idx["i"] += 1
        return texts[i]

    code = watch_clipboard(
        interval_seconds=0.5,
        exit_on_find=True,
        reader=reader,
        sleeper=clock.sleep,
        clock=clock,
        on_alert=lambda alert, _snap: alerts.append(alert.result.total),
    )
    assert code == CLIPBOARD_EXIT_FINDINGS
    assert alerts == [1]


def test_watch_max_seconds_returns_ok_without_realerting() -> None:
    alerts: list[str] = []
    clock = FakeClock()
    code = watch_clipboard(
        interval_seconds=0.5,
        max_seconds=1.0,
        reader=lambda: "a" + ZWJ,
        sleeper=clock.sleep,
        clock=clock,
        on_alert=lambda alert, snap: alerts.append(snap.digest),
    )
    assert code == CLIPBOARD_EXIT_OK
    assert len(alerts) == 1


def test_watch_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError):
        watch_clipboard(interval_seconds=0, once=True, reader=lambda: "")
    with pytest.raises(ValueError):
        watch_clipboard(max_seconds=-1, once=True, reader=lambda: "")


def test_cli_scan_json_and_dispatch(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.clipboard_watch.read_clipboard", lambda: TROJAN)
    out, err = StringIO(), StringIO()
    code = run_clipboard_argv(["scan", "--json"], out, err)
    assert code == CLIPBOARD_EXIT_FINDINGS
    payload = json.loads(out.getvalue())
    assert payload["algorithm_version"] == WATCH_ALGORITHM_VERSION
    assert payload["action"] == "scan"
    assert payload["removed"] == 2
    assert payload["scan"]["found"] is True
    assert payload["scan"]["counts"]["bidi_control"] == 2
    dispatched_out, dispatched_err = StringIO(), StringIO()
    dispatched = main(
        StringIO(""),
        dispatched_out,
        error_stream=dispatched_err,
        argv=("clipboard", "scan", "-q"),
    )
    assert dispatched == CLIPBOARD_EXIT_FINDINGS
    assert "fuckmark-scan" in dispatched_out.getvalue()
    assert "found=yes" in dispatched_out.getvalue()


def test_cli_scan_plain_is_ok(monkeypatch) -> None:
    code, _out, err = _run(["scan"], reader=lambda: "nothing hidden", monkeypatch=monkeypatch)
    assert code == CLIPBOARD_EXIT_OK
    assert "no hidden characters found" in err


def test_cli_clean_rewrites(monkeypatch) -> None:
    store = {"text": "hi" + ZWJ}
    writes: list[str] = []
    monkeypatch.setattr("fuckmark.clipboard_watch.read_clipboard", lambda: store["text"])
    monkeypatch.setattr(
        "fuckmark.clipboard_watch.write_clipboard",
        lambda text: writes.append(text) or store.update(text=text),
    )
    out, err = StringIO(), StringIO()
    code = main(StringIO(""), out, error_stream=err, argv=("clipboard", "clean", "--json"))
    assert code == CLIPBOARD_EXIT_FINDINGS
    assert store["text"] == "hi"
    assert writes == ["hi"]
    payload = json.loads(out.getvalue())
    assert payload["action"] == "cleaned"
    assert payload["removed"] == 1


def test_cli_watch_once_clean(monkeypatch) -> None:
    store = {"text": "x" + ZWJ}
    monkeypatch.setattr("fuckmark.clipboard_watch.read_clipboard", lambda: store["text"])
    monkeypatch.setattr(
        "fuckmark.clipboard_watch.write_clipboard",
        lambda text: store.update(text=text),
    )
    out, err = StringIO(), StringIO()
    code = run_clipboard_argv(["watch", "--once", "--clean", "-q"], out, err)
    assert code == CLIPBOARD_EXIT_FINDINGS
    assert store["text"] == "x"
    assert "fuckmark-scan" in out.getvalue()


def test_cli_unavailable_is_exit_three(monkeypatch) -> None:
    def boom() -> str:
        raise ClipboardUnavailableError("no supported clipboard read command found")

    code, _out, err = _run(["scan"], reader=boom, monkeypatch=monkeypatch)
    assert code == CLIPBOARD_EXIT_UNAVAILABLE
    assert "clipboard unavailable" in err


def test_cli_usage_errors(monkeypatch) -> None:
    code, _out, err = _run(["scan", "--select", "not_a_category"], reader=lambda: "x", monkeypatch=monkeypatch)
    assert code == CLIPBOARD_EXIT_USAGE
    assert "unknown scan categories" in err
    bad_interval, _out2, err2 = _run(
        ["watch", "--once", "--interval", "0"],
        reader=lambda: "x",
        monkeypatch=monkeypatch,
    )
    assert bad_interval == CLIPBOARD_EXIT_USAGE
    assert "interval" in err2
    missing = run_clipboard_argv([], StringIO(), StringIO())
    assert missing == CLIPBOARD_EXIT_USAGE


def test_cli_help_mentions_clipboard_watch(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "fuckmark clipboard" in rendered
    assert "OS clipboard" in rendered


def test_read_clipboard_missing_tools(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.clipboard_watch.shutil.which", lambda _name: None)
    with pytest.raises(ClipboardUnavailableError) as error:
        read_clipboard()
    assert "no supported clipboard read command found" in str(error.value)


def test_read_clipboard_decodes_utf8(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.clipboard_watch._read_commands", lambda: (("fake-paste",),))
    monkeypatch.setattr("fuckmark.clipboard_watch.shutil.which", lambda _name: "/bin/fake-paste")

    def fake_run(_command, **_kwargs):
        completed = type("Completed", (), {})()
        completed.stdout = ("hello" + ZWJ).encode("utf-8")
        return completed

    monkeypatch.setattr("fuckmark.clipboard_watch.subprocess.run", fake_run)
    assert read_clipboard() == "hello" + ZWJ


def test_write_clipboard_wraps_cli_error(monkeypatch) -> None:
    def boom(_text: str) -> None:
        from fuckmark.cli import ClipboardUnavailableError as WriteError

        raise WriteError("no supported clipboard command found")

    monkeypatch.setattr("fuckmark.cli.copy_to_clipboard", boom)
    with pytest.raises(ClipboardUnavailableError):
        write_clipboard("x")


def test_snapshot_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        snapshot_text(1)
    with pytest.raises(TypeError):
        clean_clipboard_text(1)
