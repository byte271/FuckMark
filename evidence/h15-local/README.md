# H15 sequence and representation class

Status: `VERIFIED` as a negative sequence-level extension of H14. Not product authorization. Mix sanitizer robustness stays **FAIL**.

This folder records local research that did not repeat assigned width-0 enumeration or the H14 single-codepoint Mc/Lm/blank sweep. It measures multi-codepoint sequences, grapheme prepend, joining, Hangul composition, bidi wraps, ISO-6429 escapes, partial-sanitizer remainders, and DejaVu Sans Mono GSUB ligatures.

## What was measured

- Thirteen UAX #29 prepend letters survive the required sanitizer bundle. Chromium `pre` rejects Malayalam Dot Reph, Sharada jihvamuliya, Zanabazar RA, and Kawi repha in front of Latin `I`.
- Arabic tatweel, Nko lajanyalan, Mongolian nirugu, and character tie survive those sanitizers and change Chromium `pre` pixels in Latin. ZWJ/ZWNJ die to Cf-strip.
- Hangul L plus V jamo NFC-compose, so NFC rewrites the sequence. The composed syllable NFKD-decomposes, so NFKD rewrites that form. Neither representation survives the required bundle.
- ASCII plus sanitizer-surviving `Mc` does not NFC-compose.
- Matched LRI/FSI plus PDI around LTR English is pixel-equal on this Chromium host and dies to Cf-strip and default-ignorable-strip. RLI and RLO wraps change pixels.
- 7-bit ESC CSI sequences survive the sanitizer bundle because they are `Cc` plus ASCII. Chromium `pre` does not interpret them; the parameter characters stay visible.
- Mix plus DEL stays pixel-equal here. Mn-strip leaves DEL. That remainder is the H12 `Cc` class.
- DejaVu Sans Mono has no sanitizer-surviving zero-advance mapped glyph, including composites. Latin extra-component GSUB ligatures are discretionary `fi`/`fl` to compatibility characters that die to NFKC. Chromium `pre` does not apply that ligature: CGJ between `f` and `i` in `affirm` is pixel-equal.

No measured sequence class is simultaneously sanitizer-surviving, Chromium-portable, ordinary plain text, and Priority-Zero safe.

Spec: `specs/cycle8/fuckmark-cycle8-post-sanitizer-sequences-v1.json`.

Do not generate `950000`. Do not retune spent confirmation seeds `830000` / `840000` / `850000`.
