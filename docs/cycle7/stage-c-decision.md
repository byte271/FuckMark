# Cycle 7 Stage C decision

**Decision: `INSUFFICIENT_EVIDENCE`**

This is development-only. It is not a Cycle 7 formal confirmation. Seeds `830000` / `840000` / `850000` were not inspected. Seed `880000` remains unused validation and was **not** generated.

Catalog: `cycle7-durable-rule-catalog-v4`. Scheduler: unchanged cover-greedy v4. Detector threshold: frozen Cycle 6 value `0.5570987654320988`. Model: `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

v4 adds Family 10 (clause punctuation newline) and Family 11 (optional quantifier `of` before a closed determiner/possessive). Families 1–9 are unchanged from catalog v3.

## Stage C1 corpus

Exploratory seed `870000` and topic `measurement protocol` were frozen in `cycle7-seed-ledger-v3` before generation. Pair stride 32, one pair per TinyDev domain, 8 texts (4 watermarked + 4 matched unwatermarked). Seeds `810000`, `860000`, and `820000` were not used as rule-construction data for v4.

Artifact hashes:

- samples `b336e857c49a42a5668b8ab886a3c7b5e7813a050ce81eed068f168cfecf45f8`
- density `64413b60c5d1a659d1d7ea6eec19d06dba35a756589b97d28cca86e5ca8e01b2`
- geometry `8ff51b7845553ed94552ba6f327996424d13809145edf8a114c15cc0284c826f`
- detector-compare `ef9c40420e663ea3ebc26232f0e4c021907c2f5b2c652fa61341dd58c5bfe177`

## Density (VERIFIED on seed 870000)

Mean durable candidates: **4.75** per sample (Stage B was 4.25 on 860000 and 4.0 on 820000). Stage C required a mean of at least 8 to call density promising.

Family means:

| Family | Mean candidates |
| --- | --- |
| all format (sentence + clause newline) | 2.875 |
| clause punctuation newline | 1.50 |
| non-format residual | 1.875 |
| coordinating comma | 0.25 |
| quantifier `of` | **0.00** |
| complementizer / discourse / prenominal / parenthetical | 0.00 |

Min 1 / max 11 / zero-candidate rows 0/8. Family 10 did fire (mean 1.5). Family 11 did not fire on this TinyDev 64-token GPT-2 corpus.

## Geometry (VERIFIED on seed 870000)

Durable-only, GPT-2 tokenizer, budget 14:

- mean root windows: 53.0
- mean intact after durable edits: 37.875
- mean intact after `whitespace-collapse-v1`: 37.875
- collapsed intact / root: **0.715**

Collapse does not restore durable edits. Cycle 6 spacing on the same texts:

- raw intact / root: 0.170
- collapsed intact / root: **0.955**

Combined after collapse: intact / root **0.837**, worse than durable-only. This replicates the Stage A/B combined-arm geometry warning on a **new** exploratory seed. Cover-greedy v4 was not changed.

## Detector (VERIFIED on seed 870000, n=4 watermarked)

Frozen threshold `0.5570987654320988`. Detector scores were not used to select edits.

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW |
| --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |
| Cycle 7 durable v4 | 4/4 | **3/4** | 0/4 | **3/4** | 0/4 |
| Combined | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |

NFKC, Cf-strip, NFKC+Cf-strip matched raw. `ws_collapse_nfkc_cf_strip` matched `ws_collapse`.

Unwatermarked transformed controls: **0 detections** on every arm and sanitizer.

The durable 3/4 collapse-surviving result is SOURCE-BOUND to seed `870000`. Stage B already showed that a 2/4 development snapshot on 860000 did not replicate on 820000. This C1 snapshot is not treated as a catalog freeze.

## Claim boundary

Safe claim: under the frozen SynthID-Text/GPT-2 protocol, catalog v4 on seed `870000` did not raise natural durable-site density out of the Stage B four-site regime (4.75 vs 4.0–4.25), Family 11 did not fire, collapse-surviving intact root windows remained ~71.5%, and Cycle 6 spacing still returned to 4/4 detections after whitespace collapse.

Do not claim: universal watermark removal; proprietary-detector transfer; formal confirmation; human-fidelity validation; that clause newlines would survive a wrap/reflow sanitizer; that catalog v4 is a Cycle 6 spacing replacement.

## Overall Stage C1 conclusion

**`INSUFFICIENT_EVIDENCE`** as a Cycle 6 whitespace-collapse replacement.

Replicated on a third exploratory seed: punctuation-newline layout is the only durable family that supplies multiple natural sites on TinyDev 64-token GPT-2 text; those edits survive `whitespace-collapse-v1`; most root windows remain intact; Cycle 6 spacing still returns to 4/4 after collapse; transformed unwatermarked controls stay clean; combined-after-collapse geometry is worse than durable-only.

New negative: optional `all/both/half of DET` did not occur on this corpus (mean 0.0). Expanding sentence newlines to clause commas added about 1.5 candidates/sample and did not move collapse-surviving geometry.

HYPOTHESIS strengthened toward: local semantically conservative English surface equivalence, plus layout newlines that survive `whitespace-collapse-v1`, does not provide enough natural sites on this domain to replace the Cycle 6 spacing channel.

Do not freeze catalog v4 against seed `880000`. Do not inspect `880000`. Do not inspect `830000` / `840000` / `850000`. Do not retune v4 on `870000`. Do not open Cycle 7 formal confirmation.

## Next

1. Keep `880000` unseen. If a later mechanism version is justified, freeze that version first, then use `880000` as disjoint validation.
2. Do not accumulate more tiny lexical whitelists against 870000.
3. A later mechanism, if pursued, should target a different context-disruption primitive (longer-range deterministic edits, or a collapse-resistant channel denser than clause punctuation) rather than additional closed-list surface equivalences.
4. A detector-blind combined scheduler that prefers collapse-surviving families remains a HYPOTHESIS. It was not applied after seeing 870000.
