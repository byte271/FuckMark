# Audit follow-up (2026-08-28)

This directory records 0.4.1 audit follow-up that does not rewrite frozen confirmation files.

Audited main: `d7dc98b7ee99fc46b767c93444a9f051fdbea2ba`.

## D16

`evidence/cycle7-stage-a-2026-08-25/README.md` is LF in Git. The historical `SHA256SUMS.txt` digest is the CRLF encoding of the same text. See `evidence/cycle7-stage-a-2026-08-25/CHECKSUM-PROVENANCE.md`. The original manifest is unchanged.

## E01

Transfer tests now compare `live_mix_hash(source)` to the stored `mix.text_sha256`. Permitted drift is listed in `tests/audit_mix_replay.py` with old and new hashes. Gate v2 confirmation live mix hashes still match all 384 stored transformed hashes. Unexplained drift fails the test. Stored detector scores are not inherited for drifted samples.

## E02 / E03

`render-v2.json` in `evidence/audit-fixes-2026-08-27/` remains the frozen AAAA/BBBB control harness. It is not rewritten.

`render-payload-v2.json` in this directory is a dated this-host Chromium measurement of the actual U+034F/U+FE00 mix sentence `I do not agree.` on `pre`, `textarea`, and `contenteditable`, plus AAAA negative/positive controls and a below-fold pair that must be `INCOMPLETE` rather than VERIFIED. Safari/WebKit and terminal pixels remain UNKNOWN. Viewport equality is only claimed for the captured window. No UNKNOWN-to-PASS promotion.

## E04

Restored archive pointers: `docs/cycle8/gate-v2.md` and `docs/cycle8/mix-second-model-transfer.md`. Current map: `docs/research.md`.
