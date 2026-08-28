# Research archive

This directory's user manuals are [`install.md`](install.md), [`cli.md`](cli.md), [`limits.md`](limits.md), and [`website.md`](website.md).

Frozen scientific records are not the user manual. They stay in the repository so the product claims can be audited.

## Live versus historical authorization

| Record | What it is | CLI at that time |
| --- | --- | --- |
| Gate v2 confirmation READMEs | Frozen 188/192 identity and 0/192 mix after required sanitizers | Historical sentence "CLI remains empty" / `process_text` identity **at confirmation time**. Live product is authorized letter-mix. |
| `cycle8-product-authorization-v1` | Live authorization | Public CLI applies mix (`release-cli-v5`) |
| mix-freeze / mix-confirmation 830000+ | Historical 0/192 on earlier seeds | Not rewritten |

## Evidence index

- Gate v2 confirmation: [`evidence/cycle8-gate-v2-confirmation-2026-08-27/README.md`](../evidence/cycle8-gate-v2-confirmation-2026-08-27/README.md)
- DeepMind 30-key transfer: [`evidence/cycle8-mix-deepmind-transfer-2026-08-27/README.md`](../evidence/cycle8-mix-deepmind-transfer-2026-08-27/README.md)
- DistilGPT2 n=16: [`evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/README.md`](../evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/README.md)
- H16 sanitizer audit: [`evidence/h16-local/README.md`](../evidence/h16-local/README.md)
- F01–F07 render/path notes: [`evidence/audit-fixes-2026-08-27/README.md`](../evidence/audit-fixes-2026-08-27/README.md)
- 0.4.1 audit follow-up: [`evidence/audit-fixes-2026-08-28/README.md`](../evidence/audit-fixes-2026-08-28/README.md)

Cycle 8 archive pointers:

- [`cycle8/gate-v2.md`](cycle8/gate-v2.md)
- [`cycle8/mix-second-model-transfer.md`](cycle8/mix-second-model-transfer.md)

Also:

- [`../evidence/`](../evidence/) — confirmation corpora, scorecards, and hashes
- [`../specs/`](../specs/) — frozen contracts and protocol JSON
- [`../evidence/frozen-spec-revision-2/spec.md`](../evidence/frozen-spec-revision-2/spec.md) — historical research specification (old project name; not the product identity)

Do not treat those files as installation or usage docs.
