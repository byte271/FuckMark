import time

from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    apply_letter_alternating_mix,
    select_letter_mix_sites,
)
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1


def test_letter_mix_scan_keeps_eligible_prose_bytes_and_invariants() -> None:
    source = "Abcd"
    applied = apply_letter_alternating_mix(source)
    assert applied == (
        "A\u034f\u007f\u20dd\U00013430\ufff9"
        "b\ufe00\u0080\u20dd\U00013431\ufffa"
        "c\u034f\u0081\u20dd\U00013432\ufffb"
        "d\ufe00\u0082\u20dd\U00013433\ufff9"
    )
    prose = "Hello world. This is ordinary English ASCII text without paths."
    mixed = apply_letter_alternating_mix(prose)
    assert project_visible_v1(mixed, LETTER_MIX_APPROVED_CARRIERS) == prose
    assert is_carrier_insertion_v1(prose, mixed, LETTER_MIX_APPROVED_CARRIERS)
    assert select_letter_mix_sites(prose) == select_letter_mix_sites(prose)
    assert apply_letter_alternating_mix(prose) == mixed


def test_letter_mix_scan_handles_url_only_and_empty_eligibility() -> None:
    urls = "\n".join(f"https://example.com/item-{index}" for index in range(50))
    mixed = apply_letter_alternating_mix(urls)
    assert mixed == urls
    assert select_letter_mix_sites(urls) == ()
    assert apply_letter_alternating_mix("123.") == "123."
    long_protected = "https://example.com/" + ("a" * 4000)
    assert apply_letter_alternating_mix(long_protected) == long_protected


def test_letter_mix_scan_is_deterministic_on_long_documents() -> None:
    source = ("Hello world. " * 200) + ("abcdefghijklmnopqrstuvwxyz" * 20)
    first = apply_letter_alternating_mix(source)
    second = apply_letter_alternating_mix(source)
    assert first == second
    assert project_visible_v1(first, LETTER_MIX_APPROVED_CARRIERS) == source
    sites = select_letter_mix_sites(source)
    assert first.count("\u034f") + first.count("\ufe00") == len(sites)


def test_letter_mix_scan_records_repeated_timings() -> None:
    payloads = {
        "prose_1k": "Hello world. " * 80,
        "prose_10k": "Hello world. " * 800,
        "url_only": "\n".join(["https://example.com/alpha-beta-gamma"] * 200),
        "no_sites": "1234567890 " * 200,
        "long_protected": "https://example.com/" + ("abcde/" * 400),
    }
    for _name, source in payloads.items():
        times: list[float] = []
        outputs: list[str] = []
        for _repeat in range(3):
            started = time.perf_counter()
            outputs.append(apply_letter_alternating_mix(source))
            times.append(time.perf_counter() - started)
        assert len(set(outputs)) == 1
        assert min(times) >= 0
        assert project_visible_v1(outputs[0], LETTER_MIX_APPROVED_CARRIERS) == source
