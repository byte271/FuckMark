import json
from pathlib import Path

import pytest

from fuckmark.cycle7.ledger import (
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE,
    CYCLE7_STAGE_D1_TOPIC,
    assert_development_seed,
)
from fuckmark.cycle8.ledger import (
    CYCLE8_EXPLORATORY_SEED_BASE,
    CYCLE8_EXPLORATORY_TOPIC,
    CYCLE8_REPLICATION_SEED_BASE,
    CYCLE8_SECONDARY_EXPLORATORY_SEED_BASE,
    CYCLE8_VALIDATION_SEED_BASE,
    assert_cycle8_development_seed,
)


def test_cycle7_stage_d_and_cycle8_share_890000_with_disjoint_corpora() -> None:
    assert CYCLE7_STAGE_D1_EXPLORATORY_SEED_BASE == CYCLE8_EXPLORATORY_SEED_BASE == 890000
    assert CYCLE7_STAGE_D1_TOPIC == "document structure"
    assert CYCLE8_EXPLORATORY_TOPIC == "invisible carrier development"
    assert CYCLE7_STAGE_D1_TOPIC != CYCLE8_EXPLORATORY_TOPIC
    cycle7 = json.loads(
        Path("evidence/cycle7-stage-d-2026-08-25/samples.json").read_text(encoding="utf-8")
    )
    cycle8 = json.loads(
        Path("evidence/cycle8-exploratory-890000-2026-08-25/detector-compare.json").read_text(
            encoding="utf-8"
        )
    )
    assert cycle7["topic"] == CYCLE7_STAGE_D1_TOPIC
    assert cycle8["topic"] == CYCLE8_EXPLORATORY_TOPIC
    cycle7_hashes = {sample["text_sha256"] for sample in cycle7["samples"]}
    cycle8_hashes = {sample["text_sha256"] for sample in cycle8["samples"]}
    assert cycle7_hashes.isdisjoint(cycle8_hashes)
    assert len(cycle7_hashes) == 8
    assert len(cycle8_hashes) == 8


def test_cycle8_still_blocks_cycle7_stage_d_validation_seed() -> None:
    with pytest.raises(ValueError):
        assert_cycle8_development_seed(880000, role="validation_development")


def test_cycle7_does_not_admit_cycle8_exclusive_seeds() -> None:
    for seed in (
        CYCLE8_REPLICATION_SEED_BASE,
        CYCLE8_VALIDATION_SEED_BASE,
        CYCLE8_SECONDARY_EXPLORATORY_SEED_BASE,
    ):
        with pytest.raises(ValueError, match="not in the Cycle 7 ledger"):
            assert_development_seed(seed, role=CYCLE7_EXPLORATORY_ROLE)
