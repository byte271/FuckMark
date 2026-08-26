# Cycle 8 mix freeze confirmation scorecard

One-shot formal confirmation of frozen mechanism `u034f-ufe00-letter-alt-v1` (`cycle8-mix-freeze-v1`). Label: `VERIFIED`. Not product authorization. Public CLI remains empty.

Seeds `830000`, `840000`, and `850000` were preregistered before generation, generated once under the freeze, and are now spent. Do not rerun looking for zero. Do not retune on these corpora. Do not generate `950000`.

Do not collapse this confirmation **0/192** into development mix 0/256, letter-x1 system benchmark 0/128, or experimental letter-x1 0/192. Letter-space on seeds `1000000` and `1010000` remains **1/128**. Do not rewrite that 1/128 as zero.

The freeze spec `specs/cycle8/fuckmark-cycle8-mix-freeze-v1.json` remains the algorithm freeze snapshot (`confirmation: false`, `confirmation_generated: false`). This scorecard is the confirmation outcome.

## Scorecard

| Axis | Result | Label |
| --- | --- | --- |
| Transformed mix raw WM | **0/192** (0/64 + 0/64 + 0/64) | `VERIFIED` |
| Transformed mix raw UW | **0/192** | `VERIFIED` |
| Mix max score | 0.524300 | `VERIFIED` |
| Mix min gap below threshold | 0.032798 | `VERIFIED` |
| Visible mix WM | **192/192** | `VERIFIED` |
| Frozen sanitizers vs raw mix detections | match zeros (NFC, NFKC, Cf-strip, whitespace-collapse, combined) | `VERIFIED` |
| Letter-x1 on the same confirmation corpora | **0/192**, max 0.524425 | `HYPOTHESIS` (not the confirmation arm) |
| Identity WM / UW | 185/192 / 2/192 | control; identity UW is noise, not mix leakage |
| Mn-strip / default-ignorable-strip | remove U+034F and U+FE00 | `REJECTED` durability |
| Latin-1 | cannot encode U+034F or U+FE00 | `REJECTED` |
| Max transformed token count | 612 / 1024 | below GPT-2 context |
| Product authorization | false | CLI remains empty |

See `scorecard.json` for the machine-readable copy. Per-corpus detector files are in the sibling confirmation directories.

## Confirmation detector corpora

Protocol: identity vs letter-x1 vs letter-alt, frozen sanitizer matrix including NFC, CPU, detector-blind, watermark-key-blind, non-neural. Algorithm version `cycle8-mix-confirmation-detector-compare-v1`.

| Seed | Role | Mix raw WM | Mix UW | Visible mix WM | Mix max | Closest mix gap |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 830000 | mix formal confirmation primary | 0/64 | 0/64 | 64/64 | 0.519600 | 0.037499 |
| 840000 | mix formal confirmation replication | 0/64 | 0/64 | 64/64 | 0.524300 | 0.032798 |
| 850000 | mix formal confirmation holdout | 0/64 | 0/64 | 64/64 | 0.516948 | 0.040151 |
| **Combined** | one-shot 3 x 64 | **0/192** | **0/192** | **192/192** | **0.524300** | **0.032798** |

Closest confirmation mix residual geometry only: `cycle8-840000-35-structured_instructional-watermarked`, 45 insertions, score 0.524300. Residual text was not inspected to write lexical rules.

Identity unwatermarked on seed `830000` is 2/64. Mix unwatermarked detections are 0/192. Fail-closed identity count is 0. Per-domain mix raw WM is 0/16 on all four domains in each corpus.

## Mechanism

Frozen detector-blind U+034F / U+FE00 alternating insertions after ASCII letters outside raw unmerged hard machine spans. Even selected-site index receives U+034F; odd receives U+FE00. Selected-site cap 192. Visible projection must equal the source. Not in `release_transform_registry()`. `process_text("I do not agree.")` is unchanged.

## What this does not rewrite

- development mix 0/128 on `1020000`+`1030000` (`cycle8-mix-margin-scorecard-v1`)
- development mix 0/256 including `1040000`+`1050000`
- letter-x1 system benchmark 0/128 on `980000`+`990000`
- letter-space 1/128 on `1000000`+`1010000`
- freeze hash `cycle8-mix-freeze-v1`
