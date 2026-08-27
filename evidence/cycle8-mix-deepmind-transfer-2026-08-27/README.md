# Cycle 8 mix DeepMind 30-key transfer

Status: `HYPOTHESIS`. Confirmation-scale independent configuration. Not mix-freeze confirmation. Not a second model. Not product authorization.

Seeds `1060000`, `1070000`, and `1080000` were reserved in `global-seed-ledger-v1` before generation. Each is a 64-pair corpus of GPT-2 continuations from `synthid_text.SynthIDGPT2LMHeadModel` with DeepMind `DEFAULT_WATERMARKING_CONFIG` (30 keys). Detection used official `synthid_text.logits_processing.SynthIDLogitsProcessor` weighted mean at frozen threshold `0.5570987654320988`.

This is not Hugging Face `SynthIDTextWatermarkingConfig`, not the Cycle 6 nine-key adapter, and not Mean-versus-Weighted-Mean on the same observations. It is still `openai-community/gpt2`, so `second_model` is false.

Frozen mix apply `u034f-ufe00-letter-alt-v1` was scored on these texts. Residual mix text is not stored in this combined scorecard.

Seed `920000` n=16 was a prior exploratory look on the same stack and is not part of this 0/192.

## Combined result

| Arm | Detected |
| --- | ---: |
| Identity WM | **189/192** |
| Mix WM | **0/192** |
| Identity UW | **0/192** |
| Mix UW | **0/192** |

Mix WM max `0.5067599700507657`. Visible projection passed on every row.

| Seed | Identity WM | Mix WM | Mix UW | Mix WM max |
| ---: | ---: | ---: | ---: | ---: |
| 1060000 | 63/64 | 0/64 | 0/64 | 0.505630 |
| 1070000 | 63/64 | 0/64 | 0/64 | 0.502999 |
| 1080000 | 63/64 | 0/64 | 0/64 | 0.506760 |

Do not rewrite mix-freeze confirmation. Do not generate `950000`. Do not retune mix sites.
