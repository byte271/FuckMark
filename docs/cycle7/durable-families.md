# Cycle 7 durable families

Catalog identity: `cycle7-durable-rule-catalog-v2`.

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
