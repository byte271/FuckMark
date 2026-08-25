from fuckmark.cycle7.whitespace_collapse import CYCLE7_SANITIZER_VARIANT_IDS
from fuckmark.experiments.cycle6_confirmation import CYCLE6_SANITIZER_IDS
from fuckmark.sanitizer_robustness import SANITIZER_VARIANT_IDS


def test_cycle6_sanitizer_ids_are_untouched() -> None:
    assert SANITIZER_VARIANT_IDS == ("raw", "nfkc", "cf_strip", "nfkc_cf_strip")
    assert CYCLE6_SANITIZER_IDS == SANITIZER_VARIANT_IDS
    assert CYCLE7_SANITIZER_VARIANT_IDS[:4] == SANITIZER_VARIANT_IDS
    assert "ws_collapse" in CYCLE7_SANITIZER_VARIANT_IDS
    assert "ws_collapse_nfkc_cf_strip" in CYCLE7_SANITIZER_VARIANT_IDS
