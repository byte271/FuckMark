# Cycle 8 mix publishability gates

Status: **not product-publishable**. Mix freeze confirmation remains `VERIFIED` **0/192**. The public CLI stays empty.

Report identity: `cycle8-mix-publishability-v1` (`specs/cycle8/fuckmark-cycle8-mix-publishability-v1.json`). This report does not rewrite `cycle8-mix-freeze-v1` or `cycle8-mix-confirmation-scorecard-v1`. Tag `v0.3.0` is not retagged.

The five gates are the bar for calling mix a publishable FuckMark product. Passing a research confirmation is not enough.

## Outcome

| Gate | Verdict | Blocks product |
| --- | --- | --- |
| Reproducibility | PASS | yes |
| Cross-environment visibility invariance | PASS | yes |
| Real-world software compatibility | FAIL | yes |
| Known sanitizer weaknesses | FAIL | yes |
| Cross-detector generalization | FAIL | yes |

`product_publishable` is false. `product_authorized` is false. `product_approved_carriers_v1()` is empty. `process_text("I do not agree.")` is unchanged.

## Reproducibility

PASS. The freeze hash, confirmation scorecard hash, and product contract hash replay. Letter-mix apply is deterministic. Confirmation remains mix **0/192**, mix UW **0/192**, visible **192/192**. Do not rerun looking for zero.

## Visibility invariance

PASS on measured Unicode-capable surfaces: exact visible projection, NFC, UTF-8 file bytes, stdin/stdout, and terminal display width on the supported ASCII fixtures. WebKit/Safari pixels and terminal pixels stay UNKNOWN. Chromium `pre` / textarea / contenteditable equality was measured earlier on mix fixtures and is not rehashed here.

## Software compatibility

FAIL. UTF-8 and JSON roundtrips preserve mix. Protected URL and email spans stay intact. Latin-1 cannot encode U+034F or U+FE00. Literal search for `do not` misses after letter-mix insertion on short English text.

## Sanitizer weaknesses

FAIL as a product gate. Frozen Cycle 6/7 sanitizers (raw, NFKC, Cf-strip, whitespace-collapse, combined, NFC) keep mix, matching confirmation zeros. Mn-strip and default-ignorable-strip remove both carriers. NFKD keeps them. Those stress sanitizers are documented, not frozen product assumptions, and they still kill the mechanism.

## Cross-detector generalization

FAIL. Confirmation used one open detector: GPT-2 / Hugging Face SynthID Weighted Mean at threshold `0.5570987654320988`. In-tree Mean and Bayesian families were not confirmed on the mix freeze. No second model. Closed detectors are UNKNOWN.

## What this does not do

- It does not authorize mix in `release_transform_registry()`.
- It does not retag or republish `v0.3.0`.
- It does not generate `950000`.
- It does not rewrite the 0/128, 0/256, or 0/192 mix scorecards.

See `docs/cycle8/mix-freeze.md` and `docs/product-contract.md`.
