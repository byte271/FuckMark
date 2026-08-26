# Cycle 8 letter-x1 system benchmark

Status: `HYPOTHESIS` / `PROMISING_DEVELOPMENT`. Measurement, not confirmation.

Evidence: [`evidence/cycle8-letter-system-benchmark-2026-08-26/`](../../evidence/cycle8-letter-system-benchmark-2026-08-26/).

The current development mechanism `u034f-letter-x1` was measured as-is. It is not in `release_transform_registry()`. `process_text("I do not agree.")` is unchanged.

## Headline numbers

Fresh reserved-before-generation corpora `980000` n=64 plus `990000` n=64:

- letter-x1 raw transformed WM **0/128**
- letter-x1 raw transformed UW **0/128**
- space-x1 on the same corpora **1/128**
- letter-x1 maximum score **0.554066** versus threshold **0.557099** (gap **0.003032**)
- fixture visible projection **21/21**
- Chromium `pre` / textarea / contenteditable pixel-equal on the measured fixtures
- frozen sanitizers match raw letter detections
- Mn-strip and default-ignorable-strip remove the carrier

The earlier experimental letter-x1 **0/192** remains a separate tally: 128 seen diagnostic (`930000`+`940000`) plus 64 independent (`970000`). Do not collapse it into the fresh 0/128.

Formal confirmation readiness: `NOT_READY`.
