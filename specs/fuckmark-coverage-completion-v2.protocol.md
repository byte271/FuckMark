# Frozen Research Protocol: Key-Blind Coverage Completion (v2)

Protocol ID: `coverage-completion-v2`
Cycle 2 of the budget-scaled effectiveness line. Frozen before any cycle-2 scoring. Hash-binding
freeze record: `specs/fuckmark-coverage-completion-v2.freeze.json`.

## 1. Objective and claim boundary

Level A: for the same fixed open detector and uncleaned text-only input path as cycle 1, test
whether a coverage-completion ruleset - the cycle-1 development ruleset plus an extended
surface spacing word list chosen from standard general-English function words - lowers
watermarked held-out detection on a new source-disjoint 64-source confirmation corpus relative
to cycle 1's 11/64 residual, with stretch target 0/64. Mechanistic endpoint: mean achievable
detector-n-gram coverage of the confirmation watermarked sources must be at least 0.80 (cycle 1
measured 0.819 overall with 0.682 among residual sources). The claim boundary is identical to
cycle 1: detector-specific detection reduction under the documented fixed condition only; no
removal, undetectability, unknown-key, proprietary-detector, cleaning-durability, or release
claims. Level B is not pursued; the candidate edits visible text.

## 2. Candidate mechanism

Profile `key-blind-coverage-completion-v2`: the cycle-1 registry (forward contractions, surface
spacing, lexical, syntax) EXTENDED by 65 additional surface spacing words, frozen below;
COVERAGE_GREEDY_KEY_BLIND scheduling over public-tokenizer n-gram disruption geometry
(ngram_len 5); replicate count 1; schedule seed base 1_140_000 plus sorted source index;
budget fixed at 16 operations (cycle 1 demonstrated coverage saturation below 16 on every
source, so a budget sweep carries no information; this is pre-registered, not tuned).
Selection accesses only public tokenizer geometry and the public detector n-gram length.

Frozen extension words (65, lowercase alphabetic, length >= 2, none already in the cycle-1
surface list, chosen from standard general-English function-word rankings, not mined from any
project corpus):

an, he, she, his, her, its, our, their, them, him, us, me, my, your, if, when, where, which,
who, what, how, why, because, so, than, then, there, here, all, any, each, more, most, some,
such, only, very, just, also, into, about, over, under, after, before, between, during,
through, without, while, do, does, been, being, would, could, should, may, might, must, were,
one, even, still, often

## 3. Data splits and source disjointness

- Development: fresh corpus at seed base 430000 (v3, 8 attack pairs per domain, 32 watermarked
  attack sources) plus the cycle-1 development corpus at seed base 410000 (repeat use,
  labeled; overfitting caveat noted) and the locally regenerated 401000 corpus. No cycle-2
  scoring may read the cycle-1 confirmation corpus at 420000.
- Confirmation: fresh corpus at seed base 440000 (v3, 16 attack pairs per domain, 64
  watermarked attack sources plus 64 unwatermarked controls), generated after this protocol is
  frozen and scored exactly once.
- Disjointness: pairwise text-hash overlap zero across 410000, 430000, and 440000 corpora;
  degenerate-generation collisions (cycle 1 recorded one against 401000) are checked and
  reported; any collision is a reportable deviation.

## 4. Generation and detector configuration

Identical to cycle 1 (pinned GPT-2 revision, CPU, temperature 0.8, top-k 50, top-p 0.95,
64 tokens, 16 attempts; HF SynthID weighted mean, ngram_len 5, public development keys,
per-corpus text-only calibration at target FPR 0.01, decision score >= threshold).

## 5. Controls, gates, robustness

All four paired controls scored. All cycle-1 section-6 gates apply unchanged (hard invariants,
protected spans zero, word edit rate <= 0.30, no introduced non-ASCII or hidden-category
codepoints, no introduced normalization instability, Cf-strip identity on introduced
characters, fixed-browser DOM text equality with archived screenshot).

## 6. Pre-registered endpoints and success criteria

Primary: confirmation transformed-watermarked detected count, target 0/64.
Improvement criterion (secondary, must hold for the cycle to count as progress): detected
count strictly below 11 (cycle 1 residual on an equally constructed corpus).
Mechanistic criterion: mean achievable coverage >= 0.80 on confirmation watermarked sources.
Control criteria: pristine watermarked >= 60/64 detected; transformed unwatermarked == 0/64;
all fidelity gates pass on 100% of rows.
Adverse results (residual detection, any gate failure, any cross-corpus text collision,
pristine-unwatermarked exceedances, zero-candidate sources) are reportable, never hidden.
The frozen budget (16) is recorded in the freeze-record appendix before confirmation scoring;
no post-hoc change.

## 7. Reproducibility

Canonical JSON artifacts with SHA-256 hashes; plan binds corpus, manifest, code commit, and
explicit detector_access_observed=False / secret_access_observed=False; evidence binds plan,
profile, ruleset, detector identity, calibration bundle, threshold; robustness report binds
plans and corpora; rendering manifest binds the plan; independent hash cross-check at the end;
full test suite, `git diff --check`, and clean status; local commits only, no pushes.
