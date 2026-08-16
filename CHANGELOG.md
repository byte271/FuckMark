# Changelog

The project remains at `v0.1.0` for this research line.

## v0.1.0 — Foundation hardening

- Added strict source-pin loading and a deterministic source-pin registry with duplicate-key and schema-drift rejection.
- Added the implementation-neutral watermark adapter protocol and deterministic adapter registry.
- Added a pinned DeepMind SynthID Text reference observation adapter.
- Reproduced the reference signed-int64 LCG-style hash semantics without adding a Torch runtime dependency.
- Added source-conformant n-gram key generation, binary g-value generation, bounded context-repetition masks, and EOS masks.
- Added immutable native observation records and batches that preserve g-values, repetition state, EOS validity, combined validity, exact n-gram geometry, source revision, and adapter fingerprint.
- Added fixed upstream-derived golden conformance fixtures and randomized differential validation against a direct Torch reproduction of the pinned source behavior.
- Added a separate pinned Hugging Face Transformers SynthID observation adapter without conflating its hashing and g-value path with the DeepMind reference implementation.
- Added exact Hugging Face n-gram hashing from the source-defined initial hash value and binary g-value lookup through the source-defined sampling table.
- Added an optional Torch bridge that reproduces the pinned Hugging Face sampling table from its seed while keeping Torch out of FuckMark core dependencies.
- Added sampling-table hashing and provenance tracking so Hugging Face observation artifacts bind to the effective table used for computation.
- Added randomized differential validation against direct Torch reproductions for both pinned open implementations.
- Strengthened native observation batches to retain the exact immutable token sequence and verify every recorded n-gram against it.
- Renamed the project completely to FuckMark while preserving the frozen project version.
- Renamed the distribution and Python package namespace to `fuckmark`.
- Added project-name and version regression enforcement.
- Switched wheel packaging to bounded `fuckmark*` package discovery so future internal subpackages cannot disappear from built artifacts.
- Replaced full Python-object alignment matrices with packed traceback and tie grids plus rolling numeric distance rows.
- Preserved exact deterministic traceback priority while substantially reducing alignment memory overhead.
- Added strict construction validation for alignment steps and results.
- Preserved positional correspondence for one-to-one substitutions so replaced observations retain their transformed index.
- Distinguished replaced observations from observations that have no contiguous aligned counterpart after insertion or deletion.
- Added full alignment consistency validation before observation comparison.
- Added a dynamic-programming cell limit to prevent accidental unbounded alignment allocation.
- Rejected non-sequence and non-integer token inputs at public boundaries.
- Rejected invalid observation states and malformed observation index/count types.
- Rejected non-string canonical JSON object keys instead of allowing key coercion collisions.
- Normalized negative floating-point zero in canonical JSON.
- Rejected dataclass types when an instance is required for canonicalization.
- Preserved type separation between integer and string master seeds.
- Rejected invalid file-hashing input types and chunk sizes.
- Strengthened source pins to require immutable Git revisions and canonical repository-relative file paths.
- Strengthened run identities to require immutable revisions, SHA-256 digests, and clean control-free identity strings.
- Added validation for malformed observation summaries and structural diff indices.
- Expanded regression, exhaustive, packaging, and invariant coverage.
