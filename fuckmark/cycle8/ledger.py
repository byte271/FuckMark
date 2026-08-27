from __future__ import annotations

from collections.abc import Mapping, Sequence

from .._validation import require_int
from ..hashing import sha256_json
from ..seeds.ledger import (
    CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
    CYCLE8_DENSITY_EXPLORATORY_TOPIC,
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
    CYCLE8_LETTER_EXPLORATORY_SEED_BASE,
    CYCLE8_LETTER_EXPLORATORY_TOPIC,
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
CYCLE8_LETTER_EXPLORATORY_ROLE = "letter_exploratory_development"
CYCLE8_LETTER_BENCHMARK_PRIMARY_ROLE = "letter_benchmark_primary"
CYCLE8_LETTER_BENCHMARK_REPLICATION_ROLE = "letter_benchmark_replication"
CYCLE8_MARGIN_PRIMARY_ROLE = "margin_robustness_primary"
CYCLE8_MARGIN_REPLICATION_ROLE = "margin_robustness_replication"
CYCLE8_MIX_PRIMARY_ROLE = "mix_margin_primary"
CYCLE8_MIX_REPLICATION_ROLE = "mix_margin_replication"
CYCLE8_MIX_SCALE_PRIMARY_ROLE = "mix_scale_primary"
CYCLE8_MIX_SCALE_REPLICATION_ROLE = "mix_scale_replication"
CYCLE8_DEEPMIND_TRANSFER_PRIMARY_ROLE = "deepmind_transfer_primary"
CYCLE8_DEEPMIND_TRANSFER_REPLICATION_ROLE = "deepmind_transfer_replication"
CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_ROLE = "deepmind_transfer_holdout"
CYCLE8_SECOND_MODEL_TRANSFER_ROLE = "second_model_transfer"
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
CYCLE8_LETTER_EXPLORATORY_SEED_BASES = (CYCLE8_LETTER_EXPLORATORY_SEED_BASE,)
CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASES = (CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE,)
CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASES = (CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE,)
CYCLE8_MARGIN_PRIMARY_SEED_BASES = (CYCLE8_MARGIN_PRIMARY_SEED_BASE,)
CYCLE8_MARGIN_REPLICATION_SEED_BASES = (CYCLE8_MARGIN_REPLICATION_SEED_BASE,)
CYCLE8_MIX_PRIMARY_SEED_BASES = (CYCLE8_MIX_PRIMARY_SEED_BASE,)
CYCLE8_MIX_REPLICATION_SEED_BASES = (CYCLE8_MIX_REPLICATION_SEED_BASE,)
CYCLE8_MIX_SCALE_PRIMARY_SEED_BASES = (CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE,)
CYCLE8_MIX_SCALE_REPLICATION_SEED_BASES = (CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE,)
CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASES = (CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,)
CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASES = (CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,)
CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASES = (CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,)
CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASES = (CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE,)
CYCLE8_CONFIRMATION_RESERVED_SEED_BASES = (830_000, 840_000, 850_000)
CYCLE8_EXPLORATORY_TOPIC = "invisible carrier development"
CYCLE8_REPLICATION_TOPIC = "invisible carrier replication"
CYCLE8_VALIDATION_TOPIC = "invisible carrier validation"
CYCLE8_TINY_SCORED_SEED_BASES = (890_000, 900_000, 910_000)
CYCLE8_SCALE_PAIR_COUNT = 16
CYCLE8_LETTER_BENCHMARK_PAIR_COUNT = 64

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
        "letter_exploratory_seed_base": CYCLE8_LETTER_EXPLORATORY_SEED_BASE,
        "letter_exploratory_topic": CYCLE8_LETTER_EXPLORATORY_TOPIC,
        "letter_benchmark_primary_seed_base": CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE,
        "letter_benchmark_primary_topic": CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC,
        "letter_benchmark_replication_seed_base": CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE,
        "letter_benchmark_replication_topic": CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC,
        "margin_primary_seed_base": CYCLE8_MARGIN_PRIMARY_SEED_BASE,
        "margin_primary_topic": CYCLE8_MARGIN_PRIMARY_TOPIC,
        "margin_replication_seed_base": CYCLE8_MARGIN_REPLICATION_SEED_BASE,
        "margin_replication_topic": CYCLE8_MARGIN_REPLICATION_TOPIC,
        "mix_primary_seed_base": CYCLE8_MIX_PRIMARY_SEED_BASE,
        "mix_primary_topic": CYCLE8_MIX_PRIMARY_TOPIC,
        "mix_replication_seed_base": CYCLE8_MIX_REPLICATION_SEED_BASE,
        "mix_replication_topic": CYCLE8_MIX_REPLICATION_TOPIC,
        "mix_scale_primary_seed_base": CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE,
        "mix_scale_primary_topic": CYCLE8_MIX_SCALE_PRIMARY_TOPIC,
        "mix_scale_replication_seed_base": CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE,
        "mix_scale_replication_topic": CYCLE8_MIX_SCALE_REPLICATION_TOPIC,
        "deepmind_transfer_primary_seed_base": CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,
        "deepmind_transfer_primary_topic": CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC,
        "deepmind_transfer_replication_seed_base": CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,
        "deepmind_transfer_replication_topic": CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC,
        "deepmind_transfer_holdout_seed_base": CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,
        "deepmind_transfer_holdout_topic": CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC,
        "second_model_transfer_seed_base": CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE,
        "second_model_transfer_topic": CYCLE8_SECOND_MODEL_TRANSFER_TOPIC,
        "scale_pair_count": CYCLE8_SCALE_PAIR_COUNT,
        "letter_benchmark_pair_count": CYCLE8_LETTER_BENCHMARK_PAIR_COUNT,
        "confirmation_reserved_seed_bases": list(CYCLE8_CONFIRMATION_RESERVED_SEED_BASES),
        "selection_rule": (
            "Cycle 8 seeds 890000, 900000, 910000, and 920000 were assigned before "
            "any Cycle 8 text generation or detector look. Scale seeds 930000, "
            "940000, and 950000 and topics 'carrier scaling', 'independent scale "
            "replication', and 'clean scale validation' were reserved in "
            "global-seed-ledger-v1 before any scale generation. Seed 880000 is "
            "PUBLICLY_EXPOSED by PR #98 and is not eligible as unseen validation. "
            "Seeds 830000, 840000, and 850000 were generated once as "
            "cycle8-mix-freeze-v1 confirmation and are spent. Do not inspect residual "
            "text to write rules. Do not generate 950000 until "
            "the U+034F x1 mechanism is frozen. Density seed 960000 and topic "
            "'carrier density follow-up' were reserved in global-seed-ledger-v1 "
            "before density generation. Letter seed 970000 and topic "
            "'intra-word carrier follow-up' were reserved in global-seed-ledger-v1 "
            "before letter generation. Benchmark seeds 980000 and 990000 and topics "
            "'letter carrier system benchmark' and 'letter carrier benchmark "
            "replication' were reserved in global-seed-ledger-v1 before benchmark "
            "generation. Margin seeds 1000000 and 1010000 and topics 'margin "
            "robustness development' and 'margin robustness replication' were "
            "reserved in global-seed-ledger-v1 before margin generation. Mix seeds "
            "1020000 and 1030000 and topics 'letter mix margin development' and "
            "'letter mix margin replication' were reserved in global-seed-ledger-v1 "
            "before mix generation. Mix scale seeds 1040000 and 1050000 and topics "
            "'letter mix scale development' and 'letter mix scale replication' were "
            "reserved in global-seed-ledger-v1 before mix scale generation. "
            "DeepMind mix transfer seeds 1060000, 1070000, and 1080000 and topics "
            "'deepmind mix transfer primary', 'deepmind mix transfer replication', "
            "and 'deepmind mix transfer holdout' were reserved in global-seed-ledger-v1 "
            "before DeepMind transfer generation. Second-model mix transfer seed "
            "1090000 and topic 'second model mix transfer' were reserved in "
            "global-seed-ledger-v1 before second-model transfer generation. "
            "cycle8-mix-freeze-v1 confirmation of 830000, 840000, and 850000 was "
            "generated once under the freeze; those bases are spent. Do not rerun "
            "looking for zero, and do not retune on Cycle 6 formal residuals."
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
    if seed_base in CYCLE8_LETTER_EXPLORATORY_SEED_BASES:
        return CYCLE8_LETTER_EXPLORATORY_ROLE
    if seed_base in CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASES:
        return CYCLE8_LETTER_BENCHMARK_PRIMARY_ROLE
    if seed_base in CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASES:
        return CYCLE8_LETTER_BENCHMARK_REPLICATION_ROLE
    if seed_base in CYCLE8_MARGIN_PRIMARY_SEED_BASES:
        return CYCLE8_MARGIN_PRIMARY_ROLE
    if seed_base in CYCLE8_MARGIN_REPLICATION_SEED_BASES:
        return CYCLE8_MARGIN_REPLICATION_ROLE
    if seed_base in CYCLE8_MIX_PRIMARY_SEED_BASES:
        return CYCLE8_MIX_PRIMARY_ROLE
    if seed_base in CYCLE8_MIX_REPLICATION_SEED_BASES:
        return CYCLE8_MIX_REPLICATION_ROLE
    if seed_base in CYCLE8_MIX_SCALE_PRIMARY_SEED_BASES:
        return CYCLE8_MIX_SCALE_PRIMARY_ROLE
    if seed_base in CYCLE8_MIX_SCALE_REPLICATION_SEED_BASES:
        return CYCLE8_MIX_SCALE_REPLICATION_ROLE
    if seed_base in CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASES:
        return CYCLE8_DEEPMIND_TRANSFER_PRIMARY_ROLE
    if seed_base in CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASES:
        return CYCLE8_DEEPMIND_TRANSFER_REPLICATION_ROLE
    if seed_base in CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASES:
        return CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_ROLE
    if seed_base in CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASES:
        return CYCLE8_SECOND_MODEL_TRANSFER_ROLE
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
        CYCLE8_LETTER_EXPLORATORY_ROLE: CYCLE8_LETTER_EXPLORATORY_SEED_BASES,
        CYCLE8_LETTER_BENCHMARK_PRIMARY_ROLE: CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASES,
        CYCLE8_LETTER_BENCHMARK_REPLICATION_ROLE: CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASES,
        CYCLE8_MARGIN_PRIMARY_ROLE: CYCLE8_MARGIN_PRIMARY_SEED_BASES,
        CYCLE8_MARGIN_REPLICATION_ROLE: CYCLE8_MARGIN_REPLICATION_SEED_BASES,
        CYCLE8_MIX_PRIMARY_ROLE: CYCLE8_MIX_PRIMARY_SEED_BASES,
        CYCLE8_MIX_REPLICATION_ROLE: CYCLE8_MIX_REPLICATION_SEED_BASES,
        CYCLE8_MIX_SCALE_PRIMARY_ROLE: CYCLE8_MIX_SCALE_PRIMARY_SEED_BASES,
        CYCLE8_MIX_SCALE_REPLICATION_ROLE: CYCLE8_MIX_SCALE_REPLICATION_SEED_BASES,
        CYCLE8_DEEPMIND_TRANSFER_PRIMARY_ROLE: CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASES,
        CYCLE8_DEEPMIND_TRANSFER_REPLICATION_ROLE: CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASES,
        CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_ROLE: CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASES,
        CYCLE8_SECOND_MODEL_TRANSFER_ROLE: CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASES,
        CYCLE8_CONFIRMATION_RESERVED_ROLE: CYCLE8_CONFIRMATION_RESERVED_SEED_BASES,
    }
