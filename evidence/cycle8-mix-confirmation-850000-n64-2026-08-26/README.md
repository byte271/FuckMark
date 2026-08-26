# Cycle 8 mix freeze confirmation detector (seed 850000, 64 pairs)

One-shot formal confirmation of `cycle8-mix-freeze-v1`. Seed `850000` and topic `mix formal confirmation holdout` were preregistered before generation. This corpus is spent. Do not retune on residuals. Do not rerun looking for zero.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F/U+FE00 letter-alt v1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

`decision.json` is the shared scale classifier and still says development classification. The confirmation claim is this README plus `cycle8-mix-confirmation-scorecard-v1`.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 62/64 | 62/64 | 0/64 | 128/128 | 0 | 0.68834 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 184.57 | 0.52366 |
| u034f-ufe00-letter-alt-v1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.01 | 0.51695 |

Closest mix watermarked row geometry only: `cycle8-850000-47-structured_instructional-watermarked`, 192 insertions, score 0.516948, gap 0.040151 below threshold 0.557099. Residual text was not inspected to write lexical rules.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Mix unwatermarked detections are 0/64. Maximum transformed GPT-2 token count on scored mix watermarked rows is 609/1024.

Combined with independent confirmation seeds `830000` and `840000`: mix **0/192** raw WM, mix UW **0/192**, visible mix WM **192/192**, worst mix max 0.524300 from `840000` (gap 0.032798). That combined 0/192 is the one-shot confirmation result. Do not collapse it into development mix 0/256 or letter-x1 0/128.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`.
