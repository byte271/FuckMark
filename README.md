<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a UTF-8 CLI that inserts a frozen invisible Unicode payload into ordinary English ASCII text without changing what the user sees.

**Product contract (Priority Zero):** `VISIBLE(original) == VISIBLE(transformed)`. The only allowed difference is insertion of the approved carriers U+034F and U+FE00. Semantic edits, contractions, homoglyphs, extra spaces, and renderer tricks are forbidden.

The public CLI (`release-cli-v5`) applies frozen mechanism `u034f-ufe00-letter-alt-v1`: even selected ASCII-letter sites receive U+034F, odd sites receive U+FE00, outside hard machine spans, cap 192. `release_transform_registry()` stays empty. Mix is not a greedy contraction catalog.

This does **not** remove every AI watermark. It is not a claim against unknown, proprietary, or future detectors. Mn-strip and default-ignorable-strip still restore the source (`STRESS_ONLY` / `KNOWN_DESTRUCTIVE_COUNTERMEASURE`). The Cycle 8 v1 mix sanitizer gate stays **FAIL**. `required_sanitizers_keep` is not weakened.

**Current release: v0.4.0**  
Website: [mark.q1z.org](https://mark.q1z.org)  
License: MIT

## What was verified

Gate v2 (`cycle8-publishability-gate-v2`) is `VERIFIED` / `confirmed_and_product_authorized` on one-shot confirmation seeds `1200000` / `1210000` / `1220000` (spent):

| Check | Result |
| --- | --- |
| Identity / pristine watermarked | **188/192** (floor 168) |
| Mix watermarked after every required sanitizer | **0/192** |
| Mix unwatermarked raw | **0/192** |
| Exact visible invariance | **192/192** |
| `lm-watermarking` UnicodeSanitizer mix | **0/192** |
| Carrier-free identity plus that sanitizer | **182/192** (drop 6; max drop 16) |
| Worst mix max score | 0.526739 vs threshold 0.557099 |

Required sanitizers: raw, NFC, NFKC, Cf-strip, NFKC+Cf-strip, whitespace collapse, the Cycle 7 combination, and the real `jwkirchenbauer/lm-watermarking` UnicodeSanitizer default. Homoglyphs and truecase remain `UNSUPPORTED`.

Existing cross-detector transfer (not rescored here): Google synthid-text 30-key GPT-2 mix **0/192** on seeds `1060000` / `1070000` / `1080000`. DistilGPT2 n=16 remains `HYPOTHESIS`. Mean versus Weighted Mean on the same Hugging Face GPT-2 adapter remains `HYPOTHESIS`.

Earlier mix-freeze confirmation on seeds `830000` / `840000` / `850000` is **0/192** raw transformed WM and is spent. Do not rerun looking for zero. Do not generate `950000`. Do not retag `v0.3.0`.

See [`docs/cycle8/gate-v2.md`](docs/cycle8/gate-v2.md), [`docs/product-contract.md`](docs/product-contract.md), and `specs/cycle8/fuckmark-cycle8-product-authorization-v1.json`.

## Install

Python 3.11 or newer is required. Install a **tagged GitHub Release wheel** and check `SHA256SUMS.txt` from that same release. Do not pipe `https://d.q1z.org/mark` into a shell.

```text
python3 -m venv .venv
.venv/bin/python -m pip install https://github.com/byte271/FuckMark/releases/download/v0.4.0/fuckmark-0.4.0-py3-none-any.whl
```

Verify `SHA256SUMS.txt` from the same release before trusting the environment:

```text
https://github.com/byte271/FuckMark/releases/download/v0.4.0/SHA256SUMS.txt
```

The historical v0.3.0 identity-CLI wheel SHA-256 remains `cb4ee7b6c06d1dde8c612c237df78f68f8364bc74bf469086288e55a2d5c9325`. That tag is not retagged.

See [`docs/install.md`](docs/install.md) for checksum verification, the in-repo installer, and Windows notes.

## CLI

The same entry point is installed as `FuckMark`, `Fuckmark`, and `fuckmark`.

```text
FuckMark
printf 'I do not agree.\n' | FuckMark
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
FuckMark --stdin --visible < input.txt
```

Piped input writes the raw mix payload. `--visible` writes the user-visible projection (the original text when the transform succeeded). `--copy` copies whatever is written. The CLI does not emit contractions such as `I don't agree.`

Outside ordinary English ASCII (tab / LF / CR / U+0020..U+007E), or when there are no eligible letter sites, or when approved carriers are already present, the CLI fail-closes and returns the input unchanged.

Useful options: `--version`, `--stdin`, `-o FILE`, `--copy`, `--visible`, `--encoding utf-8` (latin-1 / ascii / cp1252 are rejected), `-q`, `--no-color`.

See [`docs/cli.md`](docs/cli.md).

## Threat model

- Output is ordinary Unicode plain text. No HTML, CSS, custom fonts, canvas, or hidden metadata.
- Protected spans stay intact: fenced/inline code, markdown destinations, URLs, emails, IPs, dates, currency, percents, numbers, POSIX/Windows paths, CLI flags. Quote interiors are eligible. Math and citation spans are not hard.
- Frozen product-contract sanitizers keep the mix. Mn-strip and default-ignorable-strip remove it and reconstruct the source. Those two are recorded stress tests, not required product sanitizers.
- UTF-8 only. Latin-1 cannot roundtrip U+034F or U+FE00.
- Raw codepoint search of the payload can miss ordinary English phrases. Product search uses the visible projection.
- Clipboard is the Unicode string itself (macOS `pbcopy`, Windows `clip`, Linux `wl-copy` / `xclip` / `xsel` / `clip.exe`). Clipboard failure exits 2 after still writing the text.

## Historical research

v0.3.0 was the identity CLI (`release-cli-v4`) after the visible-invariance correction. The historical `v0.2.0` tag still applies contractions. Cycle 4 exact-survival confirmation (`CONFIRMATORY_IMPROVEMENT`, 8/192 to 5/192) and Cycle 6 / Cycle 7 visible-edit work remain scientific records and are **PRODUCT_DISQUALIFIED** for the public CLI.

Cycle 8 chronology, seed ledger, H9-H16 carrier search, and mix-freeze evidence live under [`docs/cycle8/`](docs/cycle8/README.md) and [`docs/seeds.md`](docs/seeds.md). Frozen contracts under `specs/` are immutable.

## Reproduce the research environment

```text
python -m pip install -e ".[dev]"
python -m pip install -r requirements-smoke.txt
python -m pytest
```

## Release engineering

v0.4.0 builds one wheel and one source distribution and verifies both on Linux, macOS, and Windows before publication. GitHub Release publication happens only from an immutable `v*` tag after the package matrix succeeds. See [`docs/release.md`](docs/release.md).

## Links

- Website: [mark.q1z.org](https://mark.q1z.org)
- Repository: [github.com/byte271/FuckMark](https://github.com/byte271/FuckMark)
- Issues: [github.com/byte271/FuckMark/issues](https://github.com/byte271/FuckMark/issues)

## License

MIT. See [`LICENSE`](LICENSE).
