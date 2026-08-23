# Frozen Research Protocol: Budget-Scaled Key-Blind Coverage Effectiveness (v1)

Protocol ID: `budget-scaled-coverage-effectiveness-v1`
Frozen before any detector scoring for this cycle. See the machine-readable contract in
`specs/fuckmark-budget-scaled-coverage-effectiveness-v1.contract.json` and the hash-binding
freeze record in `specs/fuckmark-budget-scaled-coverage-effectiveness-v1.freeze.json`.

## 1. Objective and claim boundary

Level A (this protocol): for the fixed, documented open detector and the existing uncleaned
text-only input path, measure whether a budget-scaled, detector-blind, key-blind transform
profile lowers watermarked held-out detection on a new source-disjoint confirmation corpus while
preserving all pre-registered fidelity gates. The stretch exploratory target is 0 detected
watermarked sources out of at least 64. A 0/64 result is a narrow detector-specific measurement
under the documented fixed input path; it is not watermark removal, universal undetectability,
immunity to input cleaning, or safety against unknown keys or proprietary detectors.

Level B (product/release admissibility): this candidate family intentionally edits visible text
(spacing and contractions), so it is NOT a product candidate this cycle regardless of Level A
outcome. No candidate output will be added to default, development-release, or CLI registries.

## 2. Candidate mechanism

Profile `key-blind-full-pool-coverage-v1`: the frozen development ruleset already used by the
B16 line (ruleset hash bound in artifacts; forward contractions, surface spacing, lexical, and
syntax rules), the COVERAGE_GREEDY_KEY_BLIND scheduler over public-tokenizer n-gram disruption
geometry (ngram_len 5), one replicate, and schedule seeds derived from the frozen seed base plus
sorted source index. The only new degree of freedom is the requested budget, swept on
development data and then frozen by the pre-registered rule in section 7. Selection reads the
public tokenizer and public detector n-gram length only; it never reads detector scores,
decisions, keys beyond the public development keys, or confirmation results.

## 3. Data splits and source disjointness

- Development: the canonical pinned TinyDev corpus (seed base 401000, corpus artifact hash
  recorded at generation time) plus one fresh development corpus at seed base 410000 with 8
  attack pairs per domain (32 watermarked attack sources). Pooled development watermarked
  attack sources: 36.
- Confirmation: one fresh corpus at seed base 420000 with 16 attack pairs per domain
  (64 watermarked attack sources plus 64 unwatermarked attack controls), generated only after
  the protocol, contract, and freeze record exist, and scored exactly once.
- Every corpus keeps the frozen 25 threshold-calibration pairs per domain (100 negatives).
- Disjointness gates: no text SHA-256 may appear in more than one corpus used by this protocol;
  confirmation text hashes must be disjoint from all development text hashes; recorded
  automatically at scoring time. Neither corpus reuses any example from the archived B10 or
  B16 holdout corpora; disjointness from those corpora is asserted by artifact-hash inequality
  and text-hash disjointness against any locally available recorded holdout text hashes.

## 4. Generation and detector configuration

- Model: `openai-community/gpt2` at revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`,
  CPU, temperature 0.8, top-k 50, top-p 0.95, 64 target continuation tokens, max 16 attempts
  per pair, seeds derived from the corpus seed base by the existing frozen seed policy.
- Watermarking: Hugging Face SynthID text integration with the public development keys
  (654, 400, 836, 123, 340, 443, 597, 160, 57), ngram_len 5, context history 1024, sampling
  table seed 0, size 65536, debug off.
- Detector: the Hugging Face SynthID weighted-mean open detector over the text-only
  re-tokenized track, ngram_len 5, public development keys (the detector is the open research
  harness detector; the keys are public development keys, not provider secrets).
- Threshold: text-only calibration on the 100 unwatermarked calibration negatives of the SAME
  corpus being scored, target FPR 0.01, decision rule score >= threshold. Threshold value and
  identity hashes are bound inside every scoring artifact. The confirmation threshold is
  computed only from the confirmation corpus calibration split.

## 5. Controls

All four paired controls are scored for every source: pristine watermarked, transformed
watermarked, pristine unwatermarked, transformed unwatermarked. Summaries report raw counts,
rates, mean scores, mean per-source score change, and false positives, overall and per domain.

## 6. Fidelity, representation, and robustness gates

Gates evaluated on every plan row, development and confirmation:

1. Hard invariants: status PASS (enforced at plan build; any failure aborts).
2. Protected spans: zero violations under the symmetric protected-span counter.
3. Word edit rate: word-level edit distance divided by source word count must be <= 0.30.
4. Introduced-codepoint gate: every character the transformation introduces (present in the
   transformed text but absent from the source alphabet) must be ASCII; pre-existing source
   characters such as newlines are corpus properties and are reported, not gated.
5. Codepoint audit: the transformation must introduce no Unicode Cf, Cc, Mn, Mc, Me, Zl, Zp,
   or Zs characters other than U+0020. Pre-existing forbidden-category characters in the
   source are reported separately and do not gate the candidate.
6. Normalization stability: the transformation must not introduce normalization instability;
   for each of NFC, NFD, NFKC, NFKD, if the source text is stable under the form then the
   transformed text must be stable under it too. Sources that are themselves normalization
   unstable (for example precomposed accented characters under NFD) are corpus properties,
   reported without gating the candidate. Unicode Cf stripping must not alter any
   candidate-introduced character; candidates introduce ASCII only, so this holds by
   construction and is verified per row.
7. Copy/DOM: transformed text must contain no control or format characters, so DOM
   textContent equals the transformed string; verified by the codepoint audit and archived
   fixed-browser renders.
8. Fixed-browser rendering: every confirmation watermarked source/transform pair is rendered
   side by side in a fixed browser and screenshotted; the rendered DOM text must equal the
   plan transformed text. Screenshots are archived; the deterministic gates above carry the
   decision weight.

## 7. Pre-registered budget selection rule (frozen)

Development sweep budgets: 16, 24, 32, 48. For each budget, compute on the pooled 36
development watermarked attack sources: transformed detected count at the development
thresholds, and gate status for every development row. A budget is eligible when its
development transformed-watermarked detected count is 0 and all gates pass on all development
rows at that budget. The confirmation budget is the smallest eligible budget. If no budget is
eligible, the confirmation budget is the budget with the smallest development
transformed-watermarked detected count (ties broken toward the smaller budget); in that case
the primary target is expected to fail and the confirmation run proceeds and reports honestly.
The rule is fully determined before any confirmation scoring; no post-hoc budget change is
permitted. No confirmation score may be computed before the confirmation budget is recorded in
the freeze record appendix.

## 8. Success and falsification criteria

Primary (Level A stretch target): transformed watermarked detected count == 0 out of 64
confirmation watermarked sources at the frozen confirmation threshold.

Mandatory secondary gates on the confirmation corpus: pristine watermarked detected >= 60/64;
transformed unwatermarked detected == 0/64; every gate in section 6 passes on 100% of
confirmation rows; all four controls' artifacts replay and hash-bind.

Adverse results that must be reported, never hidden: any residual transformed-watermarked
detection; any gate failure; any normalization or Cf-stripping non-identity; any pristine
watermarked source below threshold (weak watermark); any false positive; per-domain or
per-length heterogeneity.

Permitted conclusion language is exactly: detector-specific detection reduction under the
documented fixed open detector, public development keys, and uncleaned text-only input path.
Prohibited: watermark removal, undetectability, untraceability, robustness against cleaning,
unknown-key or proprietary-detector claims, release readiness.

## 9. Reproducibility and artifacts

Canonical JSON artifacts with SHA-256 hashes: corpora (+ provenance), plans (+ provenance),
scoring evidence (+ provenance), robustness report, rendering archive manifest, final report,
and the freeze record appendix recording the rule-selected confirmation budget before
confirmation scoring. All artifacts bind the source code commit, corpus artifact hash,
plan hash, profile hash, ruleset hash, detector identity hash, calibration bundle hash, and
threshold hash. Full test suite, `git diff --check`, and `git status --short --branch` run at
the end. No pushes, PRs, merges, or releases in this cycle.
