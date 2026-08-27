# Cycle 8 Gate v2 confirmation scorecard

One-shot formal confirmation of detector-after-sanitizer publishability Gate v2 (`cycle8-publishability-gate-v2`) on frozen mechanism `u034f-ufe00-letter-alt-v1`. Label: `VERIFIED`. Status: `confirmed_not_product_authorized`. Not product authorization. Public CLI remains empty. `required_sanitizers_keep` is not weakened. The v1 mix sanitizer gate stays `FAIL`.

Seeds `1200000`, `1210000`, and `1220000` were preregistered before generation, generated once under the Gate v2 protocol, and are now spent. Do not rerun looking for zero. Do not retune on these corpora. Do not generate `950000`. Do not reuse mix-freeze seeds `830000` / `840000` / `850000`.

Do not collapse this confirmation into mix-freeze confirmation 0/192 on `830000`/`840000`/`850000`, development mix 0/256, or H16 exploratory 0/48.

The Gate v2 spec `specs/cycle8/fuckmark-cycle8-publishability-gate-v2.json` is the versioned gate. This scorecard is the confirmation outcome.

## Scorecard

| Axis | Result | Label |
| --- | --- | --- |
| Identity / pristine WM | **188/192** (floor was >= 168) | `VERIFIED` |
| Mix WM after every required sanitizer | **0/192** | `VERIFIED` |
| Mix raw UW | **0/192** | `VERIFIED` |
| Visible mix WM | **192/192** | `VERIFIED` |
| Mix max score | 0.526739 | `VERIFIED` |
| Mix min gap below threshold | 0.030360 | `VERIFIED` |
| lm-watermarking UnicodeSanitizer mix WM | **0/192** | `VERIFIED` |
| Carrier-free identity plus UnicodeSanitizer | **182/192** (drop 6 from identity; max drop was <= 16) | `VERIFIED` |
| required_bundle mix WM | 188/192 | diagnostic; reconstructs the source; not a pass condition |
| Frozen product-contract sanitizer arms | 0/192 each | `VERIFIED` |
| DeepMind 30-key mix on 1060000/1070000/1080000 | 0/192 | existing transfer; not rescored here |
| Product authorization | false | CLI remains empty |

Required sanitizers: raw, nfc, nfkc, cf_strip, nfkc_cf_strip, ws_collapse, ws_collapse_nfkc_cf_strip, `lm_watermarking_unicode_sanitizer`.

See `scorecard.json` and `specs/cycle8/fuckmark-cycle8-gate-v2-confirmation-scorecard-v1.json` for the machine-readable copy. Per-corpus detector files are in the sibling confirmation directories.

## Confirmation detector corpora

Protocol: identity vs letter-alt, Gate v2 sanitizer matrix including the real UnicodeSanitizer and a carrier-free control, CPU, detector-blind, watermark-key-blind, non-neural. Algorithm version `cycle8-gate-v2-confirmation-detector-compare-v1`.

| Seed | Role | Identity WM | Mix required WM | Mix UW | Unicode mix WM | Carrier-free Unicode | Visible mix WM | Mix max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1200000 | gate v2 confirmation primary | 64/64 | 0/64 | 0/64 | 0/64 | 61/64 | 64/64 | 0.519124 |
| 1210000 | gate v2 confirmation replication | 61/64 | 0/64 | 0/64 | 0/64 | 60/64 | 64/64 | 0.526739 |
| 1220000 | gate v2 confirmation holdout | 63/64 | 0/64 | 0/64 | 0/64 | 61/64 | 64/64 | 0.516419 |
| **Combined** | one-shot 3 x 64 | **188/192** | **0/192** | **0/192** | **0/192** | **182/192** | **192/192** | **0.526739** |

Closest confirmation mix residual geometry only: `cycle8-1210000-52-general_explanatory-watermarked`, 47 insertions, score 0.526739. Residual text was not inspected to write lexical rules.

Identity unwatermarked on seed `1200000` is 1/64. Mix unwatermarked detections are 0/192. Fail-closed identity count is 0. Per-domain mix raw WM is 0/16 on all four domains in each corpus. Maximum transformed token count is 605 / 1024.

Generic `classify_scale_detector_compare` still labels each corpus `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. That is the shared scale classifier, not the Gate v2 claim.

## Mechanism

Frozen detector-blind U+034F / U+FE00 alternating insertions after ASCII letters outside raw unmerged hard machine spans. Even selected-site index receives U+034F; odd receives U+FE00. Selected-site cap 192. Visible projection must equal the source. Not in `release_transform_registry()`. `process_text("I do not agree.")` is unchanged.

## What this does not rewrite

- mix-freeze confirmation 0/192 on `830000`+`840000`+`850000` (`cycle8-mix-confirmation-scorecard-v1`)
- development mix 0/256 including `1020000`+`1030000`+`1040000`+`1050000`
- H16 exploratory UnicodeSanitizer 0/48 on seed `890000`
- v1 mix sanitizer FAIL
- `required_sanitizers_keep`
- empty public CLI
