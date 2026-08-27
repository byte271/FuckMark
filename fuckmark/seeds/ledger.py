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
CYCLE8_LETTER_EXPLORATORY_SEED_BASE = 970_000
CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE = 980_000
CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE = 990_000
CYCLE8_MARGIN_PRIMARY_SEED_BASE = 1_000_000
CYCLE8_MARGIN_REPLICATION_SEED_BASE = 1_010_000
CYCLE8_MIX_PRIMARY_SEED_BASE = 1_020_000
CYCLE8_MIX_REPLICATION_SEED_BASE = 1_030_000
CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE = 1_040_000
CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE = 1_050_000
CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE = 1_060_000
CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE = 1_070_000
CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE = 1_080_000
CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE = 1_090_000
CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE = 1_100_000
CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE = 1_200_000
CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE = 1_210_000
CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE = 1_220_000
CYCLE8_SCALE_EXPLORATORY_TOPIC = "carrier scaling"
CYCLE8_SCALE_REPLICATION_TOPIC = "independent scale replication"
CYCLE8_SCALE_VALIDATION_TOPIC = "clean scale validation"
CYCLE8_DENSITY_EXPLORATORY_TOPIC = "carrier density follow-up"
CYCLE8_LETTER_EXPLORATORY_TOPIC = "intra-word carrier follow-up"
CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC = "letter carrier system benchmark"
CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC = "letter carrier benchmark replication"
CYCLE8_MARGIN_PRIMARY_TOPIC = "margin robustness development"
CYCLE8_MARGIN_REPLICATION_TOPIC = "margin robustness replication"
CYCLE8_MIX_PRIMARY_TOPIC = "letter mix margin development"
CYCLE8_MIX_REPLICATION_TOPIC = "letter mix margin replication"
CYCLE8_MIX_SCALE_PRIMARY_TOPIC = "letter mix scale development"
CYCLE8_MIX_SCALE_REPLICATION_TOPIC = "letter mix scale replication"
CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC = "deepmind mix transfer primary"
CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC = "deepmind mix transfer replication"
CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC = "deepmind mix transfer holdout"
CYCLE8_SECOND_MODEL_TRANSFER_TOPIC = "second model mix transfer"
CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC = "control mix sanitizer exploratory"
CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC = "mix formal confirmation primary"
CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC = "mix formal confirmation replication"
CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC = "mix formal confirmation holdout"
CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_TOPIC = "gate v2 confirmation primary"
CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_TOPIC = "gate v2 confirmation replication"
CYCLE8_GATE_V2_CONFIRMATION_HOLD_TOPIC = "gate v2 confirmation holdout"
CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_TOPIC = CYCLE8_GATE_V2_CONFIRMATION_HOLD_TOPIC


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
        _row(830000, "shared", "confirmation_reserved", CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC, "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="cycle8-mix-freeze-v1 one-shot confirmation n=64: mix 0/64 raw WM, mix UW 0/64, visible 128/128, mix max 0.51960. Combined 0/192. Spent. Do not retune on residuals. Do not rerun looking for zero."),
        _row(840000, "shared", "confirmation_reserved", CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC, "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="cycle8-mix-freeze-v1 one-shot confirmation n=64: mix 0/64 raw WM, mix UW 0/64, visible 128/128, mix max 0.52430. Combined 0/192. Spent. Do not retune on residuals. Do not rerun looking for zero."),
        _row(850000, "shared", "confirmation_reserved", CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC, "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="cycle8-mix-freeze-v1 one-shot confirmation n=64: mix 0/64 raw WM, mix UW 0/64, visible 128/128, mix max 0.51695. Combined 0/192. Spent. Do not retune on residuals. Do not rerun looking for zero."),
        _row(860000, "cycle7", "exploratory_development", "independent replication", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage B1. Do not keep expanding rules against it."),
        _row(870000, "cycle7", "exploratory_development", "measurement protocol", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 7 Stage C1. Spent for new rule construction."),
        _row(880000, "cycle7", "validation_development", "independent check", "cycle7-seed-ledger-v3", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="PUBLICLY_EXPOSED by closed unmerged PR #98 Stage D validation artifacts. No longer eligible as unseen validation. Do not inspect residual rows for product tuning. Do not copy Stage D newline edits onto the product path."),
        _row(890000, "cycle8", "exploratory_development", "invisible carrier development", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 on main. Identifier was also used on unmerged PR #98 Cycle 7 Stage D. Do not treat as unseen validation."),
        _row(900000, "cycle8", "exploratory_replication", "invisible carrier replication", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 replication. Spent as unseen validation."),
        _row(910000, "cycle8", "validation_development", "invisible carrier validation", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=True, spent=True, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 tiny n=4 validation. Spent. Do not reuse as future clean validation."),
        _row(920000, "cycle8", "exploratory_development", "invisible carrier development", "cycle8-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Cycle 8 secondary exploratory. DeepMind synthid-text 30-key GPT-2 mix transfer n=16 HYPOTHESIS: identity WM 16/16, mix WM 0/16, mix UW 0/16, visible pass. Not confirmation. Not a second model."),
        _row(930000, "cycle8", "scale_exploratory_development", CYCLE8_SCALE_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. U+034F space x1 scale exploratory: 0/16, 0/32, then 1/64 raw transformed WM. Letter-x1 diagnostic rescore of this seen corpus is 0/64. Do not rewrite space 1/64 as zero. Not confirmation."),
        _row(940000, "cycle8", "scale_replication", CYCLE8_SCALE_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F space x1 n=64 replication: 0/64 raw transformed WM. Max score 0.557052 vs threshold 0.557099. Letter-x1 diagnostic rescore of this seen corpus is 0/64. Does not erase space-x1 930000 1/64. Not confirmation."),
        _row(950000, "cycle8", "scale_validation", CYCLE8_SCALE_VALIDATION_TOPIC, "global-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=True, notes="Reserved before generation. Clean unseen validation after mechanism freeze. Do not generate until U+034F x1 is frozen."),
        _row(960000, "cycle8", "density_exploratory_development", CYCLE8_DENSITY_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Detector-blind U+034F space plus word-final letter n=16: space-x1 1/16 and space-wordfinal 1/16 on the same residual row. Density did not beat space-x1. Letter-x1 diagnostic rescore of this seen corpus is 0/16. Do not rewrite space 1/16 as zero. Do not inspect residual text to write lexical rules. Not confirmation."),
        _row(970000, "cycle8", "letter_exploratory_development", CYCLE8_LETTER_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F letter-x1: n=16 0/16 then n=64 0/64 raw transformed WM, 0 UW, visible 128/128. Experimental letter-x1 0/192 = seen diagnostic 930000 n=64 0/64 plus 940000 n=64 0/64 plus independent 970000 n=64 0/64 (128/192 seen, 64/192 independent). Do not rewrite space-x1 1/64 or 1/16 as zero. Do not generate 950000. Not confirmation."),
        _row(980000, "cycle8", "letter_benchmark_primary", CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Letter-x1 system benchmark primary n=64: letter-x1 0/64 raw WM, space-x1 0/64, identity 62/64, visible 128/128. Letter max score 0.55407 vs threshold 0.55710. Not confirmation. Do not generate 950000."),
        _row(990000, "cycle8", "letter_benchmark_replication", CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Letter-x1 system benchmark independent replication n=64: letter-x1 0/64 raw WM, space-x1 1/64, identity 64/64, visible 128/128. Letter max score 0.52727. Combined with 980000: letter 0/128, space 1/128. Residual text not inspected. Not confirmation. Do not generate 950000."),
        _row(1000000, "cycle8", "margin_robustness_primary", CYCLE8_MARGIN_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Letter-space n=64: letter-x1 0/64, letter-space 0/64, identity 63/64, visible 128/128. Letter-space max 0.52477. Not confirmation. Spent as unseen for letter-space. Do not generate 950000."),
        _row(1010000, "cycle8", "margin_robustness_replication", CYCLE8_MARGIN_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent letter-space n=64: letter-x1 1/64, letter-space 1/64 on the same residual row, identity 64/64, UW letter-space 0/64. Combined letter-space 1/128. Residual text not inspected. Not confirmation. Do not generate 950000."),
        _row(1020000, "cycle8", "mix_margin_primary", CYCLE8_MIX_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. U+034F/U+FE00 letter-alt n=64: mix 0/64 raw WM, letter-x1 0/64, identity 64/64, visible 128/128. Mix max 0.51369 versus threshold 0.55710 (gap 0.04341). Not confirmation. Do not generate 950000."),
        _row(1030000, "cycle8", "mix_margin_replication", CYCLE8_MIX_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F/U+FE00 letter-alt n=64: mix 0/64 raw WM, letter-x1 0/64, identity 64/64, mix UW 0/64. Mix max 0.51307. Combined with 1020000: mix 0/128, worst max 0.51369, gap 0.04341. Not confirmation. Do not generate 950000."),
        _row(1040000, "cycle8", "mix_scale_primary", CYCLE8_MIX_SCALE_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F/U+FE00 letter-alt n=64: mix 0/64 raw WM, letter-x1 0/64, identity 62/64, visible 128/128. Mix max 0.51952 versus threshold 0.55710 (gap 0.03758). Closest row had 31 insertions. Not confirmation. Do not generate 950000."),
        _row(1050000, "cycle8", "mix_scale_replication", CYCLE8_MIX_SCALE_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent U+034F/U+FE00 letter-alt n=64: mix 0/64 raw WM, letter-x1 0/64, identity 60/64, mix UW 0/64. Mix max 0.51051. Combined with 1020000+1030000+1040000: mix 0/256, worst max 0.51952, gap 0.03758. Not confirmation. Do not generate 950000."),
        _row(1060000, "cycle8", "deepmind_transfer_primary", CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent DeepMind synthid-text 30-key GPT-2 mix transfer n=64: identity WM 63/64, mix WM 0/64, mix UW 0/64, visible pass, mix max 0.505630. Combined with 1070000+1080000: mix 0/192. Not mix-freeze confirmation. Do not generate 950000."),
        _row(1070000, "cycle8", "deepmind_transfer_replication", CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent DeepMind synthid-text 30-key GPT-2 mix transfer n=64: identity WM 63/64, mix WM 0/64, mix UW 0/64, visible pass, mix max 0.502999. Combined with 1060000+1080000: mix 0/192. Not mix-freeze confirmation. Do not generate 950000."),
        _row(1080000, "cycle8", "deepmind_transfer_holdout", CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent DeepMind synthid-text 30-key GPT-2 mix transfer n=64: identity WM 63/64, mix WM 0/64, mix UW 0/64, visible pass, mix max 0.506760. Combined with 1060000+1070000: mix 0/192. Not mix-freeze confirmation. Do not generate 950000."),
        _row(1090000, "cycle8", "second_model_transfer", CYCLE8_SECOND_MODEL_TRANSFER_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent DistilGPT2 DeepMind 30-key mix transfer n=16 HYPOTHESIS: identity WM 16/16, mix WM 0/16, mix UW 0/16, visible pass, mix max 0.504800. Different weights from openai-community/gpt2, same GPT-2 BPE tokenizer (vocab 50257). Not mix-freeze confirmation. Not confirmation-scale. Do not generate 950000."),
        _row(1100000, "cycle8", "control_mix_exploratory_development", CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC, "global-seed-ledger-v1", generated=True, scored=True, publicly_exposed=False, spent=False, eligible_for_confirmation=False, eligible_as_unseen_validation=False, notes="Reserved before generation. Independent DeepMind 30-key GPT-2 control-mix exploratory n=16: identity WM 15/16, control-mix WM 0/16, UW 0/16, visible pass, required sanitizers keep, control-mix max 0.505851. Seen diagnostic on 920000 is not this corpus. Not confirmation. Do not generate 950000."),
        _row(1200000, "cycle8", "gate_v2_confirmation", CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_TOPIC, "global-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=True, notes="Reserved before generation. Gate v2 confirmation primary n=64. Detector-after-sanitizer protocol including lm-watermarking UnicodeSanitizer and carrier-free control. Do not inspect 830000/840000/850000. Do not generate 950000. Do not retune after looking at detector scores."),
        _row(1210000, "cycle8", "gate_v2_confirmation", CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_TOPIC, "global-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=True, notes="Reserved before generation. Gate v2 confirmation replication n=64. Independent of 1200000. Do not inspect 830000/840000/850000. Do not generate 950000. Do not retune after looking at detector scores."),
        _row(1220000, "cycle8", "gate_v2_confirmation", CYCLE8_GATE_V2_CONFIRMATION_HOLD_TOPIC, "global-seed-ledger-v1", generated=False, scored=False, publicly_exposed=False, spent=False, eligible_for_confirmation=True, eligible_as_unseen_validation=True, notes="Reserved before generation. Gate v2 confirmation holdout n=64. Independent of 1200000 and 1210000. Do not inspect 830000/840000/850000. Do not generate 950000. Do not retune after looking at detector scores."),
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
            "and is not eligible as unseen validation. Seeds 830000, 840000, and 850000 "
            "were generated once under cycle8-mix-freeze-v1 and are spent. Do not rerun "
            "looking for zero. Do not generate 950000. "
            "Seed 960000 is reserved for detector-blind density follow-up. "
            "Seed 970000 is reserved for detector-blind intra-word letter-carrier follow-up. "
            "Seeds 980000 and 990000 are reserved for the letter-x1 system benchmark. "
            "Seeds 1000000 and 1010000 are reserved for detector-blind letter-plus-space "
            "margin robustness follow-up. "
            "Seeds 1020000 and 1030000 are reserved for detector-blind U+034F/U+FE00 "
            "letter-mix margin follow-up. "
            "Seeds 1040000 and 1050000 are reserved for detector-blind letter-mix "
            "scale follow-up. "
            "Seeds 1060000, 1070000, and 1080000 are reserved for independent "
            "DeepMind synthid-text 30-key mix transfer. "
            "Seed 1090000 is reserved for independent second-model mix transfer. "
            "Seed 1100000 is reserved for independent control-mix sanitizer exploratory. "
            "Seeds 1200000, 1210000, and 1220000 are reserved for Gate v2 confirmation "
            "before generation. Do not reuse 830000, 840000, or 850000. Do not generate 950000."
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
        "cycle8_letter_exploratory_seed_base": CYCLE8_LETTER_EXPLORATORY_SEED_BASE,
        "cycle8_letter_exploratory_topic": CYCLE8_LETTER_EXPLORATORY_TOPIC,
        "cycle8_letter_benchmark_primary_seed_base": CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE,
        "cycle8_letter_benchmark_primary_topic": CYCLE8_LETTER_BENCHMARK_PRIMARY_TOPIC,
        "cycle8_letter_benchmark_replication_seed_base": CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE,
        "cycle8_letter_benchmark_replication_topic": CYCLE8_LETTER_BENCHMARK_REPLICATION_TOPIC,
        "cycle8_margin_primary_seed_base": CYCLE8_MARGIN_PRIMARY_SEED_BASE,
        "cycle8_margin_primary_topic": CYCLE8_MARGIN_PRIMARY_TOPIC,
        "cycle8_margin_replication_seed_base": CYCLE8_MARGIN_REPLICATION_SEED_BASE,
        "cycle8_margin_replication_topic": CYCLE8_MARGIN_REPLICATION_TOPIC,
        "cycle8_mix_primary_seed_base": CYCLE8_MIX_PRIMARY_SEED_BASE,
        "cycle8_mix_primary_topic": CYCLE8_MIX_PRIMARY_TOPIC,
        "cycle8_mix_replication_seed_base": CYCLE8_MIX_REPLICATION_SEED_BASE,
        "cycle8_mix_replication_topic": CYCLE8_MIX_REPLICATION_TOPIC,
        "cycle8_mix_scale_primary_seed_base": CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE,
        "cycle8_mix_scale_primary_topic": CYCLE8_MIX_SCALE_PRIMARY_TOPIC,
        "cycle8_mix_scale_replication_seed_base": CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE,
        "cycle8_mix_scale_replication_topic": CYCLE8_MIX_SCALE_REPLICATION_TOPIC,
        "cycle8_deepmind_transfer_primary_seed_base": CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,
        "cycle8_deepmind_transfer_primary_topic": CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC,
        "cycle8_deepmind_transfer_replication_seed_base": CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,
        "cycle8_deepmind_transfer_replication_topic": CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC,
        "cycle8_deepmind_transfer_holdout_seed_base": CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,
        "cycle8_deepmind_transfer_holdout_topic": CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC,
        "cycle8_second_model_transfer_seed_base": CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE,
        "cycle8_second_model_transfer_topic": CYCLE8_SECOND_MODEL_TRANSFER_TOPIC,
        "cycle8_control_mix_exploratory_seed_base": CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE,
        "cycle8_control_mix_exploratory_topic": CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC,
        "cycle8_gate_v2_confirmation_primary_seed_base": CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
        "cycle8_gate_v2_confirmation_primary_topic": CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_TOPIC,
        "cycle8_gate_v2_confirmation_replication_seed_base": CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
        "cycle8_gate_v2_confirmation_replication_topic": CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_TOPIC,
        "cycle8_gate_v2_confirmation_holdout_seed_base": CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
        "cycle8_gate_v2_confirmation_holdout_topic": CYCLE8_GATE_V2_CONFIRMATION_HOLD_TOPIC,
        "cycle8_mix_confirmation_primary_topic": CYCLE8_MIX_CONFIRMATION_PRIMARY_TOPIC,
        "cycle8_mix_confirmation_replication_topic": CYCLE8_MIX_CONFIRMATION_REPLICATION_TOPIC,
        "cycle8_mix_confirmation_hold_topic": CYCLE8_MIX_CONFIRMATION_HOLD_TOPIC,
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


def assert_new_cycle8_letter_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base != CYCLE8_LETTER_EXPLORATORY_SEED_BASE:
        raise ValueError("seed_base is not a Cycle 8 letter generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_letter_benchmark_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {CYCLE8_LETTER_BENCHMARK_PRIMARY_SEED_BASE, CYCLE8_LETTER_BENCHMARK_REPLICATION_SEED_BASE}:
        raise ValueError("seed_base is not a Cycle 8 letter benchmark generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_margin_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {CYCLE8_MARGIN_PRIMARY_SEED_BASE, CYCLE8_MARGIN_REPLICATION_SEED_BASE}:
        raise ValueError("seed_base is not a Cycle 8 margin robustness generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_mix_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {
        CYCLE8_MIX_PRIMARY_SEED_BASE,
        CYCLE8_MIX_REPLICATION_SEED_BASE,
        CYCLE8_MIX_SCALE_PRIMARY_SEED_BASE,
        CYCLE8_MIX_SCALE_REPLICATION_SEED_BASE,
    }:
        raise ValueError("seed_base is not a Cycle 8 letter-mix generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_deepmind_transfer_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {
        CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,
        CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,
        CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,
    }:
        raise ValueError("seed_base is not a Cycle 8 DeepMind mix transfer generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_second_model_transfer_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base != CYCLE8_SECOND_MODEL_TRANSFER_SEED_BASE:
        raise ValueError("seed_base is not a Cycle 8 second-model mix transfer generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def assert_new_cycle8_gate_v2_confirmation_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base not in {
        CYCLE8_GATE_V2_CONFIRMATION_PRIMARY_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_REPLICATION_SEED_BASE,
        CYCLE8_GATE_V2_CONFIRMATION_HOLDOUT_SEED_BASE,
    }:
        raise ValueError("seed_base is not a Cycle 8 Gate v2 confirmation seed")
    if row["eligible_for_confirmation"] is not True:
        raise ValueError("Gate v2 confirmation seed is not eligible for confirmation")
    if row["generated"] is True:
        raise ValueError("Gate v2 confirmation seed already generated")
    if row["scored"] is True:
        raise ValueError("Gate v2 confirmation seed already scored")


def assert_new_cycle8_control_mix_generation_seed(seed_base: int) -> None:
    require_int("seed_base", seed_base)
    assert_seed_not_confirmation_content(seed_base)
    row = row_for_seed_base(seed_base)
    if seed_base == CYCLE8_SCALE_VALIDATION_SEED_BASE:
        raise ValueError("scale validation seed is reserved until the U+034F x1 mechanism is frozen")
    if seed_base != CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE:
        raise ValueError("seed_base is not a Cycle 8 control-mix generation seed")
    if row["eligible_for_confirmation"] is True:
        raise ValueError("confirmation-reserved seeds must not be used for development")
    if row["eligible_as_unseen_validation"] is True:
        raise ValueError("unseen validation seeds must not be used for development generation")


def known_seed_bases() -> Sequence[int]:
    return tuple(int(row["seed_base"]) for row in global_seed_rows())


def ledger_index() -> Mapping[int, dict[str, object]]:
    return {int(row["seed_base"]): row for row in global_seed_rows()}
