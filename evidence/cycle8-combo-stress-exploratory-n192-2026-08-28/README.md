# Combo stress exploratory n=192 (2026-08-28)

Exploratory GPT-2 / Hugging Face SynthID Weighted Mean rescore of frozen Gate v2 confirmation watermarked sources from seeds `1200000`, `1210000`, and `1220000`. Confirmation artifacts were not rewritten and were not used to retune the mix. Status: `HYPOTHESIS`. Do not generate `950000`.

Historical mark-only and historical dual-layer mixes under Mn-strip then UnicodeSanitizer remain detected (`182/192`). Live triple-layer mix (`u034f-ufe00-cc-me-letter-alt-v1`) keeps Me/Cc residuals after Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, and the required sanitizer bundle. Weighted-mean GPT-2 SynthID detection stays `0/192` on those live arms. Identity on the same frozen watermarked sources is `188/192`.

This is not a new confirmation corpus and is not a second-model result.

| Seed | Identity | Historical dual Mn then US | Live triple Mn then US | Live triple bundle then US |
| ---: | ---: | ---: | ---: | ---: |
| 1200000 | 64/64 | 61/64 | 0/64 | 0/64 |
| 1210000 | 61/64 | 60/64 | 0/64 | 0/64 |
| 1220000 | 63/64 | 61/64 | 0/64 | 0/64 |
| combined | **188/192** | **182/192** | **0/192** | **0/192** |
