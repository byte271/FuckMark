# fuckmark-robustness-bench-v1

Public sanitizer-restore robustness bench for the live five-layer mix.
Hash-binding freeze record: `specs/fuckmark-robustness-bench-v1.freeze.json`.
Conformance vectors: `specs/fuckmark-robustness-bench-v1.vectors.json`
(source strings as codepoint arrays only).

This bench answers: after the public mix, do standard Unicode sanitizers restore
the original source? It does **not** rerun GPT-2, SynthID, or any neural
detector. Detector numbers stay on the sealed Gate v2 scorecard.

## 1. Identity

- Algorithm version: `fuckmark-robustness-bench-v1`
- Mix mechanism: `u034f-ufe00-cc-me-cf-ia-letter-alt-v1`
- Python reference: `fuckmark.robustness`
- CLI: `fuckmark robustness`
- Contact: `Fhelp@q1z.org`

A later v2 may add detector adapters from `fuckmark.adapters` as an opt-in
track. This v1 freeze is local, deterministic, and model-free.

## 2. Cell

For each fixture S and attack A:

1. Mix: `M = apply_letter_alternating_mix(S)`.
2. Attack: `T = A(M)`.
3. Record:
   - `restores_source`: `T == S`
   - `mix_projection_equals_source`: visible projection of `M` equals `S`
   - `projection_equals_source`: visible projection of `T` equals `S`
   - `carrier_detected`: closed-set FuckMark insertion scan of `T`
   - `residual_categories`: `fuckmark-hidden-scan-v1` categories still present in `T`
   - `mix_sha256` / `output_sha256`: SHA-256 of UTF-8 `M` and `T`

Visible projection is `project_visible_v1` (approved carriers removed; Me, Cc,
and Cf residuals remain).

## 3. Attacks

Applied to the mixed string, in this order in the catalog:

1. `identity` — no sanitizer
2. `mn_strip` — drop general category Mn
3. `default_ignorable_strip` — drop default-ignorable codepoints
4. `nfc` / `nfkc` / `nfkd`
5. `cf_strip` — drop general category Cf
6. `me_strip` — drop general category Me
7. `cc_strip` — drop general category Cc
8. `unicode_sanitizer` — frozen copy of lm-watermarking `UnicodeSanitizer`
   (NFC, BMP regex to space, collapse spaces, drop Cc)
9. `mn_then_us` / `di_then_us` / `us_then_mn` — orderings of Mn/DI strip and
   UnicodeSanitizer
10. `required_bundle` — NFC, NFKC, Mn-strip, default-ignorable strip, Cf-strip
11. `required_bundle_then_us`
12. `mn_me_us` — Mn-strip, Me-strip, UnicodeSanitizer
13. `mn_me_us_cf` / `di_me_us_cf` — that path plus frozen Cf-strip

UnicodeSanitizer turns interlinear annotation controls into spaces, so Cf-strip
after it cannot rebuild the original spacing.

## 4. Fixtures

Public fixtures are short. They are not the GPT-2 Gate v2 corpus. `digits` has
no eligible letter or emoji site, so mix is a no-op and every attack restores.
Mixed letter/emoji fixtures must not restore under the attacks above.

## 5. Sealed detector track

The Gate v2 confirmation scorecard remains the historical GPT-2 / SynthID
record (identity 188/192 detected; mix 0/192 after required sanitizers;
visible 192/192). This bench hashes that file and the inner `scorecard_hash`.
It does not regenerate those corpora.

## 6. Exit status

`fuckmark robustness` exits 0 when every selected cell matches the frozen
vectors and the sealed scorecard hash still matches. Exit 1 is a mismatch
(mix or sanitizer drift). Exit 2 is usage.
