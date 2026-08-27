# Cycle 8 Gate v2 confirmation detector (seed 1210000, 64 pairs)

One-shot formal confirmation of `cycle8-publishability-gate-v2`. Seed `1210000` and topic `gate v2 confirmation replication` were preregistered before generation. This corpus is spent. Do not retune on residuals. Do not rerun looking for zero.

Detector-after-sanitizer comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F/U+FE00 letter-alt v1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

`decision.json` is the shared scale classifier and still says development classification. The Gate v2 confirmation claim is this README plus `cycle8-gate-v2-confirmation-scorecard-v1`.

## Result

| Arm | Identity / pristine WM | Mix required sanitizers WM | Mix UW | Visible mix WM | Carrier-free Unicode WM | Mix max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 61/64 | n/a | 0/64 | 128/128 | 60/64 | n/a |
| u034f-ufe00-letter-alt-v1 | n/a | **0/64** after every required sanitizer | **0/64** | **64/64** | n/a | 0.526739 |

Required sanitizers on this corpus are all 0/64 mix WM: raw, nfc, nfkc, cf_strip, nfkc_cf_strip, ws_collapse, ws_collapse_nfkc_cf_strip, `lm_watermarking_unicode_sanitizer`. Diagnostic `required_bundle` is 61/64; it reconstructs the source and is not a pass condition.

Closest mix watermarked row geometry only: `cycle8-1210000-52-general_explanatory-watermarked`, 47 insertions, score 0.526739, gap 0.030360 below threshold 0.557099. Residual text was not inspected to write lexical rules.

Identity unwatermarked detections are 0/64 on this corpus. Mix unwatermarked detections are 0/64.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Maximum transformed GPT-2 token count on scored mix watermarked rows is 605/1024.

This corpus holds the worst mix max among the three Gate v2 confirmation seeds. Combined with `1200000` and `1220000`: mix required-sanitizer WM **0/192**, mix UW **0/192**, visible mix WM **192/192**, identity WM **188/192**, carrier-free Unicode **182/192**.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`. Do not reuse mix-freeze seeds `830000` / `840000` / `850000`.
