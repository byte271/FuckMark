# fuckmark-hidden-scan-v1

Frozen classification spec for hidden or suspicious Unicode. Hash-binding
freeze record: `specs/fuckmark-hidden-scan-v1.freeze.json`. Conformance
vectors: `specs/fuckmark-hidden-scan-v1.vectors.json` (codepoint arrays only;
the files never embed the raw hidden characters).

This is a text-integrity spec. It answers what a string contains that a human
glyph stream may not show. It is not a semantic prompt-injection detector and
it is not a general AI-watermark detector.

## 1. Identity

- Algorithm version: `fuckmark-hidden-scan-v1`
- Python reference: `fuckmark.product.scan.scan_hidden_characters`
- JavaScript port: `editors/vscode/scan.js` (category table locked to the
  Python engine across the Unicode scalar space)
- Contact: `Fhelp@q1z.org`

A later `fuckmark-hidden-scan-v2` may extend categories, context, or severity.
This v1 table is frozen.

## 2. Input model

Input is a Unicode string of scalar values. Classification is per scalar, not
per grapheme cluster and not per UTF-16 code unit.

Finding `index` is the Python string index (scalar offset). Editor ports that
talk to UTF-16 APIs (VS Code) may report a UTF-16 `offset` instead; category,
context, and severity must still match this spec.

Tab (U+0009), line feed (U+000A), carriage return (U+000D), and space (U+0020)
are never flagged. Ordinary combining marks (`Mn`), including U+0301, are left
alone.

## 3. Category table (first match wins)

1. Allowed whitespace listed above: not hidden.
2. `bidi_control`: U+061C, U+200E, U+200F, U+202A-U+202E, U+2066-U+2069.
3. `deprecated`: U+206A-U+206F, U+FFF9-U+FFFB.
4. `zero_width`: U+00AD, U+034F, U+115F, U+1160, U+17B4, U+17B5, U+180E,
   U+200B, U+200C, U+200D, U+2060-U+2064, U+3164, U+FEFF, U+FFA0.
5. `variation_selector`: U+FE00-U+FE0F, U+E0100-U+E01EF.
6. `tag`: U+E0000-U+E007F.
7. `noncharacter`: U+FDD0-U+FDEF, or any scalar whose low 16 bits are U+FFFE
   or U+FFFF.
8. `surrogate`: U+D800-U+DFFF.
9. `format`: explicit Cf ranges that must classify the same on Unicode 14 and
   Unicode 15: U+0600-U+0605, U+06DD, U+070F, U+0890-U+0891, U+08E2, U+110BD,
   U+110CD, U+13430-U+1343F, U+1BCA0-U+1BCA3, U+1D173-U+1D17A. Then any other
   general category `Cf` not already classified.
10. `enclosing_mark`: general category `Me`.
11. `line_separator`: general category `Zl` or `Zp`.
12. `control`: general category `Cc` (C0/C1), excluding allowed whitespace.
13. `private_use`: general category `Co`.

The explicit `format` ranges exist so Python 3.11 (Unicode 14) agrees with
Python 3.12+ and with the JavaScript port on Egyptian hieroglyph format
controls and related Cf assignments.

## 4. Context (heuristic)

Context is assigned to each finding from a lightweight source mask plus
immediate neighbors. It is not a full language parser.

Roles (optional `language` argument to `scan_hidden_characters`; default
`auto`):

- `comment`: `//` line comments and `/* */` block comments (`auto`,
  `javascript`, `c`, `sql`). `#` line comments (`python`). `--` line comments
  (`sql`). `<!-- -->` (`html`). `//` after `:` is not a comment (`http://`).
- `string`: `"`, `'`, or backtick literals, with backslash escapes.

Then:

- `emoji` if the previous or next scalar is emoji-ish (regional indicators
  U+1F1E6-U+1F1FF, U+1F000-U+1FAFF, U+2600-U+27BF, a small BMP emoji set,
  ZWJ, or a BMP variation selector U+FE00-U+FE0F).
- else `comment` / `string` from the role mask.
- else `identifier` if the previous or next scalar is `_` or alphanumeric.
- else `prose`.

`language` may be passed on the vector as `"language"`. Omitted means `auto`.
Lint infers language from the file suffix. This lexer does not nest block
comments, does not parse raw strings, and does not understand every dialect.

## 5. Severity

| Category | identifier / comment / string | emoji | other |
| --- | --- | --- | --- |
| `tag` | critical | critical | critical |
| `bidi_control` | critical | high | high |
| `zero_width` | high (identifier) / medium (comment, string) | info | medium |
| `variation_selector` | medium | info | medium |
| `control`, `noncharacter`, `surrogate` | high | high | high |
| remaining flagged categories | medium | medium | medium |

`bidi_control` in identifier, comment, or string is the three Trojan Source
encodings (CVE-2021-42574): identifier reordering, commenting-out, and
stretched-string. `autofix_trojan_source` strips only `bidi_control`.

Each finding also carries a one-line `why` and `remedy`. Those strings are
informative; conformance is category, context, and severity.

`highest_severity` on a scan result is the maximum among findings, ordered
info < medium < high < critical. Clean text has an empty highest severity.

## 6. Cleaning vs normalize

`--clean` / `clean_hidden_characters` strips every flagged category (or a
caller-chosen subset). That is the blunt inverse of insertion.

`fuckmark-normalize-v1` is a separate algorithm: NFC, an optional identifier
lookalike subset (UTS #39-inspired; not a full Unicode confusable map), then
strip of the security category set, plus a JSON receipt of input/output
hashes and steps. It is not part of this scan freeze.

Default security categories (lint, guard, normalize strip): `bidi_control`,
`zero_width`, `tag`, `control`, `noncharacter`, `surrogate`.

## 7. Conformance

Reconstruct each vector as `"".join(chr(cp) for cp in codepoints)` (Python
scalars). Run `scan_hidden_characters` with `language` from the vector or
`auto`. For every expected finding, require matching `index`, `codepoint`,
`category`, `context`, and `severity`, in order. Vectors that expect no
findings must produce `detected is False`.

Do not store the reconstructed strings in the vector file.
