# Cycle 7 Stage D decision

**Decision: `PROMISING_DEVELOPMENT`**

This is development-only. It is not a Cycle 7 formal confirmation. Seeds `830000` / `840000` / `850000` were not inspected. Catalog v5 is frozen against further rule expansion on seed `890000`. Seed `880000` is the next unused validation split.

Catalog: `cycle7-durable-rule-catalog-v5`. Scheduler: unchanged cover-greedy v4. Detector threshold: frozen Cycle 6 value `0.5570987654320988`. Model: `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

v5 adds Family 12 (word-boundary newline). Families 1–11 are unchanged from catalog v4. No new lexical whitelist was added.

## Stage D1 corpus

Exploratory seed `890000` and topic `document structure` were frozen in `cycle7-seed-ledger-v4` before generation. Pair stride 32, one pair per TinyDev domain, 8 texts (4 watermarked + 4 matched unwatermarked). Seeds `810000`, `860000`, `820000`, and `870000` were not used as rule-construction data for v5.

Artifact hashes:

- samples `70affa24d42354a0812e66fe731a15e85ab32478884bb8df6bd6adb3de2a2219`
- density `d6d6669cf31940289c97c6d56778f06e1e9a00e92b2e5e90349a3b3958bee991`
- geometry `5a0fe8cfffa8db11ff6f25da93cad26dc8d532a5a36a1454a1c4fb7876ef981a`
- detector-compare `4781844f967595fb00596b462390bc8fc134b37bb5a2d28999e43fa37f19366b`

## Density (VERIFIED on seed 890000)

Mean durable candidates: **38.0** per sample. Mean word-boundary newlines: **33.375**. Stage D required a mean of at least 8 word-boundary sites and at least 8 total durable sites.

Family means:

| Family | Mean candidates |
| --- | --- |
| word-boundary newline | **33.375** |
| all punctuation format (sentence + clause) | 2.125 |
| clause punctuation newline | 1.50 |
| coordinating comma | 0.375 |
| quantifier `of` | 0.00 |
| complementizer / discourse / prenominal / parenthetical | 0.00 |

Min 8 / max 52 / zero-candidate rows 0/8. This escaped the Stage B/C four-site regime. The new density is almost entirely the layout channel, not lexical substitution.

## Geometry (VERIFIED on seed 890000)

Durable-only, GPT-2 tokenizer, budget 14:

- mean selected: 12.625
- mean root windows: 56.375
- mean intact after durable edits: 9.25
- mean intact after `whitespace-collapse-v1`: 9.25
- collapsed intact / root: **0.164**

Collapse does not restore durable edits. This is the strong geometry band (≤0.5). Cycle 6 spacing on the same texts:

- raw intact / root: 0.248
- collapsed intact / root: **0.982**

Combined after collapse: intact / root **0.528**, worse than durable-only. Cover-greedy v4 was not changed after seeing 890000. Combined-after-collapse worse than durable-only now replicates on 810000, 860000, 820000, 870000, and 890000.

## Detector (VERIFIED on seed 890000, n=4 watermarked)

Frozen threshold `0.5570987654320988`. Detector scores were not used to select edits.

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW |
| --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 3/4 | **0/4** | 0/4 | **3/4** | 0/4 |
| Cycle 7 durable v5 | 3/4 | **0/4** | 0/4 | **0/4** | 0/4 |
| Combined | 3/4 | **1/4** | 0/4 | **3/4** | 0/4 |

NFKC, Cf-strip, NFKC+Cf-strip matched raw. `ws_collapse_nfkc_cf_strip` matched `ws_collapse`.

Unwatermarked transformed controls: **0 detections** on every arm and sanitizer.

One watermarked row (`technical_explanation`, seed 890032, 115 characters) was already below threshold on the pristine text (score 0.5461). Conditional on the 3 pristine-detected rows: Cycle 6 spacing returned to 3/3 after collapse; durable v5 stayed 0/3 after collapse.

The durable 0/4 collapse-surviving result is SOURCE-BOUND to seed `890000` and n=4. Stage B already showed that a tiny development detector snapshot can fail to replicate. This D1 snapshot is not Cycle 7 formal confirmation.

## Claim boundary

Safe claim: under the frozen SynthID-Text/GPT-2 protocol, catalog v5 on seed `890000` raised natural durable-site density out of the Stage B/C four-site regime (38.0 vs 4.0–4.75), almost all of that density is word-boundary newlines, collapse-surviving intact root windows dropped to ~16.4%, Cycle 6 spacing still returned to 3/4 detections after whitespace collapse, and durable v5 stayed at 0/4 after the same collapse.

Do not claim: universal watermark removal; proprietary-detector transfer; formal confirmation; human-fidelity validation; that word-boundary newlines would survive a wrap/reflow sanitizer; that combined cover-greedy v4 plus spacing is a Cycle 6 replacement; that 0/4 on n=4 is 0/192.

## Overall Stage D1 conclusion

**`PROMISING_DEVELOPMENT`** as a Cycle 6 whitespace-collapse replacement candidate.

The Stage C hypothesis that local semantically conservative English surface equivalence plus sparse punctuation-newlines cannot replace Cycle 6 spacing is still true for families 1–11. Family 12 is a different primitive: the same layout channel, densified to ordinary word boundaries. On this seed it matches Cycle 6 raw geometry (~0.16 intact/root) and keeps that geometry after `whitespace-collapse-v1`.

HYPOTHESIS unchanged: a wrap/reflow sanitizer would erase Family 12. That sanitizer is not in the frozen Cycle 7 suite.

Do not retune v5 on `890000`. Do not inspect `830000` / `840000` / `850000`. Do not open Cycle 7 formal confirmation. A detector-blind combined scheduler that prefers collapse-surviving families remains a HYPOTHESIS. It was not applied after seeing 890000.

## Next

1. Keep catalog v5 frozen. Use seed `880000` / topic `independent check` as disjoint validation. Do not recycle `820000`.
2. If validation fails to replicate density, geometry, or detector reduction, overall Stage D is `INSUFFICIENT_EVIDENCE` and v5 is not a confirmation candidate.
3. If validation replicates, still do not open confirmation on n=4+4. Confirmation, if ever justified, uses reserved seeds `830000` / `840000` / `850000` under a frozen protocol.
