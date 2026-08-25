# Cycle 7 — durable transform development

Cycle 6 is **frozen**. Formal outcome: `NONZERO_RESIDUAL` **7/192**, not 0/192.

This directory starts Cycle 7 development. It does not retune Cycle 6 and does not authorize a new formal confirmation.

## Live state (verified 2026-08-25)

See `docs/cycle7/live-state-audit.md`. Independent GitHub inspection matched the Cycle 6 freeze:

- `main` HEAD `ddccd74a9e0e710085b385fed98959f2730b9d60`
- PR #93 and PR #94 merged
- Recovery run `32886342498` success
- Aggregate hash `30577aafaffd0c50f0ddb384a4509eb0bb93e4374bf39704869ddbf5053186a4`

## Spent-corpus rule

Do not use as Cycle 7 development, tuning, or confirmation data:

- `720000`, `730000` (earlier development)
- `760000`, `770000`, `780000` (formal confirmation; the 7 residuals are spent)

The 7 formal residuals may be used only for high-level forensic classification. They must not be used as development examples.

## Seed ledger

See `docs/cycle7/seed-ledger.md` and `fuckmark/cycle7/ledger.py`.

| Role | Seed base | Status |
| --- | --- | --- |
| Exploratory development (Stage A) | `810000` | in use |
| Validation development (Stage B) | `820000` | reserved, unused |
| Confirmation reserved | `830000`, `840000`, `850000` | must not be inspected |

Confirmation seeds were chosen as unused 10k blocks before any Cycle 7 detector look.

## Whitespace-collapse sanitizer

See `docs/cycle7/whitespace-collapse-v1.md`.

Cycle 7 evaluation arms:

`raw`, `nfkc`, `cf_strip`, `nfkc_cf_strip`, `ws_collapse`, `ws_collapse_nfkc_cf_strip`

The Cycle 6 frozen sanitizer module is unchanged.

## Durable transform family (first attempt)

Unambiguous contractions (existing catalog + reversible have-forms) and UK/US `towards`/`toward`, `amongst`/`among`.

These change tokens without relying on repeated U+0020. They survive ASCII whitespace collapse by construction.

Quote interiors may receive these durable edits under `quote-container-durable-v1` without changing quote delimiters. Cycle 6 `quote-container-surface-spacing-v1` still admits only spacing inside quotes.

## Stage A result

**`INSUFFICIENT_EVIDENCE`** as a Cycle 6 replacement.

Cycle 6 spacing: 0/4 raw detections, 4/4 after whitespace collapse (fresh seed `810000`).

Cycle 7 durable family: 4/4 raw and 4/4 after collapse. Collapse-survival works on contraction-rich fixtures; natural density on GPT-2 TinyDev text is too low.

Details: `docs/cycle7/stage-a-decision.md`.


- Not a Cycle 7 formal confirmation
- Not a ZERO_RESIDUAL claim
- Not human-fidelity validation
- Not threshold or FPR manipulation
- Not neural rewriting
