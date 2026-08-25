# Decision: restore exact user-visible invariance

Live GitHub at the start of this work:

- repository `byte271/FuckMark` exists and is public;
- `main` HEAD `d7eeb0f905b7046ddc4a4d8281354f06713d58b0` (PR #96 squash-merge);
- PR #93, #94, #95, #96 merged;
- no open PRs;
- no open issues;
- latest tag `v0.2.0`;
- this environment's prebuilt checkout was stale at `ddccd74` until `origin/main` was fetched.

## Violation

The public CLI called `release_transform_registry()`, which resolved to `default_contraction_rules()`. Local reproduction before the fix:

| Input | CLI output |
| --- | --- |
| `I do not agree.` | `I don't agree.` |
| `We cannot continue.` | `We can't continue.` |
| `You should not do that.` | `You shouldn't do that.` |

Hard invariants allowed this because they checked protected spans, negation, and modality, not visible projection.

Cycle 6 formal `NONZERO_RESIDUAL` 7/192 remains valid detector science and is **PRODUCT_DISQUALIFIED** (visible U+0020 runs).

Cycle 7 Stage A/B/C remain **INSUFFICIENT_EVIDENCE** and **PRODUCT_DISQUALIFIED** (visible word/punctuation/layout edits).

U+200C remains diagnostic: product-aligned on visibility, **REJECTED** as a durable mechanism because Cf-strip removes it.

## Repair

- Versioned contract `fuckmark-user-visible-invariance-v1`.
- Visible-projection validator and product hard gate.
- `release_transform_registry()` is an empty product registry.
- CLI `release-cli-v4` fail-closes to original text.
- Historical contraction/lexical/syntax/spacing registries remain for replay under explicit names.
- Cycle 8 starts invisible-carrier research. Combining grapheme joiner U+034F is a durable-track sanitizer candidate, not a release promotion.
- The GitHub CI installed-CLI check still expected contraction output after the product path was emptied. That leftover assertion is now aligned with unchanged visible text.
