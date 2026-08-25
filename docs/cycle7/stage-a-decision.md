# Cycle 7 Stage A decision

**Decision: `INSUFFICIENT_EVIDENCE`**

This is development-only. It is not a Cycle 7 formal confirmation. Seeds `830000` / `840000` / `850000` were not inspected.

## What was measured

Fresh exploratory seed `810000`, one pair per domain (8 texts), frozen GPT-2 revision, frozen Cycle 6 threshold `0.5570987654320988`, budget 14, detector-blind cover-greedy v4.

Arms on the same texts:

- Cycle 6 spacing-heavy B14 (`quote_safe_zrd_transform_registry`)
- Cycle 7 durable (contractions + bounded `it's` copulas + toward/among; no extra spaces)
- Combined durable + Cycle 6 spacing

Sanitizer arms included `raw` and `ws_collapse`.

## Detector counts (watermarked 4, unwatermarked 4)

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW |
| --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |
| Cycle 7 durable | 4/4 | **4/4** | 0/4 | **4/4** | 0/4 |
| Combined | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |

Family-1 snapshot (before bounded `it's` copulas) is preserved as `detector-compare-family1-pre-copula.json`. After adding `it's like` / `it's important` / `it's a|an|the`, durable still 4/4 detected. Two watermarked samples gained surviving non-space edits (`it's important`, `it's like`); that did not move detections under the frozen threshold.

## VERIFIED (this Stage A)

1. Cycle 6 spacing can drive raw detections from 4/4 to 0/4 on this tiny corpus.
2. The same Cycle 6 outputs are detected 4/4 after `whitespace-collapse-v1`. Collapse restores the attack. This is the Cycle 6 channel weakness, reproduced on **new** development data, not on spent 760000–780000 rows.
3. Unwatermarked transformed controls stayed 0/4 on every arm.
4. On contraction-rich fixtures, durable edits remain after collapse; inside quotes, Cycle 6 spacing collapses away and Cycle 7 durable edits remain.
5. Bare `it's not` ↔ `it is not` is not admitted: hard invariants treat `it's not` as a different negation atom than `is not`, matching the existing `he's not` / `he is not` split.

## SOURCE-BOUND forensic note (Cycle 6 spent residuals)

Not used for tuning. High-level class only: most formal residuals looked like budget-limited leftover leak windows under a spacing-heavy attack.

## HYPOTHESIS going forward

GPT-2 64-token TinyDev continuations rarely contain reversible contraction/orthography sites. A collapse-resistant family needs **higher natural density** than unambiguous copula/orthography, or a different tokenizer-boundary channel that is still non-neural and detector-blind.

Do not chase 7/192 → 0/192 by adding more U+0020 spaces.

## Next development direction

1. Keep Cycle 6 geometry/scheduler/protected-span machinery.
2. Search additional **high-frequency, invariant-safe** durable rules (not ambiguous `'d` / bare `it's`).
3. Measure density on Stage B seed `820000` only after a family is frozen.
4. Do not open Cycle 7 formal confirmation until a collapse-resistant family replicates on disjoint development data.
