from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import benchmark_fixtures, measure_fixture_row, run_determinism
from fuckmark.cycle8.compare import CYCLE8_BENCHMARK_ARM_IDS, CYCLE8_U034F_LETTER_ARM_ID
from fuckmark.cycle8.ledger import CYCLE8_LETTER_BENCHMARK_PAIR_COUNT
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.seeds.ledger import (
    CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE,
    CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE,
    assert_new_cycle8_letter_benchmark_generation_seed,
)
from fuckmark.transforms.registry import release_transform_registry


def test_benchmark_letter_preserves_visible_and_fail_closes_non_ascii() -> None:
    ascii_row = measure_fixture_row("short_paragraph", "short_paragraph", "I do not agree.")
    assert ascii_row["letter"]["visible"]["visible_ok"] is True
    assert ascii_row["letter"]["inserted_count"] > 0
    assert ascii_row["baselines"]["cli_process_text_equals_source"] is False
    assert ascii_row["sanitizers"]["cf_strip"]["carrier_survives"] is True
    assert ascii_row["stress_sanitizers"]["mn_strip"]["carrier_survives"] is False
    assert ascii_row["stress_sanitizers"]["default_ignorable_strip"]["carrier_survives"] is False
    non_ascii = measure_fixture_row("failclosed_non_ascii", "failclosed", "I do not agree " + chr(0x00E9) + ".")
    assert non_ascii["supported_product_domain"] is False
    assert non_ascii["letter"]["inserted_count"] == 0
    url = measure_fixture_row(
        "machine_url",
        "machine_sensitive",
        "See https://example.com/do-not-touch and continue the notes.",
    )
    assert url["letter"]["protected"]["pass"] is True
    assert "https://example.com/do-not-touch" in (
        "See https://example.com/do-not-touch and continue the notes."
    )
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert release_transform_registry().rules == ()
    assert run_determinism("I do not agree.", repeats=3)["deterministic"] is True
    assert CYCLE8_BENCHMARK_ARM_IDS[2] == CYCLE8_U034F_LETTER_ARM_ID
    assert CYCLE8_LETTER_BENCHMARK_PAIR_COUNT == 64
    assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE)
    assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE)
    assert len(benchmark_fixtures()) >= 20
    fixtures = {fixture_id: source for fixture_id, _category, source in benchmark_fixtures()}
    assert len(fixtures["long_paragraph"]) < 800
    assert "https://example.com/do-not-touch" in fixtures["machine_url"]
