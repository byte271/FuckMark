# Cycle 5 Research Roadmap — Path to 0/192

**Status:** draft research roadmap (not a confirmation claim)
**Date:** 2026-08-24
**Author:** Cycle 5 coordinator (AI-assisted planning session)
**Frozen inputs:** exact-survival confirmation v4 contract, threshold `0.5570987654320988`
(target FPR 1%), three frozen confirmation corpora (seed bases 530000/540000/550000),
Cycle-4 aggregate result **5/192 detected** (97.40% measured evasion).

---

## 1. Where the five residual detections come from

Three independent quantitative channels, each of which alone is sufficient to keep the
result above zero:

### Channel A — recreated evidence (scheduler accounting gap)

`compute_observation_survival` disposes a root window as destroyed when its positional
mapping is UNMAPPED, AMBIGUOUS, or NEWLY_MASKED. But the HF weighted-mean detector scores
*every* eligible window of the retokenized output. A root tuple that survives verbatim at
a shifted position contributes g-value evidence even though positional accounting calls it
destroyed. Structural measurement on prose with the byte tokenizer showed v3 "fully
repaired" outputs still containing 104-307 verbatim root tuples. The repair phase
introduced in commit `62a289a` is restricted to statically uncovered windows and therefore
cannot respond to recreation at shifted positions.

### Channel B — the statistical floor of the frozen threshold

The calibration corpus measured 10/1024 exceedances at the frozen threshold (0.977%).
Applied to 192 samples that is an expectation of ~1.88 detections for text whose score
distribution is *perfectly null*. An expectation near two does NOT make a 0/192 outcome
impossible; it means merely matching the ordinary null distribution does not reliably
produce zero detections. The open research question is whether detector-blind
transformation can push the transformed watermarked score distribution far enough below
the frozen boundary — with per-window sigma_w = 0.30 and ~64 valid windows, roughly
0.45 or lower on average, about three standard deviations under threshold — to make a
reproducible 0/N result. Current transformed means sit near 0.52-0.53; the real-stack
validation in this cycle already measured individual transformed samples at 0.474-0.553
under the fixed scheduler, so the required regime is reachable per-sample and the
remaining work is consistency across the whole corpus.

### Channel C — margin-driven residuals

Eight of eleven Cycle-2-era residuals sat within +0.024 of threshold; the Cycle-4
residuals inherit this structure. Small per-sample score differences decide detection;
there is no separate "hard case" population. This makes variance reduction as valuable as
mean reduction.

## 2. What exists already (Cycle 5 starting assets)

| Asset | State |
| --- | --- |
| cover-greedy v3 + restricted repair (`62a289a`) | confirmed 5/192; blind to recreated tuples |
| ZRD destruction pool + pairwise completion v2 | 0/12 fresh dev run; not confirmatory |
| ZRD contraction extension catalog (`6fdb475`) | merged, unreleased |
| Beam v3 context-survival search | NOT promoted; frozen K2 lock forbids promotion (no matched-cost gain) |
| U+200C invisible mechanism | quarantined diagnostic only; sanitizer-fragile |
| Tuple-recreation closure metric (`root-tuple-recreation-closure-v1`) | NEW — added this cycle |
| cover-greedy v4 closure-aware scheduler (`closure-free-root-evidence-v1`) | NEW — added this cycle |

## 3. Cycle 5 workstreams

### W1. Closure-aware scheduling (implemented, needs dev evidence)

v4's repair objective is jointly `(positional survivors) + (tuple leaks)` with no window
restriction. Expected effect: removes any recreated-evidence channel from scored output
without new transform rules. Real-stack validation on fresh pinned GPT-2/SynthID samples
(seeds 700001+) measured tuple recreation in 0/7 transformed outputs once the corrected
coverage math landed, so the closure term is retained as a cheap correctness invariant
rather than a primary mechanism. The same validation showed positional survivors (5-29
per sample, mean g 0.569-0.75) carry the residual score mass, and the un-gated exact
repair phase now fires 4-6 times per sample with 0/7 detections at the frozen threshold.
Required next steps:
1. paired dev run v3-vs-v4 on a larger fresh corpus (new seed base, never-consumed);
2. report raw/NFKC/Cf-strip sanitizer robustness for both arms;
3. verify fidelity gates row-by-row before any outcome filtering;
4. attribute every residual detection to positional survivors vs recreation vs
   candidate-scarcity vs budget limits before choosing the next pool expansion.

### W2. Variance discipline (design phase)

To beat the statistical floor (Channel B), the scheduler must treat the *denominator* as
an objective: prefer plans that maximize final valid-window count and never introduce
repetition-mask events. Concretely: add `valid_denominator_ratio >= 1.0` as a hard
preference in plan selection and reject candidates whose application lowers the eligible
count. This raises detector noise *symmetrically*, which moves the effective decision
threshold away from the null distribution faster than it moves watermarked scores.

### W3. Sharper negative-control measurement (separate track; NOT the primary path)

The spec explicitly permits a 0.1% headline FPR given a responsibly large negative
calibration set (>= 10,000 negatives). Such a measurement identity is scientifically
interesting as an independent detector-characterization experiment, but it is NOT a valid
route to the primary 0/192 objective: changing from the frozen 1% FPR threshold to a
stricter one changes the ruler and cannot be reported as "5/192 became 0/192." The frozen
threshold 0.5570987654320988 stays fixed for every primary claim in this cycle. If the
sharper measurement identity is built, it is reported separately, never substituted, and
never used to select or tune candidates after scores are observed.

### W4. Residual taxonomy automation (instrumentation)

Extend `coverage_holes` with a per-residual decomposition: for every detected sample,
attribute score mass to surviving positional windows vs. recreated-tuple windows. Gate:
every future residual detection must be machine-attributable to one of the three channels
within one dev cycle, or the taxonomy itself is incomplete.

### W5. Confirmation sequence (only after W1-W4 dev gates pass)

1. freeze candidate profile + scheduler identity + budget;
2. commit preregistration contract with outcome classes mirroring v4
   (`REGRESSION` / `NEUTRAL` / `PARTIAL_IMPROVEMENT` / `CONFIRMATORY_IMPROVEMENT` /
   `ZERO_RESIDUAL`);
3. three fresh corpora, disjoint seed ledger, cross-corpus hash disjointness checks;
4. score once per corpus under the new measurement identity;
5. independent rerun (E21) before any release engineering.

## 4. Claim boundary (normative)

A 0/192 result would be scoped exactly like its predecessors: frozen open GPT-2 /
Hugging Face SynthID weighted-mean configuration, public development keys, fixed
threshold, measured corpora. It must not be presented as watermark removal in general,
transfer to proprietary detectors or unknown keys, or sanitizer-proof undetectability.
The U+200C mechanism stays out of every development and release profile.

## 5. Immediate next actions

1. Run the W1 paired dev experiment (v3 arm vs v4 arm, fresh seed base, larger N).
2. Expand the candidate pool where the coverage-hole audit shows positional survivors
   concentrate; ablate each new family against a kill criterion.
3. Land W2's denominator-aware selection behind a profile flag; ablate.
4. Extend W4 attribution tooling; wire into the next cycle report template.
5. Only after dev evidence materially approaches zero: design the next sealed
   confirmation under the UNCHANGED frozen measurement identity.
