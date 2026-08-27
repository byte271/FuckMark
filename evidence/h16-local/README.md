# H16 threat-model audit

Status: `VERIFIED` as an audit of the H12-H15 sanitizer gate. Not product authorization. Mix sanitizer robustness stays **FAIL** and the required sanitizer bundle is unchanged.

H9-H15 searched for a carrier that is invisible to the reader and also survives a required sanitizer bundle. Seven cycles returned negatives. H16 stops searching and asks whether the gate that produced those negatives is the right one.

## 1. The search space was empty by construction

`tools/h16_shaping_closure_scan.py` replaces per-probe Chromium screenshots with a HarfBuzz oracle. A code point counts as invisible only when inserting it leaves both the total advance width and the inked glyph sequence unchanged in the font Chromium resolves for `pre`.

| measurement | value |
| --- | --- |
| assigned code points scanned | 286719 |
| shaping contexts advertised | 12 |
| shaping contexts executed in the original scan | 1 (latin `A`/`B`) |
| code points that are a required-bundle fixed point | 267550 |
| code points that are shaping-invisible on that A/B oracle | 396 |
| shaping-invisible categories | `Mn` 262, `Cf` 134 |
| shaping-invisible outside `Mn`/`Cf` | none |
| **intersection** | **0** |

The original H16 write-up advertised 12 shaping contexts. Independent review (Codex P1) found that `tools/h16_shaping_closure_scan.py` called `primary.invisible(codepoint)` with the default latin `A`/`B` context and never iterated `SHAPING_CONTEXTS`. Artifact `shaping-closure.json` has no contexts-scanned field. The 286719 / 396 / intersection 0 numbers are therefore **VERIFIED** for latin `A`/`B` only. That overclaim is recorded in `cycle8-threat-model-audit-v1`. The scan tool now iterates all 12 advertised contexts. The corrected measurement is recorded in `shaping-closure-12context.json` and does not overwrite the frozen A/B artifact: union still 396, all `Mn` or `Cf`, intersection still 0; product-context union 396; arabic 390; digit/punct/start 395. Script contexts on DejaVu Sans Mono may be missing-glyph behavior.

The 396 invisible code points occupy 15 contiguous ranges and are the familiar invisible set: soft hyphen, CGJ, ALM, Khmer inherent vowels, Mongolian free variation selectors, the zero-width and bidi marks, bidi embedding and isolate controls, word joiner and the invisible operators, variation selectors, BOM, musical combining marks, and the tag characters.

Every one of them is `Mn` or `Cf`. The required bundle strips exactly `Mn`, `Cf`, and default-ignorable. On the executed A/B oracle, invisibility and required-bundle survival are therefore complementary by construction, not by coincidence.

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

Because this sanitizer is real, `proposed_gate_v2` **requires** it.

`tools/h16_real_sanitizer_detector.py` then measures whether the detector actually fires on its output, on the exploratory lane (seed 890000, GPT-2, 48 watermarked rows). Seed 890000 is the lane CI already runs on every PR; it is not a confirmation corpus, and none of the spent seeds `830000` / `840000` / `850000` or the forbidden `950000` is touched.

| variant | detected, with mix | detected, no mix | rows where the source is restored |
| --- | --- | --- | --- |
| pristine, no transform | 47/48 | — | — |
| raw | 0/48 | 47/48 | 0/96 |
| nfkc | 0/48 | 47/48 | 0/96 |
| cf_strip | 0/48 | 47/48 | 0/96 |
| **lm-watermarking UnicodeSanitizer** | **0/48** | 46/48 | 0/96 |
| required bundle | 47/48 | 47/48 | **96/96** |

Mix evades the real sanitizer exactly as well as it evades raw.

The third column is a control, and it matters. This sanitizer collapses space runs and strips `Cc`, so it damages ordinary text on its own, and a 0/48 could have meant the sanitizer was suppressing detection rather than mix evading it. Applied to carrier-free watermarked text it still detects 46 of 48 against a 47 of 48 baseline. It costs one row of detection power by itself, so the drop to zero is attributable to the carrier.

The fourth column explains the one variant that does restore detection. The required bundle reconstructs the original string on every single row. That is the mechanism behind the whole H12-H15 blockage — the bundle does not defeat the carrier, it deletes it and hands the detector back the untouched watermarked text.

This is an exploratory measurement, not a confirmation run, and it is labelled `exploratory_only_not_confirmation` with `confirmation_grade: false`.

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

The remaining condition, detection after the lm-watermarking `UnicodeSanitizer`, is met too: 0 of 48 on the exploratory lane, against 47 of 48 pristine. Confirmation-grade measurement of that same condition is now on record: seeds `1200000` / `1210000` / `1220000`, mix **0/192** after the UnicodeSanitizer, carrier-free **182/192**, drop 6 from identity **188/192**. See `docs/cycle8/gate-v2.md`.

So every frozen condition of `proposed_gate_v2` now has a measurement behind it. The H16 draft still records `proposed_gate_v2_fully_satisfied` as `false` because that draft's remaining-condition sentence was written against the exploratory lane. Formal Gate v2 is `cycle8-publishability-gate-v2`. At audit time its status was `confirmed_not_product_authorized`. Live status is `confirmed_and_product_authorized`. It adds `ws_collapse_nfkc_cf_strip` versus the H16 draft.

## What this does not do

This record is an audit. It does not authorize a mechanism, does not relax `required_sanitizers_keep`, and does not rewrite the mix verdict. `proposed_gate_v2` in the spec is marked `proposal_only_not_active`. Live product authorization is recorded in Gate v2 and `cycle8-product-authorization-v1`, not in this audit file.

Spec: `specs/cycle8/fuckmark-cycle8-threat-model-audit-v1.json`.

Artifacts in this folder: `shaping-closure.json` (frozen A/B scan), `shaping-closure-12context.json` (12-context rescan), `oracle-validation.json`, `tokenizer-threat-model.json`, `sanitizer-deployability.json`, `real-sanitizer-detector.json`.

Reproduce with the research extra:

```text
python -m pip install -e ".[research]"
python tools/h16_shaping_closure_scan.py --out evidence/h16-local/shaping-closure-12context.json
python tools/h16_oracle_validation.py
python tools/h16_tokenizer_threat_model.py
python tools/h16_sanitizer_deployability.py
```

The detector measurement additionally needs the SynthID runtime:

```text
python -m pip install "torch==2.13.0" --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-smoke.txt
python tools/h16_real_sanitizer_detector.py --pair-count 48
```

Do not generate `950000`. Do not retune spent confirmation seeds `830000` / `840000` / `850000` or `1200000` / `1210000` / `1220000`.
