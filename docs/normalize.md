# FuckMark normalize — NFC, lookalikes, receipts

`--clean` is the blunt strip of hidden Unicode. `fuckmark normalize` is the
pipeline default: compose to NFC, optionally fold an identifier lookalike
subset toward ASCII, then strip the security hidden-character set, and emit a
receipt of exactly what changed.

This is **not** a full [UTS #39](https://www.unicode.org/reports/tr39/)
confusable mapping. The lookalike table is a small Cyrillic/Greek/nbsp/
fullwidth subset for identifiers. It does not cover CJK, and it does not claim
complete homoglyph defense.

## One-liner

```python
from fuckmark import normalize_text

cleaned, receipt = normalize_text(user_text, confusable=True)
# receipt.input_sha256 / output_sha256 / steps / stripped
```

Default flags: NFC on, confusable off, strip on (same security categories as
`fuckmark lint` / `fuckmark guard`).

```python
from fuckmark import skeleton_fold, normalize_receipt_dict

assert skeleton_fold("\u0430") == "a"
payload = normalize_receipt_dict(receipt)
```

## What the receipt records

The JSON receipt (`normalize_receipt_dict`) includes:

- `algorithm_version`: `fuckmark-normalize-v1`
- `nfc`, `confusable`: the requested flags
- `stripped`: count of hidden characters removed
- `steps`: which of `nfc`, `confusable`, `strip` actually changed the text
- `changed`: whether the output differs from the input
- `input_sha256`, `output_sha256`
- `report_hash`: SHA-256 of the canonical JSON of those fields

Cleaning without a receipt is data loss. The hashes let a downstream reviewer
audit or re-run the same input.

## Command line

```text
printf 'a\u200bb\n' | fuckmark normalize
fuckmark normalize --confusable --receipt notes.txt
fuckmark normalize --keep-hidden --receipt decomposed.txt
```

Stdout is the normalized text. Stderr reports whether anything changed, unless
`-q`. `--receipt` writes the JSON receipt to stderr after that line.

`--clean` still exists: it only strips hidden characters, with no NFC, no
lookalike fold, and no receipt. Use `normalize` when a pipeline should
canonicalize first.

## HTTP

`fuckmark web` serves `POST /api/normalize` with `{ "text": "..." }` and
optional `"confusable": true`.

## Related

- Scan spec: [`specs/fuckmark-hidden-scan-v1.protocol.md`](../specs/fuckmark-hidden-scan-v1.protocol.md)
- Strip-only: `fuckmark --clean` / `clean_hidden_characters`
- LLM input: [`guard.md`](guard.md)
