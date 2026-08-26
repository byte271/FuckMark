from __future__ import annotations

from collections.abc import Mapping, Sequence

from .._validation import require_int
from ..hashing import sha256_json
from ..seeds.ledger import (
    CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
    CYCLE8_DENSITY_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
    CYCLE8_SCALE_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_REPLICATION_SEED_BASE,
    CYCLE8_SCALE_REPLICATION_TOPIC,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    CYCLE8_SCALE_VALIDATION_TOPIC,
)


CYCLE8_LEDGER_VERSION = "cycle8-seed-ledger-v2"
CYCLE8_HISTORICAL_LEDGER_VERSION = "cycle8-seed-ledger-v1"
CYCLE8_EXPLORATORY_ROLE = "exploratory_development"
CYCLE8_REPLICATION_ROLE = "exploratory_replication"
CYCLE8_VALIDATION_ROLE = "validation_development"
CYCLE8_SCALE_EXPLORATORY_ROLE = "scale_exploratory_development"
CYCLE8_SCALE_REPLICATION_ROLE = "scale_replication"
CYCLE8_SCALE_VALIDATION_ROLE = "scale_validation"
CYCLE8_DENSITY_EXPLORATORY_ROLE = "density_exploratory_development"
CYCLE8_CONFIRMATION_RESERVED_ROLE = "confirmation_reserved"

CYCLE8_EXPLORATORY_SEED_BASE = 890_000
CYCLE8_REPLICATION_SEED_BASE = 900_000
CYCLE8_VALIDATION_SEED_BASE = 910_000
CYCLE8_SECONDARY_EXPLORATORY_SEED_BASE = 920_000
CYCLE8_EXPLORATORY_SEED_BASES = (890_000, 920_000)
CYCLE8_REPLICATION_SEED_BASES = (900_000,)
CYCLE8_VALIDATION_SEED_BASES = (910_000,)
CYCLE8_SCALE_EXPLORATORY_SEED_BASES = (CYCLE8_SCALE_EXPLORATORY_SEED_BASE,)
CYCLE8_SCALE_REPLICATION_SEED_BASES = (CYCLE8_SCALE_REPLICATION_SEED_BASE,)
CYCLE8_SCALE_VALIDATION_SEED_BASES = (CYCLE8_SCALE_VALIDATION_SEED_BASE,)
CYCLE8_DENSITY_EXPLORATORY_SEED_BASES = (CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,)
CYCLE8_CONFIRMATION_RESERVED_SEED_BASES = (830_000, 840_000, 850_000)
CYCLE8_EXPLORATORY_TOPIC = "invisible carrier development"
CYCLE8_REPLICATION_TOPIC = "invisible carrier replication"
CYCLE8_VALIDATION_TOPIC = "invisible carrier validation"
CYCLE8_TINY_SCORED_SEED_BASES = (890_000, 900_000, 910_000)
CYCLE8_SCALE_PAIR_COUNT = 16

INHERITED_SPENT_SEED_BASES = (
    760_000,
    770_000,
    780_000,
    720_000,
    730_000,
    401_000,
    402_000,
    500_000,
    61000,
    1_120_000,
    1_130_000,
    1_140_000,
    1_150_000,
    1_160_000,
    810_000,
    820_000,
    860_000,
    870_000,
)
CYCLE7_PUBLICLY_EXPOSED_VALIDATION_SEED_BASE = 880_000

_ALL_BLOCKED = frozenset((*INHERITED_SPENT_SEED_BASES, CYCLE7_PUBLICLY_EXPOSED_VALIDATION_SEED_BASE))


def cycle8_seed_ledger_payload() -> dict[str, object]:
    return {
        "algorithm_version": CYCLE8_LEDGER_VERSION,
        "generation": "cycle8_exact_visible_projection",
        "historical_ledger_version": CYCLE8_HISTORICAL_LEDGER_VERSION,
        "inherited_spent_seed_bases": list(INHERITED_SPENT_SEED_BASES),
        "cycle7_publicly_exposed_validation_seed_base": CYCLE7_PUBLICLY_EXPOSED_VALIDATION_SEED_BASE,
        "tiny_scored_seed_bases": list(CYCLE8_TINY_SCORED_SEED_BASES),
        "exploratory_development_seed_base": CYCLE8_EXPLORATORY_SEED_BASE,
        "exploratory_development_seed_bases": list(CYCLE8_EXPLORATORY_SEED_BASES),
        "exploratory_topic": CYCLE8_EXPLORATORY_TOPIC,
        "exploratory_replication_seed_base": CYCLE8_REPLICATION_SEED_BASE,
        "exploratory_replication_topic": CYCLE8_REPLICATION_TOPIC,
        "validation_development_seed_base": CYCLE8_VALIDATION_SEED_BASE,
        "validation_topic": CYCLE8_VALIDATION_TOPIC,
        "secondary_exploratory_seed_base": CYCLE8_SECONDARY_EXPLORATORY_SEED_BASE,
        "scale_exploratory_seed_base": CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
        "scale_exploratory_topic": CYCLE8_SCALE_EXPLORATORY_TOPIC,
        "scale_replication_seed_base": CYCLE8_SCALE_REPLICATION_SEED_BASE,
        "scale_replication_topic": CYCLE8_SCALE_REPLICATION_TOPIC,
        "scale_validation_seed_base": CYCLE8_SCALE_VALIDATION_SEED_BASE,
        "scale_validation_topic": CYCLE8_SCALE_VALIDATION_TOPIC,
        "density_exploratory_seed_base": CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
        "density_exploratory_topic": CYCLE8_DENSITY_EXPLORATORY_TOPIC,
        "scale_pair_count": CYCLE8_SCALE_PAIR_COUNT,
        "confirmation_reserved_seed_bases": list(CYCLE8_CONFIRMATION_RESERVED_SEED_BASES),
        "selection_rule": (
            "Cycle 8 seeds 890000, 900000, 910000, and 920000 were assigned before "
            "any Cycle 8 text generation or detector look. Scale seeds 930000, "
            "940000, and 950000 and topics 'carrier scaling', 'independent scale "
            "replication', and 'clean scale validation' were reserved in "
            "global-seed-ledger-v1 before any scale generation. Seed 880000 is "
            "PUBLICLY_EXPOSED by PR #98 and is not eligible as unseen validation. "
            "Do not inspect 830000, 840000, or 850000. Do not generate 950000 until "
            "the U+034F x1 mechanism is frozen. Density seed 960000 and topic "
            "'carrier density follow-up' were reserved in global-seed-ledger-v1 "
            "before density generation. Do not retune on Cycle 6 formal residuals."
        ),
    }


def cycle8_seed_ledger_hash() -> str:
    return sha256_json(cycle8_seed_ledger_payload())


def role_for_seed_base(seed_base: int) -> str | None:
    require_int("seed_base", seed_base)
    if seed_base in CYCLE8_EXPLORATORY_SEED_BASES:
        return CYCLE8_EXPLORATORY_ROLE
    if seed_base in CYCLE8_REPLICATION_SEED_BASES:
        return CYCLE8_REPLICATION_ROLE
    if seed_base in CYCLE8_VALIDATION_SEED_BASES:
        return CYCLE8_VALIDATION_ROLE
    if seed_base in CYCLE8_SCALE_EXPLORATORY_SEED_BASES:
        return CYCLE8_SCALE_EXPLORATORY_ROLE
    if seed_base in CYCLE8_SCALE_REPLICATION_SEED_BASES:
        return CYCLE8_SCALE_REPLICATION_ROLE
    if seed_base in CYCLE8_SCALE_VALIDATION_SEED_BASES:
        return CYCLE8_SCALE_VALIDATION_ROLE
    if seed_base in CYCLE8_DENSITY_EXPLORATORY_SEED_BASES:
        return CYCLE8_DENSITY_EXPLORATORY_ROLE
    if seed_base in CYCLE8_CONFIRMATION_RESERVED_SEED_BASES:
        return CYCLE8_CONFIRMATION_RESERVED_ROLE
    return None


def assert_cycle8_development_seed(seed_base: int, *, role: str) -> None:
    require_int("seed_base", seed_base)
    if not isinstance(role, str) or not role:
        raise ValueError("role must be a non-empty string")
    if seed_base in _ALL_BLOCKED:
        raise ValueError("seed_base is spent or reserved outside Cycle 8 development")
    if seed_base in CYCLE8_CONFIRMATION_RESERVED_SEED_BASES:
        raise ValueError("confirmation-reserved seeds must not be used for Cycle 8 development")
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    expected = role_for_seed_base(seed_base)
    if expected is None:
        raise ValueError("seed_base is not in the Cycle 8 ledger")
    if role != expected:
        raise ValueError("seed_base role does not match the Cycle 8 ledger")


def ledger_roles() -> Mapping[str, Sequence[int]]:
    return {
        CYCLE8_EXPLORATORY_ROLE: CYCLE8_EXPLORATORY_SEED_BASES,
        CYCLE8_REPLICATION_ROLE: CYCLE8_REPLICATION_SEED_BASES,
        CYCLE8_VALIDATION_ROLE: CYCLE8_VALIDATION_SEED_BASES,
        CYCLE8_SCALE_EXPLORATORY_ROLE: CYCLE8_SCALE_EXPLORATORY_SEED_BASES,
        CYCLE8_SCALE_REPLICATION_ROLE: CYCLE8_SCALE_REPLICATION_SEED_BASES,
        CYCLE8_SCALE_VALIDATION_ROLE: CYCLE8_SCALE_VALIDATION_SEED_BASES,
        CYCLE8_DENSITY_EXPLORATORY_ROLE: CYCLE8_DENSITY_EXPLORATORY_SEED_BASES,
        CYCLE8_CONFIRMATION_RESERVED_ROLE: CYCLE8_CONFIRMATION_RESERVED_SEED_BASES,
    }
