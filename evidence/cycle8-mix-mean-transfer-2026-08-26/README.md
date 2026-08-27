# Cycle 8 mix Mean versus Weighted Mean transfer

Status: `HYPOTHESIS`. Not confirmation. Not a second model. Not product authorization.

This scores the frozen mix apply `u034f-ufe00-letter-alt-v1` on the spent confirmation *source* texts from seeds `830000`, `840000`, and `850000`. It does not regenerate those corpora. It does not retune sites. Residual transformed text is not stored; only source hashes and mix payload hashes are kept.

Both families are computed from one Hugging Face GPT-2 SynthID observation adapter (`HuggingFaceSynthIDAdapter`, model `openai-community/gpt2`) at the frozen threshold `0.5570987654320988`.

## Result

| Family | Mix WM | Mix UW | Identity WM | Identity UW | Mix WM max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weighted Mean | **0/192** | 0/192 | 185/192 | 2/192 | 0.524300 |
| Mean | **0/192** | 0/192 | 187/192 | 1/192 | 0.520947 |

Weighted Mean mix max `0.5243003808577579` matches the frozen confirmation scorecard. Identity Weighted Mean 185/192 and 2/192 match confirmation identity counts. That is a sanity check that this runner used the same apply and scoring path. It is not a new 0/192 confirmation.

Mean 0/192 is the same observations with a different aggregator. It is not an independent model, not a proprietary detector, and not Bayesian-family evidence.

`product_authorized` is false. Do not generate `950000`. Do not rerun looking for zero.
