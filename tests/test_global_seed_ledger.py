import json
from pathlib import Path

import pytest

from fuckmark.hashing import sha256_json
from fuckmark.seeds.ledger import (
    CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES,
    CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    CYCLE8_SCALE_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_REPLICATION_SEED_BASE,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    GLOBAL_SEED_LEDGER_VERSION,
    PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES,
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


def test_global_ledger_marks_880000_exposed_and_keeps_confirmation_unseen() -> None:
    exposed = row_for_seed_base(880000)
    assert exposed["publicly_exposed"] is True
    assert exposed["spent"] is True
    assert exposed["eligible_as_unseen_validation"] is False
    assert exposed["eligible_for_confirmation"] is False
    assert PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES == (880000,)
    for seed_base in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        row = row_for_seed_base(seed_base)
        assert row["generated"] is False
        assert row["scored"] is False
        assert row["eligible_for_confirmation"] is True
        with pytest.raises(ValueError, match="must not be inspected"):
            assert_seed_not_confirmation_content(seed_base)


def test_scale_seeds_are_reserved_before_generation() -> None:
    exploratory = row_for_seed_base(CYCLE8_SCALE_EXPLORATORY_SEED_BASE)
    assert exploratory["generation_topic"] == CYCLE8_SCALE_EXPLORATORY_TOPIC == "carrier scaling"
    assert exploratory["generated"] is True
    assert exploratory["scored"] is True
    assert exploratory["eligible_as_unseen_validation"] is False
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
    assert 930000 in bases and 940000 in bases and 950000 in bases
