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

Independent scale seeds `1040000` and `1050000` were reserved before generation. Combined with `1020000`+`1030000`, mix is **0/256** raw transformed WM, mix UW **0/256**, worst mix max 0.519522 (gap 0.037577). The two-corpus 0/128 scorecard is not rewritten. This 0/256 is development scale. The mechanism is frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on seeds `830000` / `840000` / `850000` is **0/192**, mix UW **0/192**, visible **192/192**, worst max 0.524300 (gap 0.032798). Those confirmation seeds are spent. It is not product-authorized. Publishability: software compatibility PASS on the UTF-8 / visible-search product surface; sanitizer FAIL; cross-detector PASS on Hugging Face nine-key GPT-2 Weighted Mean plus independent DeepMind 30-key GPT-2 mix **0/192**. DistilGPT2 n=16 is `HYPOTHESIS` second-model transfer, not confirmation-scale. See `docs/cycle8/mix-freeze.md` and `docs/cycle8/mix-publishability.md`.

## H3-H8

Placement geometry, Cycle 6 scheduler reuse, and root-window correlation remain `HYPOTHESIS` for larger corpora. Tiny-corpus detector looks on seeds `890000`, `900000`, and `910000` are `PROMISING_DEVELOPMENT` only.

## H9. Feasibility boundary

`VERIFIED` as a negative result for product-safe stronger carriers. Assigned Unicode scalar values were scanned in `cycle8-invisible-carrier-feasibility-v1`. No code point is simultaneously invisible, not Mn, not Cf, not default-ignorable, and pixel-equal on Chromium `pre`.

Mix carriers U+034F and U+FE00 are Mn and default-ignorable, so Mn-strip and default-ignorable-strip restore the source. Cf dies to frozen Cf-strip. The 13 enclosing marks (Me, probe U+20DD) survive those stress sanitizers and have display width 0, but they change rendered pixels and are `REJECTED`. Other non-Mn/Cf assigned characters: 0.

Cycle 8 freezes that width-0 assigned boundary rather than weaken Priority Zero. Mix sanitizer robustness stays FAIL. The H9 scan skipped general category `Cc` as control risk and did not treat it as a width-0 assigned insertion.

## H12. Sanitizer-surviving control-code insertion

`HYPOTHESIS` / `PROMISING_DEVELOPMENT`. A new class, not a rewrite of mix and not a reopening of the width-0 closed set. Assigned width-0 insertions remain Mn, Me, or Cf. Mix still dies to Mn-strip and default-ignorable-strip.

The next insertion class is Unicode general category `Cc`. Layout controls (TAB, LF, VT, FF, CR, NEXT LINE, line/paragraph separators) stay excluded. NUL is Chromium-pixel-equal on `pre`/textarea/contenteditable but is hostile to ordinary C-string text and is excluded. Most other C0 controls survive the required sanitizers and are Chromium-`REJECTED` (tofu). Braille blank, Ogham space, replacement character, noncharacters, and BMP private-use probes also survive some sanitizers and change Chromium `pre` pixels.

DEL (U+007F) and C1 (U+0080..U+009F except U+0085) are 32 code points that:

- are `Cc`, not default-ignorable, not Mn, not Cf;
- survive Mn-strip, default-ignorable-strip, Cf-strip, NFC, NFKC, NFKD, frozen Cycle 6/7 sanitizers, and the combination of those arms;
- keep exact `project_visible_v1` when used as approved insertion carriers;
- are Chromium-pixel **host-dependent**: one research host matched `pre`/textarea/contenteditable PNG bytes on single-insert probes and a full apply; GitHub Actions Chromium `REJECTED` the same full apply (`png_bytes_differ`);
- keep Chromium `window.find` HIT for `do not` on the short paragraph on the research host;
- disrupt GPT-2 BPE (`ids_equal=false`, token-count delta positive);
- round-trip through UTF-8, JSON, and latin-1;
- fail the v1 product display-width proxy, which still counts `Cc` as width 1. Research width skips the eligible set. That is a proxy gap, not a visible-text change.

The apply path `cc-del-c1-letter-alt-v1` uses the same letter sites as mix, cycling the 32 eligible controls instead of U+034F / U+FE00. Hard machine spans stay blocked. Quote interiors stay eligible. Cap 192. Public CLI remains empty. `product_approved_carriers_v1()` remains empty. Mix confirmation 0/192 is not transferred. Mix publishability sanitizer stays FAIL. Do not generate `950000`.

Seen-corpus DeepMind 30-key diagnostic rescore of seed `920000` n=16: identity WM **16/16**, control-mix WM **0/16**, mix WM **0/16**, all UW **0/16**, visible pass, required sanitizers keep every control-mix row, control-mix max `0.505337`. That look is `HYPOTHESIS`, seen, not independent generation, and not confirmation.

Independent reserved seed `1100000` n=16: identity WM **15/16**, control-mix WM **0/16**, all UW **0/16**, visible pass, required sanitizers keep every control-mix row, control-mix max `0.505851`. The identity miss is one structured-instructional watermarked row at `0.556873` versus threshold `0.557099`. Do not rewrite 15/16 as 16/16. This n=16 is `HYPOTHESIS`, not confirmation, and does not transfer mix-freeze 0/192.

ISO-6429 C1 device controls including CSI (U+009B) remain in the measured 32-codepoint eligible set. Product `display_column_width` still counts `Cc` as width 1. Terminal pixels stay UNKNOWN. Chromium `pre` pixels are host-dependent. Those ordinary-text, terminal, and cross-Chromium visibility risks block product authorization. They do not rewrite mix sanitizer FAIL.

Spec: `cycle8-control-carrier-scan-v1`.

## H13. Post-sanitizer mechanism class

`VERIFIED` as a negative classification, not a Unicode re-scan. Assigned width-0 insertions stay closed (H9). This classifies the broader transform families that remain after Mn-strip, default-ignorable-strip, Cf-strip, NFC/NFKC, and their combination.

No measured class is simultaneously:

- sanitizer-surviving on that required set,
- Chromium-portable (`pre` pixels `VERIFIED` on every measured host),
- ordinary plain text,
- Priority-Zero safe.

Mix (Mn + default-ignorable) dies to Mn-strip and default-ignorable-strip. Enclosing marks survive those sanitizers and change Chromium pixels. Control-code insertion survives those sanitizers and is Chromium host-dependent, with ISO-6429 device controls remaining in the measured set. Homoglyphs, whitespace edits, HTML/CSS, and custom fonts stay forbidden.

This does **not** rewrite mix sanitizer FAIL. H12 did not product-authorize any carrier. Live mix authorization is Gate v2.

Spec: `cycle8-post-sanitizer-mechanism-class-v1`.

## H14. Extended post-sanitizer classes

`VERIFIED` as a negative extension, not a product unlock. H13 classified insertion families after the required sanitizers. H14 does not re-scan assigned width-0 code points. It measures classes H9 skipped as "visible" and classes H13 only probed with a handful of empty glyphs.

No measured class is simultaneously sanitizer-surviving, Chromium-portable, ordinary plain text, and Priority-Zero safe.

Live Unicode 15.0 scan:

- 419 `Mc` spacing combining marks survive the required sanitizers. Product display-width delta is not 0. Chromium `pre` rejects Hangul tone marks and Indic vowel-sign probes.
- 128 NFKC-stable `Lm` modifier letters survive. Chromium `pre` rejects prime, apostrophe, glottal-stop, and raised-exclamation probes. U+02B0 and U+FF9E/U+FF9F die to NFKC.
- Designed blanks and gap fillers (U+13441, U+13442, U+A8F9, U+1144E, U+11C44, U+11F48, U+2800, U+2422, U+1680, U+FFFC) survive and change Chromium `pre` pixels.
- Hangul jamo fillers U+115F+U+1160 are default-ignorable. The sequence dies to default-ignorable-strip and changes Chromium pixels.
- Project default-ignorable ranges match Unicode 15.0. That is not a cheat channel.
- DejaVu Sans Mono, the Chromium `pre` font, has no sanitizer-surviving simple empty zero-advance glyph. Simple empty means TrueType `numberOfContours == 0`. Composite glyphs (`numberOfContours == -1`) are not empty. U+FFFC is a full cell there. System-font zero-advance empties that survive sanitizers are `Cc` or layout separators, plus U+FFFC in DejaVu Sans.
- A CSI-filtered C1 subset is still `Cc`. It is not a new class. Chromium remains host-dependent. Ordinary-text FAIL remains.

The only sanitizer-surviving pixel-equal probes on the research host were control codes. H12 already closed that class for product use.

This does **not** rewrite mix sanitizer FAIL. H13/H14/H15 did not authorize a carrier. Live mix authorization is Gate v2. Do not generate `950000`. Do not retune spent confirmation seeds.

Spec: `cycle8-post-sanitizer-extended-class-v1`. Evidence: `evidence/h14-local/`.

## H15. Sequence and representation class

`VERIFIED` as a negative sequence-level extension, not a product unlock. H14 closed the next single-codepoint graphic classes. H15 does not repeat that sweep. It measures multi-codepoint sequences and representation interactions.

No measured class is simultaneously sanitizer-surviving, Chromium-portable, ordinary plain text, and Priority-Zero safe.

Live sequence measurements:

- Thirteen UAX #29 prepend letters survive the required sanitizers. Chromium `pre` rejects them in front of Latin `I`.
- Joining connectors (tatweel, Nko lajanyalan, Mongolian nirugu, character tie) survive and change Chromium `pre` pixels. ZWJ/ZWNJ die to Cf-strip.
- Hangul L plus V jamo is NFC-unstable. The composed syllable is NFKD-unstable. Either form dies to the required bundle.
- ASCII plus sanitizer-surviving `Mc` does not NFC-compose.
- LRI/FSI wraps around LTR English are pixel-equal on this Chromium host and die to Cf-strip. RLI/RLO wraps change pixels.
- ISO-6429 ESC CSI sequences survive because they are `Cc` plus ASCII, but Chromium `pre` shows the ASCII parameters.
- Mix plus DEL is pixel-equal here; Mn-strip leaves DEL. That is the H12 remainder, not a new class.
- DejaVu Sans Mono has no sanitizer-surviving zero-advance mapped glyph, including composites. Discretionary `fi`/`fl` ligatures map to NFKC-fragile compatibility characters and are not applied in Chromium `pre`.

This does **not** rewrite mix sanitizer FAIL. H13/H14/H15 did not authorize a carrier. Live mix authorization is Gate v2. Do not generate `950000`. Do not retune spent confirmation seeds.

Spec: `cycle8-post-sanitizer-sequences-v1`. Evidence: `evidence/h15-local/`.

## H16. Threat-model audit

`VERIFIED` as an audit of the gate itself, not another carrier search. H9-H15 all returned negatives; H16 asks whether the gate that produced them is correct. It is not.

**The search space was empty by construction on the executed A/B oracle.** A HarfBuzz advance-and-ink oracle over 286719 assigned code points finds 396 invisible code points in the Chromium `pre` font between latin `A` and `B`. Every one is `Mn` or `Cf`, in 15 contiguous ranges. The required bundle strips exactly `Mn`, `Cf`, and default-ignorable, so invisibility and required-bundle survival are complementary sets on that oracle. The intersection is 0. The original H16 write-up advertised 12 shaping contexts; the committed scan executed only latin `A`/`B` (Codex P1). That overclaim is recorded. The scan tool now iterates all 12 advertised contexts. The corrected 12-context rescan is recorded in `evidence/h16-local/shaping-closure-12context.json` and does not rewrite the frozen A/B artifact: union still 396, all Mn or Cf, intersection still 0; product-context union 396; arabic 390; digit/punct/start 395. Script contexts on DejaVu Sans Mono may be missing-glyph behavior. The oracle agrees with real Chromium pixels on 20 of 23 stratified samples; all three disagreements are understood and none weakens the A/B closure.

The other transformation classes close too. Substitution: 14 code points render as an ASCII space, all 14 NFKC-collapse to `U+0020`, none survives. Canonical re-encoding: the declared ASCII input domain is a fixed point of all four normalization forms. Deletion and reordering change visible text. The single remainder in all of Unicode is `Cc`, which ordinary-plain-text excludes — the H12 result, now shown to be unique rather than one option among many.

**Production detectors do not apply these sanitizers.** SynthID-Text scores model tokens, so the tokenizer is the real normalizer. The Gemma tokenizers it is deployed on declare only the SentencePiece whitespace `Replace` and strip no `Mn`, `Cf`, or `Cc`; all nine probe carriers reach the token stream and a 5-token sentence becomes 22-23 tokens. The only tokenizers that drop anything are the two SentencePiece `Precompiled` ones, and what they drop is DEL — inverting the gate, which permits `Cc` and forbids `Mn`/`Cf`.

**The stress sanitizers are not deployable.** Mn-strip corrupts 5 of 7 ordinary multilingual samples and default-ignorable-strip corrupts 4 of 7. Thai loses every vowel and tone mark, Hebrew loses all niqqud, Hindi `नहीं` becomes `नही`, Persian loses its ZWNJ, and `👨‍👩‍👧` becomes three separate people. No platform can run these as preprocessing.

**The gate is wrong on scope and on form.** On scope, the frozen product contract classifies `default_ignorable_removal` and `nonspacing_mark_removal` as `stress_only_not_frozen`, yet `required_sanitizers_keep` treats both as hard requirements. That is the entire blockage: mix survives 21/21 frozen sanitizer fixtures and every other publishability gate passes, so `sanitizer_weaknesses` fails only on those two. On form, the gate asks for carrier fixed-point survival `S(T(x)) == T(x)`, which is strictly stronger than the product goal that detection fail after sanitization.

**One sanitizer is real, and it is not either stress sanitizer.** The `UnicodeSanitizer` in `jwkirchenbauer/lm-watermarking` ships on by default and runs before tokenization. It is NFC plus a fixed BMP regex plus `Cc`-strip, and its matches are replaced with a space rather than deleted. Measured here it keeps 366 of the 396 invisible code points including `U+034F`, removes `U+FE00`, injects spurious spaces, corrupts 5 of 7 ordinary samples, and does not restore the unwatermarked source. Because it is real, `proposed_gate_v2` requires it.

**Mix still evades the real sanitizer.** Measured on the exploratory lane, seed 890000 with GPT-2 and 48 watermarked rows: pristine detects 47/48, and mix detects 0/48 under raw, NFKC, Cf-strip, and the lm-watermarking `UnicodeSanitizer` alike. That sanitizer collapses space runs and strips `Cc`, so it could have suppressed detection by itself; the carrier-free control rules that out, detecting 46/48. It costs one row of detection power on its own, so the drop to zero belongs to the carrier. The only variant that restores detection is the required bundle, at 47/48 — and it restores the original string on 96/96 rows. That is the mechanism behind the whole H12-H15 blockage: the bundle does not defeat the carrier, it deletes it and hands the detector back the untouched watermarked text. No spent or forbidden seed is used.

**Where the corrected gate stands.** Reading the existing mix-freeze confirmation evidence against the frozen sanitizers: identity detects 185/192, mix detects 0/192 watermarked and 0/192 unwatermarked, visible text passes 192/192, and every frozen sanitizer still detects 0. The real-sanitizer condition is now confirmation-grade on seeds `1200000` / `1210000` / `1220000`: mix **0/192** after the UnicodeSanitizer, carrier-free **182/192**, drop 6 from identity **188/192**, visible **192/192**. The H16 audit recorded Gate v2 as `confirmed_not_product_authorized`. Live Gate v2 is now `confirmed_and_product_authorized` after a separate engineering step. The audit file itself is not rewritten.

`proposed_gate_v2` in the H16 audit spec remains `proposal_only_not_active` as a historical draft. Formal Gate v2 is `cycle8-publishability-gate-v2`. It adds frozen Cycle 7 sanitizer `ws_collapse_nfkc_cf_strip` versus the H16 draft. This does **not** rewrite mix sanitizer FAIL and does not relax `required_sanitizers_keep`. Do not generate `950000`. Do not retune spent confirmation seeds `830000` / `840000` / `850000` or `1200000` / `1210000` / `1220000`.

Spec: `cycle8-threat-model-audit-v1` and `cycle8-publishability-gate-v2`. Evidence: `evidence/h16-local/`. Protocol: `docs/cycle8/gate-v2.md`.

## Rejected as product mechanisms

| Mechanism | Label | Why |
| --- | --- | --- |
| Contractions / Cycle 7 durable edits | `PRODUCT_DISQUALIFIED` | visible words or punctuation change |
| Cycle 6 U+0020 runs | `PRODUCT_DISQUALIFIED` | visible spacing change |
| U+200C / other Cf | `REJECTED` as durable; diagnostic only | Cf-strip restores the original string |
| Enclosing marks (Me, probe U+20DD) | `REJECTED` | survive Mn/DI/Cf-strip but change Chromium `pre` pixels |
| NBSP / hair spaces / dashes / homoglyphs | `REJECTED` | visible or NFKC-mapped layout/glyph change |
| C0 tofu (U+0001..U+0008, U+000E..U+001F) | `REJECTED` | survive the required sanitizers; Chromium `pre` pixels change |
| NUL (U+0000) | `REJECTED` as product-ordinary text | Chromium pixels match; C-string / ordinary-text hazard |
| FF / VT / NEXT LINE / CR / TAB / LF | `REJECTED` | newline or layout change even when some Chromium surfaces ignore them |
| Braille blank / Ogham space / PUA / noncharacters | `REJECTED` | sanitizer-survive in some cases; Chromium `pre` pixels change |
| Spacing combining marks (`Mc`) | `REJECTED` | survive required sanitizers; Chromium `pre` pixels change |
| NFKC-stable modifier letters (`Lm`) | `REJECTED` | survive required sanitizers; Chromium `pre` pixels change |
| Egyptian blanks / Indic gap fillers / U+FFFC | `REJECTED` | sanitizer-survive with width; Chromium `pre` pixels change |
| Hangul filler sequences | `REJECTED` | default-ignorable; DI-strip restores the source |
| CSI-filtered C1 subset | `PRODUCT_DISQUALIFIED` | still `Cc`; Chromium host-dependent; not ordinary text |
| Grapheme prepend plus Latin base | `REJECTED` | sanitizer-survive; Chromium `pre` pixels change |
| Joining connectors (tatweel / nirugu) | `REJECTED` | sanitizer-survive; Chromium `pre` pixels change |
| Hangul L plus V composition | `REJECTED` | NFC or NFKD rewrites the representation |
| Bidi isolate wrap | `REJECTED` as durable | pixel-equal on LTR here; Cf-strip restores the source |
| ISO-6429 escape sequences | `PRODUCT_DISQUALIFIED` | sanitizer-survive as `Cc` plus ASCII; parameters stay visible |
| Mix plus DEL remainder | `PRODUCT_DISQUALIFIED` | leftover is still H12 `Cc` |

## Baseline

U+200C after ASCII word spaces: visibility-aligned on the v1 projection, Cf-fragile, and Chromium-pixel-`REJECTED`. Keep as the diagnostic control. Do not promote to release.
