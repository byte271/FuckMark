# Cycle 8 publishability Gate v2

Status: `preregistered_not_active`. Evidence label: `HYPOTHESIS`. Not confirmation. Not product authorization.

Gate v2 is a versioned publishability definition. It is not a claim that mix is solved, and it does not change the public CLI.

## Decision

The product objective is:

- `VISIBLE(x) == VISIBLE(T(x))` on every eligible row (Priority Zero)
- `detector(S(T(x)))` remains negative for each required sanitizer `S`

The H12-H15 search gate asked for carrier fixed-point survival:

- `S(T(x)) == T(x)` for every sanitizer in `required_sanitizers_keep`, including Mn-strip and default-ignorable-strip

Fixed-point survival is sufficient for detector-after-sanitizer evasion, but it is not required. The required bundle deletes mix carriers and reconstructs the source, so a fixed-point gate against those two sanitizers is a stress test of carrier survival, not a product publishability requirement.

This is independently checked against the frozen product contract:

- `default_ignorable_removal` and `nonspacing_mark_removal` are `stress_only_not_frozen`
- mix already survives 21/21 frozen sanitizer fixtures
- the v1 mix sanitizer gate remains `FAIL` because `required_sanitizers_keep` is not weakened

## Classifications

| sanitizer | classification |
| --- | --- |
| `raw` | `real_deployed_preprocessing` |
| `nfc`, `nfkc`, `cf_strip`, `nfkc_cf_strip`, `ws_collapse`, `ws_collapse_nfkc_cf_strip` | `frozen_product_requirement` |
| `lm_watermarking_unicode_sanitizer` | `real_deployed_preprocessing` (jwkirchenbauer/lm-watermarking `UnicodeSanitizer`, `WatermarkDetector(normalizers=["unicode"])` default) |
| `nonspacing_mark_removal`, `default_ignorable_removal` | `stress_only_not_frozen` / `KNOWN_DESTRUCTIVE_COUNTERMEASURE` |
| `required_bundle` | `KNOWN_DESTRUCTIVE_COUNTERMEASURE` (diagnostic; reconstructs the source) |
| `homoglyphs`, `truecase` | `UNSUPPORTED` (opt-in lm-watermarking normalizers, not the unicode default) |

Gate v2 adds `ws_collapse_nfkc_cf_strip` versus the H16 draft. That arm is a frozen Cycle 7 product-contract sanitizer.

Mn-strip and default-ignorable-strip remain recorded. They still restore mix. They are not treated as harmless.

## Confirmation protocol

Reserved before generation, before any detector look:

| seed | topic | role | n |
| --- | --- | --- | --- |
| 1200000 | `gate v2 confirmation primary` | confirmation | 64 |
| 1210000 | `gate v2 confirmation replication` | confirmation | 64 |
| 1220000 | `gate v2 confirmation holdout` | confirmation | 64 |

Do not use `830000` / `840000` / `850000`. Do not generate `950000`. Do not reuse exploratory seed `890000` as confirmation.

Pass thresholds, frozen before scoring:

- identity / pristine watermarked detected `>= 168/192`
- mix watermarked detected `= 0/192` after every required sanitizer
- mix unwatermarked detected `= 0/192` on raw
- exact visible invariance `192/192` on mix watermarked rows
- `lm_watermarking_unicode_sanitizer` mix watermarked detected `= 0/192`
- carrier-free identity plus that real sanitizer `>= 96/192` and drop from identity `<= 16`
- `required_bundle` is scored as a diagnostic, not a pass condition
- existing DeepMind 30-key mix `0/192` on `1060000` / `1070000` / `1080000` remains the current cross-detector evidence and is not rescored here

Run once. If the result is `1/N`, report `1/N`. Do not rerun looking for zero. Do not retune on these rows.

Spec: `specs/cycle8/fuckmark-cycle8-publishability-gate-v2.json`.

Runner: `python -m fuckmark.cycle8_gate_v2_confirmation_hf --seed-base 1200000`.
