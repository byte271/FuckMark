# Cycle 8 mix DeepMind 30-key transfer (seed 920000)

Status: `HYPOTHESIS`. Not confirmation. Not a second model. Not product authorization.

Reserved Cycle 8 secondary exploratory seed `920000` (`invisible carrier development`) generated watermarked and unwatermarked 64-token continuations with `synthid_text.SynthIDGPT2LMHeadModel` on `openai-community/gpt2` using DeepMind `DEFAULT_WATERMARKING_CONFIG` (30 keys). Detection used official `synthid_text.logits_processing.SynthIDLogitsProcessor.compute_g_values` with weighted mean at the frozen Cycle 6 threshold `0.5570987654320988`.

This is an independent **configuration and implementation**: Google `synthid-text` mixin generation and official logits processor, 30 keys, sampling table 65536. It is not Hugging Face `SynthIDTextWatermarkingConfig` and not the Cycle 6 nine-key adapter. It is still GPT-2, so `second_model` is false.

Frozen mix apply `u034f-ufe00-letter-alt-v1` was scored on these fresh texts. Residual mix text is not stored in the scorecard; source texts are in `samples.json` so mix hashes can be replayed.

## Result

| Arm | Detected |
| --- | ---: |
| Identity WM | **16/16** |
| Mix WM | **0/16** |
| Identity UW | **0/16** |
| Mix UW | **0/16** |

Mix WM max score `0.5063963600986625`. Visible projection passed on every row.

Do not treat this n=16 look as mix-freeze confirmation. Do not generate `950000`. Do not retune mix sites.
