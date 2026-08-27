# H16 threat-model audit

Status: `VERIFIED` as an audit of the H12-H15 sanitizer gate. Not product authorization. Mix sanitizer robustness stays **FAIL** and the required sanitizer bundle is unchanged.

H9-H15 searched for a carrier that is invisible to the reader and also survives a required sanitizer bundle. Seven cycles returned negatives. H16 stops searching and asks whether the gate that produced those negatives is the right one.

## 1. The search space was empty by construction

`tools/h16_shaping_closure_scan.py` replaces per-probe Chromium screenshots with a HarfBuzz oracle. A code point counts as invisible only when inserting it leaves both the total advance width and the inked glyph sequence unchanged in the font Chromium resolves for `pre`.

| measurement | value |
| --- | --- |
| assigned code points scanned | 286719 |
| shaping contexts per code point | 12 |
| code points that are a required-bundle fixed point | 267550 |
| code points that are shaping-invisible | 396 |
| shaping-invisible categories | `Mn` 262, `Cf` 134 |
| shaping-invisible outside `Mn`/`Cf` | none |
| **intersection** | **0** |

The 396 invisible code points occupy 15 contiguous ranges and are the familiar invisible set: soft hyphen, CGJ, ALM, Khmer inherent vowels, Mongolian free variation selectors, the zero-width and bidi marks, bidi embedding and isolate controls, word joiner and the invisible operators, variation selectors, BOM, musical combining marks, and the tag characters.

Every one of them is `Mn` or `Cf`. The required bundle strips exactly `Mn`, `Cf`, and default-ignorable. Invisibility and required-bundle survival are therefore complementary by construction, not by coincidence. No further enumeration of code points, sequences, or shaping contexts can find a survivor, because the two sets partition the space.

The other transformation classes close as well:

- **Substitution.** 14 code points render as an ASCII space in the `pre` font. All 14 collapse to `U+0020` under NFKC, so none survives the bundle.
- **Canonical re-encoding.** The declared input domain `U+0009`, `U+000A`, `U+000D`, `U+0020..U+007E` is a fixed point of NFC, NFD, NFKC, and NFKD, so there is no alternate encoding of the same ASCII text.
- **Deletion and reordering.** Both change visible text and are excluded by Priority Zero.

The single remainder in all of Unicode is `Cc`: 63 of the 65 control code points survive the bundle, and Chromium hides them at layout time. The ordinary-plain-text requirement excludes them. That is the H12 result, now shown to be the unique remainder rather than one option among many.

### Oracle validation

`tools/h16_oracle_validation.py` cross-checks the shaping oracle against real Chromium `pre` pixels on a 23-sample stratified set. Agreement is 20/23. All three disagreements are understood:

- `U+200C` ZWNJ: the oracle says invisible, Chromium says visible. The oracle is the more generous of the two, so the true invisible set is even smaller and the closure is stronger.
- `U+007F` DEL and `U+0080` PAD: the oracle says visible because the font has no glyph, Chromium says invisible because Blink drops controls at layout time rather than in the font. This is exactly the `Cc` class, which is tracked separately for that reason.

## 2. Production detectors do not apply these sanitizers

SynthID-Text scores model tokens, so the normalizer that actually matters is the model tokenizer, not a hypothetical external scrubber. `tools/h16_tokenizer_threat_model.py` measures nine carriers spanning `Mn`, `Cf`, and `Cc` against eight locally cached tokenizers.

| tokenizer | declared normalizer | carriers reaching the token stream |
| --- | --- | --- |
| gemma-2-2b-it | `Replace` | 9/9 |
| gemma-3-1b-it | `Replace` | 9/9 |
| gpt2 | none | 9/9 |
| llama-2-7b | `Sequence[Prepend, Replace]` | 9/9 |
| llama-3-8b | none | 9/9 |
| mistral-7b-v0.2 | none | 9/9 |
| xlm-roberta-base | `Precompiled` | 8/9 |
| t5-small | `Precompiled` | 8/9 |

The Gemma tokenizers that SynthID-Text is deployed on declare only the SentencePiece whitespace `Replace`. They strip no `Mn`, no `Cf`, and no `Cc`. A 5-token sentence becomes 22-23 tokens once a carrier is inserted.

The two SentencePiece `Precompiled` (`nmt_nfkc`) normalizers are the only ones that drop anything, and what they drop is DEL. That inverts the project's gate: real normalization removes the one class the gate permits and preserves the classes the gate forbids.

### The one sanitizer that is real

"No production tokenizer strips these" is not the same as "no real sanitizer exists". Exactly one ships on by default in the watermarking ecosystem: the `UnicodeSanitizer` in [`jwkirchenbauer/lm-watermarking`](https://github.com/jwkirchenbauer/lm-watermarking/blob/main/normalizers.py), which `WatermarkDetector` enables via `normalizers=["unicode"]` and applies before tokenization. It is not Mn-strip or default-ignorable-strip. It is NFC, then a fixed BMP regex whose matches are replaced with a **space**, then a space collapse, then `Cc` removal.

Measured against it:

| measurement | value |
| --- | --- |
| restores the unwatermarked source from mix | **no** |
| mix carriers surviving | `U+034F` (`U+FE00` is removed) |
| invisible code points surviving | 366 of 396 |
| injects spurious visible spaces | yes |
| ordinary samples corrupted | 5 of 7 |

Because matches are replaced with a space rather than deleted, running it on mixed text turns `I do not agree with that.` into `I͏ d o͏ n o͏t a͏g r͏e e͏ w i͏t h͏ t h͏a t͏.` — the CGJ survives, `U+FE00` becomes a space, and word boundaries move. The sanitizer does not recover the original string; it produces mangled text. It is also lossy on ordinary input, splitting `👨‍👩‍👧` into three people separated by spaces and breaking the Persian ZWNJ and the Devanagari conjunct.

Because this sanitizer is real, `proposed_gate_v2` **requires** it. Whether the detector fires on its output is not measured here and is recorded as `UNMEASURED`.

## 3. The stress sanitizers are not deployable

`tools/h16_sanitizer_deployability.py` runs each sanitizer in the bundle over ordinary, non-adversarial text where every code point is needed to spell the sentence correctly.

| sanitizer | contract category | samples corrupted |
| --- | --- | --- |
| nfc | frozen | 1/7 |
| nfkc | frozen | 1/7 |
| cf_strip | frozen | 3/7 |
| mn_strip | `stress_only_not_frozen` | 5/7 |
| default_ignorable_strip | `stress_only_not_frozen` | 4/7 |

Examples of the collateral damage:

- Thai `ฉันไม่เห็นด้วย` becomes `ฉนไมเหนดวย` under Mn-strip. Every vowel and tone mark is gone.
- Hebrew `אֲנִי לֹא מַסְכִּים` loses all niqqud.
- Hindi `नहीं` becomes `नही`.
- Persian `نیستم‌ها` loses the ZWNJ that separates the words.
- The emoji family `👨‍👩‍👧` becomes three separate people.

A detector vendor cannot run Mn-strip or default-ignorable-strip as preprocessing without corrupting ordinary user text across Indic, Semitic, Southeast Asian, and emoji content. These are stress tests, not countermeasures.

## 4. The gate is wrong on scope and on form

**Scope.** The frozen product contract `specs/fuckmark-user-visible-invariance-v1.contract.json` classifies `default_ignorable_removal` and `nonspacing_mark_removal` as `stress_only_not_frozen`. `required_sanitizers_keep` treats both as hard requirements. H12-H15 gated on sanitizers the contract never required.

This is the whole of the blockage. Mix survives 21/21 frozen sanitizer fixtures. It dies to mn-strip and default-ignorable-strip on 21/21. Every other publishability gate — reproducibility, visibility invariance, software compatibility, cross-detector generalization — already passes. `sanitizer_weaknesses` is the only FAIL, and it fails only on the two stress-only sanitizers.

**Form.** The gate asks whether the carrier is a fixed point of every sanitizer, `S(T(x)) == T(x)`. The product goal is that detection fail after sanitization. Fixed-point survival is sufficient for that but not necessary, so the gate is strictly stronger than the goal it stands in for.

## 5. Where the corrected gate stands on evidence already on record

Reading the already-recorded frozen confirmation evidence against `proposed_gate_v2` — without running any new corpus and without retuning any spent seed — the frozen conditions are already satisfied:

| measurement | value |
| --- | --- |
| watermarked detected at identity | 185/192 |
| watermarked detected after the mix transform | 0/192 |
| unwatermarked detected after the mix transform | 0/192 |
| visible-text pass rate | 192/192 |
| detected after `nfc` / `nfkc` / `cf_strip` / `nfkc_cf_strip` / `ws_collapse` / `ws_collapse_nfkc_cf_strip` | 0 each |
| frozen sanitizer fixture survival | 21/21 |

One condition is **not** satisfied and is recorded as `UNMEASURED`: detection after the lm-watermarking `UnicodeSanitizer`. That sanitizer removes `U+FE00`, keeps `U+034F`, and injects spaces, so mix reaches the detector in a materially different form than under the frozen sanitizers. Answering it needs a detector run, which this record does not perform.

So `proposed_gate_v2` is **not** claimed to be satisfied. What the evidence does show is that the remaining work is one measurement plus a decision about which sanitizers the gate should require — not a further carrier search, which the closure result rules out entirely.

## What this does not do

This record is an audit. It does not authorize a mechanism, does not relax `required_sanitizers_keep`, and does not rewrite the mix verdict. `proposed_gate_v2` in the spec is marked `proposal_only_not_active`; adopting it needs an explicit product decision and a fresh confirmation run on an unspent corpus.

Spec: `specs/cycle8/fuckmark-cycle8-threat-model-audit-v1.json`.

Artifacts in this folder: `shaping-closure.json`, `oracle-validation.json`, `tokenizer-threat-model.json`, `sanitizer-deployability.json`.

Reproduce with the research extra:

```text
python -m pip install -e ".[research]"
python tools/h16_shaping_closure_scan.py --out evidence/h16-local/shaping-closure.json
python tools/h16_oracle_validation.py
python tools/h16_tokenizer_threat_model.py
python tools/h16_sanitizer_deployability.py
```

Do not generate `950000`. Do not retune spent confirmation seeds `830000` / `840000` / `850000`.
