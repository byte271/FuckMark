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

### W1. Closure-aware scheduling (implemented, dev-run measured)

v4's repair objective is jointly `(positional survivors) + (tuple leaks)` with no window
restriction. Expected effect: removes any recreated-evidence channel from scored output
without new transform rules. Real-stack validation on fresh pinned GPT-2/SynthID samples
(seeds 700001+) measured tuple recreation in 0/7 transformed outputs once the corrected
coverage math landed, so the closure term is retained as a cheap correctness invariant
rather than a primary mechanism. The same validation showed positional survivors (5-29
per sample, mean g 0.569-0.75) carry the residual score mass, and the un-gated exact
repair phase now fires 4-6 times per sample with 0/7 detections at the frozen threshold.

A fresh paired development experiment on a hash-frozen 16-sample corpus
(`tools/cycle5_dev_paired_run.py`, single-process generation then separate scoring pass,
seed base 710000, budget 16, frozen threshold unchanged) produced:

| Arm | Detected | Mean score | Mean drop |
| --- | --- | --- | --- |
| pristine | n/a | ~0.61 | - |
| fixed v3 | 2/16 | 0.530 | 0.086 |
| cover-greedy v4 | 2/16 | 0.523 | 0.094 |

An identical-corpus arm with the expanded `zrd_destruction_transform_registry` pool
(contraction extensions, sentence-leading spacing, extended word list) reproduced the
same two residuals byte-identically and changed no detection counts: pool expansion does
not address this residual class.

### Residual root cause (frozen-corpus forensics)

Both residual sources (indices 5, 12) are QUOTE-DOMINANT continuations: the model
generated multi-sentence direct dialogue. Blanket quotation-span protection rejects
46-53 of roughly 50 candidates per source, leaving 2-3 eligible operations and 53-54
intact root windows whose above-null g-values keep the weighted-mean score near 0.62.
Because the detector mean runs over valid windows only, destroying every window OUTSIDE
the quotes cannot lower a score carried almost entirely by untouched quote-interior
windows. Classification per the residual taxonomy: PROTECTED-REGION-UNREACHABLE.

### W6. In-quote durable surface rules (proposed; requires full family onboarding)

The fidelity principle protects quotation MEANING, and durable spacing/punctuation
surface edits are meaning-preserving inside dialogue exactly as outside. Allowing only
surface-tier spacing rules inside quotation spans - while keeping contractions, lexical,
syntax families and all hard invariants blocked - would remove the unreachable region
without touching quoted wording. This is a fidelity-policy change and must follow the
full family protocol before any adoption: mechanism hypothesis, deterministic
implementation, dedicated blind fidelity review packet covering in-quote edits,
sanitizer analysis, isolated ablation against this exact residual class, and an explicit
kill criterion. Until that gate passes, quote-dominant samples remain protected-region
residuals by design and any headline count inherits them.

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

---

## 6. Cycle 6 update — quote-container reachability (2026-08-25)

### Live base and reproduction

Cycle 6 started from PR #87 head `92371eedf84848ad3b67df8e1a34fc53006f2ed6`
on main base `4f69271c12e5b33072f0727c0168fcc4783be6f8`. The exact seed-720000
fresh16 scores reproduced byte-for-byte at six-decimal reporting precision:

| Registry / scheduler | Detected | Mean score | Artifact hash from PR #87 |
| --- | ---: | ---: | --- |
| coverage v4 | 2/16 | 0.519564 | `4a0082935244fd71ed5bb12252ca5fe96f347f9c1d0f28229c709e8e8f1b9b3e` |
| ZRD v4 | 2/16 | 0.521805 | `f3570d2a407ad18f8a3f08f1dc7c4e3f361e67d6726f7c8ce54e4aef51e53aa8` |

The original corpus hash `2cbb8483fcfcc1be55c7f0a436aa3664fa3b6c50654ddaa63fd615964434d1dd`
binds `recorded_at_utc`, so an identical regeneration cannot reproduce that container hash.
Cycle 6 adds the timestamp-independent content hash
`b114cf4d869c5a5d78ac52855a1a480b1f0e605137aee2cb269062880fcc22d3`
and keeps the original container hash as historical provenance.

### Complete original-residual classification

| Sample | Quote-blocked candidates | Selected | Intact (quote/outside) | Tuple leaks | Score | Exact classification |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 30 | 8 | 30 (26/4) | 33 | 0.560003 | protected-region unreachable; candidate exhausted |
| 10 | 57 | 2 | 51 (47/4) | 51 | 0.617551 | protected-region unreachable; candidate exhausted |

Neither residual exhausted the operation budget. Sample 8 had no candidate conflicts;
sample 10 had one conflict and only three admitted candidates, so neither stronger greedy
ranking nor more budget could reach the quote-contained observations under blanket
protection. Quote-contained observations contributed 45.41% and 80.84% of the final
detector numerator, respectively; as signed excess above the 0.5 null mean, the fractions
were 50.69% and 91.51%. The full observation-to-character-to-protection mapping is emitted
by `tools/cycle6_residual_reachability.py`.

### One-family isolated ablation

`quote-container-surface-spacing-v1` separates exact protected content from quotation
container policy. It admits only existing surface-spacing rule types strictly inside one
recognized quote container. Contractions, lexical templates, syntax templates, quote
delimiters, URLs, numbers, code, citations, identifiers, and user ranges remain blocked.
Every admitted operation adds exactly one ASCII space and is replay-validated from the
trace. No invisible Unicode is used.

With the registry change only—same v4 scheduler, B16 budget, detector, threshold, corpus,
and denominator—the fresh16 development result became:

| Arm | Detected | Mean score | Raw | NFKC | Cf strip | Combined |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| quote-safe ZRD v4 | **0/16** | **0.510771** | 0/16 | 0/16 | 0/16 | 0/16 |

Original residual changes:

| Sample | Before | After | Selected | Intact | Tuple leaks |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 | 0.560003 | 0.514545 | 16 | 5 | 6 |
| 10 | 0.617551 | 0.486465 | 16 | 3 | 3 |

This is development detector-zero, not geometry-zero. Across all sixteen outputs v4
intact counts were `6,7,5,13,4,6,5,6,5,4,3,8,2,5,4,9`; tuple leaks were
`6,7,5,13,4,7,5,6,6,8,3,8,5,6,4,9`. The geometry target remains open and is not
conflated with the measured 0/16 detector result.

### Fidelity and adverse findings

All selected quote operations preserve non-whitespace quoted bytes, attribution words,
numbers, exact protected entities, negation, modality, and quote delimiters. NFKC and Cf
stripping leave ASCII spaces unchanged. Aggressive whitespace collapse removes this
mechanism; that adverse limitation is explicit.

The deterministic blind packet hash is
`4bde66e0a9f2148373afa78213aecf582dab5d6b6a756f2b96300699181b41fd`.
Independent human review is pending. Therefore this cycle does not claim the family is
release-ready or fidelity-complete even though the frozen detector result reached zero.

### Rejected or demoted approaches

* Global removal of quote protection: rejected; it admits semantic rewriting of quoted
  content and weakens provenance guarantees.
* Quote-interior contraction-only registry: insufficient for sample 10, which contains no
  existing reversible contraction candidate in the dominant protected continuation.
* Quote-boundary-only retokenization: insufficient reach for 47-51 interior intact windows.
* Invisible Unicode: remains forbidden and sanitizer-fragile.
* Detector-score planner ranking: forbidden; the successful planner saw geometry only.
* A focused exact-greedy replay on samples 8 and 10 was demoted: it improved sample 8
  geometry only from 5/6 to 4/4 intact/leak windows and left sample 10 at 3/3, while
  still consuming all 16 operations. It did not reach geometry zero or reduce cost, so
  no search change was promoted after detector zero was already achieved.

### Frozen development evidence and disjoint replication

The timestamp-independent scored result hash for the seed-720000 corpus is
`2e1bcf862bfa0d24423ac5f2d8bca6374e3d72020fc9f092e91f5d4f7d66152c`.
The complete post-fix geometry artifact hash is
`fb27790381207b4edee4cbb1febebbc1480347391008638f2ec29b9d00339e31`.
All 16 plans consumed the B16 budget. Exact-protected positional residual counts were
`0,0,0,1,2,0,0,0,0,0,0,2,0,0,0,0`; quote-container positional residual counts were
`0,0,0,0,0,0,3,0,4,0,3,0,0,0,0,0`. Quote-container residuals are measured separately
because quote containers are no longer exact-protected content under this policy.

After freezing the registry, quote policy, v4 scheduler, B16 budget, tokenizer/model
revision, detector, threshold, and sanitizer policy, a disjoint seed-730000 development
corpus was generated. Its container hash is
`12243766af4bc642f10c02a503de7b2794abcf59102e9bce108ca72008732dc1` and stable content
hash is `e055e0f7a6417c9294a7ed55718cae6fba276cab1256869e1f8babe9d1a84208`.
It also produced **0/16** detections for raw, NFKC, Cf strip, and combined, with v4 mean
score `0.506611`. Its stable scored result hash is
`13731d69a2a710c6a0d37aacb63af23e0a6c112be2093438a64dd074431d2848` and geometry
artifact hash is `d8a6090e9dd18e5679dac62925b4f234b051c1e39ae486784ccfa1b1a0fb3485`.

This disjoint result is replication on unseen development data, not a formal confirmation
and not a universal claim. Independent fidelity adjudication remains a release gate before
designing a new sealed 0/192 experiment.
