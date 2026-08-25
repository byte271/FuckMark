# Cycle 7 Stage A decision

**Decision: `INSUFFICIENT_EVIDENCE`**

This is development-only. It is not a Cycle 7 formal confirmation. Seeds `830000` / `840000` / `850000` were not inspected.

Catalog `cycle7-durable-rule-catalog-v2` adds attested open/hyphen compounds and in-word typographic apostrophes on top of Family 1 contractions. The generated seed-`810000` texts were not regenerated.

## What was measured

Fresh exploratory seed `810000`, one pair per domain (8 texts), frozen GPT-2 revision, frozen Cycle 6 threshold `0.5570987654320988`, budget 14, detector-blind cover-greedy v4.

Arms on the same texts:

- Cycle 6 spacing-heavy B14 (`quote_safe_zrd_transform_registry`)
- Cycle 7 durable (catalog v2; no extra spaces)
- Combined durable + Cycle 6 spacing

Sanitizer arms included `raw` and `ws_collapse`.

## Detector counts (watermarked 4, unwatermarked 4)

Catalog v2 (latest `detector-compare.json`):

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW | Raw WM mean |
| --- | --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 | 0.525449 |
| Cycle 7 durable | 4/4 | **4/4** | 0/4 | **4/4** | 0/4 | 0.624884 |
| Combined | 4/4 | **1/4** | 0/4 | **4/4** | 0/4 | 0.531142 |

Family 1 copula snapshot remains `detector-compare-family1-copula.json` (durable 4/4 raw and collapse; combined 0/4 raw, 4/4 collapse).

## VERIFIED (this Stage A)

1. Cycle 6 spacing can drive raw detections from 4/4 to 0/4 on this tiny corpus.
2. The same Cycle 6 outputs are detected 4/4 after `whitespace-collapse-v1`. Collapse restores the attack. Reproduced on **new** development data, not on spent 760000–780000 rows.
3. Unwatermarked transformed controls stayed 0/4 on durable and Cycle 6 spacing. Combined unwatermarked stayed 0/4.
4. On contraction-rich fixtures, durable edits remain after collapse; inside quotes, Cycle 6 spacing collapses away and Cycle 7 durable edits remain.
5. Bare `it's not` ↔ `it is not` is not admitted.
6. GPT-2 tokenization changes for Family 2 and Family 3 are real and collapse-resistant. Durable-only still leaves 4/4 detections because site density is too low (often 1 surviving non-space edit on a watermarked 64-token sample). Intact root windows remain ~44–53 of ~54–60.
7. Combined raw moved from 0/4 (Family 1) to 1/4 (catalog v2) on this corpus: cover-greedy spent a budget slot on `proof-of-concept` opening instead of a space, and that watermarked technical sample scored 0.5606 (threshold 0.5571). This is not used to retune the scheduler on these rows. It is a high-level geometry note: mixing sparse durable edits into a spacing budget can reduce raw coverage.

## SOURCE-BOUND forensic note (Cycle 6 spent residuals)

Not used for tuning. High-level class only: most formal residuals looked like budget-limited leftover leak windows under a spacing-heavy attack.

## Decision

**`INSUFFICIENT_EVIDENCE`** as a Cycle 6 replacement. Collapse-survival of the durable *channel* is real. Detector-side replacement of Cycle 6 spacing is not demonstrated on this 8-text exploratory corpus.

Do not open Cycle 7 formal confirmation. Do not chase 7/192 → 0/192 by adding U+0020 spaces.

## Next development direction

1. Keep Cycle 6 geometry/scheduler/protected-span machinery.
2. Search a durable family with **high natural density on ordinary TinyDev prose**, not only contraction/compound/apostrophe sites. Apostrophe-free and compound-free samples still have almost no durable candidates.
3. A detector-blind combined scheduler that fills spacing *after* durable ops is a hypothesis, not authorized from these four watermarked rows.
4. Measure Stage B seed `820000` only after a family is frozen.
5. REJECTED as durable channels: NBSP (NFKC→space), ZWSP/soft hyphen (Cf-strip).
