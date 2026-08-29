# Four-layer restore census (2026-08-29)

Exploratory restore-only census of frozen Gate v2 confirmation watermarked sources from seeds `1200000`, `1210000`, and `1220000` after live four-layer mix (`u034f-ufe00-cc-me-cf-letter-alt-v1`). Detector scores were not computed. Confirmation artifacts were not rewritten and were not used to retune the mix. Status: `HYPOTHESIS`. Do not generate `950000`.

Visible projection stays identical (`192/192`). UnicodeSanitizer mutates `166/192` frozen sources even without mix (`26/192` are US-stable). Historical triple-layer mix under Mn then Me then UnicodeSanitizer matches `UnicodeSanitizer(source)` on every row (`192/192`) and equals the raw source on the `26` US-stable rows. Live four-layer mix keeps Egyptian hieroglyph format-control residuals (U+13430-U+1343F) after Mn then Me then UnicodeSanitizer (`0/192` restore, `0/192` match to `UnicodeSanitizer(source)`, Cf residual on `192/192`). Adding frozen Cf-strip after that path matches `UnicodeSanitizer(source)` again (`192/192`).

This is not a new confirmation corpus and is not a detector result.

| Arm | Restores source | Matches UnicodeSanitizer(source) |
| --- | ---: | ---: |
| Live four-layer raw | 0/192 | 0/192 |
| Live four-layer + Mn then UnicodeSanitizer | 0/192 | 0/192 |
| Live four-layer + Mn then Me then UnicodeSanitizer | **0/192** | **0/192** |
| Live four-layer + DI then Me then UnicodeSanitizer | 0/192 | 0/192 |
| Live four-layer + Mn then Me then Cc-strip | 0/192 | 0/192 |
| Live four-layer + required-bundle then UnicodeSanitizer | 0/192 | 0/192 |
| Live four-layer + Mn then Me then US then Cf-strip | 26/192 | 192/192 |
| Historical triple-layer + Mn then Me then UnicodeSanitizer | 26/192 | 192/192 |
