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
distribution is *perfectly null*. Zero detections requires pushing transformed scores below
the null mean, not merely to it: with per-window sigma_w = 0.30 and ~64 valid windows,
the transformed mean must land at or below roughly **0.45** (about 0.11 under threshold,
3 standard deviations) for E[detections] < 0.5 across all three corpora simultaneously.
Current transformed means sit near 0.52-0.53.

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
restriction. Expected effect: removes Channel-A evidence from scored output without any
new transform rules. Required next steps:
1. paired dev run v3-vs-v4 on a fresh corpus (new seed base, never-consumed);
2. report raw/NFKC/Cf-strip sanitizer robustness for both arms;
3. verify fidelity gates row-by-row before any outcome filtering.

### W2. Variance discipline (design phase)

To beat the statistical floor (Channel B), the scheduler must treat the *denominator* as
an objective: prefer plans that maximize final valid-window count and never introduce
repetition-mask events. Concretely: add `valid_denominator_ratio >= 1.0` as a hard
preference in plan selection and reject candidates whose application lowers the eligible
count. This raises detector noise *symmetrically*, which moves the effective decision
threshold away from the null distribution faster than it moves watermarked scores.

### W3. Threshold sharpening under spec §5 (protocol work)

The spec explicitly permits a 0.1% headline FPR given a responsibly large negative
calibration set (>= 10,000 negatives). A new measurement identity (following the Cycle-3
`open-detector-measurement-stability-v1` precedent) with a 16k-negative corpus yields a
threshold near the empirical null maximum, collapsing the null tail contribution
(Channel B) from ~1.9 expected detections toward ~0.2. This is a new measurement, not a
recalibration of the frozen one; the v4 contract's `threshold_must_not_be_recalibrated`
constraint remains respected because the old protocol stays intact and replayable.

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

1. Run the W1 paired dev experiment (v3 arm vs v4 arm, fresh seed base).
2. Land W2's denominator-aware selection behind a profile flag; ablate.
3. Draft the W3 measurement-identity contract and negative-corpus generation plan.
4. Extend W4 attribution tooling; wire into the next cycle report template.
