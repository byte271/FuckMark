import json
from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.compare import CYCLE8_BENCHMARK_ARM_IDS, CYCLE8_LETTER_ALT_ARM_ID
from fuckmark.cycle8.mix_freeze import (
    CYCLE8_MIX_FREEZE_PATH,
    CYCLE8_MIX_FREEZE_VERSION,
    assert_cycle8_mix_confirmation_generation_seed,
    assert_mix_freeze_committed,
    mix_freeze_hash,
    mix_freeze_payload,
)
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.hashing import sha256_json
from fuckmark.seeds.ledger import (
    CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
    CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
    CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
    assert_new_cycle8_mix_generation_seed,
    row_for_seed_base,
)
from fuckmark.transforms.registry import release_transform_registry


def test_mix_freeze_file_matches_embedded_payload() -> None:
    path = Path(__file__).resolve().parents[1] / CYCLE8_MIX_FREEZE_PATH
    disk = json.loads(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in disk.items() if key != "freeze_hash"}
    assert payload == mix_freeze_payload()
    assert disk["freeze_hash"] == mix_freeze_hash() == sha256_json(payload)
    assert disk["freeze_hash"] == "2286aa201bd9cb70136f2895740489136aa1ba7cfd9471c6e233fe201af41986"
    assert disk["algorithm_version"] == CYCLE8_MIX_FREEZE_VERSION
    assert disk["freeze"] is True
    assert disk["confirmation"] is False
    assert disk["confirmation_generated"] is False
    assert disk["product_authorized"] is False
    assert disk["mechanism_id"] == CYCLE8_LETTER_ALT_ARM_ID
    assert disk["max_selected"] == 192
    assert disk["development_evidence"]["rate"] == "0/256"
    assert disk["development_evidence"]["raw_watermarked_detected"] == 0
    assert float(disk["development_evidence"]["worst_max_score"]) < 0.52
    assert disk["confirmation_protocol"]["seed_bases"] == [830000, 840000, 850000]
    assert disk["confirmation_protocol"]["generated"] is False
    assert disk["do_not_generate_950000"] is True
    assert_mix_freeze_committed()
    assert release_transform_registry().rules == ()
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert CYCLE8_LETTER_ALT_ARM_ID not in CYCLE8_BENCHMARK_ARM_IDS


def test_mix_confirmation_seeds_are_spent_after_one_shot() -> None:
    primary = row_for_seed_base(830000)
    replica = row_for_seed_base(840000)
    hold = row_for_seed_base(850000)
    assert primary["generation_topic"] == CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC
    assert replica["generation_topic"] == CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC
    assert hold["generation_topic"] == CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC
    for row in (primary, replica, hold):
        assert row["generated"] is True
        assert row["scored"] is True
        assert row["spent"] is True
        assert row["eligible_for_confirmation"] is False
    with pytest.raises(ValueError, match="already generated"):
        assert_cycle8_mix_confirmation_generation_seed(830000)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_mix_generation_seed(830000)
    with pytest.raises(ValueError, match="not a Cycle 8 mix confirmation"):
        assert_cycle8_mix_confirmation_generation_seed(1020000)
    with pytest.raises(ValueError, match="not a Cycle 8 mix confirmation"):
        assert_cycle8_mix_confirmation_generation_seed(950000)
