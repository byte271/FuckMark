from __future__ import annotations

from collections.abc import Mapping, Sequence

from .._validation import require_int
from ..hashing import sha256_json


GLOBAL_SEED_LEDGER_VERSION = "global-seed-ledger-v1"
GLOBAL_SEED_LEDGER_PATH = "specs/fuckmark-global-seed-ledger-v1.json"

CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES = (830_000, 840_000, 850_000)
PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES = (880_000,)
CYCLE8_SCALE_EXPLORATORY_SEED_BASE = 930_000
CYCLE8_SCALE_REPLICATION_SEED_BASE = 940_000
CYCLE8_SCALE_VALIDATION_SEED_BASE = 950_000
CYCLE8_DENSITY_EXPLORATORY_SEED_BASE = 960_000
CYCLE8_SCALE_EXPLORATORY_TOPIC = "carrier scaling"
CYCLE8_SCALE_REPLICATION_TOPIC = "independent scale replication"
CYCLE8_SCALE_VALIDATION_TOPIC = "clean scale validation"
CYCLE8_DENSITY_EXPLORATORY_TOPIC = "carrier density follow-up"


def _row(
    seed_base: int,
    cycle: str,
    role: str,
    topic: str,
    first_reservation: str,
    *,
    generated: bool,
    scored: bool,
    publicly_exposed: bool,
    spent: bool,
    eligible_for_confirmation: bool,
    eligible_as_unseen_validation: bool,
    notes: str,
) -> dict[str, object]:
    require_int("seed_base", seed_base)
    return {
        "seed_base": seed_base,
        "cycle": cycle,
        "role": role,
        "generation_topic": topic,
        "first_reservation": first_reservation,
        "generated": generated,
        "scored": scored,
        "publicly_exposed": publicly_exposed,
        "spent": spent,
        "eligible_for_confirmation": eligible_for_confirmation,
        "eligible_as_unseen_validation": eligible_as_unseen_validation,
        "notes": notes,
    }


def global_seed_rows() -> tuple[dict[str, object], ...]:
    rows = (
        _row(61000, "tiny_dev", "schedule", "historic schedule", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Historic TinyDev schedule base."),
        _row(401000, "tiny_dev", "attack_development", "historic tiny-dev", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Historic TinyDev canonical attack base."),
        _row(402000, "tiny_dev", "historic", "historic tiny-dev", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Historic TinyDev base."),
        _row(410000, "tiny_dev", "attack_development", "tiny-dev-v3", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Budget-scaled coverage tiny-dev-v3 base."),
        _row(420000, "tiny_dev", "historic", "coverage", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Coverage-effectiveness seed."),
        _row(430000, "tiny_dev", "historic", "coverage", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Coverage-completion seed."),
        _row(440000, "tiny_dev", "historic", "coverage", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Coverage-completion seed."),
        _row(500000, "calibration", "threshold_calibration", "historic calibration", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Historic calibration base."),
        _row(530000, "cycle4", "confirmation", "exact survival", "cycle4", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 4 confirmation corpus. Spent."),
        _row(540000, "cycle4", "confirmation", "exact survival", "cycle4", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 4 confirmation corpus. Spent."),
        _row(550000, "cycle4", "confirmation", "exact survival", "cycle4", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 4 confirmation corpus. Spent."),
        _row(720000, "cycle6", "development", "cycle6 development", "cycle6", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 6 development 0/16. Spent."),
        _row(730000, "cycle6", "development", "cycle6 development", "cycle6", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 6 development. Spent."),
        _row(760000, "cycle6", "confirmation", "cycle6 formal", "cycle6", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 6 formal confirmation 2/64. Spent. Do not retune on residuals."),
        _row(770000, "cycle6", "confirmation", "cycle6 formal", "cycle6", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 6 formal confirmation 2/64. Spent. Do not retune on residuals."),
        _row(780000, "cycle6", "confirmation", "cycle6 formal", "cycle6", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 6 formal confirmation 3/64. Spent. Do not retune on residuals."),
        _row(810000, "cycle7", "exploratory_development", "reproducibility", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage A. Do not keep expanding rules against it."),
        _row(820000, "cycle7", "validation_development", "held-out evaluation", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage B3 validation. Spent. Do not retune."),
        _row(830000, "shared", "confirmation_reserved", "", "cycle7-seed-ledger-v3", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=False, notes="Formal confirmation reserve. Do not generate, tokenize, score, or inspect content."),
        _row(840000, "shared", "confirmation_reserved", "", "cycle7-seed-ledger-v3", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=False, notes="Formal confirmation reserve. Do not generate, tokenize, score, or inspect content."),
        _row(850000, "shared", "confirmation_reserved", "", "cycle7-seed-ledger-v3", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=False, notes="Formal confirmation reserve. Do not generate, tokenize, score, or inspect content."),
        _row(860000, "cycle7", "exploratory_development", "independent replication", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage B1. Do not keep expanding rules against it."),
        _row(870000, "cycle7", "exploratory_development", "measurement protocol", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage C1. Spent for new rule construction."),
        _row(880000, "cycle7", "validation_development", "independent check", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="PUBLICLY_EXPOSED by closed unmerged PR #98 Stage D validation artifacts. No longer eligible as unseen validation. Do not inspect residual rows for product tuning. Do not copy Stage D newline edits onto the product path."),
        _row(890000, "cycle8", "exploratory_development", "invisible carrier development", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 on main. Identifier was also used on unmerged PR #98 Cycle 7 Stage D. Do not treat as unseen validation."),
        _row(900000, "cycle8", "exploratory_replication", "invisible carrier replication", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 replication. Spent as unseen validation."),
        _row(910000, "cycle8", "validation_development", "invisible carrier validation", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 validation. Spent. Do not reuse as future clean validation."),
        _row(920000, "cycle8", "exploratory_development", "invisible carrier development", "cycle8-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 secondary exploratory. Unused. Not a confirmation reserve."),
        _row(930000, "cycle8", "scale_exploratory_development", CYCLE8_SCALE_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. U+034F x1 scale exploratory: 0/16, 0/32, then 1/64 raw transformed WM. Do not rewrite 1/64 as zero. Not confirmation."),
        _row(940000, "cycle8", "scale_replication", CYCLE8_SCALE_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F x1 n=64 replication: 0/64 raw transformed WM. Max score 0.557052 vs threshold 0.557099. Does not erase 930000 1/64. Not confirmation."),
        _row(950000, "cycle8", "scale_validation", CYCLE8_SCALE_VALIDATION_TOPIC, "global-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=True, notes="Reserved before generation. Clean unseen validation after mechanism freeze. Do not generate until U+034F x1 is frozen."),
        _row(960000, "cycle8", "density_exploratory_development", CYCLE8_DENSITY_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Detector-blind U+034F space plus word-final letter n=16: space-x1 1/16 and space-wordfinal 1/16 on the same residual row. Density did not beat space-x1. Do not rewrite 1/16 as zero. Do not inspect residual text to write lexical rules. Not confirmation."),
        _row(1120000, "effectiveness", "schedule", "effectiveness profile", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Frozen effectiveness-profile schedule base."),
        _row(1130000, "effectiveness", "schedule", "effectiveness profile", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Frozen effectiveness-profile schedule base."),
        _row(1140000, "effectiveness", "schedule", "effectiveness profile", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Frozen effectiveness-profile schedule base."),
        _row(1150000, "effectiveness", "schedule", "effectiveness profile", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Frozen effectiveness-profile schedule base."),
        _row(1160000, "effectiveness", "schedule", "effectiveness profile", "historic", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Frozen effectiveness-profile schedule base."),
    )
    bases = tuple(int(row["seed_base"]) for row in rows)
    if len(bases) != len(set(bases)):
        raise ValueError("global seed ledger contains duplicate seed bases")
    return rows


def global_seed_ledger_payload() -> dict[str, object]:
    rows = global_seed_rows()
    return {
        "algorithm_version": GLOBAL_SEED_LEDGER_VERSION,
        "selection_rule": (
            "Every new development, validation, or confirmation seed must be reserved "
            "in this ledger before generation. Seed 880000 is PUBLICLY_EXPOSED by PR #98 "
            "and is not eligible as unseen validation. Do not inspect 830000, 840000, or "
            "850000. Do not generate 950000 until the U+034F x1 mechanism is frozen. "
            "Seed 960000 is reserved for detector-blind density follow-up."
        ),
        "confirmation_content_forbidden_seed_bases": list(CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES),
        "publicly_exposed_unseen_invalid_seed_bases": list(PUBLICLY_EXPOSED_UNSEEN_INVALID_SEED_BASES),
        "cycle8_scale_exploratory_seed_base": CYCLE8_SCALE_EXPLORATORY_SEED_BASE,
        "cycle8_scale_exploratory_topic": CYCLE8_SCALE_EXPLORATORY_TOPIC,
        "cycle8_scale_replication_seed_base": CYCLE8_SCALE_REPLICATION_SEED_BASE,
        "cycle8_scale_replication_topic": CYCLE8_SCALE_REPLICATION_TOPIC,
        "cycle8_scale_validation_seed_base": CYCLE8_SCALE_VALIDATION_SEED_BASE,
        "cycle8_scale_validation_topic": CYCLE8_SCALE_VALIDATION_TOPIC,
        "cycle8_density_exploratory_seed_base": CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
        "cycle8_density_exploratory_topic": CYCLE8_DENSITY_EXPLORATORY_TOPIC,
        "rows": list(rows),
    }


def global_seed_ledger_hash() -> str:
    return sha256_json(global_seed_ledger_payload())


def row_for_seed_base(seed_base: int) -> dict[str, object]:
    require_int("seed_base", seed_base)
    for row in global_seed_rows():
        if int(row["seed_base"]) == seed_base:
            return row
    raise ValueError("seed_base is not in the global seed ledger")


def assert_seed_not_confirmation_content(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    if seed_base in CONFIRMATION_CONTENT_FORBIDDEN_SEED_BASES:
        raise ValueError("confirmation-reserved seed content must not be inspected")


def assert_new_cycle8_scale_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {CYCLE8_SCALE_EXPLORATORY_SEED_BASE, CYCLE8_SCALE_REPLICATION_SEED_BASE}:
        raise ValueError("seed_base is not a Cycle 8 scale generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True and seed_base != CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_density_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base != CYCLE8_DENSITY_EXPLORATORY_SEED_BASE:
        raise ValueError("seed_base is not a Cycle 8 density generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def known_seed_bases() -> Sequence[int]:
    return tuple(int(row["seed_base"]) for row in global_seed_rows())


def ledger_index() -> Mapping[int, dict[str, object]]:
    return {int(row["seed_base"]): row for row in global_seed_rows()}
