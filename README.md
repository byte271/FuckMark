# FuckMark

FuckMark is a deterministic research harness for studying how text transformations alter statistical watermark observations.

The project is implemented bottom-up. The current project version is **FuckMark v0.1.0**.

## Project identity

- Display name: `FuckMark`
- Distribution name: `fuckmark`
- Python package: `fuckmark`
- Project version: `v0.1.0`

Historical project identities and the former Python namespace are retired and must not reappear in source, tests, configuration, or documentation.

## Version policy

The project remains on `v0.1.0` for this research line. Fixes and research hardening do not change the project version.

## Current foundation

1. Canonical serialization
2. Content hashing
3. Deterministic seed derivation
4. Immutable source and run identities
5. Deterministic token edit alignment
6. Packed traceback storage with bounded alignment allocation
7. Exact-match and positional alignment maps
8. Conserved contiguous token runs
9. Token n-gram construction
10. Structural observation preservation, replacement, and unmapped classification
11. Substitution observation intervals
12. Overlap-aware interval merging and union coverage
13. Strict public-boundary type and identity validation
14. Project-name and version regression checks

Detector adapters, source-conformance fixtures, watermark-native observation records, transformation rules, calibration, and experiments remain intentionally outside this foundation layer.

Python source is English-only and contains no comments or docstrings.
