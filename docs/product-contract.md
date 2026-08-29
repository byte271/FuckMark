# FuckMark product contract

Contract identity: `fuckmark-user-visible-invariance-v1`  
Machine-readable file: `specs/fuckmark-user-visible-invariance-v1.contract.json`

This contract is Priority Zero. Detector score cannot override it. The v1 JSON is immutable. Live approved carriers are filled by product authorization without rewriting that file.

## Rule

`VISIBLE(original) == VISIBLE(transformed)`

The public product path must present the same user-visible text as the input. Byte identity is not required. Visible identity is required.

The v1 projection is insertion-only:

- every original code point remains in the same order;
- no original code point is substituted, deleted, or reordered;
- visible ASCII spaces, tabs, and newlines are immutable;
- the only allowed difference is insertion of *approved* non-rendering carriers.

Conceptually, stripping approved carriers from the transformed string reproduces the original when the original did not already contain those carriers. If the original already contains an approved carrier, the product path fail-closes and inserts nothing.

## What is not enough

These are not product success:

- semantic equivalence;
- meaning preservation;
- "looks natural";
- minor visible difference;
- punctuation-only edits;
- hyphenation or apostrophe substitution;
- extra or missing visible spaces;
- newline / layout changes;
- homoglyphs or compatibility characters;
- the same visible projection implying the same Markdown, path, or search behavior in other software.

## Current product path

`release_transform_registry()` stays empty. The public CLI (`release-cli-v11`) applies `apply_letter_alternating_mix` directly: U+034F on even selected letter/emoji grapheme clusters, U+FE00 on odd sites, plus a cycling C0/C1 control, enclosing Me (U+20DD), a cycling Egyptian hieroglyph format control (U+13430-U+13438), and a cycling interlinear annotation control (U+FFF9-U+FFFB), cap 4096, outside hard machine spans. Latin (including U+00E9), Greek, Cyrillic, Han, Kana, Hangul syllables, and emoji are processed. NFD clusters receive insertions after the combining sequence. Live protection covers fenced/inline/indented code, HTML tags and entities, Markdown destinations and reference labels (including multiline and container forms), URLs including `ftp://`, and paths including `src/main.py`, `scripts/build`, and last-component spaces. Those protection changes can change outputs versus the v0.4.0 freeze of `letter_mix.py` (`cycle8-mix-freeze-v1`, `letter_mix_source_sha256` `b1ceec24e584c0e9e7135ef0c89a3bd249b0bda4a45e07aa7190b1b010ba56d4`). Frozen confirmation hashes stay historical. They are not silently rewritten. `--detect` is a closed-set scan of those approved insertions and is not a general AI-watermark detector.

Live `product_approved_carriers_v1()` is the five-layer set `{U+034F, U+FE00}` plus C0/C1 controls (DEL and C1 except NEL) plus U+20DD plus U+13430-U+13438 plus U+FFF9-U+FFFB. Visible projection strips those carriers; Me may decorate glyphs in some renderers. The v1 contract's empty `product_authorized_carriers_v1` list is a historical snapshot of that file.

Authorization is recorded in `cycle8-publishability-gate-v2` (`confirmed_and_product_authorized`) and `cycle8-product-authorization-v2`. Confirmation does not by itself enable the CLI; the engineering step did.

The Cycle 8 v1 mix publishability report (`cycle8-mix-publishability-v1`) now records dual-layer stress-strip PASS (`product_publishable: true`) while remaining `product_authorized: false` as a historical CLI snapshot (`release-cli-v4`). Gate v2 still records the historical `mix_sanitizer_gate_v1` FAIL and does not weaken `required_sanitizers_keep`. See `specs/cycle8/fuckmark-cycle8-mix-publishability-v1.json`, `specs/cycle8/fuckmark-cycle8-publishability-gate-v2.json`, and `specs/cycle8/fuckmark-cycle8-product-authorization-v2.json`.

U+200C is not authorized. It is a diagnostic baseline and is removed by Cf stripping. H12 control-mix is not authorized.

## Historical research

Historical visible-edit registries remain importable for replay:

- `historical_visible_edit_transform_registry()` / `default_transform_registry()` — contractions;
- `development_transform_registry()` — contractions plus lexical/syntax/surface visible edits;
- Cycle 6 spacing profiles;
- Cycle 7 durable visible-edit catalogs.

They must not become the CLI default.

## Renderer and payload

Output is ordinary Unicode plain text. HTML overlays, custom fonts, canvas, clipboard apps, and hidden metadata are forbidden.

## Failure behavior

If a candidate would change visible projection, if there are no eligible letter or emoji sites, if carrier safety is uncertain, or if a protected machine span would be broken, the product path leaves that region unchanged. It never falls back to a visible edit.
