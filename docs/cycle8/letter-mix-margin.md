# Cycle 8 letter-mix margin

Status: frozen as `cycle8-mix-freeze-v1`. One-shot confirmation is `VERIFIED` **0/192**. Publishability gates: not product-publishable. Not product-authorized.

Development evidence: [`evidence/cycle8-mix-margin-2026-08-26/`](../../evidence/cycle8-mix-margin-2026-08-26/). Confirmation evidence: [`evidence/cycle8-mix-confirmation-2026-08-26/`](../../evidence/cycle8-mix-confirmation-2026-08-26/). See `docs/cycle8/mix-freeze.md`.

The development mechanism `u034f-ufe00-letter-alt-v1` was measured as-is, then frozen. It is not in `release_transform_registry()`. `process_text("I do not agree.")` is unchanged.

## Headline numbers

Fresh reserved-before-generation corpora `1020000` n=64 plus `1030000` n=64:

- mix raw transformed WM **0/128**
- mix raw transformed UW **0/128**
- letter-x1 on the same corpora **0/128**
- mix maximum score **0.513691** versus threshold **0.557099** (gap **0.043407**)
- Chromium `pre` / textarea / contenteditable pixel-equal on the measured mix fixtures
- frozen sanitizers match raw mix detections
- Mn-strip and default-ignorable-strip remove the carriers

Additional independent scale seeds `1040000` n=64 plus `1050000` n=64, reserved before generation:

- mix raw transformed WM **0/256** across all four corpora
- mix raw transformed UW **0/256**
- worst mix maximum score **0.519522** versus threshold **0.557099** (gap **0.037577**)
- the two-corpus 0/128 scorecard on `1020000`+`1030000` is not rewritten

Letter-x1 system benchmark seeds `980000` and `990000` remain a separate 0/128 with gap 0.003032. Letter-space seeds `1000000` and `1010000` remain **1/128**. Do not rewrite that 1/128 as zero.

One-shot confirmation on preregistered seeds `830000` / `840000` / `850000`: mix **0/192**, mix UW **0/192**, visible **192/192**, worst max 0.524300 (gap 0.032798). Those seeds are spent. Do not rerun looking for zero. The 0/256 development tally is not the confirmation result.
