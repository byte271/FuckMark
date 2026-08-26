# Cycle 7 — durable visible-edit research (PRODUCT_DISQUALIFIED)

Cycle 6 is **frozen**. Formal outcome: `NONZERO_RESIDUAL` **7/192**, not 0/192. That detector result remains historically valid and is **not** product-compliant FuckMark removal: Cycle 6 inserted visible ASCII spaces.

Cycle 7 researched collapse-resistant *visible* transforms. Those edits may preserve meaning. They still change user-visible text, so they are **PRODUCT_DISQUALIFIED** for the CLI/product path restored under `fuckmark-user-visible-invariance-v1`.

Cycle 8 (`docs/cycle8/`) is the exact-visible-projection generation. Do not promote Cycle 7 catalogs into `release_transform_registry()`.

## Live state (verified 2026-08-25)

See `docs/cycle7/live-state-audit.md`. Independent GitHub inspection:

- `main` HEAD `af341884fff211caeb24649a6ce79305c3491c6c` (PR #95 squash-merge)
- Cycle 6 freeze parent `ddccd74a9e0e710085b385fed98959f2730b9d60`
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
| Exploratory development (Stage A) | `810000` | used; do not keep expanding rules against it |
| Exploratory development / rule construction (Stage B1) | `860000` | used; do not keep expanding rules against it |
| Exploratory development / rule construction (Stage C1) | `870000` | active; topic frozen as `measurement protocol` |
| Validation development (Stage B3) | `820000` | used as Stage B3 disjoint validation; do not retune on it |
| Validation development (Stage C, reserved) | `880000` | **PUBLICLY_EXPOSED** by closed unmerged PR #98; not eligible as unseen validation |
| Confirmation reserved | `830000`, `840000`, `850000` | must not be inspected |

Confirmation seeds were chosen as unused 10k blocks before any Cycle 7 detector look.

## Whitespace-collapse sanitizer

See `docs/cycle7/whitespace-collapse-v1.md`.

Cycle 7 evaluation arms:

`raw`, `nfkc`, `cf_strip`, `nfkc_cf_strip`, `ws_collapse`, `ws_collapse_nfkc_cf_strip`

The Cycle 6 frozen sanitizer module is unchanged.

## Durable transform families

See `docs/cycle7/durable-families.md`. Catalog `cycle7-durable-rule-catalog-v4`.

Stage A (`v2`) families:

1. Unambiguous contractions and closed orthography (Family 1).
2. Attested open ↔ hyphenated compounds (Family 2).
3. In-word ASCII apostrophe ↔ U+2019 (Family 3).

Stage B (`v3`) additions, aimed at natural site density:

4. Sentence-boundary newline (layout; survives `whitespace-collapse-v1` because that sanitizer keeps LF).
5. Bounded optional complementizer / object-relative `that`.
6. Sentence-initial discourse comma.
7. Attested prenominal hyphen modifiers.
8. Parenthetical conjunctive adverb.
9. Coordinating-conjunction comma (`and`/`but`/`or`), with determiner-gated insert.

Stage C (`v4`) additions, aimed at higher natural site density after Stage B showed families 5–9 were sparse:

10. Clause punctuation newline (`,` / `;` / `:` + space ↔ mark + LF).
11. Optional `of` after `all` / `both` / `half` before a closed determiner/possessive.

These change tokens without relying on repeated U+0020. They survive ASCII whitespace collapse by construction. Family 3 also survives NFKC and Cf-strip. Family 4 is a formatting channel: VERIFIED against the six Cycle 7 sanitizer variants, not against an unlisted reflow sanitizer.

Quote interiors may receive these durable edits under `quote-container-durable-v1` without changing quote delimiters. Cycle 6 `quote-container-surface-spacing-v1` still admits only spacing inside quotes.

## Stage A result

Family 1 detector attachment on seed `810000` was **`INSUFFICIENT_EVIDENCE`**: Cycle 6 spacing 0/4 raw / 4/4 after collapse; durable 4/4 raw and 4/4 after collapse.

Families 2–3 raise candidate density on the same frozen texts (see `evidence/cycle7-stage-a-2026-08-25/family2-density.json`). Detector rescore of those texts under catalog v2 remains **`INSUFFICIENT_EVIDENCE`**: durable 4/4 raw and 4/4 after collapse; Cycle 6 spacing 0/4 raw and 4/4 after collapse; combined 1/4 raw and 4/4 after collapse.

Details: `docs/cycle7/stage-a-decision.md`.

## Stage B

Stage B1 on seed `860000` looked **`PROMISING_DEVELOPMENT`** on a tiny detector snapshot (durable 2/4 after collapse). Disjoint validation seed `820000` reproduced density/geometry but **not** the detector reduction (durable 4/4 after collapse). Overall Stage B decision: **`INSUFFICIENT_EVIDENCE`**. Details: `docs/cycle7/stage-b-decision.md`.

Seed `820000` is spent as validation. Seed `880000` is **PUBLICLY_EXPOSED** by closed unmerged PR #98 and is not eligible as unseen validation. Seeds `830000` / `840000` / `850000` remain unseen confirmation reserves.

## Stage C

Stage C1 on seed `870000` (topic frozen as `measurement protocol`) added clause-punctuation newlines and optional quantifier `of`. Mean durable candidates: **4.75** (still the Stage B four-site regime). Quantifier `of` mean **0.00**. Collapse-surviving intact/root **0.715**. Detector: durable **3/4** after collapse; Cycle 6 spacing **4/4** after collapse. Overall: **`INSUFFICIENT_EVIDENCE`**. Seed `880000` was not inspected by Stage C on `main`. Closed unmerged PR #98 later exposed it. Details: `docs/cycle7/stage-c-decision.md`.

Not claimed:

- Cycle 7 formal confirmation
- ZERO_RESIDUAL
- Human-fidelity validation
- Threshold or FPR manipulation
- Neural rewriting
