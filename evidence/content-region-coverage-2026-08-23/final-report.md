# Content-Region Coverage Cycle 3 - Final Research Report (2026-08-23)

## Repository state

- Base `origin/main`: `16e153fdfa3739a88bca9b1559543a10ded2d859` (unchanged upstream; no open PRs).
- Research branch: `research/content-region-coverage-v1`, child of Cycle-2 HEAD `4ddd84f`.
- Final HEAD: `77354e68a45aee9b93aa73afe2ddca0db0bffaa7` (confirmation-scoring commit).
- Nothing pushed at any point. Worktree clean after final commits.
- Frozen historical identities verified at takeover: B16 profile hash
  `6ad142262bfb11a714565d7bd43daa859657fe817bdafa9c8dcf0f4884c07512` replays; Cycle-1/2
  artifacts intact; full suite 1436 passed / 8 skipped with only the pre-documented
  Windows-only `spec.md` CRLF freeze failure (`git show HEAD:spec.md` hashes to the pin).

## Measurement (Phase A)

- New identity `open-detector-measurement-stability-v1`. Dedicated calibration corpus: 40 new
  topics x 4 domains x 8 seeds = 1280 unwatermarked 64-token negatives (seed base 500000,
  artifact `7a12862c...`), prompt/seed/text disjoint from every prior corpus.
- Frozen threshold: ascending order statistic n - floor(0.01*n) + 1 = 1015 of 1024 calibration
  scores = **0.5570987654320988**; comparison `>=`; float64; no tie rounding; target FPR 1%.
- Audit: 0/256 exceedances on the independent audit split (exact 95% binomial interval
  recorded in the artifact). Calibration exceedances 10/1024 (0.977%). Detector identity
  bound and matched at every scoring invocation.
- This replaces per-corpus thresholds (Cycle 1: 0.5585; Cycle 2: 0.5803) with one
  corpus-independent value; all six confirmation scorings used it.
- Environment manifest frozen in the contract (Windows-10-10.0.26220 AMD64, Python 3.11.15,
  torch 2.13.0+cpu, transformers 5.16.0.dev0 pinned git revision, GPT-2 revision pinned).
  Cross-platform corpus-generation byte-reproducibility is NOT claimed.

## Candidate mechanism and diagnosis chain (Phases B/C)

- Phase B (structural, on consumed Cycle-1/2 artifacts): uncovered observation windows are
  dominated by lowercase content words (447 across both confirmations), then capitalized
  content (99) and listed function words in unreachable positions (142); the worst texts are
  protected numeric runs (correctly unreachable). New `coverage_holes` module reports token
  counts, per-family candidate counts, achievable/realized coverage, longest uncovered run,
  lexical categories, protected intersections, density, and redundancy per source.
- Phase C: one new rule, `GeneralWordSpacingRule` (`surface-space-after-any-word`): any
  standalone alphabetic word followed by a single space and a non-space character gains one
  trailing space. No word list, no hidden representation, case-sensitive, protected spans
  rejected by the registry. Profile `content-region-coverage-v1` (hashes in the contract),
  budget 16, unchanged COVERAGE_GREEDY_KEY_BLIND scheduler, seed base 1_150_000.
- Structural dev evidence: mean achievable coverage 0.841 (Cycle-2 ruleset) -> 0.941
  (candidate); in the 8 lowest-coverage sources the paired gain was +0.20 (gate >= 0.05);
  pools 21.6 -> 45.0; zero-candidate rate 0. Ablation: the general rule alone reproduces the
  full gain (arm C); adding the Cycle-2 word list (arm D) adds candidates but zero coverage -
  the general rule is the operative mechanism.

## Development (fresh corpus 450000, four detector-blind arms, per-corpus thresholds)

All four arms: 1/32 transformed-watermarked detections (same source), 0/32 unwatermarked
false positives, fidelity gates 256/256 rows pass. Promotion gate: all twelve criteria
passed and recorded before confirmation scoring (freeze appendix).

## Confirmation (three frozen corpora, paired A/B, fixed threshold, scored once each)

| Corpus | Pristine WM | A (Cycle-2 ruleset) | B (Cycle-3 candidate) | FP A | FP B |
| --- | --- | --- | --- | --- | --- |
| 460000 | 63/64 | 4/64 | 3/64 | 1/64 | 0/64 |
| 470000 | 64/64 | 8/64 | 7/64 | 1/64 | 1/64 |
| 480000 | 63/64 | 10/64 | 2/64 | 0/64 | 0/64 |
| Pooled | 190/192 | 22/192 (11.5%) | 12/192 (6.3%) | 2/192 | 1/192 |

B is paired-better on every corpus and pooled (relative reduction 45%). Mean watermarked
score drop: B 0.119 vs A 0.113. Margin bands (pooled, B): 9 within +-0.005, 21 within
+-0.010, 51 within +-0.025 of threshold - residual detection remains margin-driven.
Fidelity/representation gates: 256/256 rows per corpus across both arms. Cross-corpus
text-hash disjointness: pairwise zero among the three corpora; one naturally occurring
collision between 480000 and the consumed Cycle-2 corpus 440000 (single degenerate text,
policy followed: scored as generated, no regeneration). DOM text equality 384/384 pairs;
screenshot archived.

## Adverse findings (all reported)

1. Currency protected-span extractor bug: a double space before `$100` changed the extracted
   span from "$100" to " $100" (`PROTECTED_CONTENT_CHANGED`), failing plan A on corpus 480000
   fail-closed before any scoring. Root cause fixed (whitespace branch now requires a sign),
   regression tests added, recorded as pre-score amendment 1. The fail-closed builder worked
   as designed.
2. Transformed-unwatermarked false positives: 3 events across 384 arm-corpus cells
   (A: 460000 one, 470000 one; B: 470000 one). Two of the three texts were already above the
   threshold when pristine (consistent with the fixed threshold's nominal 1% FPR; the 0/64
   gate was calibrated under the old higher per-corpus thresholds). Two genuine
   transformation-induced crossings exist (A 0.5234->0.5611; B 0.4510->0.5589, a 0.1079 score
   increase on an unwatermarked text). The pre-registered 0/64 FP gate FAILED for arm A on
   460000/470000 and arm B on 470000 and is reported as such.
3. Degenerate generation events: one all-EOS continuation crash path fixed with deterministic
   retry in the v3 and calibration generators (pre-scoring); one cross-corpus degenerate text
   collision (above).
4. Dev underpredicted absolute residual rates again (1/32 dev vs 12/192 pooled
   confirmation for arm B).

## Classification

**PARTIAL_SUCCESS** (pre-registered class): the candidate is paired-better than the Cycle-2
baseline on every confirmation corpus and pooled (22/192 -> 12/192), all structural
mechanism gates passed, all fidelity gates passed, and pristine-watermark control gates
passed on all three corpora (63, 64, 63 of 64) - but residual detections remain (12/192, not
the 0/192 stretch) and the transformed-unwatermarked 0/64 gate failed in three arm-corpus
cells under the fixed 1%-FPR threshold.

## Permitted conclusion

Under the fixed open Hugging Face SynthID weighted-mean detector with public development
keys, a frozen corpus-independent threshold at nominal 1% FPR (audit 0/256), and the
uncleaned text-only input path, a detector-blind key-blind general any-word spacing rule
materially increased legal candidate coverage in content-word regions and reduced pooled
transformed watermarked detection from 22/192 to 12/192 relative to the Cycle-2 ruleset in a
paired three-corpus design, while preserving every fidelity, representation, normalization,
and rendering gate. The evidence does not establish zero detection, watermark removal,
undetectability, unknown-key or proprietary-detector performance, cleaning durability, or
release readiness, and the fixed-threshold regime exhibits expected low-rate false positives
on unwatermarked text.

## Not supported

Watermark removal; undetectability; SynthID defeat; Gemini or proprietary-detector transfer;
unknown-key transfer; normalization/cleaning durability; human semantic equivalence (blind
human fidelity evidence: NOT_PROVIDED); production readiness or release authorization;
cross-platform byte-reproducible corpus generation.

## Reproducibility

Independent binding cross-check over all Cycle-3 artifacts: every corpus, calibration,
threshold, plan, evidence, robustness, and render-manifest hash replays and mutually binds;
128/128 row hashes in all six evidence files; all plans bind the scoring commit and record
detector_access_observed=false / secret_access_observed=false. Full suite: 1436 passed,
8 skipped, 1 pre-documented environmental failure. `git diff --check` clean. Artifact
SHA-256 manifest in this directory; local commits only, nothing pushed, main untouched.
