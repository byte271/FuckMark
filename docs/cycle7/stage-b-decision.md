# Cycle 7 Stage B decision

**Decision: `PROMISING_DEVELOPMENT`**

This is development-only. It is not a Cycle 7 formal confirmation. Seeds `830000` / `840000` / `850000` were not inspected. Seed `820000` is reserved disjoint validation and was unused during Stage B1 rule construction.

Catalog: `cycle7-durable-rule-catalog-v3`. Scheduler: unchanged cover-greedy v4. Detector threshold: frozen Cycle 6 value `0.5570987654320988`. Model: `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

## Stage B1 corpus

Exploratory seed `860000` and topic `independent replication` were frozen in `cycle7-seed-ledger-v2` before generation. Pair stride 32, one pair per TinyDev domain, 8 texts (4 watermarked + 4 matched unwatermarked).

Artifact hashes (after the root-window classifier fix and detector attachment):

- samples `c345daf7233c18058052f34b16cbc905572579f362b914600372a601f37b9cd7`
- density `4f22db5ad4588744bcb99c3f06d26584242464f30cb0827730ead3f73621ea1e`
- geometry `37f16f73098736c1e69a9dbc646bf2748f4ffe08d58ba661c1d0e078a95514e8`
- detector-compare `c92bb0412b77492865a30f706a7049b1ddfc7b3024515e1e80cab3f93f396869`

## Density (VERIFIED on seed 860000)

Mean durable candidates: **4.25** per sample (Stage A durable sites were typically 1–3).

Family means:

| Family | Mean candidates |
| --- | --- |
| sentence-boundary newline | 2.50 |
| coordinating comma | 0.75 |
| non-format residual | 1.75 |
| complementizer `that` | 0.125 |
| prenominal hyphen | 0.125 |
| discourse comma | 0.00 |
| parenthetical adverb | 0.00 |

Zero-candidate rows: 0/8. Most of the new density is Family 4 formatting, not lexical/syntactic sites.

## Geometry (VERIFIED on seed 860000)

Durable-only, GPT-2 tokenizer, budget 14:

- mean root windows: 49.75
- mean intact after durable edits: 35.625
- mean intact after `whitespace-collapse-v1`: 35.625
- collapsed intact / root: **0.716**

Collapse does not restore durable edits (`collapsed_equals_collapsed_source` is false whenever a durable edit fired). Cycle 6 spacing on the same texts:

- raw intact / root: 0.171
- collapsed intact / root: **0.965**

Combined after collapse: intact / root **0.852**, worse than durable-only. Cover-greedy spends budget on spacing that collapse then erases. This replicates the Stage A combined-arm geometry warning on **new** development data. It is not used to hard-code a scheduler patch for individual 860000 rows.

## Detector (VERIFIED on seed 860000, n=4 watermarked)

Frozen threshold `0.5570987654320988`. Detector scores were not used to select edits.

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW | Raw WM mean |
| --- | --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 | 0.495731 |
| Cycle 7 durable v3 | 4/4 | **2/4** | 0/4 | **2/4** | 0/4 | 0.571097 |
| Combined | 4/4 | **0/4** | 0/4 | **3/4** | 0/4 | 0.493690 |

NFKC, Cf-strip, NFKC+Cf-strip, and `ws_collapse_nfkc_cf_strip` matched the corresponding raw or collapse arm on these rows.

Unwatermarked transformed controls: **0 detections** on every arm and sanitizer.

Compared with Stage A catalog v2 on seed 810000 (durable 4/4 raw and 4/4 after collapse), Stage B1 durable v3 is the first local development measurement in which collapse-surviving transformed-watermarked detections dropped below 4/4.

This is n=4. It is not ZERO_RESIDUAL. It is not Cycle 7 formal confirmation.

## Claim boundary

Safe claim: under the frozen SynthID-Text/GPT-2 protocol, catalog v3 durable edits on seed `860000` reduced collapse-surviving watermarked detections from the Stage A durable baseline of 4/4 to 2/4, while Cycle 6 spacing on the same texts returned to 4/4 after whitespace collapse, and transformed unwatermarked controls stayed 0/4.

Do not claim: universal watermark removal; proprietary-detector transfer; formal confirmation; human-fidelity validation; that format newlines would survive a wrap/reflow sanitizer.

## Stage B3 disjoint validation (seed 820000)

Topic `held-out evaluation` was frozen in the ledger before generation. Catalog v3 and cover-greedy v4 were not modified after seeing 820000.

Artifact hashes:

- density `502f7e2ee9e4bd27b1582bdcbdfc2ae123050177abf3b225593bc91cddd298f3`
- geometry `ee4942e8783710dae2410739932425a44c27e3d26d23c046d143aca08a249221`
- detector-compare `3da3c015194f6062837db3eb6f0ef7a615909c81733d3bef5f9099c5d0f5e4d3`

Density/geometry (VERIFIED, replicated):

- mean durable candidates: **4.0** (B1 was 4.25)
- mean format: 1.875; mean non-format: 2.125
- collapsed intact / root: **0.735** (B1 was 0.716)

Detector (VERIFIED; detector reduction did **not** replicate):

| Arm | Pristine WM | Raw WM | Raw UW | ws_collapse WM | ws_collapse UW |
| --- | --- | --- | --- | --- | --- |
| Cycle 6 spacing B14 | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |
| Cycle 7 durable v3 | 4/4 | **4/4** | 0/4 | **4/4** | 0/4 |
| Combined | 4/4 | **0/4** | 0/4 | **4/4** | 0/4 |

Unwatermarked transformed controls: 0 detections on every arm and sanitizer.

The B1 durable 2/4 collapse-surviving reduction is therefore **not** a replicated detector result. It remains SOURCE-BOUND to seed `860000`.

## Overall Stage B conclusion

**`INSUFFICIENT_EVIDENCE`** as a Cycle 6 whitespace-collapse replacement.

Replicated: catalog v3 raises natural durable-site density into a ~4 candidates/sample regime on TinyDev 64-token GPT-2 text; most of that density is sentence-boundary formatting; those edits survive `whitespace-collapse-v1`; intact root windows remain ~72–73% after collapse; Cycle 6 spacing still returns to 4/4 detections after collapse; transformed unwatermarked controls stay clean.

Not replicated: collapse-surviving detector reduction.

Do not retune catalog v3 on 820000. Do not inspect 830000/840000/850000. Do not open Cycle 7 formal confirmation.

## What remains the bottleneck

Local semantically conservative English surface equivalence is still sparse on ordinary ~64-token TinyDev GPT-2 prose. Family 4 supplies most of the new sites. Complementizer, discourse, prenominal, and parenthetical families barely fired. TinyDev 64-token GPT-2 continuations are often list-like and truncated; that domain may inflate sentence-boundary density relative to ordinary paragraph prose.

## Next

1. Do not retune catalog v3 on seeds 860000 or 820000.
2. Seed 820000 is now spent as disjoint validation. A later revised mechanism needs a new unused validation split; do not recycle 820000.
3. Do not inspect 830000/840000/850000.
4. A detector-blind combined scheduler that prefers collapse-surviving families remains a HYPOTHESIS. It was not applied after seeing 820000.
5. If more rule-construction data is required, add a **new** exploratory seed to the ledger before inspecting it.
