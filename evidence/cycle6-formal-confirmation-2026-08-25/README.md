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

Historical Actions artifact `9552122154` must not be used for independent blinded review:
it unintentionally bundled the private orientation manifest with the public packet. That
packaging error does not change the committed public/mechanical payload hashes, but it
makes that ZIP unsuitable as a blinded distribution artifact.

The corrected workflow writes the private orientation manifest outside the public artifact
directory and uploads only the public packet plus mechanical report. The private manifest
is intentionally not published by GitHub Actions. A trusted adjudicator can regenerate it
from the frozen packet construction inputs after independent reviewer decisions have been
collected.

Independent two-reviewer adjudication is pending. Formal detector scoring is not
authorized until the resulting audit hash is bound into the confirmation contract.
