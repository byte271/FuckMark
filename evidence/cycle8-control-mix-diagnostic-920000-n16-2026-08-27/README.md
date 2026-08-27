# Cycle 8 control-mix diagnostic (seen seed 920000)

Status: `HYPOTHESIS`. Seen corpus. Not independent generation. Not confirmation. Not mix-freeze confirmation. Not product authorization.

This rescores the already generated DeepMind 30-key GPT-2 n=16 texts from seed `920000` after applying `cc-del-c1-letter-alt-v1` (H12). Residual control-mix text is not stored. Source texts remain in `evidence/cycle8-mix-deepmind-30key-920000-n16-2026-08-27/samples.json`.

Detection used official `synthid_text.logits_processing.SynthIDLogitsProcessor.compute_g_values` with weighted mean at the frozen Cycle 6 threshold `0.5570987654320988`. Identity and frozen mix were rescored on the same rows as a scorer check.

Required sanitizers (Mn-strip, default-ignorable-strip, Cf-strip, NFC, NFKC, NFKD, frozen Cycle 6/7 variants, and the combination) kept every control-mix string. Visible projection passed on every row. Mix publishability sanitizer stays FAIL because mix still uses U+034F / U+FE00.

## Result

| Arm | Detected |
| --- | ---: |
| Identity WM | **16/16** |
| Control-mix WM | **0/16** |
| Mix WM | **0/16** |
| Identity UW | **0/16** |
| Control-mix UW | **0/16** |
| Mix UW | **0/16** |

Control-mix WM max score `0.505336937084192`. Do not treat this seen n=16 look as confirmation. Do not generate `950000`. Do not retune mix sites. Public CLI stays empty.
