# Cycle 7 Stage A README checksum provenance

The frozen `SHA256SUMS.txt` in this directory lists:

```text
833d1d94fcea01bc09855f0af3a4bcc18df1010065fb3e2825f8e2e31733c2eb  README.md
```

The Git object and working tree store the same README with LF line endings. SHA-256 of those LF bytes is:

```text
d7b7de433f5ca231ef2d9de586774ffdfe255b1625f902fa0bf9780019d62709
```

SHA-256 of the same text encoded with CRLF is the digest in `SHA256SUMS.txt`. The scientific text did not change. The original manifest is not rewritten. CI treats this README as a documented CRLF-vs-LF exception: the listed digest must match the CRLF reconstruction, and the Git bytes must stay LF.
