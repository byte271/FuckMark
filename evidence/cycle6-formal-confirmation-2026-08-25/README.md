# Cycle 6 formal-confirmation preregistration evidence

This directory contains the detector-blind Phase B inputs generated for PR #90.

- `full-fidelity-public.json` is the randomized A/B packet for independent reviewers. It
  covers all 16 frozen seed-720000 B14 development outputs and discloses no detector
  result or source orientation.
- `full-fidelity-mechanical.json` binds the source corpus, ruleset, packet, geometry, and
  mechanical invariant checks. All 16 rows passed hard protected-content, quote-boundary,
  invisible-character, trace replay, and repeated-space-collapse checks.

Packet hash:
`8b83c170ea04f212e8f373f96c0a8ba9dd1420fcfb6d5466cb9fc8207fe059ce`

Mechanical artifact hash:
`761aefcc26da4ecb4323b9ef7d0bfd87e6d5730cde95637111849e12f8a66384`

Reviewer-safe GitHub Actions artifact:
- run: `32868236285`
- artifact: `9571107294`
- ZIP digest: `sha256:dab28e09fa6389b90620af547e2b0fcae4b6dccb265a9ea6fb9003aaf82f1a41`
- source commit: `c7545a8037570c181bc59d26e5262f86232a5ec0`

The safe ZIP contains exactly the public packet and mechanical report. Its public packet
and mechanical artifact hashes reproduce the frozen values above. The private orientation
manifest is written outside the public artifact directory and is intentionally not
published by GitHub Actions. A trusted adjudicator can regenerate it from the frozen packet
construction inputs after independent reviewer decisions have been collected.

Historical Actions artifact `9552122154` must not be used for independent blinded review:
it unintentionally bundled the private orientation manifest with the public packet. That
packaging error does not change the committed public/mechanical payload hashes, but it
makes that historical ZIP unsuitable as a blinded distribution artifact.

Independent two-reviewer adjudication is pending. Formal detector scoring is not
authorized until the resulting audit hash is bound into the confirmation contract.
