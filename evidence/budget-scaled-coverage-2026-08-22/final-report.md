# Budget-Scaled Key-Blind Coverage Effectiveness - Research Cycle Report

Cycle date: 2026-08-22/23. Research branch: `research/ngram-window-coverage-v1` (local only;
nothing pushed). Base commit: `16e153fdfa3739a88bca9b1559543a10ded2d859` (`origin/main`, which
already contains merged PR #80).

## Executive summary

The pre-registered stretch target was NOT met. On a new, source-disjoint confirmation corpus of
64 watermarked attack sources, the frozen detector-blind key-blind budget-16 coverage profile
reduced fixed-open-detector detection from 63/64 (pristine) to 11/64 (transformed) - an 82.5%
relative reduction in the detected count under the documented condition - but did not reach 0/64.
All fidelity and representation gates passed on every confirmation row. The evidence supports
only: detector-specific detection reduction under the fixed open detector, public development
keys, and uncleaned text-only input path. It does not support watermark removal,
undetectability, unknown-key, proprietary-detector, cleaning-durability, or release claims.
Level B (product/release admissibility) is explicitly NOT met and was not pursued: the
candidate intentionally edits visible text.

## Protocol provenance

- Protocol, contract, and hash-binding freeze record committed before any scoring
  (commit `29d7a40`).
- Five timestamped pre-score amendments, all recorded before confirmation scoring:
  1. Seed bases moved to 410000 (dev) / 420000 (confirmation) - pair-stride overlap arithmetic.
  2. CI canonical corpus pin (`ee09527d...`) is not byte-reproducible on the local Windows CPU
     runtime (locally regenerated 401000 corpus `42240f72...` / file `57b580c8...` used as
     development data only; adverse reproducibility finding, reported not hidden).
  3. Word-edit-rate gate raised from 0.15 to 0.30 (contractions cost two word edits each; the
     original gate was below the mechanical floor of the ruleset).
  4. Codepoint audit re-scoped to candidate-INTRODUCED characters (absolute ban flagged
     pre-existing source newlines, category Cc).
  5. Normalization gate re-scoped to introduced instability (precomposed accented source
     characters are NFD-unstable; the candidate introduces ASCII only).
- Final protocol SHA-256 `4fa68c7519a2064c2bf131393598c5b181b92f2ae5fd62f9fd1959b7ebea0367`,
  contract SHA-256 `c878ff9fdbf4c412361f6058a72af1fa8c925e78997c89825d255c8d437f598f`.
- Budget selection rule applied exactly as frozen: no budget reached 0/36 pooled dev
  transformed-watermarked detections (all budgets tied at 1/36 because n-gram-window coverage
  saturates at 9-13 edits, below the smallest swept budget), so the fallback selected
  the smallest budget, 16. Recorded in the freeze-record appendix before confirmation scoring.

## Development results (iteration data; separate from confirmation)

| Corpus (seed base) | Watermarked sources | Transformed detected | False positives (unwm) | Mean score drop |
| --- | --- | --- | --- | --- |
| 401000 local | 4 | 0/4 | 0/4 | 0.0980 |
| 410000 (v3, 8 attack pairs/domain) | 32 | 1/32 | 0/32 | 0.1052 |
| Pooled | 36 | 1/36 | 0/36 | - |

Budget sweep {16, 24, 32, 48} produced identical detections at every budget on every dev source
(coverage saturation; realized edit costs 9-13). Dev robustness gates: 288/288 rows pass.

## Confirmation results (scored once, at commit `46c220f`, profile `key-blind-full-pool-coverage-v1`, budget 16)

Detector: HF SynthID weighted mean, ngram_len 5, public development keys, uncleaned text-only
re-tokenized path. Threshold 0.558485 calibrated at target FPR 0.01 on the confirmation corpus's
own 100 unwatermarked calibration negatives (>= comparison).

| Condition | Detected | Rate | Mean score |
| --- | --- | --- | --- |
| Pristine watermarked | 63/64 | 98.4% | 0.6333 |
| Transformed watermarked | 11/64 | 17.2% | 0.5315 |
| Pristine unwatermarked | 1/64 | 1.6% | - |
| Transformed unwatermarked | 0/64 | 0.0% | 0.5029 |

Mean per-source watermarked score drop: 0.1018. Residual detection by domain:
technical_explanation 5/16, conversational_prose 3/16, structured_instructional 2/16,
general_explanatory 1/16. Eight of eleven residuals sit within +0.024 of the threshold; four
non-detected sources sit within -0.012 - the residual is margin-driven. Realized edit costs:
mean 11.89 of a mean candidate pool of 18.6; only 2/64 sources exhausted the budget-16 cap;
one source enumerated zero candidates and passed through unchanged (still detected).

Pre-registered secondary gates: pristine watermarked >= 60/64 PASSED (63; one weak-watermark
source below threshold at 0.5569 vs 0.5585, reported as an adverse observation).
Transformed-unwatermarked == 0/64 PASSED. Section-6 fidelity gates on 128/128 confirmation
rows PASSED (hard invariants, protected spans zero, word edit rate max 0.1333 <= 0.30, no
introduced non-ASCII or hidden-category codepoints, no introduced normalization instability,
Cf stripping is the identity on every introduced character by construction and per row).

Primary endpoint (0/64): FAILED.

## Representation, normalization, and rendering evidence

- Codepoint audit: no introduced Cc/Cf/Mn/Mc/Me/Zl/Zp or non-space Zs characters on any of the
  128 rows; no introduced non-ASCII characters at all. Pre-existing source newlines and two
  precomposed accented characters (NFD-unstable sources) are corpus properties, reported.
- Normalization: NFC/NFD/NFKC/NFKD stability preserved on all rows (sources stable under a form
  imply transformed stable under it). The two NFD-unstable sources were unstable before
  transformation.
- Fixed-browser rendering: all 128 source/transform pairs rendered in a fixed browser page;
  DOM textContent equals the plan texts byte-for-byte on 128/128 pairs (0 source mismatches,
  0 transformed mismatches); screenshot archived
  (`confirmation-render-screenshot.png`, SHA-256 `b0c740c8...`).
- Copy/DOM divergence: none possible by construction and none observed (no control or format
  characters introduced).

## Independent hash cross-check

Reloaded artifacts from disk and recomputed every binding: corpus artifact hash replays;
plan hash replays and binds corpus artifact hash, manifest hash, code commit
`46c220f1c0dfe4c2b401cc32ecf4aaf70ac5ed7b`, detector_access_observed=False,
secret_access_observed=False; evidence artifact hash replays, binds the plan hash, corpus hash,
profile id `key-blind-full-pool-coverage-v1`, detector identity, calibration bundle, and
threshold; 128/128 row hashes replay; every scored transformed text hash matches the plan
variant's transformed text; robustness artifact hash replays and binds the plan; rendering
manifest binds the plan with 128 pairs. See `artifacts/budget-scaled/binding-cross-check.json`
(copied into this evidence directory).

## Adverse and deviation findings (all reported, none suppressed)

1. Canonical CI corpus pin is not byte-reproducible on this Windows CPU runtime despite pinned
   versions; corpus generation is platform-sensitive. All within-cycle comparisons use one
   runtime and per-corpus calibration, so the science is internally consistent, but
   cross-platform regeneration of the same corpus artifact is not guaranteed.
2. Disjointness deviation: one confirmation attack text is byte-identical to one development
   corpus (401000) watermarked calibration sample - a degenerate GPT-2 repetition under
   different prompts and seeds. Calibration thresholds use only unwatermarked negatives, and
   no development tuning ever read this text's detector score, so no optimization leak is
   possible; the text-hash disjointness gate (all pairwise corpus overlaps zero) was violated
   once (1 shared hash, dev-corpus-401000-local to confirmation corpus) and is reported as a
   protocol deviation.
3. Development underpredicted confirmation residual detection (1/36 dev vs 11/64
   confirmation). The budget sweep showed saturation, so no frozen-rule budget choice could
   have changed the outcome.
4. One pristine unwatermarked source scored above threshold (1.6% observed vs 1% nominal FPR;
   consistent with binomial noise at n=64, P >= 1 at 1% is about 47%).
5. One pristine watermarked source scored below threshold (weak watermark signal).
6. One confirmation source enumerated zero transform candidates (no rule matched) and was
   passed through unchanged.

## Classification

- Product-safe code delivered: corpus profile v3 (parameterized attack pairs, frozen
  calibration), full-pool coverage profile factory with resolver, parameterized plan/score
  runners (defaults preserve the frozen B16 CI behavior), robustness audit module with
  introduced-codepoint and normalization-stability semantics, render-page tool, and 24 new
  tests.
- Quarantined experiment status: unchanged; the U+200C visible-projection experiment was not
  touched and remains excluded from default, development-release, and CLI paths.
- Candidate outcome: exploratory partial effectiveness under one fixed condition; primary
  target failed; NOT product/release admissible (visible-text edits); no overclaim.
- Deviations: enumerated above; the corpus-generation platform sensitivity is the most
  significant reproducibility limitation.

## Reproducibility

Full suite at final state: `python -m pytest -o addopts=` -> 1415 passed, 8 skipped, 1 failed
(`test_frozen_revision_2_spec_is_exact`, the pre-existing Windows CRLF-only `spec.md` freeze
assertion documented in PR #80; `git show HEAD:spec.md` hashes exactly to the pinned value).
`git diff --check` clean. Artifact SHA-256 manifest: `artifacts-SHA256SUMS.txt` in this
directory. Environment: Python 3.11.15, torch 2.13.0+cpu, transformers 5.16.0.dev0 at the
pinned git commit, Windows-10-10.0.26220.

## Permitted conclusion, precisely

Under the fixed Hugging Face SynthID weighted-mean open detector with public development keys
and the uncleaned text-only input path, at the pre-registered frozen threshold, the budget-16
key-blind coverage profile reduced watermarked detection from 63/64 to 11/64 on a new,
source-disjoint 64-source confirmation corpus while passing all pre-registered fidelity,
representation, normalization, and rendering gates. It did not reach zero detection. Nothing in
this cycle demonstrates watermark removal, undetectability, robustness against input cleaning,
unknown keys, proprietary detectors, or release readiness.
