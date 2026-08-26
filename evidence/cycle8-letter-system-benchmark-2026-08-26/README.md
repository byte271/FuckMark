# Cycle 8 letter-x1 system benchmark

Measurement of the current development mechanism `u034f-letter-x1`. Not confirmation. Not a freeze. Not product authorization. Public CLI remains empty.

Do not collapse this fresh **0/128** into the earlier experimental **0/192**. The 0/192 tally is 128 seen-corpus diagnostic plus 64 independent exploratory pairs on seeds `930000` / `940000` / `970000`. This benchmark uses new seeds `980000` and `990000`, reserved before generation.

Formal confirmation readiness: `NOT_READY`. Closest fresh letter-x1 score is 0.554066 versus threshold 0.557099 (gap 0.003032).

## Scorecard

| Axis | Result | Label |
| --- | --- | --- |
| Fresh letter-x1 raw WM | **0/128** (0/64 + 0/64) | `HYPOTHESIS` |
| Fresh letter-x1 raw UW | **0/128** | `HYPOTHESIS` |
| Fresh letter-x1 max score | 0.554066 | `HYPOTHESIS` |
| Fresh letter-x1 min gap below threshold | 0.003032 | `HYPOTHESIS` |
| Fresh space-x1 on the same corpora | **1/128** | `HYPOTHESIS` |
| Experimental letter-x1 0/192 | **0/192** (128 seen + 64 independent) | `HYPOTHESIS` |
| Frozen historical space-x1 930000+940000 | **1/128** | `HYPOTHESIS` |
| Fixture visible projection | **21/21** | `VERIFIED` |
| Chromium `pre` / textarea / contenteditable | pixel-equal on measured fixtures | `VERIFIED` |
| Safari / terminal pixels | not measured here | `UNKNOWN` |
| Frozen sanitizers vs raw letter detections | match | `VERIFIED` |
| Mn-strip / default-ignorable-strip | remove U+034F | `REJECTED` durability |
| UTF-8 file, CLI stdin, `cat`, xclip, NFC/NFKC/Cf-strip | survive | `VERIFIED` |
| Ordinary vim save | appends trailing newline | `REJECTED` exact bytes |
| vim `binary noeol` | exact bytes | `VERIFIED` |
| Latin-1 | cannot encode U+034F | `REJECTED` |
| Protected spans | **21/21** | `VERIFIED` |
| Non-ASCII input | fail closed | `VERIFIED` |
| Mean insertions (fresh, WM+UW rows) | 186.02 | diagnostic |
| Mean UTF-8 overhead | 372.03 bytes | diagnostic |
| Mean token-count delta | 515.55 | diagnostic |
| Max transformed token count | 608 / 1024 | below GPT-2 context |
| Cap-192 binds | 106 / 128 fresh WM rows | diagnostic |
| Short / medium / long transform | 16 ms / 595 ms / 1482 ms | `SOURCE-BOUND` |
| Deterministic output | 5/5 identical SHA-256 | `VERIFIED` |
| Linux this host | measured | `VERIFIED` |
| macOS / Windows letter transform | CI covers CLI identity only | `SOURCE-BOUND` |

See `scorecard.md` and `scorecard.json` for the machine-readable copy. Detector provenance is in `environment.json`. Per-corpus distributions are in `detector-stats.json`.

## Fresh detector corpora

Protocol: identity vs space-x1 vs letter-x1, frozen sanitizer matrix including NFC, CPU, no CUDA, detector-blind.

| Seed | Role | Letter raw WM | Space raw WM | Identity WM | Letter max | Closest letter gap |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 980000 | primary, reserved before generation | 0/64 | 0/64 | 62/64 | 0.554066 | 0.003032 |
| 990000 | independent replication | 0/64 | 1/64 | 64/64 | 0.527273 | 0.029826 |
| **Combined** | two independent n=64 corpora | **0/128** | **1/128** | 126/128 | 0.554066 | 0.003032 |

Closest letter residual geometry only: `cycle8-980000-04-general_explanatory-watermarked`, 159 insertions, score 0.554066. Residual text was not inspected to write lexical rules.

Space residual geometry only on the fresh pair: `cycle8-990000-14-conversational_prose-watermarked`, 18 insertions, score 0.570619. Do not rewrite frozen `930000` space-x1 1/64 as zero.

Per-domain fresh letter-x1 (32 watermarked rows per domain):

| Domain | detected | max score |
| --- | ---: | ---: |
| conversational_prose | 0/32 | 0.527273 |
| general_explanatory | 0/32 | 0.554066 |
| structured_instructional | 0/32 | 0.514108 |
| technical_explanation | 0/32 | 0.539885 |

No fresh domain is hidden inside the aggregate. The thin margin is in general explanatory prose on seed `980000`.

## Experimental 0/192 (not this benchmark's fresh claim)

| Corpus | Kind | Letter raw WM |
| --- | --- | ---: |
| 930000 n=64 | seen diagnostic | 0/64 |
| 940000 n=64 | seen diagnostic | 0/64 |
| 970000 n=64 | independent exploratory | 0/64 |
| **Total** | **128 seen + 64 independent** | **0/192** |

## What beats what

On the same frozen detector and the same fresh corpora, letter-x1 is 0/128 and space-x1 is 1/128. That is an apples-to-apples scientific improvement, still `HYPOTHESIS`.

Historical methods that change visible text remain `PRODUCT_DISQUALIFIED` even when their detector counts looked strong:

| Mechanism | Detector snapshot | Product |
| --- | --- | --- |
| Cycle 4 exact-survival | 5/192 | `PRODUCT_DISQUALIFIED` visible edits |
| Cycle 6 U+0020 runs | 7/192 formal | `PRODUCT_DISQUALIFIED` visible spacing |
| Cycle 7 durable visible edits | stage research | `PRODUCT_DISQUALIFIED` |
| U+200C space-x1 | tokenizer-disruptive | `REJECTED` (Cf-strip) |
| U+034F space-x1 | frozen 1/128; fresh 1/128 | `HYPOTHESIS`, not authorized |
| U+034F letter-x1 | fresh 0/128; experimental 0/192 | `HYPOTHESIS`, not authorized |

Identity / pristine watermarked detections on the fresh corpora remain high (62/64 and 64/64). The transform is doing the work.

## What breaks it

- Mn-strip and default-ignorable-strip remove U+034F.
- Latin-1 cannot roundtrip U+034F.
- Ordinary vim `wq` appends a trailing newline (carrier codepoints still present; visible projection then includes that extra newline).
- Exact-byte search for substrings such as `do not` can miss after intra-word insertion even though the visible projection still contains `do not`.
- Selected-site cap 192 binds on 106 of 128 fresh watermarked rows. Token expansion is large (mean delta about 516 tokens) but stayed under GPT-2's 1024-token context (max 608).
- Applications that strip nonspacing marks or default-ignorables destroy the carrier. NFC, NFKC, Cf-strip, and whitespace-collapse-v1 do not.

Pearson correlation between insertion count and detector score is weak and sign-unstable across corpora. Insertion count is diagnostic only. It is not used for per-sample runtime selection.

## Runtime

This 4-core Linux CPU host, Python 3.12.3, torch 2.13.0+cpu:

- short (15 chars): about 16 ms/transform
- medium (308 chars): about 595 ms/transform
- long (616 chars): about 1482 ms/transform

Letter-x1 is not a cheap streaming transform on long ASCII. Product CLI still fail-closes, so installed `FuckMark` latency remains the identity path.

## Ready for formal confirmation?

No. `NOT_READY`.

Reasons: the fresh 0/128 has only 0.003 margin on seed `980000`; experimental 0/192 is mostly seen diagnostic; letter-x1 is not frozen; `950000` is ungenerated; Mn-strip removes the carrier; this file is a measurement report, not a confirmation protocol.
