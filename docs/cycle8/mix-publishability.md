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
| Cross-detector generalization | PASS | yes |

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

Assigned-Unicode feasibility `cycle8-invisible-carrier-feasibility-v1` found no stronger Priority-Zero invisible mechanism. Closed set `cycle8-invisible-carrier-closed-set-v1` confirms display-width-0 assigned insertions are only Mn, Me, or Cf. Frozen counts are a CPython 3.12 Unicode snapshot. Live scans on other Python versions must still find zero width-0 assigned insertions outside Mn/Me/Cf and must not claim a stronger mechanism.

- visible/control: 140882
- Cf: 161 (dies to frozen Cf-strip)
- Mn: 1985 (dies to Mn-strip; mix lives here)
- Me enclosing marks: 13 (survive Mn/DI/Cf-strip, display width 0, Chromium `pre` pixels change; rejected)
- other non-Mn/Cf: 0
- width-0 Cf that are not default-ignorable: 32 (die to frozen Cf-strip)

Enclosing marks are not product-safe. Cycle 8 freezes that H9 / closed-set boundary rather than changing visible English text.

H12 is a **different class**: general category `Cc`, which H9 skipped as control risk. DEL and C1 except NEXT LINE survive the required sanitizers. Chromium pixels are host-dependent: one research host matched, GitHub Actions Chromium rejected the full apply. Independent reserved seed `1100000` n=16 is control-mix **0/16** WM with identity **15/16**. That does **not** rewrite this mix sanitizer FAIL. Mix still uses U+034F / U+FE00. Control-mix is not product-authorized and is not mix-freeze confirmation. See `docs/cycle8/carrier-research.md`.

## Cross-detector generalization

PASS. Mix-freeze confirmation used GPT-2 / Hugging Face SynthID Weighted Mean at threshold `0.5570987654320988` and remains **0/192**.

Independent Google `synthid-text` 30-key mixin generation and official logits-processor detection on fresh reserved seeds `1060000` / `1070000` / `1080000` is confirmation-scale mix **0/192**, mix UW **0/192**, identity WM **189/192**, identity UW **0/192**, visible pass, mix max `0.506760`. That stack is not the Hugging Face nine-key adapter. It is still GPT-2. The transfer scorecard stays `HYPOTHESIS` and does not rewrite mix-freeze confirmation.

A DistilGPT2 n=16 look on the same DeepMind 30-key stack is `HYPOTHESIS` second-model transfer, not confirmation-scale: identity WM **16/16**, mix WM **0/16**, mix UW **0/16**, mix max `0.504800`. Weights differ from GPT-2. The tokenizer is still GPT-2 BPE. DistilGPT2 is not added to confirmation-scale families.

Independent Mean-family scoring on the **same** Hugging Face adapter, model, threshold, and spent confirmation *source* texts remains `HYPOTHESIS`:

- mix Mean WM **0/192**, mix Mean UW **0/192**, max 0.520947
- mix Weighted Mean WM **0/192**, mix Weighted Mean UW **0/192**, max 0.524300 (matches confirmation)
- identity Weighted Mean 185/192 WM and 2/192 UW match confirmation identity counts

That Mean look is not a second model. Bayesian-family evidence was not collected. Closed detectors stay UNKNOWN. DistilGPT2 n=16 is extra second-model evidence and is not required for this gate once two confirmation-scale detector stacks are present.

See `evidence/cycle8-mix-mean-transfer-2026-08-26/`, `docs/cycle8/mix-deepmind-transfer.md`, and `docs/cycle8/mix-second-model-transfer.md`.

## What this does not do

- It does not authorize mix in `release_transform_registry()`.
- It does not retag or republish `v0.3.0`.
- It does not generate `950000`.
- It does not rewrite the 0/128, 0/256, or 0/192 mix scorecards.

See `docs/cycle8/mix-freeze.md`, `docs/cycle8/carrier-research.md`, and `docs/product-contract.md`.
