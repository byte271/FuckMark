from __future__ import annotations

from collections.abc import Mapping, Sequence

from .._validation import require_int
from ..hashing import sha256_json


CYCLE7_LEDGER_VERSION = "cycle7-seed-ledger-v1"
CYCLE7_EXPLORATORY_ROLE = "exploratory_development"
CYCLE7_VALIDATION_ROLE = "validation_development"
CYCLE7_CONFIRMATION_RESERVED_ROLE = "confirmation_reserved"

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
CYCLE7_VALIDATION_SEED_BASE = 820_000
CYCLE7_CONFIRMATION_RESERVED_SEED_BASES = (830_000, 840_000, 850_000)

_ALL_BLOCKED = frozenset(
    (
        *SPENT_CONFIRMATION_SEED_BASES,
        *SPENT_DEVELOPMENT_SEED_BASES,
        *BLOCKED_PROFILE_SEED_BASES,
        *BLOCKED_HISTORIC_SEED_BASES,
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
        "validation_development_seed_base": CYCLE7_VALIDATION_SEED_BASE,
        "confirmation_reserved_seed_bases": list(CYCLE7_CONFIRMATION_RESERVED_SEED_BASES),
        "selection_rule": (
            "Confirmation-reserved seeds were chosen as unused 10k blocks "
            "without inspecting detector outcomes. Do not promote exploratory "
            "or validation seeds into confirmation after seeing scores."
        ),
        "spent_corpus_rule": (
            "Do not use 720000, 730000, 760000, 770000, or 780000 as "
            "Cycle 7 development, tuning, or confirmation data."
        ),
    }


def cycle7_seed_ledger_hash() -> str:
    return sha256_json(cycle7_seed_ledger_payload())


def role_for_seed_base(seed_base: int) -> str | None:
    require_int("seed_base", seed_base)
    if seed_base == CYCLE7_EXPLORATORY_SEED_BASE:
        return CYCLE7_EXPLORATORY_ROLE
    if seed_base == CYCLE7_VALIDATION_SEED_BASE:
        return CYCLE7_VALIDATION_ROLE
    if seed_base in CYCLE7_CONFIRMATION_RESERVED_SEED_BASES:
        return CYCLE7_CONFIRMATION_RESERVED_ROLE
    return None


def assert_development_seed(seed_base: int, *, role: str) -> None:
    require_int("seed_base", seed_base)
    if not isinstance(role, str) or not role:
        raise ValueError("role must be a non-empty string")
    if seed_base in _ALL_BLOCKED:
        raise ValueError("seed_base is spent or otherwise blocked for Cycle 7 development")
    expected = role_for_seed_base(seed_base)
    if expected is None:
        raise ValueError("seed_base is not in the Cycle 7 ledger")
    if expected == CYCLE7_CONFIRMATION_RESERVED_ROLE or role == CYCLE7_CONFIRMATION_RESERVED_ROLE:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if role == CYCLE7_EXPLORATORY_ROLE and expected != CYCLE7_EXPLORATORY_ROLE:
        raise ValueError("seed_base is not the Cycle 7 exploratory development seed")
    if role == CYCLE7_VALIDATION_ROLE and expected != CYCLE7_VALIDATION_ROLE:
        raise ValueError("seed_base is not the Cycle 7 validation development seed")


def assert_seed_not_spent(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    if seed_base in _ALL_BLOCKED:
        raise ValueError("seed_base is spent or otherwise blocked for Cycle 7")


def ledger_roles() -> Mapping[str, Sequence[int]]:
    return {
        CYCLE7_EXPLORATORY_ROLE: (CYCLE7_EXPLORATORY_SEED_BASE,),
        CYCLE7_VALIDATION_ROLE: (CYCLE7_VALIDATION_SEED_BASE,),
        CYCLE7_CONFIRMATION_RESERVED_ROLE: CYCLE7_CONFIRMATION_RESERVED_SEED_BASES,
    }
