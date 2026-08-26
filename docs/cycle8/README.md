# Cycle 8 — exact visible projection

Cycle 7 is frozen as **visible-edit durability research**. It is **PRODUCT_DISQUALIFIED** even where detector snapshots looked interesting.

Cycle 8 is a new scientific generation. The mechanism class is hidden Unicode representation that leaves `VISIBLE(original)` identical to `VISIBLE(transformed)`.

## Priority order

0. Exact user-visible text preservation
1. Real detector evasion
2. Sanitizer durability
3. Independent replication
4. Protected machine-content safety
5. Low hidden payload
6. Mechanistic explanation
7. Proxy metrics

## Seed ledger

See `docs/cycle8/seed-ledger.md`. Seeds `890000`, `900000`, `910000`, and `920000` were assigned before Cycle 8 generation. Do not inspect `830000` / `840000` / `850000`. Do not inspect Cycle 7 validation seed `880000` (used by Cycle 7 Stage D; still blocked from Cycle 8). Seed `890000` is also Cycle 7 Stage D's exploratory pair-seed with a disjoint `document structure` corpus; do not mix those texts.

## Carrier research

See `docs/cycle8/carrier-research.md`.

U+200C is the diagnostic baseline. It is not durable under Cf-strip.

Early durable-track *hypothesis* (sanitizer and tokenizer screen, not a detector claim): U+034F COMBINING GRAPHEME JOINER and variation selectors U+FE00..U+FE0F. These are not product-authorized.

Fixture compare `specs/cycle8/fixture-compare-v1.json` reports visible-projection pass `20/20` across identity, U+200C, U+034F x1, U+034F x8, and U+FE00 arms. Quote interiors remain protected spans. Seed `890000` exploratory detector scoring is development-only (`PROMISING_DEVELOPMENT`, not confirmation). U+034F is not product-authorized.
