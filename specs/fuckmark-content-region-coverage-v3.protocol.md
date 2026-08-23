# Frozen Research Protocol: Content-Region Coverage (Cycle 3)

Protocol ID: `content-region-coverage-v3`. Frozen before any Cycle-3 detector scoring.
Freeze record: `specs/fuckmark-content-region-coverage-v3.freeze.json`.

## 1. Objective and claim boundary

Test whether a general any-word spacing candidate family (a) closes the content-region
candidate holes diagnosed in Cycles 1-2, (b) beats the Cycle-2 coverage-completion ruleset in
a paired design on fresh corpora, and (c) holds across three independent confirmation corpora
under a fixed corpus-independent threshold. Claim boundary unchanged: fixed open HF SynthID
weighted-mean detector, public development keys, uncleaned text-only path; no removal,
undetectability, unknown-key, proprietary-detector, or cleaning claims; Level B not pursued.

## 2. Candidate mechanism

Profile `content-region-coverage-v1` (ruleset hash recorded in artifacts): forward
contractions, the six punctuation spacing rules, ONE new `GeneralWordSpacingRule`
(`surface-space-after-any-word`, pattern `(?<![A-Za-z])[A-Za-z]+(?= [^ \t\r\n])`, replacement
= matched word + one space, case-sensitive, word-boundary anchored, no word list), plus the
existing lexical and syntax rules. Budget 16 operations; COVERAGE_GREEDY_KEY_BLIND over
public-tokenizer 5-gram geometry; replicate 1; schedule seed base 1_150_000 + sorted source
index. The Cycle-2 word-list spacing rules are intentionally absent because the general rule
subsumes them; ablation arm D (dev only) tests the combined ruleset to separate mechanisms.
Selection uses text and public tokenizer geometry only; no detector information anywhere in
planning.

## 3. Measurement (Phase A)

`open-detector-measurement-stability-v1`: a dedicated calibration corpus (seed base 500000,
40 new topics x 4 domains x 8 seeds = 1280 unwatermarked 64-token negatives; 1024 calibration
+ 256 audit by frozen sample-id order) generates the frozen threshold: ascending order
statistic n - floor(0.01 * n) + 1 = 1015 of 1024 calibration scores; detection score >=
threshold; float64, no tie rounding. The threshold artifact freezes detector identity,
corpus hash, counts, realized audit FPR with exact 95% binomial interval, and environment
identity. ALL Cycle-3 confirmation scoring uses this fixed threshold; per-corpus calibration
thresholds are recorded alongside for comparison only. Threshold frozen before any
confirmation score. Dev scoring (both arms on the same corpus) may additionally report
per-corpus thresholds; paired comparisons use one threshold within each corpus.

## 4. Seed-range ledger (recovered from artifacts)

Consumed: 401000-404296, 410000-414192, 420000-425216, 430000-434192, 440000-445216,
calibration 500000-520480 (span 160 prompts x 8 slots x stride 16). Cycle 3 uses: dev
450000 (v3, 8 attack pairs/domain, spans about 450000-454224), confirmations 460000,
470000, 480000 (v3, 16 attack pairs/domain, each spanning about 5264 seeds). All ranges are
pairwise disjoint from every consumed range and from each other.

## 5. Development design

Fresh dev corpus 450000 (32 watermarked attack sources). Four plan arms per source, all
detector-blind before scoring:

A. Cycle-2 coverage-completion ruleset (paired baseline)
B. Cycle-3 content-region profile
C. General-spacing-only arm (general rule + punctuation only, no contractions/lexical/syntax)
D. Combined arm (Cycle-2 word list + general rule)

Primary structural endpoints (no detector data): candidate count, achievable coverage,
zero-candidate rate, longest uncovered run, uncovered window count, per-source paired
differences B minus A. Detector outcomes are evaluation-only.

## 6. Promotion gate (all required before any confirmation scoring)

1-8: historical hashes unchanged; suite green except documented environmental failures; hard
invariants pass on every dev row; protected-span violations 0; introduced hidden/control
codepoints 0; introduced normalization instability 0; Cf-strip identity holds; no source
becomes empty or corrupted. 9: B raises achievable coverage materially in the A-low-coverage
subset (mean paired gain >= 0.05 among the 8 lowest-A-coverage sources). 10: zero-candidate
rate not above baseline. 11: fidelity metrics not materially regressed (word edit rate,
protected spans, invariants). 12: paired detector result for B not clearly worse than A on
dev (detected count difference <= 2 on 32 sources). The confirmation decision (proceed or
reject) is recorded in the freeze record appendix before confirmation scoring.

## 7. Confirmation design

Three corpora frozen before the first confirmation score (hashes recorded in the appendix
after generation, before scoring): 460000, 470000, 480000; each 64 watermarked + 64
unwatermarked attack sources. For each corpus, two frozen plans (A baseline, B candidate)
built detector-blind, then scored once each with the fixed threshold. Control gates per
corpus: pristine watermarked >= 60/64 (unconditional denominator primary; conditional count
reported); transformed unwatermarked == 0/64; fidelity/representation gates 128/128 per arm;
text-hash overlap 0 against every prior corpus with the pre-registered collision policy:
any naturally occurring collision is reported and followed by scoring the corpus as
generated; no regeneration or substitution after seeing outcomes.

## 8. Outcome classes (pre-registered)

STRONG_SUCCESS: all control gates pass on all three corpora AND pooled B residuals strictly
fewer than pooled A residuals AND B no worse than A on every corpus; stretch target 0/192.
PARTIAL_SUCCESS: B paired-better overall but residuals remain, or exactly one non-primary
gate fails. NEUTRAL: B not better than A pooled. REJECTED: B worse, false positives appear,
fidelity regresses, or the structural hypothesis fails on dev. Post-scoring margin analysis
(±0.005/±0.010/±0.025 bands) is diagnosis only.

## 9. Fidelity and reporting

All Cycle-1/2 gates retained. For the general-rule family report separately: number of
spacing insertions, number of sources receiving them, maximum and mean per source, exact
changed tokens, rule identities; word-level substitutions from other families reported as in
prior cycles. Blind human fidelity evidence: NOT_PROVIDED (no fabricated judgments).

## 10. Reproducibility

Environment manifest bound in the freeze record (Windows-10-10.0.26220 AMD64, Python
3.11.15, torch 2.13.0+cpu, transformers 5.16.0.dev0 at the pinned git revision, GPT-2
revision 607a30d783dfa663caf39e06633721c8d4cfcd7e). Cross-platform corpus generation is NOT
claimed byte-reproducible (documented Cycle-1 finding); plans, scoring, and thresholds are
deterministic given texts and the pinned runtime. All artifacts content-addressed; amendments
only before affected scores, timestamped and hash-bound; local commits only, nothing pushed.
