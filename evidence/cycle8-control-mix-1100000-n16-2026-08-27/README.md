# Cycle 8 control-mix exploratory (seed 1100000)

Status: `HYPOTHESIS`. Reserved before generation. Independent corpus. Not confirmation. Not mix-freeze confirmation. Not product authorization.

This generates ASCII 64-token GPT-2 pairs with Google `synthid_text.SynthIDGPT2LMHeadModel` using DeepMind `DEFAULT_WATERMARKING_CONFIG` (30 keys) and scores official `synthid_text.logits_processing.SynthIDLogitsProcessor` weighted mean at frozen threshold `0.5570987654320988`.

Apply path is `cc-del-c1-letter-alt-v1` (H12). Residual control-mix text is not stored in the scorecard. Source texts are in `samples.json`.

n=16. Identity WM **15/16**. Control-mix WM **0/16**. Identity UW **0/16**. Control-mix UW **0/16**. Control-mix WM max `0.5058514183090623`. Visible pass. Required sanitizers keep every control-mix row.

The identity miss is one structured-instructional watermarked row at `0.5568728032677877`, just under the frozen threshold. Do not rewrite 15/16 as 16/16.

Seen diagnostic `920000` is not this corpus. Mix confirmation 0/192 is not transferred. Mix publishability sanitizer stays FAIL. Public CLI stays empty. Do not generate `950000`.
