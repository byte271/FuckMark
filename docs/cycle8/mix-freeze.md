# Cycle 8 mix freeze

Status: frozen development mechanism. One-shot confirmation **VERIFIED 0/192**. Not product authorization.

Freeze identity: `cycle8-mix-freeze-v1` (`specs/cycle8/fuckmark-cycle8-mix-freeze-v1.json`). Freeze-time fields stay `confirmation: false` and `confirmation_generated: false`. The confirmation outcome is `cycle8-mix-confirmation-scorecard-v1`.

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

The two-corpus 0/128 scorecard on `1020000`+`1030000` is not rewritten. That 0/256 remains `HYPOTHESIS` development evidence.

## Confirmation result

Generated once. Spent. Do not rerun looking for zero. Do not retune on residuals.

Seeds `830000`, `840000`, and `850000`:

- mix raw transformed WM **0/192**
- mix raw transformed UW **0/192**
- visible mix WM **192/192**
- frozen sanitizers match raw zeros
- worst mix score **0.524300** versus threshold **0.557099** (gap **0.032798**)
- closest geometry: `cycle8-840000-35-structured_instructional-watermarked`, 45 insertions

Evidence: [`evidence/cycle8-mix-confirmation-2026-08-26/`](../../evidence/cycle8-mix-confirmation-2026-08-26/).

Letter-x1 on those same confirmation corpora is also 0/192 (worst max 0.524425). Do not collapse that diagnostic into the mix confirmation claim.

## Weaknesses

Mn-strip and default-ignorable-strip remove the carriers. Latin-1 cannot encode them. Low-site rows remain closer to the threshold than high-site rows. Token expansion remains large.

The five publishability gates in `docs/cycle8/mix-publishability.md` fail-close product promotion: mix is not product-publishable.

Do not generate `950000`. The public CLI remains empty.
