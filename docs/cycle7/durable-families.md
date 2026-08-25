# Cycle 7 durable families

Catalog identity: `cycle7-durable-rule-catalog-v5` (Stage D development). Families 1–3 remain the frozen Stage A `v2` set; families 4–9 remain the frozen Stage B `v3` set; families 10–11 remain the frozen Stage C `v4` set. Cycle 6 `quote_safe_zrd` ruleset hash is unchanged.

All families below are deterministic, detector-blind, key-blind, and non-neural. Cycle 6 `quote_safe_zrd` ruleset hash is unchanged.

## Shared constraints

- Protected spans (URLs, numbers, dates, code, identifiers, paths, hashes, citations, emails) block overlapping edits.
- Quote interiors: durable families may edit quoted *content* under `quote-container-durable-v1` without changing delimiters. Cycle 6 `quote-container-surface-spacing-v1` still admits only spacing inside quotes.
- Hard-invariant algorithm remains `hard-invariant-validator-v4`. Ambiguous `'d` / bare `it's` / `it's not` ↔ `it is not` stay excluded.
- Whitespace-collapse-v1 is a first-class Cycle 7 sanitizer. A family is collapse-resistant only if the rewrite still differs after `ws_collapse` and `ws_collapse_nfkc_cf_strip`.

## Family 1 — unambiguous contractions and closed orthography

Precondition: existing `LiteralTransformRule` whole-word match, all-caps blocked.

Rewrite: closed contraction/expansion pairs plus `towards`/`toward` and `amongst`/`among`. Cycle 7 additions: `I/you/we/they have` ↔ `I've/you've/we've/they've`, and bounded `it's like|important|a|an|the` ↔ `it is …`.

Inverse: each pair has an explicit reverse rule.

Tokenizer: contraction boundaries change GPT-2 BPE pieces. VERIFIED on fixtures.

Whitespace collapse: no extra U+0020 is introduced. Survives by construction.

Sanitizer: ASCII punctuation; NFKC/Cf-strip leave the rewrite in place.

Conflict geometry: overlapping contraction sites conflict; scheduler remains detector-blind cover-greedy v4.

Enumeration order: registry sort `(start, end, rule_id, candidate_id)`.

REJECTED from this family: `he'd`/`she'd`/`I'd`, bare `it's`, `it's not` ↔ `it is not`, `it's been`, `while`/`whilst` (noun `while` is not gated).

## Family 2 — attested open ↔ hyphenated compounds

Construction: `attested_open_hyphen_compound`.

Closed list (both directions):

- proof of concept ↔ proof-of-concept
- point of view ↔ point-of-view
- step by step ↔ step-by-step
- case by case ↔ case-by-case
- end to end ↔ end-to-end
- state of the art ↔ state-of-the-art
- face to face ↔ face-to-face

Precondition: whole-word match, plus no adjacent hyphen, slash, or alnum so `proof-of-concept-note` and path fragments do not match. Sentence-final punctuation is allowed (unlike sentence-initial lexical markers).

Rewrite: replace the matched open phrase with the hyphenated phrase, or the reverse.

Inverse: the opposite direction in the same list.

Tokenizer: GPT-2 `proof of concept` → 3 tokens; `proof-of-concept` → 5 tokens. VERIFIED locally on frozen GPT-2 revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

Whitespace collapse: hyphens are not spaces. Survives.

Sanitizer: ASCII hyphens. NFKC/Cf-strip leave the rewrite in place.

Conflict geometry: open and hyphenated forms of the same phrase cannot both match the same span.

Enumeration order: same registry sort.

Not admitted: `one to one` ↔ `one-to-one` (range false positive `one to one hundred` without extra gating). POS-gated pairs such as `set up`/`setup` and `real time`/`real-time` are not admitted.

## Family 3 — in-word ASCII apostrophe ↔ U+2019

Construction: `inword_typographic_apostrophe`.

Precondition: exactly one character `'` or U+2019 with alphabetic characters on both sides. Quote delimiters and plural possessives (`students'`) do not match. Both adjacent letters uppercase is rejected so `DON'T` does not fire.

Rewrite: `'` → U+2019, or the reverse.

Inverse: the opposite direction.

Tokenizer: GPT-2 `It's not uncommon` tokens `[1026, 338, 407, 19185]` versus curly `[1026, 447, 247, 82, 407, 19185]`. VERIFIED on the frozen GPT-2 revision.

Whitespace collapse: not whitespace. Survives.

Sanitizer: U+2019 is category Pf, not Cf. NFKC leaves U+2019 unchanged. VERIFIED. Combined `ws_collapse_nfkc_cf_strip` therefore keeps the edit. NBSP and ZWSP were measured and rejected as channels: NBSP NFKC-maps to U+0020; ZWSP/soft hyphen are Cf.

Hard invariants: `_WORD_RE` already treats `'` and U+2019 as equivalent after normalization. `don't` and `don’t` share the same negation atom.

Conflict geometry: an apostrophe edit overlaps contraction expansion of the same word; cover-greedy v4 picks one.

## Causal chain (what counts as promising)

text change → tokenization change → n-gram/context change → observation replacement → g-value drift → score drop.

Byte change or a one-off score drop is not enough. Family 1–3 have VERIFIED tokenization change and collapse survival on fixtures. Detector attachment on TinyDev 64-token text is a separate density question.

## Family 4 — sentence-boundary newline

Construction: `sentence_boundary_newline`.

Precondition: `. ` / `? ` / `! ` immediately before an uppercase letter. Exclusions: digits before the mark, single-letter initials, a closed abbreviation list (`Dr.`, `Fig.`, `U.S.`, months, `etc.`), already-newline after the mark, and ellipsis/multi-punctuation (`... Next`).

Rewrite: swap the single ASCII space after sentence punctuation for a single LF, or the reverse.

Inverse: the opposite direction.

Tokenizer: GPT-2 `Hello. World` vs `Hello.\nWorld` is `[15496, 13, 2159]` vs `[15496, 13, 198, 10603]`. VERIFIED on frozen revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

Whitespace collapse: `whitespace-collapse-v1` preserves newlines. The rewrite still differs after `ws_collapse` and `ws_collapse_nfkc_cf_strip`. VERIFIED on fixtures. LF is category Cc, not Cf.

Sanitizer note: this is a layout/formatting channel. A wrap/reflow sanitizer is not in the Cycle 7 frozen sanitizer suite. Survival is VERIFIED only against the six listed Cycle 7 variants. HYPOTHESIS: a paragraph-reflow sanitizer would erase it.

Conflict geometry: adjacent sentence boundaries do not overlap. Format edits can still compete with spacing for the B14 budget in the combined arm.

## Family 5 — bounded optional complementizer / object-relative `that`

Construction: `bounded_complementizer_that_drop`, `bounded_complementizer_that_insert`, `bounded_object_relative_that_drop`.

Precondition (drop): pronoun + closed attitude/report verb immediately before ` that `, and a closed clause-starter after it. Object-relative drop: determiner + noun of length at least 3 before ` that `, then a subject pronoun + lowercase word.

Precondition (insert): the same pronoun+verb pattern with a clause-starter and no `that` already present. The stored source `I think ` is a sentinel; matching uses the shared complementizer pattern.

Rewrite: delete or insert optional `that`.

Inverse: insert vs drop on the complementizer pair. Object-relative drop is one-way in v3.

Tokenizer: GPT-2 `I think that the protocol works` versus `I think the protocol works` differs by the `that` token. VERIFIED on the frozen GPT-2 revision.

Whitespace collapse: the edit is a word, not spaces. Survives.

False positives blocked: `I found that book`, `so that the logs`, all-caps.

EXTERNAL-VALIDATION-ONLY: optional complementizer *that* is a high-frequency English alternation in the UID/Jaeger literature. Local admission still requires the closed verb list.

## Family 6 — sentence-initial discourse comma

Construction: `sentence_initial_discourse_comma`.

Closed markers include `However`, `Therefore`, `Moreover`, `In fact`, and other listed conjunctive adverbs.

Precondition: sentence-initial (start or after `.?!`). Insert is blocked before degree-adverb followers (`much`, `many`, `long`, and the listed set) so `However much evidence` is not rewritten as `However, much evidence`.

Rewrite: drop or insert the comma after the marker.

Tokenizer: comma token appears or disappears. HYPOTHESIS on TinyDev density: sparse unless the sample uses discourse markers.

Whitespace collapse: comma is not space. Survives.

## Family 7 — attested prenominal hyphen modifiers

Construction: `attested_prenominal_hyphen_modifier`.

Closed list includes `well known` / `well-known`, `long term` / `long-term`, `open source` / `open-source`, and other listed prenominal compounds.

Precondition: same hyphen-chain/path guards as Family 2. Hyphenation additionally requires a following lowercase noun so predicative `The method is well known.` does not fire.

Rewrite: open / hyphenated.

Tokenizer: hyphenation splits GPT-2 pieces. VERIFIED locally for `well known` / `well-known`.

Whitespace collapse: hyphens are not spaces. Survives.

EXTERNAL-VALIDATION-ONLY: CMOS hyphenates compound modifiers before a noun. Predicative forms stay open.

## Family 8 — parenthetical conjunctive adverb

Construction: `parenthetical_conjunctive_adverb`.

Closed adverbs: `however`, `therefore`, `moreover`, and the listed set.

Precondition: previous character alphabetic; drop matches `, however, `; insert matches ` however ` and does not fire on already-comma forms.

Rewrite: `, however, ` / ` however `.

Whitespace collapse: commas remain. Survives.

## Family 9 — coordinating-conjunction comma

Construction: `coordinating_conjunction_comma`.

Closed conjunctions: `and`, `but`, `or`.

Precondition: previous character alphabetic and next character alphabetic. Insert additionally requires a determiner follower (`the|a|an|this|these|those`) so `you and I` and `cats and dogs` do not gain a comma. Digit-comma lists such as `1, and 2` are blocked.

Rewrite: `, and ` / ` and ` (same for `but` / `or`).

Tokenizer: GPT-2 `failed and the replica` versus `failed, and the replica` differs by the comma token. VERIFIED on the frozen GPT-2 revision.

Whitespace collapse: comma is not space. Survives.

Safety: insert is a style comma before a determiner, not a full independent-clause parser. NP coordinations of the form `X and the Y` can still receive a comma. That is semantically conservative and style-marked. Stage B treats density as the first metric and may reject the insert direction if natural prose over-fires.

Not admitted: `nor` / `yet` / `so` (adverb/conjunction ambiguity). Running-text `and` to `&` remains REJECTED (CMOS/AP: ampersand is not prose-equivalent).

## Family 10 — clause punctuation newline

Construction: `clause_punctuation_newline`.

Precondition: `, ` / `; ` / `: ` immediately before an alphabetic word of length at least 2. Exclusions: start of string, digits immediately before the mark (thousands separators, `v2, and`), other punctuation immediately before the mark, already-newline after the mark, and single-letter followers (`Hello, X` / `a, b`).

Rewrite: swap the single ASCII space after the clause mark for a single LF, or the reverse.

Inverse: the opposite direction.

Tokenizer: GPT-2 `Hello, World` versus `Hello,\nWorld` differs. VERIFIED on frozen revision `607a30d783dfa663caf39e06633721c8d4cfcd7e` when transformers is present.

Whitespace collapse: same as Family 4. `whitespace-collapse-v1` preserves LF. VERIFIED on fixtures against all six Cycle 7 sanitizer variants.

Sanitizer note: this is still a layout/formatting channel. HYPOTHESIS: a wrap/reflow sanitizer would erase it. It is admitted because Stage B showed sentence-boundary newlines were the only family that raised natural site density, and clause commas are much more common than sentence terminals on ordinary prose.

Conflict geometry: `, and ` overlaps Family 9 coordinating-comma drop. Cover-greedy v4 remains detector-blind.

Not admitted: generic extra spaces, NBSP, ZWSP, or converting commas to other Unicode spaces.

## Family 11 — quantifier `of` before a determiner

Construction: `quantifier_of_determiner`.

Closed quantifiers: `all`, `both`, `half`. Closed followers: `the`, `this`, `that`, `these`, `those`, and the possessives `my` / `our` / `your` / `their` / `his` / `her`. `both` does not pair with singular `this` / `that`.

Precondition: whole-word match plus the same hyphen/slash/alnum adjacency guard as Family 2. All-caps blocked.

Rewrite: `all of the` ↔ `all the` (and the other closed pairs).

Inverse: the opposite direction in the same closed list.

Tokenizer: GPT-2 `All of the replicas failed` versus `All the replicas failed` differs. VERIFIED on the frozen GPT-2 revision when transformers is present.

Whitespace collapse: the edit is the word `of`, not spaces. Survives.

False positives blocked: `all of them` / `both of us` / `half of it` (pronouns require `of`), `all of a sudden`, `some/most/each of the` (those quantifiers are not optional-`of` in the same way).

EXTERNAL-VALIDATION-ONLY: Cambridge Grammar of English / English Grammar Today: `all`, `both`, and `half` may appear with or without `of` before articles, demonstratives, and possessives, with no meaning change. Pronoun objects keep obligatory `of`. That literature is not a local TinyDev density measurement.

## Family 12 — word-boundary newline

Construction: `word_boundary_newline`.

This is the Stage D density primitive. It is not another closed lexical whitelist. It is the collapse-resistant analogue of Cycle 6 general word spacing: replace a single ASCII space between two alphabetic words with a single LF, or the reverse.

Precondition: both sides are ASCII alphabetic runs of length at least 2. Single-letter words (`a`, `I`), digits, punctuation-adjacent spaces (`. `, `, `, `: `), and already-newline punctuation sites do not match. Protected spans still block overlapping edits.

Rewrite: `The protocol` ↔ `The\nprotocol`.

Inverse: the opposite direction.

Tokenizer: GPT-2 `The protocol remains fixed` versus `The\nprotocol remains fixed` differs. VERIFIED on the frozen GPT-2 revision when transformers is present.

Whitespace collapse: `whitespace-collapse-v1` preserves LF. The rewrite still differs after `ws_collapse` and `ws_collapse_nfkc_cf_strip`. VERIFIED on fixtures.

Sanitizer note: this is a layout/formatting channel, denser than Families 4 and 10. HYPOTHESIS: a wrap/reflow sanitizer would erase it. It is admitted because Stages B and C showed punctuation-newline was the only durable family with repeated natural sites, and those sites were still too sparse (mean ~4–4.75) to replace Cycle 6 spacing after collapse.

Conflict geometry: adjacent word-boundary spaces do not overlap (each candidate is the one-character separator). Cover-greedy v4 can spend the B14 budget on up to 14 wraps. Format punctuation newlines remain separate spans.

Not admitted: extra U+0020 insertion, NBSP, ZWSP, wrapping after length-1 words, or converting punctuation spaces that Families 4 and 10 already own.

Adjacent-sentence transposition remains a HYPOTHESIS for a later stage. It is not in catalog v5, so cover-greedy cannot spend the B14 budget on one long overlapping swap that would starve this dense channel.

