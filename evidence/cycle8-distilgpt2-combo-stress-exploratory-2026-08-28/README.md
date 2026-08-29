# DistilGPT2 combo stress exploratory (2026-08-28)

Exploratory rescore of frozen DistilGPT2 n=16 watermarked sources (`evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/samples.json`). The frozen second-model scorecard was not rewritten. Status: `HYPOTHESIS`. Not confirmation-scale. Tokenizer remains GPT-2 BPE.

Detection used Hugging Face `SynthIDTextWatermarkLogitsProcessor` with DeepMind default 30 keys, `sampling_table_size` 65536, and frozen threshold `0.5570987654320988`. Identity scores on these sources replay the frozen DistilGPT2 identity scores exactly (`16/16`).

Historical dual-layer mix under Mn-strip then UnicodeSanitizer remains detected (`16/16`). Live triple-layer mix (`u034f-ufe00-cc-me-letter-alt-v1`) stays `0/16` on raw, Mn then UnicodeSanitizer, default-ignorable then UnicodeSanitizer, and required-bundle then UnicodeSanitizer. Visible projection is unchanged. Do not generate `950000`.

See `docs/cycle8/mix-second-model-transfer.md`.
