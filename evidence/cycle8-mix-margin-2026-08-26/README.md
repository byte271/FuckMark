# Cycle 8 letter-mix margin scorecard

Measurement of the development mechanism `u034f-ufe00-letter-alt-v1`. Not confirmation. Not a freeze. Not product authorization. Public CLI remains empty.

Do not collapse this fresh **0/128** into the letter-x1 system benchmark 0/128 or the experimental letter-x1 0/192. Letter-space on seeds `1000000` and `1010000` remains **1/128**. Do not rewrite that 1/128 as zero.

Independent scale seeds `1040000` and `1050000` later measured mix **0/256** with worst max 0.519522 (gap 0.037577). That 0/256 is additional development scale. This scorecard remains the two-corpus 0/128 measurement and is not rewritten.

Formal confirmation readiness: `NOT_READY` as a property of this two-corpus 0/128 measurement hash. Closest fresh mix score is 0.513691 versus threshold 0.557099 (gap 0.043407). The mechanism was later frozen as `cycle8-mix-freeze-v1` and confirmed once on seeds `830000` / `840000` / `850000`. This scorecard is not rewritten as that confirmation result.

## Scorecard

| Axis | Result | Label |
| --- | --- | --- |
| Fresh mix raw WM | **0/128** (0/64 + 0/64) | `HYPOTHESIS` |
| Fresh mix raw UW | **0/128** | `HYPOTHESIS` |
| Fresh mix max score | 0.513691 | `HYPOTHESIS` |
| Fresh mix min gap below threshold | 0.043407 | `HYPOTHESIS` |
| Fresh letter-x1 on the same corpora | **0/128**, max 0.527389, gap 0.029709 | `HYPOTHESIS` |
| Letter-x1 system benchmark 980000+990000 | **0/128**, max 0.554066, gap 0.003032 | `HYPOTHESIS` |
| Letter-space spent 1000000+1010000 | **1/128** | `HYPOTHESIS` |
| Fixture visible projection | **3/3** | `VERIFIED` |
| Chromium `pre` / textarea / contenteditable | pixel-equal on measured mix fixtures | `VERIFIED` |
| Frozen sanitizers vs raw mix detections | match | `VERIFIED` |
| Mn-strip / default-ignorable-strip | remove U+034F and U+FE00 | `REJECTED` durability |
| NFC / NFKC / Cf-strip / whitespace-collapse | survive | `VERIFIED` |
| Latin-1 | cannot encode U+034F or U+FE00 | `REJECTED` |
| Max transformed token count | 604 / 1024 | below GPT-2 context |
| Deterministic output | 5/5 identical SHA-256 | `VERIFIED` |

See `scorecard.json` and `local-system.json` for the machine-readable copy. Detector provenance is in `environment.json`.

## Fresh detector corpora

Protocol: identity vs letter-x1 vs letter-alt, frozen sanitizer matrix including NFC, CPU, no CUDA, detector-blind.

| Seed | Role | Mix raw WM | Letter-x1 raw WM | Identity WM | Mix max | Closest mix gap |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1020000 | primary, reserved before generation | 0/64 | 0/64 | 64/64 | 0.513691 | 0.043407 |
| 1030000 | independent replication | 0/64 | 0/64 | 64/64 | 0.513071 | 0.044027 |
| **Combined** | two independent n=64 corpora | **0/128** | **0/128** | 128/128 | 0.513691 | 0.043407 |

Closest mix residual geometry only: `cycle8-1020000-29-technical_explanation-watermarked`, 192 insertions, score 0.513691. Residual text was not inspected to write lexical rules.

Identity unwatermarked on seed `1030000` is 1/64. Mix unwatermarked detections are 0/64 on both corpora.

Per-domain fresh mix (32 watermarked rows per domain):

| Domain | detected | max score |
| --- | ---: | ---: |
| conversational_prose | 0/32 | 0.508488 |
| general_explanatory | 0/32 | 0.513071 |
| structured_instructional | 0/32 | 0.509336 |
| technical_explanation | 0/32 | 0.513691 |

No fresh domain is hidden inside the aggregate.

## Mechanism

Detector-blind U+034F / U+FE00 alternating insertions after ASCII letters outside raw unmerged hard machine spans (URLs, email, IPs, dates, currency, percent, numbers, code, paths, CLI flags, markdown destinations). MATH / CITATION / QUOTATION merge-poisoning is not treated as a hard block. Even selected-site index receives U+034F; odd receives U+FE00. Selected-site cap 192. Visible projection must equal the source. Not in `release_transform_registry()`.

## What beats what

On the same frozen detector:

- mix fresh 0/128, max 0.513691, gap 0.043407
- letter-x1 on those same mix corpora 0/128, max 0.527389, gap 0.029709
- letter-x1 system benchmark 0/128, max 0.554066, gap 0.003032
- letter-space spent 1/128

Mix is the current strongest product-aligned development result. It is still `HYPOTHESIS`.

## Ready for formal confirmation?

This file remains a measurement report, not a confirmation protocol. `NOT_READY` applies to this 0/128 hash. Later scale seeds `1040000` and `1050000` exist as additional development evidence and are not part of this hash-pinned scorecard. The mechanism was later frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on `830000` / `840000` / `850000` is recorded separately as `cycle8-mix-confirmation-scorecard-v1`. Do not rewrite this 0/128 scorecard. Do not generate `950000`.
