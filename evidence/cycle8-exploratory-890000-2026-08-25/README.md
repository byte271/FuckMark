# Cycle 8 exploratory detector evidence (seed 890000)

Development-only. Not confirmation. Seed `890000` is the Cycle 8 exploratory ledger entry.

Mechanism under test: U+034F space-carrier x1 (and matched x8 / U+200C / identity arms). Transform selection is detector-blind (`apply_all` at non-overlapping ASCII spaces). Detector access was not used for selection.

Files:

- `fixture-compare.json` — hand fixtures plus attached detector summaries.
- `detector-compare.json` — GPT-2 / Hugging Face SynthID Weighted Mean scores on four ASCII domain pairs.
- `decision.json` — `PROMISING_DEVELOPMENT`, `VISIBLE_INVARIANT_PASS`, `HYPOTHESIS`.

Headline on this tiny corpus (4 watermarked + 4 unwatermarked):

| Arm | WM detected raw | UW detected raw | WM detected after Cf-strip |
| --- | ---: | ---: | ---: |
| identity | 3/4 | 0/4 | 3/4 |
| U+034F x1 | 0/4 | 0/4 | 0/4 |
| U+034F x8 | 0/4 | 0/4 | 0/4 |
| U+200C x1 | 0/4 | 0/4 | 3/4 |

Visible projection pass rate on scored arms: `32/32`.

Do not promote U+034F into `release_transform_registry()`. Do not inspect `830000`, `840000`, `850000`, or Cycle 7 reserved `880000`.
