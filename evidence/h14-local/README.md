# H14 post-sanitizer extended class

Status: `VERIFIED` as a negative extension of H13. Not product authorization. Mix sanitizer robustness stays **FAIL**.

This folder records local research that went beyond assigned width-0 insertion and beyond H13's handful of empty-glyph probes.

## What was measured

- Project `Default_Ignorable` ranges match Unicode 15.0 `DerivedCoreProperties`.
- 419 `Mc` and 128 NFKC-stable `Lm` code points survive the required sanitizer bundle. None have product display-width 0.
- Designed blanks and gap fillers (Egyptian hieroglyph blanks, Indic gap fillers, Braille blank, Ogham space, U+FFFC) survive those sanitizers with nonzero width.
- Hangul jamo fillers U+115F+U+1160 and Hangul filler U+3164 are default-ignorable and die to default-ignorable-strip.
- NBSP, U+02B0, and U+FF9E/U+FF9F die to NFKC.
- DejaVu Sans Mono has no sanitizer-surviving simple empty zero-advance glyph.
- Chromium `pre` pixels: Mc, Lm, designed blanks, PUA, noncharacters, and layout separators `REJECTED`. CGJ remains pixel-equal and sanitizer-fragile. The only sanitizer-surviving pixel-equal probes on this host were `Cc` (DEL, NUL, CSI-filtered C1), which H12 already recorded as host-dependent and not ordinary text.

`scan.json` is a local working dump and is not committed. Spec: `specs/cycle8/fuckmark-cycle8-post-sanitizer-extended-class-v1.json`.

Do not generate `950000`. Do not retune spent confirmation seeds `830000` / `840000` / `850000`.
