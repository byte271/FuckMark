# Cycle 8 mix publishability gates

Status: **not product-publishable**. Mix freeze confirmation remains `VERIFIED` **0/192**. The public CLI stays empty.

Report identity: `cycle8-mix-publishability-v1` (`specs/cycle8/fuckmark-cycle8-mix-publishability-v1.json`). This report does not rewrite `cycle8-mix-freeze-v1` or `cycle8-mix-confirmation-scorecard-v1`. Tag `v0.3.0` is not retagged.

The five gates are the bar for calling mix a publishable FuckMark product. Passing a research confirmation is not enough.

## Outcome

| Gate | Verdict | Blocks product |
| --- | --- | --- |
| Reproducibility | PASS | yes |
| Cross-environment visibility invariance | PASS | yes |
| Real-world software compatibility | PASS | yes |
| Known sanitizer weaknesses | FAIL | yes |
| Cross-detector generalization | FAIL | yes |

`product_publishable` is false. `product_authorized` is false. `product_approved_carriers_v1()` is empty. `process_text("I do not agree.")` is unchanged.

## Reproducibility

PASS. The freeze hash, confirmation scorecard hash, and product contract hash replay. Letter-mix apply is deterministic. Confirmation remains mix **0/192**, mix UW **0/192**, visible **192/192**. Do not rerun looking for zero.

## Visibility invariance

PASS on measured Unicode-capable surfaces: exact visible projection, NFC, UTF-8 file bytes, stdin/stdout, and terminal display width on the supported ASCII fixtures. WebKit/Safari pixels and terminal pixels stay UNKNOWN. Chromium `pre` / textarea / contenteditable equality was measured earlier on mix fixtures and is not rehashed here.

## Software compatibility

PASS on the product surface:

- UTF-8 is the only supported product encoding. JSON roundtrips preserve mix.
- Latin-1, ASCII, and cp1252 are **unsupported**. Mix cannot encode there; the CLI rejects `--encoding latin-1` instead of claiming a roundtrip.
- Product search is visible-projection search (`visible_contains`). After letter-mix, `do not` is found on the visible projection and missed by raw codepoint `in`.
- Raw codepoint search is **not** the product search API. Many editors that search UTF-16 code units will miss intra-letter carriers. That is a payload limitation, not a claimed editor Ctrl+F guarantee.
- Chromium `window.find` HIT for `do not` on mix text was measured on a host with Chrome. That measurement is host-dependent and is **not** hashed into this spec. CI without Chrome reports UNKNOWN.
- Protected URL and email spans stay intact. Clipboard copies Unicode text. `--visible` writes the product-authorized visible projection (currently identity, because no carrier is authorized).

## Sanitizer weaknesses

FAIL as a product gate. Frozen Cycle 6/7 sanitizers (raw, NFKC, Cf-strip, whitespace-collapse, combined, NFC) keep mix, matching confirmation zeros. Mn-strip and default-ignorable-strip remove both carriers because U+034F and U+FE00 are Mn and default-ignorable. NFKD keeps them.

Assigned-Unicode feasibility `cycle8-invisible-carrier-feasibility-v1` found no stronger Priority-Zero invisible mechanism:

- visible/control: 140882
- Cf: 161 (dies to frozen Cf-strip)
- Mn: 1985 (dies to Mn-strip; mix lives here)
- Me enclosing marks: 13 (survive Mn/DI/Cf-strip, display width 0, Chromium `pre` pixels change; rejected)
- other non-Mn/Cf: 0

Enclosing marks are not product-safe. Cycle 8 freezes that H9 boundary rather than changing visible English text.

## Cross-detector generalization

FAIL. Confirmation used one open detector: GPT-2 / Hugging Face SynthID Weighted Mean at threshold `0.5570987654320988`.

Independent Mean-family scoring on the **same** adapter, model, threshold, and spent confirmation *source* texts is `HYPOTHESIS`:

- mix Mean WM **0/192**, mix Mean UW **0/192**, max 0.520947
- mix Weighted Mean WM **0/192**, mix Weighted Mean UW **0/192**, max 0.524300 (matches confirmation)
- identity Weighted Mean 185/192 WM and 2/192 UW match confirmation identity counts

That is not a second model. It is not proprietary-detector transfer. It is not a confirmation rewrite. Bayesian-family evidence was not collected. Closed detectors stay UNKNOWN.

See `evidence/cycle8-mix-mean-transfer-2026-08-26/`.

## What this does not do

- It does not authorize mix in `release_transform_registry()`.
- It does not retag or republish `v0.3.0`.
- It does not generate `950000`.
- It does not rewrite the 0/128, 0/256, or 0/192 mix scorecards.

See `docs/cycle8/mix-freeze.md`, `docs/cycle8/carrier-research.md`, and `docs/product-contract.md`.
