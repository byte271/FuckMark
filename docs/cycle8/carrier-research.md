# Cycle 8 carrier research

Labels: `VERIFIED`, `HYPOTHESIS`, `REJECTED`, `PRODUCT_DISQUALIFIED`, `HISTORICAL_ONLY`, `UNKNOWN`.

## H1. Normalization-stable non-Cf carrier

`HYPOTHESIS` for product use. Sanitizer screen `VERIFIED` for U+034F and U+FE00..U+FE0F on the frozen arms:

- category Mn, default-ignorable, combining class 0;
- NFC/NFKC-stable in isolation;
- survives Cf-strip (not Cf);
- survives `whitespace-collapse-v1` when placed after an ASCII space.

GPT-2 tokenizer screen `VERIFIED` on the Cycle 8 fixture (tiktoken `gpt2`): inserting U+034F after ASCII word spaces changed token IDs (`ids_equal=false`, token-count delta +40) with suffix realignment of only one token. An 8-copy space run produced delta +208. U+200C also disrupts GPT-2 (delta +28) but remains Cf-fragile.

Not product-authorized. Fixture compare on four ASCII texts is `VERIFIED` for visible projection (`20/20`) and for U+034F / U+FE00 survival under Cf-strip, NFKC, and `whitespace-collapse-v1`. Chromium `pre` screenshots: U+034F and U+FE00 are `VERIFIED` pixel-equal to the original; U+200C is `REJECTED` (PNG bytes differ). Detector-blind GPT-2 / SynthID looks on seeds `890000`, `900000`, and `910000` are `PROMISING_DEVELOPMENT` / `HYPOTHESIS` only (four watermarked pairs per seed). Prefer U+034F x1: x8 overflowed GPT-2's 1024-token context on seed `900000`. The public CLI still authorizes zero carriers.

## H2. Carrier runs at space boundaries

`HYPOTHESIS` for the space-x1 product-research arm. Repeating an approved carrier after existing ASCII spaces increases hidden payload without splitting `[A-Za-z]+` words, so historical hard-invariant word matching still passes. Word-final ASCII letter x1 (`[A-Za-z](?![A-Za-z])`) plus space x1 was a detector-blind density follow-up on reserved seed `960000`. On that 16-pair corpus both space x1 and space-wordfinal were **1/16** raw transformed WM on the same residual row. Density did not beat space x1. Space-x1 scale remains **1/64** on seed `930000` and **0/64** on seed `940000` (combined **1/128**). These space-x1 results are frozen. Do not rewrite them as zero.

## H10. Intra-word visible-preserving letter carrier

`HYPOTHESIS` / `PROMISING_DEVELOPMENT`. The frozen hard-invariant word regex is a raw-byte check. User-visible words are the Priority Zero object, so the letter arm computes negation/modality signatures on `project_visible_v1` and opt-in quote-interior policy `quote-visible-carrier-v1` allows approved letter carriers inside surface-editable quotations without changing quote delimiters. Machine spans (URLs, paths, code, numbers) stay blocked on raw protected-span identity. A detector-blind selected-site cap of 192 keeps GPT-2 context under 1024 tokens.

Letter-x1 is **not** in `release_transform_registry()`. Space-x1 still uses blanket quotes and raw word signatures.

Diagnostic rescore of seen corpora (not unseen): `960000` n=16 **0/16**, `930000` n=64 **0/64**, `940000` n=64 **0/64**. Independent reserved seed `970000` is **0/16** then **0/64**. Experimental letter-x1 **0/192** = seen `930000` n=64 plus seen `940000` n=64 plus independent `970000` n=64 (**128/192 seen**, **64/192 independent**). Matched unwatermarked controls stayed clean. Visible projection passed on every scored letter row.

A later system benchmark reserved seeds `980000` and `990000` before generation. Fresh letter-x1 is **0/128** raw transformed WM on those two independent 64-pair corpora, with space-x1 **1/128** on the same texts. Maximum fresh letter score is 0.554066 versus threshold 0.557099. That 0/128 is measurement, not confirmation, and must not be collapsed into the experimental 0/192. Formal confirmation readiness is `NOT_READY`. See `docs/cycle8/letter-system-benchmark.md`.

Still `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. Not confirmation. Not a freeze. Public CLI remains empty. Do not generate `950000`.

Intra-word insertion is no longer treated as tokenizer-diagnostic-only. Letter-x1 was the previous strongest visible-invariant U+034F arm. The later mix arm below is stronger on fresh independent corpora.

## H11. Alternating U+034F / U+FE00 letter mix

`VERIFIED` for one-shot mix confirmation 0/192 on the frozen GPT-2 / SynthID protocol. Still not product-authorized. Uniform CGJ repeats are masked by SynthID `valid_mask` on repeated 5-gram contexts. The mix arm places U+034F on even selected-site indexes and U+FE00 on odd indexes after ASCII letters, using raw unmerged hard machine spans instead of merged MATH+NUMBER protection. Quote interiors are allowed. URLs, numbers, code, and paths stay blocked.

Seeds `1020000` and `1030000` were reserved before generation. Fresh mix is **0/128** raw transformed WM, mix UW **0/128**, visible 256/256 on the detector rows, frozen sanitizers matching raw zeros. Worst fresh mix score is 0.513691 versus threshold 0.557099 (gap 0.043407). Letter-x1 on the same corpora is also 0/128 with worst max 0.527389. Letter-space on `1000000`+`1010000` remains **1/128**. Chromium `pre`/textarea/contenteditable were pixel-equal on the measured mix fixtures.

Independent scale seeds `1040000` and `1050000` were reserved before generation. Combined with `1020000`+`1030000`, mix is **0/256** raw transformed WM, mix UW **0/256**, worst mix max 0.519522 (gap 0.037577). The two-corpus 0/128 scorecard is not rewritten. This 0/256 is development scale. The mechanism is frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on seeds `830000` / `840000` / `850000` is **0/192**, mix UW **0/192**, visible **192/192**, worst max 0.524300 (gap 0.032798). Those confirmation seeds are spent. It is not product-authorized. Publishability: software compatibility PASS on the UTF-8 / visible-search product surface; sanitizer and cross-detector still FAIL. See `docs/cycle8/mix-freeze.md` and `docs/cycle8/mix-publishability.md`.

## H3-H8

Placement geometry, Cycle 6 scheduler reuse, and root-window correlation remain `HYPOTHESIS` for larger corpora. Tiny-corpus detector looks on seeds `890000`, `900000`, and `910000` are `PROMISING_DEVELOPMENT` only.

## H9. Feasibility boundary

`VERIFIED` as a negative result for product-safe stronger carriers. Assigned Unicode scalar values were scanned in `cycle8-invisible-carrier-feasibility-v1`. No code point is simultaneously invisible, not Mn, not Cf, not default-ignorable, and pixel-equal on Chromium `pre`.

Mix carriers U+034F and U+FE00 are Mn and default-ignorable, so Mn-strip and default-ignorable-strip restore the source. Cf dies to frozen Cf-strip. The 13 enclosing marks (Me, probe U+20DD) survive those stress sanitizers and have display width 0, but they change rendered pixels and are `REJECTED`. Other non-Mn/Cf assigned characters: 0.

Cycle 8 freezes that boundary rather than weaken Priority Zero. There is no stronger invisible Unicode product mechanism under the current contract.

## Rejected as product mechanisms

| Mechanism | Label | Why |
| --- | --- | --- |
| Contractions / Cycle 7 durable edits | `PRODUCT_DISQUALIFIED` | visible words or punctuation change |
| Cycle 6 U+0020 runs | `PRODUCT_DISQUALIFIED` | visible spacing change |
| U+200C / other Cf | `REJECTED` as durable; diagnostic only | Cf-strip restores the original string |
| Enclosing marks (Me, probe U+20DD) | `REJECTED` | survive Mn/DI/Cf-strip but change Chromium `pre` pixels |
| NBSP / hair spaces / dashes / homoglyphs | `REJECTED` | visible or NFKC-mapped layout/glyph change |

## Baseline

U+200C after ASCII word spaces: visibility-aligned on the v1 projection, Cf-fragile, and Chromium-pixel-`REJECTED`. Keep as the diagnostic control. Do not promote to release.
