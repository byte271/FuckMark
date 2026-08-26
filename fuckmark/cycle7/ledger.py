from __future__ import annotations

from collections.abc import Mapping, Sequence

from .._validation import require_int
from ..hashing import sha256_json


CYCLE7_LEDGER_VERSION = "cycle7-seed-ledger-v4"
CYCLE7_EXPLORATORY_ROLE = "exploratory_development"
CYCLE7_VALIDATION_ROLE = "validation_development"
CYCLE7_CONFIRMATION_RESERVED_ROLE = "confirmation_reserved"
CYCLE7_RULE_CONSTRUCTION_ROLE = "rule_construction_development"

SPENT_CONFIRMATION_SEED_BASES = (760_000, 770_000, 780_000)
SPENT_DEVELOPMENT_SEED_BASES = (720_000, 730_000)
BLOCKED_PROFILE_SEED_BASES = (
    1_120_000,
    1_130_000,
    1_140_000,
    1_150_000,
    1_160_000,
)
BLOCKED_HISTORIC_SEED_BASES = (401_000, 402_000, 500_000, 61000)

CYCLE7_EXPLORATORY_SEED_BASE = 810_000
CYCLE7_STAGE_A_EXPLORATORY_SEED_BASE = 810_000
CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE = 860_000
CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE = 870_000
CYCLE7_EXPLORATORY_SEED_BASES = (810_000, 860_000, 870_000)
CYCLE7_USED_EXPLORATORY_SEED_BASES = (810_000, 860_000)
CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES = (870_000,)
CYCLE7_VALIDATION_SEED_BASE = 820_000
CYCLE7_STAGE_C_VALIDATION_SEED_BASE = 880_000
CYCLE7_VALIDATION_SEED_BASES = (820_000, 880_000)
CYCLE7_USED_VALIDATION_SEED_BASES = (820_000, 880_000)
CYCLE7_ACTIVE_VALIDATION_SEED_BASES = ()
CYCLE7_PUBLICLY_EXPOSED_SEED_BASES = (880_000,)
CYCLE7_VALIDATION_TOPIC = "held-out evaluation"
CYCLE7_STAGE_C_VALIDATION_TOPIC = "independent check"
CYCLE7_CONFIRMATION_RESERVED_SEED_BASES = (830_000, 840_000, 850_000)
CYCLE7_STAGE_B1_TOPIC = "independent replication"
CYCLE7_STAGE_C1_TOPIC = "measurement protocol"

_ALL_BLOCKED = frozenset(
    (
        *SPENT_CONFIRMATION_SEED_BASES,
        *SPENT_DEVELOPMENT_SEED_BASES,
        *BLOCKED_PROFILE_SEED_BASES,
        *BLOCKED_HISTORIC_SEED_BASES,
        *CYCLE7_PUBLICLY_EXPOSED_SEED_BASES,
    )
)


def cycle7_seed_ledger_payload() -> dict[str, object]:
    return {
        "algorithm_version": CYCLE7_LEDGER_VERSION,
        "spent_confirmation_seed_bases": list(SPENT_CONFIRMATION_SEED_BASES),
        "spent_development_seed_bases": list(SPENT_DEVELOPMENT_SEED_BASES),
        "blocked_profile_seed_bases": list(BLOCKED_PROFILE_SEED_BASES),
        "blocked_historic_seed_bases": list(BLOCKED_HISTORIC_SEED_BASES),
        "exploratory_development_seed_base": CYCLE7_EXPLORATORY_SEED_BASE,
        "exploratory_development_seed_bases": list(CYCLE7_EXPLORATORY_SEED_BASES),
        "used_exploratory_development_seed_bases": list(CYCLE7_USED_EXPLORATORY_SEED_BASES),
        "active_exploratory_development_seed_bases": list(CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES),
        "stage_b1_exploratory_seed_base": CYCLE7_STAGE_B1_EXPLORATORY_SEED_BASE,
        "stage_b1_topic": CYCLE7_STAGE_B1_TOPIC,
        "stage_c1_exploratory_seed_base": CYCLE7_STAGE_C1_EXPLORATORY_SEED_BASE,
        "stage_c1_topic": CYCLE7_STAGE_C1_TOPIC,
        "validation_development_seed_base": CYCLE7_VALIDATION_SEED_BASE,
        "validation_development_seed_bases": list(CYCLE7_VALIDATION_SEED_BASES),
        "used_validation_development_seed_bases": list(CYCLE7_USED_VALIDATION_SEED_BASES),
        "active_validation_development_seed_bases": list(CYCLE7_ACTIVE_VALIDATION_SEED_BASES),
        "publicly_exposed_seed_bases": list(CYCLE7_PUBLICLY_EXPOSED_SEED_BASES),
        "validation_topic": CYCLE7_VALIDATION_TOPIC,
        "stage_c_validation_seed_base": CYCLE7_STAGE_C_VALIDATION_SEED_BASE,
        "stage_c_validation_topic": CYCLE7_STAGE_C_VALIDATION_TOPIC,
        "confirmation_reserved_seed_bases": list(CYCLE7_CONFIRMATION_RESERVED_SEED_BASES),
        "selection_rule": (
            "Confirmation-reserved seeds were chosen as unused 10k blocks "
            "without inspecting detector outcomes. Do not promote exploratory "
            "or validation seeds into confirmation after seeing scores. "
            "Seed 860000 and topic 'independent replication' were frozen before "
            "any Stage B generation or detector look. "
            "Seed 820000 and topic 'held-out evaluation' were frozen before "
            "any validation generation or detector look. "
            "Seed 870000 and topic 'measurement protocol' were frozen before "
            "any Stage C generation or detector look. "
            "Seed 880000 and topic 'independent check' were frozen before "
            "any Stage C validation generation or detector look. "
            "Closed unmerged PR #98 later publicly generated and scored 880000. "
            "Seed 880000 is PUBLICLY_EXPOSED and is not eligible as unseen validation."
        ),
        "spent_corpus_rule": (
            "Do not use 720000, 730000, 760000, 770000, or 780000 as "
            "Cycle 7 development, tuning, or confirmation data. "
            "Do not keep expanding transform rules against 810000 or 860000. "
            "Do not retune on validation seed 820000. "
            "Do not use 880000 as unseen validation. "
            "Do not inspect 830000, 840000, or 850000."
        ),
    }


def cycle7_seed_ledger_hash() -> str:
    return sha256_json(cycle7_seed_ledger_payload())


def role_for_seed_base(seed_base: int) -> str | None:
    require_int("seed_base", seed_base)
    if seed_base in CYCLE7_EXPLORATORY_SEED_BASES:
        return CYCLE7_EXPLORATORY_ROLE
    if seed_base in CYCLE7_VALIDATION_SEED_BASES:
        return CYCLE7_VALIDATION_ROLE
    if seed_base in CYCLE7_CONFIRMATION_RESERVED_SEED_BASES:
        return CYCLE7_CONFIRMATION_RESERVED_ROLE
    return None


def assert_development_seed(seed_base: int, *, role: str) -> None:
    require_int("seed_base", seed_base)
    if not isinstance(role, str) or not role:
        raise ValueError("role must be a non-empty string")
    if seed_base in CYCLE7_PUBLICLY_EXPOSED_SEED_BASES:
        raise ValueError("seed_base is publicly exposed and is not eligible as unseen validation")
    if seed_base in _ALL_BLOCKED:
        raise ValueError("seed_base is spent or otherwise blocked for Cycle 7 development")
    expected = role_for_seed_base(seed_base)
    if expected is None:
        raise ValueError("seed_base is not in the Cycle 7 ledger")
    if expected == CYCLE7_CONFIRMATION_RESERVED_ROLE or role == CYCLE7_CONFIRMATION_RESERVED_ROLE:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if role == CYCLE7_EXPLORATORY_ROLE and expected != CYCLE7_EXPLORATORY_ROLE:
        raise ValueError("seed_base is not a Cycle 7 exploratory development seed")
    if role == CYCLE7_VALIDATION_ROLE and expected != CYCLE7_VALIDATION_ROLE:
        raise ValueError("seed_base is not the Cycle 7 validation development seed")
    if role == CYCLE7_RULE_CONSTRUCTION_ROLE:
        if seed_base not in CYCLE7_ACTIVE_EXPLORATORY_SEED_BASES:
            raise ValueError("seed_base is not an active Cycle 7 rule-construction exploratory seed")


def assert_rule_construction_seed(seed_base: int) -> None:
    assert_development_seed(seed_base, role=CYCLE7_RULE_CONSTRUCTION_ROLE)


def assert_seed_not_spent(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    if seed_base in _ALL_BLOCKED:
        raise ValueError("seed_base is spent or otherwise blocked for Cycle 7")


def ledger_roles() -> Mapping[str, Sequence[int]]:
    return {
        CYCLE7_EXPLORATORY_ROLE: CYCLE7_EXPLORATORY_SEED_BASES,
        CYCLE7_VALIDATION_ROLE: CYCLE7_VALIDATION_SEED_BASES,
        CYCLE7_CONFIRMATION_RESERVED_ROLE: CYCLE7_CONFIRMATION_RESERVED_SEED_BASES,
    }
