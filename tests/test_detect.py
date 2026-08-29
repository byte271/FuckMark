from io import StringIO

from fuckmark.cli import main, transform_text
from fuckmark.cycle8.letter_mix import (
    apply_historical_mark_letter_mix,
    apply_letter_alternating_mix,
    first_unmixed_non_ascii,
)
from fuckmark.product.detect import DETECT_CONTACT_EMAIL, detect_fuckmark_insertions, detect_human_report


def test_first_unmixed_skips_processed_letter_and_emoji_sites() -> None:
    assert first_unmixed_non_ascii(chr(0x00E9) * 3) is None
    assert first_unmixed_non_ascii(chr(0x4E2D) + chr(0x6587)) is None
    assert first_unmixed_non_ascii(chr(0x1F600)) is None
    assert first_unmixed_non_ascii("I do not agree " + chr(0x00E9) + ".") is None
    assert first_unmixed_non_ascii("e" + chr(0x0301)) is None
    curly = "I don" + chr(0x2019) + "t agree."
    assert first_unmixed_non_ascii(curly) == (5, 0x2019)
    assert transform_text(chr(0x00E9) * 3).first_unsupported == ""
    assert transform_text(chr(0x1F600)).first_unsupported == ""
    assert transform_text(curly).first_unsupported == "U+2019@5"
    arabic = chr(0x0645) + chr(0x0646)
    assert transform_text(arabic).first_unsupported == "U+0645@0"


def test_detector_finds_live_and_historical_mix_and_rejects_plain() -> None:
    source = "I do not agree."
    live = apply_letter_alternating_mix(source)
    historical = apply_historical_mark_letter_mix(source)
    miss = detect_fuckmark_insertions(source)
    hit = detect_fuckmark_insertions(live)
    old = detect_fuckmark_insertions(historical)
    assert miss.detected is False
    assert miss.found == 0
    assert hit.detected is True
    assert hit.found == 55
    assert hit.mark_count == 11
    assert hit.cc_count == 11
    assert hit.me_count == 11
    assert hit.cf_count == 11
    assert hit.ia_count == 11
    assert old.detected is True
    assert old.mark_count == 11
    assert old.ia_count == 0
    report = detect_human_report(miss)
    assert "no watermark detected" in report
    assert DETECT_CONTACT_EMAIL in report
    assert DETECT_CONTACT_EMAIL in detect_human_report(miss)


def test_cli_detect_reports_miss_and_hit() -> None:
    miss_out = StringIO()
    miss_err = StringIO()
    miss_status = main(
        StringIO(""),
        miss_out,
        error_stream=miss_err,
        argv=("--detect", "--text", "I do not agree."),
    )
    assert miss_status == 0
    missed = miss_out.getvalue()
    assert "no watermark detected" in missed
    assert DETECT_CONTACT_EMAIL in missed
    assert miss_err.getvalue() == ""
    mixed = apply_letter_alternating_mix("I do not agree.")
    hit_out = StringIO()
    hit_err = StringIO()
    hit_status = main(
        StringIO(""),
        hit_out,
        error_stream=hit_err,
        argv=("--detect", "--text", mixed, "--status"),
    )
    assert hit_status == 0
    assert "watermark detected" in hit_out.getvalue()
    assert "fuckmark-detect detected=yes" in hit_err.getvalue()
    quiet_out = StringIO()
    quiet_err = StringIO()
    quiet_status = main(
        StringIO(""),
        quiet_out,
        error_stream=quiet_err,
        argv=("--detect", "-q", "--text", "plain text"),
    )
    assert quiet_status == 0
    assert quiet_out.getvalue().startswith("fuckmark-detect detected=no")
    assert quiet_err.getvalue() == ""
    visible = main(
        StringIO(""),
        StringIO(),
        error_stream=StringIO(),
        argv=("--detect", "--visible", "--text", "I do not agree."),
    )
    assert visible == 1
