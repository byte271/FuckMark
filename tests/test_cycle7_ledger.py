from fuckmark.cycle7.ledger import (
    CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES,
    CYCLE7_CONFIRMATION_RESERVED_SEED_BASES,
    CYCLE7_EXPLORATORY_ROLE,
    CYCLE7_EXPLORATORY_SEED_BASE,
    CYCLE7_EXPLORATORY_SEED_BASES,
    CYCLE7_LEDGER_VERSION,
    CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
    CYCLE7_USED_EXPLORATORY_SEED_BASES,
    CYCLE7_VALIDATION_SEED_BASE,
    SPENT_CONFIRMATION_SEED_BASES,
    SPENT_DEVELOPMENT_SEED_BASES,
    assert_development_seed,
    assert_seed_not_spent,
    cycle7_seed_ledger_hash,
    cycle7_seed_ledger_payload,
)
import pytest


def test_spent_and_reserved_seeds_are_disjoint_and_documented() -> None:
    payload = cycle7_seed_ledger_payload()
    assert tuple(payload["spent_confirmation_seed_bases"]) == SPENT_CONFIRMATION_SEED_BASES
    assert SPENT_CONFIRMATION_SEED_BASES == (760000, 770000, 780000)
    assert SPENT_DEVELOPMENT_SEED_BASES == (720000, 730000)
    assert CYCLE7_LEDGER_VERSION == "cycle7-seed-ledger-v4"
    assert CYCLE7_EXPLORATORY_SEED_BASE == 810000
    assert CYCLE7_EXPLORATORY_SEED_BASES == (810000, 860000, 870000, 890000)
    assert CYCLE7_USED_EXPLORATORY_SEED_BASES == (810000, 860000, 870000, 890000)
    assert CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES == ()
    assert CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE == 860000
    assert CYCLE7_VALIDATION_SEED_BASE == 820000
    assert CYCLE7_CONFIRMATION_RESERVED_SEED_BASES == (830000, 840000, 850000)
    blocked = {
        *SPENT_CONFIRMATION_SEED_BASES,
        *SPENT_DEVELOPMENT_SEED_BASES,
        CYCLE7_EXPLORATORY_SEED_BASE,
        CYCLE7_VALIDATION_SEED_BASE,
        *CYCLE7_CONFIRMATION_RESERVED_SEED_BASES,
    }
    assert len(blocked) == 10
    assert 860000 not in blocked
    assert 870000 not in blocked
    assert 880000 not in blocked
    assert 890000 not in blocked
    assert 830000 in blocked
    assert cycle7_seed_ledger_hash() == cycle7_seed_ledger_hash()


def test_exploratory_seed_is_admitted_and_spent_seeds_are_rejected() -> None:
    assert_development_seed(CYCLE7_EXPLORATORY_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="spent"):
        assert_development_seed(760000, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="spent"):
        assert_seed_not_spent(720000)
    with pytest.raises(ValueError, match="confirmation-reserved"):
        assert_development_seed(830000, role=CYCLE7_EXPLORATORY_ROLE)
    with pytest.raises(ValueError, match="exploratory"):
        assert_development_seed(CYCLE7_VALIDATION_SEED_BASE, role=CYCLE7_EXPLORATORY_ROLE)
