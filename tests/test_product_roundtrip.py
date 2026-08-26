import re
import unicodedata

from fuckmark.cycle8.registry import apply_all_candidates, cycle8_space_carrier_registry
from fuckmark.product.roundtrip import (
    display_column_width,
    latin1_roundtrip_survives,
    nfc_normalize,
    roundtrip_report,
    stdin_stdout_roundtrip,
    utf8_file_roundtrip,
)
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1


def test_u034f_space_carrier_survives_utf8_nfc_and_stdio_roundtrips() -> None:
    source = "I do not agree.\nWe cannot continue."
    transformed = apply_all_candidates(cycle8_space_carrier_registry(0x034F), source)
    assert transformed != source
    assert is_carrier_insertion_v1(source, transformed, (0x034F,))
    assert project_visible_v1(transformed, (0x034F,)) == source
    assert utf8_file_roundtrip(transformed) == transformed
    assert stdin_stdout_roundtrip(transformed) == transformed
    assert nfc_normalize(transformed) == transformed
    assert latin1_roundtrip_survives(transformed) is False
    report = roundtrip_report(source, transformed, (0x034F,))
    assert report["visible_ok"] is True
    assert report["utf8_roundtrip_equals_transformed"] is True
    assert report["nfc_equals_transformed"] is True
    assert report["display_column_width_equal"] is True
    assert report["newline_count_equal"] is True
    assert report["ascii_space_count_equal"] is True


def test_u034f_after_space_breaks_literal_search_but_not_visible_projection() -> None:
    source = "I do not agree."
    transformed = apply_all_candidates(cycle8_space_carrier_registry(0x034F), source)
    assert "do not" in source
    assert "do not" not in transformed
    assert re.search(r"do not", transformed) is None
    assert "do not" in project_visible_v1(transformed, (0x034F,))
    assert unicodedata.category("\u034f") == "Mn"
    assert unicodedata.combining("\u034f") == 0
    assert display_column_width(source) == display_column_width(transformed)
