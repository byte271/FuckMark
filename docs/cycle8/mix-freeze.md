# Cycle 8 mix freeze

Status: frozen development mechanism. Not product authorization. Confirmation not yet generated.

Freeze identity: `cycle8-mix-freeze-v1` (`specs/cycle8/fuckmark-cycle8-mix-freeze-v1.json`).

The frozen mechanism is `u034f-ufe00-letter-alt-v1`. It is not in `release_transform_registry()`. `process_text("I do not agree.")` remains unchanged.

## Frozen contract

- exact user-visible projection
- carriers U+034F (even selected-site index) and U+FE00 (odd selected-site index)
- ASCII letter sites outside raw unmerged hard machine spans
- selected-site cap 192
- detector-blind, watermark-key-blind, non-neural, deterministic
- frozen GPT-2 / SynthID Weighted Mean threshold 0.5570987654320988
- sanitizer matrix: raw, NFKC, Cf-strip, NFKC+Cf-strip, whitespace-collapse, combined, NFC

## Development evidence used to freeze

Four independent reserved-before-generation n=64 corpora (`1020000`, `1030000`, `1040000`, `1050000`):

- mix raw transformed WM **0/256**
- mix raw transformed UW **0/256**
- worst mix score **0.519522** versus threshold **0.557099** (gap **0.037577**)

The two-corpus 0/128 scorecard on `1020000`+`1030000` is not rewritten.

## Confirmation protocol

Preregistered. Not generated.

Seeds `830000`, `840000`, and `850000` are reserved for one-shot formal confirmation: 3 x 64 watermarked samples plus matched unwatermarked controls. Generate once under this freeze. Do not rerun looking for zero. Do not retune on residuals. Do not generate `950000`.

## Weaknesses

Mn-strip and default-ignorable-strip remove the carriers. Latin-1 cannot encode them. Low-site rows remain closer to the threshold than high-site rows.
