# Research archive

This directory's user manuals are [`install.md`](install.md), [`cli.md`](cli.md), [`limits.md`](limits.md), [`website.md`](website.md), the public sanitizer-restore bench [`robustness.md`](robustness.md), and the no-install [`demo.html`](demo.html). The demo uses fixed samples and frozen scores; it is not a live detector.

Frozen scientific records are not the user manual. They stay in the repository so the product claims can be audited.

## Live versus historical authorization

| Record | What it is | CLI at that time |
| --- | --- | --- |
| Gate v2 confirmation READMEs | Frozen 188/192 identity and 0/192 mix after required sanitizers | Historical sentence "CLI remains empty" / `process_text` identity **at confirmation time**. Live product is authorized letter-mix. |
| `cycle8-product-authorization-v1` | Historical mark-only authorization | Public CLI applied U+034F / U+FE00 (`release-cli-v5`) |
| `cycle8-product-authorization-v2` | Live five-layer authorization | Public CLI applies mark plus C0/C1 plus Me plus Cf plus interlinear annotation (`release-cli-v12`) |
| mix-freeze / mix-confirmation 830000+ | Historical 0/192 on earlier seeds | Not rewritten |

## Evidence index

- Public sanitizer-restore bench (`fuckmark-robustness-bench-v1`, model-free, does not rerun detectors): [`robustness.md`](robustness.md), [`specs/fuckmark-robustness-bench-v1.protocol.md`](../specs/fuckmark-robustness-bench-v1.protocol.md)
- Gate v2 confirmation: [`evidence/cycle8-gate-v2-confirmation-2026-08-27/README.md`](../evidence/cycle8-gate-v2-confirmation-2026-08-27/README.md)
- DeepMind 30-key transfer: [`evidence/cycle8-mix-deepmind-transfer-2026-08-27/README.md`](../evidence/cycle8-mix-deepmind-transfer-2026-08-27/README.md)
- DistilGPT2 n=16: [`evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/README.md`](../evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/README.md)
- DistilGPT2 combo stress exploratory: [`evidence/cycle8-distilgpt2-combo-stress-exploratory-2026-08-28/README.md`](../evidence/cycle8-distilgpt2-combo-stress-exploratory-2026-08-28/README.md)
- H16 sanitizer audit: [`evidence/h16-local/README.md`](../evidence/h16-local/README.md)
- F01–F07 render/path notes: [`evidence/audit-fixes-2026-08-27/README.md`](../evidence/audit-fixes-2026-08-27/README.md)
- 0.4.1 audit follow-up: [`evidence/audit-fixes-2026-08-28/README.md`](../evidence/audit-fixes-2026-08-28/README.md)
- Dual-layer stress exploratory: [`evidence/cycle8-dual-layer-stress-exploratory-2026-08-28/README.md`](../evidence/cycle8-dual-layer-stress-exploratory-2026-08-28/README.md)
- Combo stress exploratory n=192: [`evidence/cycle8-combo-stress-exploratory-n192-2026-08-28/README.md`](../evidence/cycle8-combo-stress-exploratory-n192-2026-08-28/README.md)

Cycle 8 archive pointers:

- [`cycle8/gate-v2.md`](cycle8/gate-v2.md)
- [`cycle8/mix-second-model-transfer.md`](cycle8/mix-second-model-transfer.md)

Also:

- [`../evidence/`](../evidence/) — confirmation corpora, scorecards, and hashes
- [`../specs/`](../specs/) — frozen contracts and protocol JSON
- [`../evidence/frozen-spec-revision-2/spec.md`](../evidence/frozen-spec-revision-2/spec.md) — historical research specification (old project name; not the product identity)

Do not treat those files as installation or usage docs.
