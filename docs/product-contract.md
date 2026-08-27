# FuckMark product contract

Contract identity: `fuckmark-user-visible-invariance-v1`  
Machine-readable file: `specs/fuckmark-user-visible-invariance-v1.contract.json`

This contract is Priority Zero. Detector score cannot override it.

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
- homoglyphs or compatibility characters.

## Current product path

`release_transform_registry()` is the product registry. It currently authorizes **zero** carriers.

The public CLI (`release-cli-v4`) therefore returns the original text unchanged. That fail-closed behavior is required until a carrier has:

1. exact visible-projection pass;
2. English-ASCII v1 domain evidence;
3. sanitizer evidence (whitespace collapse, and preferably NFKC + Cf-strip);
4. GPT-2 tokenizer disruption evidence;
5. protected machine-span safety;
6. later, replicated detector reduction.

Cycle 8 mix freeze confirmation is not enough. A carrier is product-publishable only after these additional gates all PASS:

1. reproducibility of frozen hashes and deterministic apply;
2. cross-environment visibility invariance on Unicode-capable surfaces;
3. real-world software compatibility on the product surface (UTF-8 only; visible-projection search; Latin-1/ASCII/cp1252 unsupported rather than pretended);
4. known sanitizer weaknesses no longer kill the carriers, or an explicit product decision to accept those sanitizers as out of scope;
5. cross-detector generalization beyond one open GPT-2 SynthID Weighted Mean detector.

`cycle8-mix-publishability-v1` currently fail-closes. Software compatibility now PASSes on that product surface. Sanitizer weaknesses and cross-detector generalization still FAIL. See `docs/cycle8/mix-publishability.md`.

U+200C is not authorized. It is a diagnostic baseline and is removed by Cf stripping.

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

If a candidate would change visible projection, if the input is outside ordinary English ASCII v1, if carrier safety is uncertain, or if a protected machine span would be broken, the product path leaves that region unchanged. It never falls back to a visible edit. Product carrier enumeration also skip-closes any insertion whose trial output would fail the frozen hard-invariant validator.
