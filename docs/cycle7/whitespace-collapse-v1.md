# whitespace-collapse-v1

Sanitizer identity: `ascii-horizontal-run-collapse-preserve-newlines-v1`.

This is a **new** Cycle 7 sanitizer. It does not modify frozen `fuckmark/sanitizer_robustness.py`.

## Exact behavior

1. Map CR LF and CR to LF.
2. Preserve LF. Do not join lines.
3. On each line, replace every maximal run of U+0020 SPACE and U+0009 HT with one U+0020 SPACE.
4. Do not trim a leftover single leading or trailing space.
5. Do not collapse other Unicode whitespace, including NBSP (U+00A0).
6. Do not strip Cf characters (that is a separate arm).

## Cycle 7 variant IDs

| ID | Definition |
| --- | --- |
| `raw` | identity |
| `nfkc` | Unicode NFKC (imported from the frozen Cycle 6 helper) |
| `cf_strip` | drop Unicode category Cf |
| `nfkc_cf_strip` | Cf-strip after NFKC |
| `ws_collapse` | whitespace-collapse-v1 |
| `ws_collapse_nfkc_cf_strip` | collapse, then NFKC, then Cf-strip, then collapse again so NFKC-introduced ASCII spaces also collapse |

Whitespace robustness may be claimed only if the `ws_collapse` and `ws_collapse_nfkc_cf_strip` arms pass.
