import json
from pathlib import Path

import pytest

from fuckmark.hashing import sha256_json
from fuckmark.seeds.ledger import (
    CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES,
    CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
    CYCLE8_LETTER_EXPLORATORY_SEED_BASE,
    CYCLE8_LETTER_EXPLORATORY_TOPIC,
    CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE,
    CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC,
    CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE,
    CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC,
    CYCLE8_MARGIN_PRIMARY_SEED_BASE,
    CYCLE8_MARGIN_PRIMARY_TOPIC,
    CYCLE8_MARGIN_REPLICATION_SEED_BASE,
    CYCLE8_MARGIN_REPLICATION_TOPIC,
    CYCLE8_MIX_PRIMARY_SEED_BASE,
    CYCLE8_MIX_PRIMARY_TOPIC,
    CYCLE8_MIX_REPLICATION_SEED_BASE,
    CYCLE8_MIX_REPLICATION_TOPIC,
    CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE,
    CYCLE8_MIX_SCALE_PRIMARY_TOPIC,
    CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE,
    CYCLE8_MIX_SCALE_REPLICATION_TOPIC,
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC,
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC,
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC,
    CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE,
    CYCLE8_SECOND_MODEL_TRANSFER_TOPIC,
    CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE,
    CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC,
    CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
    CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
    CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    CYCLE8_SCALE_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_REPLICATION_SEED_BASE,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    GLOBAL_SEED_LEDGER_VERSION,
    PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES,
    assert_new_cycle8_density_generation_seed,
    assert_new_cycle8_letter_generation_seed,
    assert_new_cycle8_letter_benchmark_generation_seed,
    assert_new_cycle8_margin_generation_seed,
    assert_new_cycle8_mix_generation_seed,
    assert_new_cycle8_deepmind_transfer_generation_seed,
    assert_new_cycle8_second_model_transfer_generation_seed,
    assert_new_cycle8_control_mix_generation_seed,
    assert_new_cycle8_scale_generation_seed,
    assert_seed_not_confirmation_content,
    global_seed_ledger_hash,
    global_seed_ledger_payload,
    known_seed_bases,
    row_for_seed_base,
)


def test_global_seed_ledger_file_matches_embedded_payload() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-global-seed-ledger-v1.json"
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in disk.items() if key != "ledger_hash"}
    assert payload == global_seed_ledger_payload()
    assert disk["ledger_hash"] == global_seed_ledger_hash() == sha256_json(payload)
    assert payload["algorithm_version"] == GLOBAL_SEED_LEDGER_VERSION


def test_global_ledger_marks_880000_exposed_and_mix_confirmation_spent() -> None:
    exposed = row_for_seed_base(880000)
    assert exposed["publicly_exposed"] is True
    assert exposed["spent"] is True
    assert exposed["eligible_as_unseen_validation"] is False
    assert exposed["eligible_for_confirmation"] is False
    assert PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES == (880000,)
    for seed_base in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        row = row_for_seed_base(seed_base)
        assert row["generated"] is True
        assert row["scored"] is True
        assert row["spent"] is True
        assert row["eligible_for_confirmation"] is False
        assert row["generation_topic"] in {
            CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
            CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
            CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
        }
        with pytest.raises(ValueError, match="must not be inspected"):
            assert_seed_not_confirmation_content(seed_base)
    assert row_for_seed_base(830000)["generation_topic"] == CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC
    assert row_for_seed_base(840000)["generation_topic"] == CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC
    assert row_for_seed_base(850000)["generation_topic"] == CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC


def test_scale_seeds_are_reserved_before_generation() -> None:
    exploratory = row_for_seed_base(CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    assert exploratory["generation_topic"] == CYCLE8_SCALE_EXPLORATORY_TOPIC == "carrier scaling"
    assert exploratory["generated"] is True
    assert exploratory["scored"] is True
    assert exploratory["eligible_as_unseen_validation"] is False
    replication = row_for_seed_base(CYCLE8_SCALE_REPLICATION_SEED_BASE)
    assert replication["generated"] is True
    assert replication["scored"] is True
    assert replication["eligible_as_unseen_validation"] is False
    assert_new_cycle8_scale_generation_seed(CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    assert_new_cycle8_scale_generation_seed(CYCLE8_SCALE_REPLICATION_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_scale_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="not a Cycle 8 scale"):
        assert_new_cycle8_scale_generation_seed(890000)
    with pytest.raises(ValueError, match="not a Cycle 8 scale"):
        assert_new_cycle8_scale_generation_seed(920000)
    bases = known_seed_bases()
    assert len(bases) == len(set(bases))
    assert 930000 in bases and 940000 in bases and 950000 in bases and 960000 in bases and 970000 in bases
    assert 980000 in bases and 990000 in bases
    assert 1000000 in bases and 1010000 in bases
    assert 1020000 in bases and 1030000 in bases
    assert 1040000 in bases and 1050000 in bases
    assert 1060000 in bases and 1070000 in bases and 1080000 in bases and 1090000 in bases
    assert 1100000 in bases
    density = row_for_seed_base(CYCLE8_DENSITY_EXPLORATORY_SEED_BASE)
    assert density["generated"] is True
    assert density["scored"] is True
    assert density["generation_topic"] == "carrier density follow-up"
    assert_new_cycle8_density_generation_seed(CYCLE8_DENSITY_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="density"):
        assert_new_cycle8_density_generation_seed(CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_density_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="density"):
        assert_new_cycle8_density_generation_seed(880000)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_density_generation_seed(830000)
    letter = row_for_seed_base(CYCLE8_LETTER_EXPLORATORY_SEED_BASE)
    assert letter["generation_topic"] == CYCLE8_LETTER_EXPLORATORY_TOPIC == "intra-word carrier follow-up"
    assert letter["generated"] is True
    assert letter["scored"] is True
    assert_new_cycle8_letter_generation_seed(CYCLE8_LETTER_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="letter"):
        assert_new_cycle8_letter_generation_seed(CYCLE8_DENSITY_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_letter_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_letter_generation_seed(830000)
    primary = row_for_seed_base(CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE)
    assert primary["generation_topic"] == CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC == "letter carrier system benchmark"
    assert primary["generated"] is True
    assert primary["scored"] is True
    assert primary["eligible_for_confirmation"] is False
    assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE)
    assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE)
    with pytest.raises(ValueError, match="benchmark"):
        assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_LETTER_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_letter_benchmark_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_letter_benchmark_generation_seed(830000)
    margin_primary = row_for_seed_base(CYCLE8_MARGIN_PRIMARY_SEED_BASE)
    assert margin_primary["generation_topic"] == CYCLE8_MARGIN_PRIMARY_TOPIC == "margin robustness development"
    assert margin_primary["generated"] is True
    assert margin_primary["scored"] is True
    assert margin_primary["eligible_for_confirmation"] is False
    assert_new_cycle8_margin_generation_seed(CYCLE8_MARGIN_PRIMARY_SEED_BASE)
    assert_new_cycle8_margin_generation_seed(CYCLE8_MARGIN_REPLICATION_SEED_BASE)
    with pytest.raises(ValueError, match="margin"):
        assert_new_cycle8_margin_generation_seed(CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_margin_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_margin_generation_seed(830000)
    mix_primary = row_for_seed_base(CYCLE8_MIX_PRIMARY_SEED_BASE)
    assert mix_primary["generation_topic"] == CYCLE8_MIX_PRIMARY_TOPIC == "letter mix margin development"
    assert mix_primary["generated"] is True
    assert mix_primary["scored"] is True
    assert mix_primary["eligible_for_confirmation"] is False
    assert_new_cycle8_mix_generation_seed(CYCLE8_MIX_PRIMARY_SEED_BASE)
    assert_new_cycle8_mix_generation_seed(CYCLE8_MIX_REPLICATION_SEED_BASE)
    mix_replica = row_for_seed_base(CYCLE8_MIX_REPLICATION_SEED_BASE)
    assert mix_replica["generation_topic"] == CYCLE8_MIX_REPLICATION_TOPIC == "letter mix margin replication"
    assert mix_replica["generated"] is True
    assert mix_replica["scored"] is True
    mix_scale = row_for_seed_base(CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE)
    assert mix_scale["generation_topic"] == CYCLE8_MIX_SCALE_PRIMARY_TOPIC == "letter mix scale development"
    assert mix_scale["generated"] is True
    assert mix_scale["scored"] is True
    assert mix_scale["eligible_for_confirmation"] is False
    assert_new_cycle8_mix_generation_seed(CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE)
    assert_new_cycle8_mix_generation_seed(CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE)
    mix_scale_replica = row_for_seed_base(CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE)
    assert mix_scale_replica["generation_topic"] == CYCLE8_MIX_SCALE_REPLICATION_TOPIC == "letter mix scale replication"
    assert mix_scale_replica["generated"] is True
    assert mix_scale_replica["scored"] is True
    with pytest.raises(ValueError, match="mix"):
        assert_new_cycle8_mix_generation_seed(CYCLE8_MARGIN_PRIMARY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_mix_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_mix_generation_seed(830000)
    deepmind_primary = row_for_seed_base(CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE)
    assert deepmind_primary["generation_topic"] == CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC == "deepmind mix transfer primary"
    assert deepmind_primary["generated"] is True
    assert deepmind_primary["scored"] is True
    assert deepmind_primary["eligible_for_confirmation"] is False
    assert_new_cycle8_deepmind_transfer_generation_seed(CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE)
    assert_new_cycle8_deepmind_transfer_generation_seed(CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE)
    assert_new_cycle8_deepmind_transfer_generation_seed(CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE)
    with pytest.raises(ValueError, match="DeepMind"):
        assert_new_cycle8_deepmind_transfer_generation_seed(CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_deepmind_transfer_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_deepmind_transfer_generation_seed(830000)
    second_model = row_for_seed_base(CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE)
    assert second_model["generation_topic"] == CYCLE8_SECOND_MODEL_TRANSFER_TOPIC == "second model mix transfer"
    assert second_model["generated"] is True
    assert second_model["scored"] is True
    assert second_model["eligible_for_confirmation"] is False
    assert_new_cycle8_second_model_transfer_generation_seed(CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE)
    with pytest.raises(ValueError, match="second-model"):
        assert_new_cycle8_second_model_transfer_generation_seed(CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_second_model_transfer_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_second_model_transfer_generation_seed(830000)
    control_mix = row_for_seed_base(CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE)
    assert control_mix["generation_topic"] == CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC == "control mix sanitizer exploratory"
    assert control_mix["generated"] is True
    assert control_mix["scored"] is True
    assert control_mix["eligible_for_confirmation"] is False
    assert_new_cycle8_control_mix_generation_seed(CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="control-mix"):
        assert_new_cycle8_control_mix_generation_seed(CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_control_mix_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_control_mix_generation_seed(830000)
