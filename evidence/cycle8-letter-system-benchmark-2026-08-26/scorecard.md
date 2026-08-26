# Cycle 8 letter-x1 system benchmark scorecard

Measurement, not confirmation. Letter-x1 is not in `release_transform_registry()`.
Evidence label: `HYPOTHESIS`. Decision: `PROMISING_DEVELOPMENT`.
Formal confirmation readiness: `NOT_READY`.

## Detector

- model: `openai-community/gpt2`
- revision: `607a30d783dfa663caf39e06633721c8d4cfcd7e`
- implementation: cycle8_hf Hugging Face SynthID Weighted Mean
- threshold: `0.5570987654320988`
- comparison: `score >= threshold`
- FPR assumption: frozen Cycle 6 GPT-2 / Hugging Face SynthID Weighted Mean threshold 0.5570987654320988

## Effectiveness

| Claim | Result | Label |
| --- | --- | --- |
| Fresh letter-x1 raw WM | 0/128 | `HYPOTHESIS` |
| Fresh letter-x1 raw UW | 0/128 | `HYPOTHESIS` |
| Fresh letter-x1 max score | 0.5540663040663041 | `HYPOTHESIS` |
| Fresh letter-x1 min gap below threshold | 0.003032461365794714 | `HYPOTHESIS` |
| Fresh space-x1 on the same corpora | 1/128 | `HYPOTHESIS` |
| Experimental letter-x1 0/192 | 0/192 (128 seen + 64 independent) | `HYPOTHESIS` |
| Frozen historical space-x1 930000+940000 | 1/128 | `HYPOTHESIS` |

Do not collapse experimental 0/192 into the fresh 0/128. Do not call either result formal confirmation.

### Fresh per-domain letter-x1

| Domain | n | detected | max score |
| --- | ---: | ---: | ---: |
| conversational_prose | 32 | 0 | 0.5272727272727272 |
| general_explanatory | 32 | 0 | 0.5540663040663041 |
| structured_instructional | 32 | 0 | 0.5141077441077441 |
| technical_explanation | 32 | 0 | 0.5398848296044558 |

## Visibility

- fixture visible-projection: `21/21` `VERIFIED`
- failures: none
- CLI identity on `I do not agree.`: `True`
- Chromium `pre`: `VERIFIED`
- Chromium textarea: `VERIFIED`
- Chromium contenteditable: `VERIFIED`
- WebKit/Safari: `UNKNOWN`
- terminal pixels: `UNKNOWN`

## Durability

- cf_strip: `VERIFIED`
- cli_stdin: `VERIFIED`
- clipboard_xclip: `VERIFIED`
- latin1: `REJECTED`
- nfc: `VERIFIED`
- nfkc: `VERIFIED`
- shell_pipe_cat: `VERIFIED`
- utf8_file: `VERIFIED`
- utf8_in_memory: `VERIFIED`
- vim_binary_noeol: `VERIFIED`
- vim_default_save: `REJECTED`
- ws_collapse: `VERIFIED`

- frozen sanitizers match raw on fresh letter: `True`
- Mn-strip removes carrier: `True`
- default-ignorable-strip removes carrier: `True`
- Cf-strip preserves carrier: `True`

## Safety

- protected-span pass rate: `21/21`
- non-ASCII fail closed: `True`

## Efficiency

- selected-site cap: `192`
- fresh mean insertions: `186.015625`
- fresh mean UTF-8 overhead bytes: `372.03125`
- fresh mean token-count delta: `515.546875`
- fresh max transformed token count: `608`
- fresh cap-binding watermarked rows: `106`
- approaches GPT-2 1024 context: `False`

## Performance

- label: `SOURCE-BOUND`
- short mean transform: `15.922345916502916` ms
- medium mean transform: `595.0850475019251` ms
- long mean transform: `1481.9776929944055` ms
- host: `Linux-6.12.94+-x86_64-with-glibc2.39`
- python: `3.12.3`
- cpu_count: `4`

## Reproducibility

- deterministic output: `True`
- fresh independent corpora: `2`
- letter zero on both fresh corpora: `True`

## Platform

- Linux this host: `VERIFIED`
- macOS CLI identity: `SOURCE-BOUND`
- Windows CLI identity: `SOURCE-BOUND`
- Package E2E on CI covers CLI identity on Linux/macOS/Windows. Letter-x1 is development-only Python and was executed on this Linux host.

## Weaknesses

- Mn-strip removes U+034F
- default-ignorable-strip removes U+034F
- latin-1 cannot roundtrip U+034F
- ordinary vim save may append a trailing newline
- exact-byte search for substrings such as do not can miss after intra-word insertion
- selected-site cap 192 binds on 106 of 128 fresh watermarked rows
- 980000 max score 0.55407 leaves only about 0.003 margin
- Safari/WebKit rendering is UNKNOWN on this Linux host
- terminal pixel equality is UNKNOWN
- accessibility/screen-reader behavior is UNKNOWN
- macOS and Windows letter-x1 transform execution is SOURCE-BOUND, not re-run here

scorecard_hash: `a7e326d78101df07a21d2da595d699d7c264214d3d13028ce1676dff0bea7cdf`
