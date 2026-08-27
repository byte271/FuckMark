# Cycle 8 publishability Gate v2

Status: `confirmed_and_product_authorized`. Evidence label: `VERIFIED`. Confirmation passed. Public CLI applies frozen `u034f-ufe00-letter-alt-v1` as `release-cli-v5`.

Gate v2 is a versioned publishability definition. Confirmation did not by itself enable the CLI. Product authorization is a separate engineering step recorded here and in `cycle8-product-authorization-v1`.

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

## Confirmation result

Reserved before generation, generated once, now spent:

| seed | topic | role | n | identity WM | mix required WM | mix UW | Unicode mix WM | carrier-free Unicode | mix max |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1200000 | `gate v2 confirmation primary` | confirmation | 64 | 64/64 | 0/64 | 0/64 | 0/64 | 61/64 | 0.519124 |
| 1210000 | `gate v2 confirmation replication` | confirmation | 64 | 61/64 | 0/64 | 0/64 | 0/64 | 60/64 | 0.526739 |
| 1220000 | `gate v2 confirmation holdout` | confirmation | 64 | 63/64 | 0/64 | 0/64 | 0/64 | 61/64 | 0.516419 |
| **combined** | one-shot 3 x 64 | confirmation | 192 | **188/192** | **0/192** | **0/192** | **0/192** | **182/192** | **0.526739** |

Pass thresholds, frozen before scoring, all met:

- identity / pristine watermarked detected `188/192` (`>= 168/192`)
- mix watermarked detected `0/192` after every required sanitizer
- mix unwatermarked detected `0/192` on raw
- exact visible invariance `192/192` on mix watermarked rows
- `lm_watermarking_unicode_sanitizer` mix watermarked detected `0/192`
- carrier-free identity plus that real sanitizer `182/192` (`>= 96/192`) and drop from identity `6` (`<= 16`)
- `required_bundle` scored as a diagnostic (188/192; reconstructs the source), not a pass condition
- existing DeepMind 30-key mix `0/192` on `1060000` / `1070000` / `1080000` remains the current cross-detector evidence and was not rescored here

Run once. Do not rerun looking for zero. Do not retune on these rows. Do not use `830000` / `840000` / `850000`. Do not generate `950000`. Do not reuse exploratory seed `890000` as confirmation.

Closest mix residual geometry only: `cycle8-1210000-52-general_explanatory-watermarked`, 47 insertions, score 0.526739. Residual text was not inspected.

Generic `classify_scale_detector_compare` still labels each corpus `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. That is the shared scale classifier, not the Gate v2 claim.

## Product authorization

After confirmation, the public CLI was authorized to apply the frozen mix. Status is now `confirmed_and_product_authorized`.

- `process_text` equals `apply_letter_alternating_mix` on ordinary English ASCII
- `product_approved_carriers_v1()` is `{U+034F, U+FE00}`
- `release_transform_registry()` stays empty
- CLI identity is `release-cli-v5`
- v1 mix publishability sanitizer stays FAIL
- mix-freeze and mix-confirmation scorecards keep `product_authorized: false` as historical snapshots
- the threat-model audit keeps `product_authorized: false` as an audit, not the authorization instrument

Spec: `specs/cycle8/fuckmark-cycle8-publishability-gate-v2.json`.

Scorecard: `specs/cycle8/fuckmark-cycle8-gate-v2-confirmation-scorecard-v1.json`.

Authorization: `specs/cycle8/fuckmark-cycle8-product-authorization-v1.json`.

Evidence: `evidence/cycle8-gate-v2-confirmation-2026-08-27/`.

Runner: `python -m fuckmark.cycle8_gate_v2_confirmation_hf --seed-base 1200000` (refuses if the artifact already exists).
