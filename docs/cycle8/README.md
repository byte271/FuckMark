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

See `docs/cycle8/seed-ledger.md` and `docs/seeds.md`. Seeds `890000`, `900000`, and `910000` are spent tiny Cycle 8 evidence. Scale seeds `930000` / `940000` / `950000` were reserved before scale generation. Density seed `960000` was reserved before density generation and scored n=16: both space x1 and space-wordfinal are 1/16. Do not inspect `830000` / `840000` / `850000`. Seed `880000` is **PUBLICLY_EXPOSED** by closed unmerged PR #98 and is not eligible as unseen validation.

## Carrier research

See `docs/cycle8/carrier-research.md`.

U+200C is the diagnostic baseline. It is not durable under Cf-strip.

Early durable-track *hypothesis* (sanitizer and tokenizer screen, not a detector claim): U+034F COMBINING GRAPHEME JOINER and variation selectors U+FE00..U+FE0F. These are not product-authorized.

Fixture compare `specs/cycle8/fixture-compare-v1.json` reports visible-projection pass `20/20` across identity, U+200C, U+034F x1, U+034F x8, and U+FE00 arms. Quote interiors remain protected spans. Seed `890000` exploratory detector scoring is development-only (`PROMISING_DEVELOPMENT`, not confirmation). U+034F is not product-authorized.
