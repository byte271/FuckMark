# Cycle 8 letter-x1 system benchmark methodology

Identity: `cycle8-letter-system-benchmark-v1`. Measurement, not confirmation. Letter-x1 is not in `release_transform_registry()`. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.

This is not a preregistered formal confirmation protocol. It does not consume confirmation-reserve seeds.

## Mechanism under test

Development mechanism `u034f-letter-x1` as implemented on the measured commit: U+034F after ASCII letters, visible-word invariants, quote-interior policy `quote-visible-carrier-v1`, detector-blind selected-site cap 192. The algorithm is not retuned during this benchmark.

Space-x1 remains a comparison baseline on the same detector configuration and the same fresh corpora. Cycle 6 spacing and Cycle 7 visible edits are `PRODUCT_DISQUALIFIED` baselines. U+200C space-x1 is `REJECTED` as a durable product mechanism (Cf-strip restores the source).

Public CLI `process_text` remains identity. `RELEASE_CLI_ALGORITHM_VERSION` remains `release-cli-v4`.

## Detector protocol

Frozen open GPT-2 / Hugging Face SynthID Weighted Mean:

- model `openai-community/gpt2`
- revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`
- implementation `cycle8_hf` / `cycle8-letter-system-benchmark-detector-v1`
- threshold `0.5570987654320988`
- comparison `score >= threshold`
- detector-blind selection (`detector_access_used_for_selection=false`)
- no watermark secret
- FPR assumption: frozen Cycle 6 GPT-2 / Hugging Face SynthID Weighted Mean threshold

Sanitizer matrix (frozen): `raw`, `nfc`, `nfkc`, `cf_strip`, `nfkc_cf_strip`, `ws_collapse`, `ws_collapse_nfkc_cf_strip`.

Stress sanitizers (benchmark-only, not frozen): `mn_strip`, `default_ignorable_strip`, `nfkd`.

## Seeds

Reserved in `global-seed-ledger-v1` before generation:

| Seed | Role | Topic | Pairs | Use |
| --- | --- | --- | ---: | --- |
| 980000 | letter_benchmark_primary | `letter carrier system benchmark` | 64 | fresh unseen benchmark |
| 990000 | letter_benchmark_replication | `letter carrier benchmark replication` | 64 | independent fresh replication |

Generation uses the frozen Cycle 8 four-domain template cycle (`general_explanatory`, `technical_explanation`, `conversational_prose`, `structured_instructional`), 16 pairs per domain per corpus.

Do not treat `890000`..`970000` as unseen benchmark data. Previous letter-x1 detector artifacts (`930000`, `940000`, `970000`) are reported as experimental / SOURCE-BOUND development evidence. The experimental 0/192 split (128 seen + 64 independent) is not rewritten and is not this benchmark's fresh 0/128.

Confirmation reserves `830000` / `840000` / `850000` are unused and uninspected. `950000` remains ungenerated.

## Local system arms

22 fixtures cover ordinary prose, quotes, punctuation, newlines, longer paragraphs, sparse short text, and machine-sensitive spans (URL, email, path, code, shell, numbers/dates, markdown destination, hash). Product-domain rejection is checked on non-ASCII input.

Every product-eligible fixture row requires exact `project_visible_v1` equality plus original visible characters, visible spaces, line breaks, punctuation, and character order. Machine-span identity is checked for URLs, emails, paths, code, numbers, dates, hashes, and markdown destinations.

Rendering uses Chromium headless PNG byte equality on `pre` (short paragraph and quote-heavy), plus `textarea` and `contenteditable` on the short paragraph. Safari/WebKit is UNKNOWN on Linux. Terminal pixels are UNKNOWN; display-column width is measured.

Roundtrips: UTF-8 file, CLI stdin identity, `cat` pipe, xclip clipboard, vim `binary noeol`, ordinary vim `wq`, NFC/NFKC/Cf-strip/whitespace-collapse. Latin-1 is expected to fail. Ordinary vim `wq` is expected to append a trailing newline.

Performance uses `time.perf_counter` on short (`I do not agree.`), medium (4 copies of the Cycle 8 GPT-2 fixture sentence), and long (8 copies). Determinism repeats the same source five times and compares SHA-256.

Letter-x1 apply cost grows with candidate count because each selected site is trial-validated against visible-word invariants. Long-paragraph fixtures are capped so local measurement finishes; corpus rows that hit the 192 cap are reported from detector artifacts rather than by applying letter-x1 to multi-thousand-character strings in this local pack.

## Reproduce

Detector (CPU, quiet host, about 9 minutes per n=64 three-arm corpus):

```text
python3 -m fuckmark.cycle8_benchmark_hf --device cpu --seed-base 980000 --pair-count 64
python3 -m fuckmark.cycle8_benchmark_hf --device cpu --seed-base 990000 --pair-count 64
```

Local system plus scorecard:

```text
python3 -m fuckmark.cycle8_benchmark --output-dir evidence/cycle8-letter-system-benchmark-2026-08-26
```

`--skip-local` rebuilds detector-stats and the scorecard from committed local-system.json without re-running transforms or Chromium.

## Labels

`VERIFIED`, `SOURCE-BOUND`, `HYPOTHESIS`, `UNKNOWN`, `REJECTED`, `PRODUCT_DISQUALIFIED`, `HISTORICAL_ONLY`.

This benchmark does not authorize product promotion and is not a frozen formal 0/192 confirmation protocol.
