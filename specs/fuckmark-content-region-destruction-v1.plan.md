# Cycle 4 — Content-Region Destruction Research Plan v1

Status: development plan on `research/content-region-destruction-v1`, child of the merged
Cycle-4 exact-survival PR #82. The frozen confirmation contract
`specs/fuckmark-exact-survival-confirmation-v4.contract.json` is NOT modified.

## Why

The Cycle-3 confirmation left 12/192 (6.3%) pooled transformed-watermarked detections with
residuals concentrated within ±0.025 of the fixed threshold, and budget-scaled evidence
showed pools saturating at 9–13 edits while requested budgets ran to 16+. Two structural
gaps follow:

1. The proxy union-coverage scheduler does not maximize what detection actually consumes —
   surviving weighted root observations after retokenization.
2. The visible candidate pool leaves sentence-leading positions and many mid-frequency
   content/function words unreachable, so budgets exhaust before coverage does.

## What this cycle adds

1. **Exact-survival greedy v2** (`fuckmark/experiments/exact_survival_greedy_v2.py`,
   `exact-survival-greedy-key-blind-v2`): frozen v1 single-candidate greedy plus one
   deterministic pairwise-completion pass for saturated sources. Pair candidates are
   bounded (lexicographically-first feasible IDs) so replay is exact. Detector-blind and
   key-blind properties are unchanged and enforced by validation.
2. **Destruction pool** (`content-region-destruction-v1` profile): a strict superset of the
   Cycle-3 ruleset adding:
   - `surface-space-before-sentence` (`general-word-space-before-v1`): one visible leading
     space before an ASCII word that follows ". ", "? ", or "! " — wording bytes preserved;
   - ~120 additional lowercase common-word trailing-space rules.
   All edits are visible whitespace insertions: NFC-stable, single-line, copy/paste-durable,
   and hard-invariant screened like every other surface rule.
3. **Sanitizer robustness reporting** (`fuckmark/sanitizer_robustness.py`,
   `sanitizer-robustness-report-v1`): every transformed text is scored under raw, NFKC,
   Cf-strip, and NFKC+Cf-strip conditions; introduced invisible-codepoint counts are
   recorded per arm; any arm introducing invisible codepoints is visible in the report by
   construction rather than silently mixed into visible-only results.
4. **Diagnostic upper bound**: the quarantined U+200C registry may appear only as an
   explicitly labeled diagnostic arm (`D_u200c_exact_v2_diagnostic`) in development runs.
   It remains forbidden in default, development, release, CLI, and automatic selection
   paths per its quarantine contract.

## Relationship to the frozen Cycle-4 confirmation

PR #82 froze scheduler v1, arms A (proxy scheduling) vs B (exact greedy v1), seed bases
530000/540000/550000, the inherited fixed threshold 0.5570987654320988, and a
preregistered outcome policy. This branch executes that confirmation through the existing
`cycle4-exact-survival-confirmation.yml` workflow without touching its inputs. The
12-source development run above already reproduces the B-vs-A direction locally
(0/12 vs 2/12 detected). Scheduler v2 and the destruction pool are separate, later-stage
candidates: if the frozen confirmation classifies as CONFIRMATORY_IMPROVEMENT or
PARTIAL_IMPROVEMENT, a follow-up cycle may freeze a new contract pairing arm C (destruction
pool + v2) against the then-current best arm under the same fixed threshold and fresh
disjoint seeds.

## Claim boundary

No watermark-removal, undetectability, unknown-key, proprietary-detector, normalization-
durability, or release claim is made or supported here. Blind human fidelity evidence
remains NOT_PROVIDED. All effectiveness numbers from the dev runner are exploratory
development evidence on watermarked TinyDev-style sources with public development keys.
