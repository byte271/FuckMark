# Runtime foundation: staged refactor

Baseline: `09c8cbf184e37e2e934e133b74a5db9af67b4f97` (main, 2026-11-04).
The product objective remains LLM statistical-watermark processing. This work
neither adds another Unicode layer nor turns the project into a detector product.

## Stage 1: stop implicit research imports

Implemented in this change:

- `fuckmark`, `fuckmark.product`, and `fuckmark.transforms` resolve public exports
  on demand. Importing the package or reading version metadata no longer loads
  all research adapters, detectors, corpora, and transform schedulers.
- Public names, their defining import targets, and the order of `__all__` are
  preserved. The two transform rules previously accessible outside `__all__`
  remain accessible. Real classes/functions are returned, not proxy objects.
- Resolved objects are cached. Import errors propagate rather than becoming
  misleading AttributeErrors. Reload clears cached exports; `dir()` lists the
  API without importing implementations.
- Cold-process tests check the boundary and all export targets. Full wildcard
  imports and explicit research APIs still work and intentionally load the
  implementations they request.

This is runtime isolation, not full core extraction or a smaller wheel. No
algorithm, detector threshold, frozen evidence, research module, CLI behavior,
workflow, release version, or dependency declaration is changed. The existing
Python, CLI I/O, frozen-readiness, and packaging suites remain the regression
checks. No speedup is claimed without a controlled measurement.

### Baseline compatibility evidence

The new explicit export tables were generated from the old import declarations,
not guessed from names. The source Git blob identities were verified first:

| Package entrypoint | Original Git blob | Exports / wildcard exports |
| --- | --- | --- |
| `fuckmark/__init__.py` | `6da7ab00a563a6cdb729aadb63bc80aef7175ece` | 239 / 239 |
| `fuckmark/product/__init__.py` | `4f17ba5f23989263a39498114c72ceb6c879d107` | 74 / 74 |
| `fuckmark/transforms/__init__.py` | `842cce605ea6f78287f30ce647c37278a4af05b9` | 156 / 154 |

`tests/test_lazy_public_api.py` pins the original ordered wildcard lists and
name-to-module mappings by SHA-256, then separately checks object identity
against the real implementations. Adding an intentional public API requires
updating this baseline with an explicit review; the digest is not a scientific
watermark-effectiveness metric.

Run the targeted checks with:

```sh
python -m pytest -q tests/test_lazy_public_api.py
```

Then run the unchanged full suite and installed CLI checks before merging.
A namespace-only local test is not a substitute for those full tests.

## Stage 2: extract the execution path, without changing results

Next, separately reviewed work:

1. Record byte-for-byte output and structured statuses for multilingual text,
   protected code/links, empty inputs, existing carriers, capped inputs, and
   malformed inputs. Include package/wheel entrypoints and legacy APIs.
2. Extract `ProcessResult` and pure transformation orchestration from `cli.py`.
   Keep command parsing, terminal messages, file writes, and clipboard access
   outside the engine. Preserve compatibility of the existing CLI imports.
3. Map actual imports, dynamic lookups, workflows, scripts, tests, documented
   APIs, and frozen source hashes before moving a module.
4. Move runtime dependencies behind a one-way boundary. Research may depend on
   core; core must not depend on research runners or detector feedback.
5. Only then separate the default wheel from optional research/replay tooling.
   Do not simply exclude `experiments/` while reachable APIs still need it.

Gate: existing output/status compatibility, reproducible historical records,
clean installed-package tests, and no weakened isolation or fidelity checks.

## Stage 3: a useful watermark experiment before a new algorithm

Build one reproducible comparison first, not dozens of new runners. Use known
watermarked and matched unwatermarked sources, a calibrated fixed threshold,
separate development/confirmation data and held-out keys. Report detector TPR
at a specified FPR, text-quality failures, normalizer behavior, cost, and
failures to process. Keep historical mark-only results separate from the live
five-layer algorithm. An exact-source restore count is not a detection rate.

Start with one pinned open statistical-watermark implementation. Expand to a
second tokenizer/model family and a different watermark mechanism only after
the first harness is valid. Do not spend model budget on a new strategy before
this baseline can detect regressions.

## Stage 4: constrained reconstruction is a hypothesis, not a release promise

Evaluate content reconstruction against a plain paraphrasing baseline under the
same budget and fidelity constraints. Lock numbers, entities, quotes, code,
formulas, negation, and factual relationships where they can be checked. Measure
omissions and invented statements separately. Independent fidelity review is
required; one model judging its own rewrite is not proof of equivalence.

Promote a new strategy only if it improves the predeclared quality/effectiveness
tradeoff on unused evaluation data. If it does not, retain the negative result
and stop that branch rather than adding layers or inventing a success metric.
No universal removal, unknown-detector guarantee, or novelty claim follows from
this architecture.

## Removal policy

A module is not dead merely because the current CLI does not call it. A removal
must identify callers (including dynamic imports and external API contracts),
historical replay value, and replacement tests. Archive historically meaningful
code; delete only demonstrably unused code after those checks. A green test
suite alone does not prove an undocumented external caller does not exist.

Keep this change independent of algorithm experiments and marketing work so it
can be reviewed or reverted without rewriting the scientific record.
