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

See `docs/cycle8/seed-ledger.md` and `docs/seeds.md`. Seeds `890000`, `900000`, and `910000` are spent tiny Cycle 8 evidence. Scale seeds `930000` / `940000` / `950000` were reserved before scale generation. Density seed `960000` was reserved before density generation and scored n=16: both space x1 and space-wordfinal are 1/16. Letter seed `970000` was reserved before letter generation; independent letter-x1 is 0/16 then 0/64. Diagnostic letter rescored of seen `930000` n=64 and `940000` n=64 are 0/64. Experimental letter-x1 0/192 is 128 seen plus 64 independent. System-benchmark seeds `980000` and `990000` were reserved before generation; fresh letter-x1 is 0/128 and fresh space-x1 is 1/128. See `docs/cycle8/letter-system-benchmark.md`. Mix seeds `1020000` and `1030000` were reserved before generation; fresh letter-alt is 0/128 with worst score 0.513691. Mix scale seeds `1040000` and `1050000` were reserved before generation; combined mix is 0/256 with worst score 0.519522. Mix is frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on seeds `830000` / `840000` / `850000` is **0/192** and those seeds are spent. DeepMind 30-key mix transfer seeds `1060000` / `1070000` / `1080000` are confirmation-scale mix **0/192** (`HYPOTHESIS`, not mix-freeze confirmation). DistilGPT2 seed `1090000` n=16 is `HYPOTHESIS` second-model transfer. Control-mix exploratory seed `1100000` n=16 is `HYPOTHESIS` (identity WM 15/16, control-mix WM 0/16) and does not rewrite mix sanitizer FAIL. Publishability gates: reproducibility PASS, visibility PASS, software compatibility PASS on the UTF-8 / visible-search product surface, sanitizer FAIL, cross-detector PASS. Mix is not product-publishable. See `docs/cycle8/letter-mix-margin.md`, `docs/cycle8/mix-freeze.md`, `docs/cycle8/mix-publishability.md`, `docs/cycle8/mix-deepmind-transfer.md`, `docs/cycle8/mix-second-model-transfer.md`, and `docs/cycle8/gate-v2.md`. Letter-space seeds `1000000` and `1010000` remain 1/128. Seed `880000` is **PUBLICLY_EXPOSED** by closed unmerged PR #98 and is not eligible as unseen validation. Gate v2 confirmation seeds `1200000` / `1210000` / `1220000` were generated once: mix required-sanitizer WM **0/192**, mix UW **0/192**, visible **192/192**, identity **188/192**, carrier-free Unicode **182/192**. Those seeds are spent. Gate v2 is `confirmed_not_product_authorized`. Public CLI stays empty.

## Carrier research

See `docs/cycle8/carrier-research.md`, `docs/cycle8/letter-mix-margin.md`, `docs/cycle8/mix-freeze.md`, `docs/cycle8/mix-publishability.md`, `docs/cycle8/mix-deepmind-transfer.md`, and `docs/cycle8/mix-second-model-transfer.md`.

Assigned width-0 insertions remain closed (H9). H12 control-code insertion (`Cc` DEL + C1 except NEXT LINE) is a new sanitizer-surviving research class. Chromium pixels are host-dependent. Independent seed `1100000` n=16 is control-mix **0/16** WM (`HYPOTHESIS`). H13 classifies the post-sanitizer mechanism families: no measured class is simultaneously sanitizer-surviving, Chromium-portable, ordinary plain text, and Priority-Zero safe. H14 extends that negative result to `Mc`, `Lm`, designed blanks, Hangul filler sequences, and font-metric empty glyphs. H15 extends it to sequence-level prepend, joining, Hangul composition, bidi wraps, escape sequences, partial-sanitizer remainders, and font GSUB ligatures. It is not mix, not product-authorized, and does not rewrite the mix sanitizer FAIL. H16 audits the gate: the original shaping scan executed latin `A`/`B` only, not the advertised 12 contexts; the 12-context rescan is recorded (union 396, intersection 0) and does not rewrite the A/B artifact. Gate v2 confirmation on seeds `1200000` / `1210000` / `1220000` is `VERIFIED` / `confirmed_not_product_authorized`. See `docs/cycle8/carrier-research.md` and `docs/cycle8/gate-v2.md`.

U+200C is the diagnostic baseline. It is not durable under Cf-strip.

Early durable-track *hypothesis* (sanitizer and tokenizer screen, not a detector claim): U+034F COMBINING GRAPHEME JOINER and variation selectors U+FE00..U+FE0F. These are not product-authorized.

Fixture compare `specs/cycle8/fixture-compare-v1.json` reports visible-projection pass `20/20` across identity, U+200C, U+034F x1, U+034F x8, and U+FE00 arms. Quote interiors remain protected spans. Seed `890000` exploratory detector scoring is development-only (`PROMISING_DEVELOPMENT`, not confirmation). U+034F is not product-authorized.
