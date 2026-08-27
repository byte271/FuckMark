# Cycle 8 mix DistilGPT2 second-model transfer

Status: `HYPOTHESIS`. n=16. Not mix-freeze confirmation. Not confirmation-scale. Not product authorization.

Seed `1090000` was reserved in `global-seed-ledger-v1` before generation. The corpus is DistilGPT2 continuations from `synthid_text.SynthIDGPT2LMHeadModel` with DeepMind `DEFAULT_WATERMARKING_CONFIG` (30 keys). Detection used official `synthid_text.logits_processing.SynthIDLogitsProcessor` weighted mean at frozen threshold `0.5570987654320988`.

This is a second model: `distilbert/distilgpt2` revision `2290a62682d06624634c1f46a6ad5be0f47f38aa` versus confirmation `openai-community/gpt2`. Weights differ. The tokenizer remains GPT-2 BPE (vocab 50257). It is not a second keying scheme; `second_configuration` is false.

Independent configuration evidence is the separate DeepMind 30-key GPT-2 transfer on seeds `1060000` / `1070000` / `1080000` (`docs/cycle8/mix-deepmind-transfer.md`).

## Result

| Arm | Detected |
| --- | ---: |
| Identity WM | **16/16** |
| Mix WM | **0/16** |
| Identity UW | **0/16** |
| Mix UW | **0/16** |

Mix WM max `0.5047997827277791`. Visible projection passed on every scored row.

Identity 16/16 shows the DistilGPT2 watermark is live under this stack. Mix 0/16 is a directional transfer look, not a 0/192 confirmation rewrite.

`product_authorized` is false. Do not generate `950000`. Do not add DistilGPT2 n=16 to confirmation-scale families.
