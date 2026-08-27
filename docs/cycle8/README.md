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

See `docs/cycle8/seed-ledger.md` and `docs/seeds.md`. Seeds `890000`, `900000`, and `910000` are spent tiny Cycle 8 evidence. Scale seeds `930000` / `940000` / `950000` were reserved before scale generation. Density seed `960000` was reserved before density generation and scored n=16: both space x1 and space-wordfinal are 1/16. Letter seed `970000` was reserved before letter generation; independent letter-x1 is 0/16 then 0/64. Diagnostic letter rescored of seen `930000` n=64 and `940000` n=64 are 0/64. Experimental letter-x1 0/192 is 128 seen plus 64 independent. System-benchmark seeds `980000` and `990000` were reserved before generation; fresh letter-x1 is 0/128 and fresh space-x1 is 1/128. See `docs/cycle8/letter-system-benchmark.md`. Mix seeds `1020000` and `1030000` were reserved before generation; fresh letter-alt is 0/128 with worst score 0.513691. Mix scale seeds `1040000` and `1050000` were reserved before generation; combined mix is 0/256 with worst score 0.519522. Mix is frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on seeds `830000` / `840000` / `850000` is **0/192** and those seeds are spent. Publishability gates: reproducibility PASS, visibility PASS, software compatibility PASS on the UTF-8 / visible-search product surface, sanitizer FAIL, cross-detector FAIL. Mix is not product-publishable. See `docs/cycle8/letter-mix-margin.md`, `docs/cycle8/mix-freeze.md`, and `docs/cycle8/mix-publishability.md`. Letter-space seeds `1000000` and `1010000` remain 1/128. Seed `880000` is **PUBLICLY_EXPOSED** by closed unmerged PR #98 and is not eligible as unseen validation.

## Carrier research

See `docs/cycle8/carrier-research.md`, `docs/cycle8/letter-mix-margin.md`, `docs/cycle8/mix-freeze.md`, and `docs/cycle8/mix-publishability.md`.

U+200C is the diagnostic baseline. It is not durable under Cf-strip.

Early durable-track *hypothesis* (sanitizer and tokenizer screen, not a detector claim): U+034F COMBINING GRAPHEME JOINER and variation selectors U+FE00..U+FE0F. These are not product-authorized.

Fixture compare `specs/cycle8/fixture-compare-v1.json` reports visible-projection pass `20/20` across identity, U+200C, U+034F x1, U+034F x8, and U+FE00 arms. Quote interiors remain protected spans. Seed `890000` exploratory detector scoring is development-only (`PROMISING_DEVELOPMENT`, not confirmation). U+034F is not product-authorized.
