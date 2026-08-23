# Coverage-Completion Cycle 2 Report - 2026-08-23

Branch `research/ngram-window-coverage-v1` (local only, nothing pushed). Confirmation scored
once at commit `6d0ad2d2...` on corpus `ccc9d5d6...`. Protocol SHA-256
`65856295a595acaa404392239ccd9db9fa43d3f45a86ae61ee0d88b0d1e0851a`, contract SHA-256
`20ba6145793a89f0aa5cbc530305d9345731a60d60ad906199b323c74942d825`.

## Executive summary

On a new, source-disjoint 64-watermarked-source confirmation corpus, the frozen
detector-blind key-blind coverage-completion profile achieved **0/64 transformed watermarked
detections** (primary stretch target met for this condition) with **0/64 transformed
unwatermarked false positives** and all 128 fidelity/representation gates passing. One
pre-registered secondary gate FAILED and is reported as such: pristine watermarked detection
was 58/64, below the required 60, because this corpus's per-corpus calibration threshold rose
to 0.580261 (cycle 1: 0.558485), leaving six watermarked sources below threshold before any
transformation. Conditional on initial detectability, 0 of the 58 pristine-detected sources
remained detected after transformation. The permitted conclusion is unchanged in kind:
detector-specific detection reduction under the fixed open detector, public development keys,
and uncleaned text-only input path - here reaching the pre-registered narrow 0/64 target on
this corpus. It is not universal undetectability, watermark removal, or any unknown-key,
proprietary-detector, or cleaning-durability claim, and Level B (product admissibility)
remains unmet.

## Mechanism and diagnosis chain

Cycle 1 ended at 11/64 residual detection. The post-hoc coverage diagnosis (tool:
`tools/budget_scaled_coverage_diagnosis.py`) showed residual sources had mean achievable
n-gram coverage 0.682 vs 0.847 for escaped sources, with realized coverage equal to achievable
everywhere - the candidate pool, not the scheduler, was the bottleneck. Cycle 2 extended the
surface spacing word list by 65 frozen general-English function words (protocol section 2),
raising mean achievable coverage on confirmation watermarked sources to 0.827 (mechanistic
endpoint >= 0.80 met) and mean candidate pools to 21.9 per source.

## Development phase (recorded before confirmation scoring; freeze appendix)

| Corpus | Cycle-2 ruleset | Cycle-1 ruleset (paired) |
| --- | --- | --- |
| 410000 (repeat use, labeled) | 0/32 detected | 1/32 (cycle 1) |
| 430000 (fresh) | 5/32 detected | 4/32 (paired baseline) |
| Pooled dev | 5/64 | 5/64 |

Dev showed NO pooled improvement; the extension grew pools where function words exist but
residual sources are content-word-dense with low candidate density (one had 5 candidates
total). Residual sets overlapped strongly across rulesets, tied to high pristine scores plus
sparse candidate regions. The confirmation proceeded as pre-registered and the outcome
exceeded the dev signal; corpus-to-corpus variance is high in both directions (cycle 1:
1/36 dev to 11/64 confirmation; cycle 2: 5/64 dev to 0/64 confirmation). This variance is
itself a finding: single-corpus dev counts are weak predictors.

## Confirmation results (64 wm + 64 unwm, budget 16, threshold 0.580261 at 1% target FPR)

| Condition | Detected | Rate | Mean score |
| --- | --- | --- | --- |
| Pristine watermarked | 58/64 | 90.6% | 0.6348 |
| Transformed watermarked | 0/64 | 0.0% | 0.5283 |
| Pristine unwatermarked | 0/64 | 0.0% | - |
| Transformed unwatermarked | 0/64 | 0.0% | - |

Mean watermarked score drop 0.1064. Closest transformed margin to threshold: -0.0020 (one
source), then -0.0115. Realized edit cost mean 12.72 of mean pool 21.9; zero-candidate
sources: 0. Six pristine-watermarked sources below threshold (0.5590-0.5775) are listed in
the evidence and constitute the failed >= 60/64 control gate.

## Gates, robustness, rendering, bindings

- Section-6 gates: 128/128 confirmation rows pass (hard invariants, protected spans zero,
  max word edit rate 0.1333 <= 0.30, no introduced non-ASCII or hidden-category codepoints,
  no introduced normalization instability, Cf-strip identity on introduced characters).
- Cross-corpus text-hash disjointness: all pairwise overlaps zero among 410000, 430000,
  440000; also zero against cycle-1 corpora 401000 and 420000 (no repeat of the cycle-1
  degenerate collision).
- Fixed-browser rendering: DOM textContent equals plan texts on 128/128 pairs; screenshot
  archived (`confirmation2-render-screenshot.png`).
- Independent cross-check: corpus/plan/evidence/robustness/render-manifest hashes all replay
  and mutually bind; 128/128 evidence row hashes replay (`binding-cross-check-2.json`).

## Adverse findings and caveats

1. The >= 60/64 pristine-watermarked control gate failed at 58/64 (threshold sensitivity of
   per-corpus calibration); the 0/64 primary result must be read together with this.
2. Dev predicted no improvement (5/64 both rulesets); the confirmation result therefore
   carries corpus-sampling uncertainty. A single 0/64 does not establish a stable zero rate.
3. One transformed source sits 0.0020 below threshold - margin-level sensitivity persists.
4. Cycle-2 word extension did not reduce dev-phase residuals; residuals concentrate in
   content-word-dense, low-candidate-density sources that word-list extension cannot reach.
5. Canonical-corpus cross-platform reproducibility limitation from cycle 1 still applies.

## Classification

- Product-safe code: extended surface ruleset (superset, base ruleset and frozen B16 profile
  hash `6ad14226...` unchanged and test-pinned), coverage-completion profile + resolver +
  registry selection, diagnosis tool, 8 new tests (total suite 1422 passing plus the known
  Windows-only `spec.md` environmental failure).
- Candidate outcome: narrow pre-registered 0/64 target MET on this corpus and condition,
  with the control-gate failure reported; exploratory only; NOT product/release admissible
  (visible-text edits); no overclaim.
- Next research lever identified by diagnosis: candidate generation for content-word-dense
  regions (rules that can place a visible-text-safe edit anywhere), which word-list
  extension cannot solve.
