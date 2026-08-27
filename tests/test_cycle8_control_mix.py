import json
import unicodedata

from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import sanitize_benchmark_stress
from fuckmark.cycle8.control_carrier import (
    apply_required_sanitizer_bundle,
    control_display_column_width,
    required_sanitizers_keep,
)
from fuckmark.cycle8.control_mix import (
    CONTROL_MIX_APPROVED_CARRIERS,
    CONTROL_MIX_MAX_SELECTED,
    CONTROL_MIX_PAYLOADS,
    apply_control_alternating_mix,
    select_control_mix_sites,
)
from fuckmark.cycle8.letter_mix import LETTER_MIX_MAX_SELECTED, apply_letter_alternating_mix, hard_machine_intervals
from fuckmark.cycle8.sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from fuckmark.cycle8.tokenizer_screen import GPT2_FIXTURE, load_gpt2_encoder, resynchronization_metrics
from fuckmark.product.roundtrip import latin1_roundtrip_survives
from fuckmark.product.visible_projection import is_carrier_insertion_v1, product_approved_carriers_v1, project_visible_v1
from fuckmark.transforms.registry import release_transform_registry


def test_control_mix_cycles_eligible_controls_and_keeps_visible_text() -> None:
    source = "Abcd"
    applied = apply_control_alternating_mix(source)
    assert applied == "A\u007fb\u0080c\u0081d\u0082"
    assert is_carrier_insertion_v1(source, applied, CONTROL_MIX_APPROVED_CARRIERS)
    assert project_visible_v1(applied, CONTROL_MIX_APPROVED_CARRIERS) == source
    assert CONTROL_MIX_MAX_SELECTED == LETTER_MIX_MAX_SELECTED == 192
    assert process_text(source) == source
    assert release_transform_registry().rules == ()
    assert product_approved_carriers_v1() == frozenset()


def test_control_mix_blocks_numbers_and_urls_and_survives_required_sanitizers() -> None:
    source = r"Keep going \[item 7 and we never wait at https://example.com/ab."
    mix = apply_letter_alternating_mix(source)
    control = apply_control_alternating_mix(source)
    sites = select_control_mix_sites(source)
    inserted = sum(control.count(payload) for payload in CONTROL_MIX_PAYLOADS)
    assert inserted == len(sites)
    assert "7" in control
    assert "https://example.com/ab" in project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS)
    url = "https://example.com/ab"
    url_start = source.index(url)
    url_end = url_start + len(url)
    for index in sites:
        assert index < url_start or index >= url_end
        assert source[index] != "7"
    intervals = hard_machine_intervals(source)
    assert any(source[start:end] == "7" for start, end in intervals)
    assert project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS) == source
    assert required_sanitizers_keep(control) is True
    assert apply_required_sanitizer_bundle(control) == control
    for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS:
        assert sanitize_cycle8_scale_variant(variant, control) == control
    assert sanitize_benchmark_stress("mn_strip", mix) == source
    assert sanitize_benchmark_stress("mn_strip", control) == control
    assert latin1_roundtrip_survives(control) is True
    assert json.loads(json.dumps(control, ensure_ascii=False)) == control
    assert process_text("I do not agree.") == "I do not agree."


def test_control_mix_inserts_inside_quotes_and_respects_cap() -> None:
    quoted = 'He said "hello world" and left.'
    applied = apply_control_alternating_mix(quoted)
    interior = applied[applied.index('"') + 1 : applied.rindex('"')]
    assert any(payload in interior for payload in CONTROL_MIX_PAYLOADS)
    source = "abcdefghijklmnopqrstuvwxyz" * 12
    capped = apply_control_alternating_mix(source, max_selected=16)
    inserted = sum(capped.count(payload) for payload in CONTROL_MIX_PAYLOADS)
    assert inserted == 16
    assert project_visible_v1(capped, CONTROL_MIX_APPROVED_CARRIERS) == source
    assert control_display_column_width(capped) == control_display_column_width(source)


def test_control_mix_disrupts_gpt2_tokens_and_breaks_raw_search() -> None:
    source = "I do not agree."
    applied = apply_control_alternating_mix(source)
    assert "do not" in source
    assert "do not" not in applied
    assert "do not" in project_visible_v1(applied, CONTROL_MIX_APPROVED_CARRIERS)
    assert all(unicodedata.category(payload) == "Cc" for payload in CONTROL_MIX_PAYLOADS)
    encoder = load_gpt2_encoder()
    if encoder is None:
        return
    metrics = resynchronization_metrics(encoder(source), encoder(applied))
    assert metrics["ids_equal"] is False
    assert int(metrics["token_count_delta"]) > 0
    long_metrics = resynchronization_metrics(encoder(GPT2_FIXTURE), encoder(apply_control_alternating_mix(GPT2_FIXTURE)))
    assert long_metrics["ids_equal"] is False
    assert int(long_metrics["token_count_delta"]) > 0
