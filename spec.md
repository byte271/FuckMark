# Watermark Fracture Lab — Complete Research & Implementation Specification

**File:** `spec.md`  
**Frozen:** 2026-08-15  
**Revision:** 2 — hardened methodology  
**Status:** frozen implementation-grade research specification; confirmatory methodology hardened  
**Core subject:** reproducible robustness analysis of statistical text watermarks, with open SynthID-Text implementations as the principal experimental family.  
**Main algorithm constraint:** the perturbation/analysis algorithm under test is deterministic and non-neural. It MUST NOT call an LLM, VLM, embedding model, masked language model, neural paraphraser, neural translator, or hosted generative-AI service. Open LMs are permitted only to create benchmark watermarked/control generations because generative watermarks inherently require generated text.

This document records the complete public engineering rationale needed to execute and audit the project: source facts, hypotheses, rejected ideas, alternatives, decisions, formulas, data structures, tests, experiment designs, statistical rules, failure gates, milestones, and reproducibility requirements. It does not contain private chain-of-thought or hidden scratch reasoning.

---

## Revision-2 hardening summary

Revision 2 does not change the core project direction. It closes methodological holes that could otherwise produce a strong-looking but invalid result:

- removes unsupported claims about Claude deployment status and makes primary provider documentation authoritative;
- adds explicit detector/configuration compatibility, including the maintained Transformers Bayesian detector's non-distortionary Bernoulli(0.5) scope;
- treats Bayesian posterior as prior-dependent detector output rather than authorship probability;
- freezes prompt/continuation/chat-template/token-round-trip rules;
- defines `POLICY_ALL`, `ELIGIBLE_ONLY`, and `PRISTINE_POSITIVE` populations to prevent eligibility and baseline-selection bias;
- propagates calibration uncertainty and defines conservative finite-sample threshold construction;
- adds a baseline TPR interpretability floor, simulation-based clustered power analysis, and minimum held-out-key requirements for generalized key claims;
- adds a sealed data firewall, post-unseal bug invalidation procedure, cross-implementation conformance matrix, kill criteria, and evidence ladder;
- adds explicit reason codes for prompt contamination, re-encoding mismatch, unsupported detector/config combinations, weak baseline, and sealed-data contamination.

These additions are normative. A revision-1 run cannot be called revision-2 compliant merely by relabeling its output.

## Epistemic labels

Every material technical claim MUST be classifiable as one of:

- **VERIFIED** — supported by a primary paper, pinned primary source code, or a deterministic reproduction against that source.
- **SOURCE-BOUND** — verified only for the explicitly named implementation/version.
- **HYPOTHESIS** — a proposition to test; not a result.
- **UNKNOWN** — reliable public evidence is absent.
- **REJECTED** — inconsistent with source mechanism, code, or a required invariant.
- **EXTERNAL-VALIDATION-ONLY** — can be evaluated only through a lawful documented external interface and is outside the reproducible open benchmark.

No UNKNOWN field may be populated by analogy. No HYPOTHESIS may be written as a result. No result may be generalized beyond its tested adapter/model/tokenizer/length/domain/key/detector/fidelity regime.

# 1. Frozen objective and claim boundary


## 1.1 Objective

Build a deterministic research harness that quantitatively traces:

`text change -> tokenization change -> context/n-gram change -> valid watermark-observation replacement -> multi-depth g-value drift -> calibrated detector-evidence change`.

The project does **not** assume a universal removal attack exists. A strong negative result is valid. The scientific output is the robustness frontier: how much detector power changes for a measured amount of observation replacement and text/fidelity cost.

## 1.2 Why SynthID-Text is the open core

Google DeepMind published SynthID-Text in Nature and released a reference implementation. Hugging Face Transformers provides a maintained SynthID Text generation/detection implementation. These provide enough primary material to reproduce generation-side watermark observations and multiple detector families instead of guessing from black-box outputs.

## 1.3 Claude / proprietary systems

**Primary-source status at the 2026-08-15 freeze:** the Anthropic Transparency Hub page available to this research does **not** publish a Claude text-watermark algorithm, secret configuration, detector architecture, threshold, or public detector interface. Its “Transparency of AI Generation” section says Anthropic continues to explore and monitor watermarking developments rather than providing a technical text-watermark specification. Accordingly, this project records the existence and internal details of any Claude text watermark as **UNKNOWN unless a newer primary Anthropic source explicitly changes that status**.

Primary provider-status source checked at freeze:
`https://www.anthropic.com/transparency/voluntary-commitments/security%26privacy`

Normative consequences:

- Do not use press reports, social posts, benchmark anecdotes, or another provider's implementation as evidence that Claude deploys a particular text watermark.
- Never state that Claude uses the DeepMind reference `ngram_len`, demonstration keys, LCG hash, Transformers sampling table, Bernoulli g-value distribution, Bayesian detector, or any other SynthID-specific detail.
- Never state that an open SynthID score predicts a proprietary Claude detector.
- Never reverse-engineer, brute-force, extract, or infer a proprietary secret key in this project.
- If Anthropic later publishes a technical specification, pin the exact primary source and create a new adapter only for the disclosed behavior.
- If an official detector API later exists, treat it as an opaque `ExternalDetectorAdapter`; the transform policy, test corpus, query count, and analysis plan MUST be frozen before any confirmatory query.
- An open-family finding does not become a Claude finding without direct external evidence.
- If primary sources conflict with secondary reporting, primary sources control the technical claim. Record the conflict rather than averaging them.

### 1.3.1 Provider fact-status protocol

Before any release mentioning a proprietary provider, create a dated provider-status record containing: checked primary URLs, retrieval timestamp, exact supported claims, explicit UNKNOWN fields, public detector availability, applicable usage/automation restrictions, and the SHA-256 of the status record. A provider claim automatically expires for “current” wording after 30 days and must be rechecked before publication. Historical open-benchmark results do not expire; current-provider claims do.

## 1.4 Version-1 outcome classes

A. **ROBUST IN TESTED REGIME** — low-cost deterministic edits do not materially weaken calibrated detection.  
B. **COSTLY DEGRADATION** — evidence weakens only with large observation replacement or unacceptable fidelity cost.  
C. **STRUCTURAL WEAKNESS IN OPEN IMPLEMENTATION** — a deterministic key-blind policy produces reproducible low/moderate-cost degradation on held-out keys.  
D. **GENERALIZED FAILURE MODE IN TESTED OPEN FAMILY** — the effect survives multiple open implementations, models/tokenizers, lengths, domains, held-out keys, detectors, and independent reruns.

None means “all AI watermarks are broken” or “Claude is undetectable.”

# 2. Primary source ledger


The implementation MUST pin immutable revisions. A branch name such as `main` is not a reproducibility identifier.

### S1 — Nature paper

P. Dathathri et al., **Scalable watermarking for identifying large language model outputs**, Nature 634, 818–823 (2024), DOI `10.1038/s41586-024-08025-4`.  
Canonical: `https://www.nature.com/articles/s41586-024-08025-4`

This establishes the published SynthID-Text family: generation-time modification of sampling; pseudorandom watermark functions conditioned on recent context and watermarking material; a tournament-sampling construction; multiple watermark layers/functions; efficient detection without rerunning the base LLM; production-scale quality evaluation in Gemini. The supplementary material studies perturbations including deletion and paraphrasing and shows that edit robustness is finite and length-dependent.

### S2 — Google DeepMind reference repository

`https://github.com/google-deepmind/synthid-text`  
Pinned revision for this specification: `addb4a158143c7c6851a1308f78b89fceed59683`.

Critical files:

- `src/synthid_text/logits_processing.py`
- `src/synthid_text/hashing_function.py`
- `src/synthid_text/detector_mean.py`
- `src/synthid_text/detector_bayesian.py`
- `src/synthid_text/synthid_mixin.py`

The repository describes itself as a reference/research implementation, not the production implementation. Its static demo configuration is therefore SOURCE-BOUND.

### S3 — Hugging Face Transformers

`https://github.com/huggingface/transformers`  
Pinned source snapshot: `a61d5f9e4fc184cff66938ff6c521cc358b5e024`.  
Docs: `https://huggingface.co/docs/transformers/internal/generation_utils`

The maintained API documents `SynthIDTextWatermarkingConfig`, `SynthIDTextWatermarkLogitsProcessor`, and Bayesian detector support. Configuration fields include `ngram_len`, `keys`, `context_history_size`, `sampling_table_seed`, `sampling_table_size`, `skip_first_ngram_calls`, and `debug_mode`. This sampling-table interface is one reason generic research logic MUST NOT hard-code the older reference hashing internals.

### S3.1 — Verified maintained-Transformers compatibility facts

At pinned Transformers revision `a61d5f9e4fc184cff66938ff6c521cc358b5e024`, `SynthIDTextWatermarkingConfig` exposes `ngram_len`, `keys`, `context_history_size`, `sampling_table_seed`, `sampling_table_size`, `skip_first_ngram_calls`, and `debug_mode`, and constructs `SynthIDTextWatermarkLogitsProcessor` with those values. The implementation therefore has an adapter identity that is not interchangeable with the older DeepMind reference hash path.

At the same revision, `BayesianDetectorConfig` contains a `base_rate` prior, and `BayesianDetectorModel` computes a posterior from likelihood evidence plus prior log-odds. The source explicitly states that this Bayesian detector is for **non-distortionary Tournament-based watermarking using a Bernoulli(0.5) g-value distribution**. This compatibility restriction is normative for this project: incompatible watermark configurations MUST NOT be silently scored with that detector.

`SynthIDTextWatermarkDetector` computes an EOS mask, a context-repetition mask, their combined mask, and g-values from supplied tokenized outputs before invoking the detector model. Generic project code MUST preserve these source semantics through the adapter rather than reconstructing a “close enough” detector.

Primary pinned code locations:

- `src/transformers/generation/configuration_utils.py`
- `src/transformers/generation/logits_process.py`
- `src/transformers/generation/watermarking.py`

### S3.2 — Evidence-rank policy

Source status is recorded independently from relevance:

- **P1 PRIMARY PEER-REVIEWED:** peer-reviewed paper/conference proceedings or official published methods paper.
- **P2 PRIMARY IMPLEMENTATION:** official maintained source code/docs pinned to revision.
- **P3 PRIMARY PROVIDER STATUS:** provider's own current documentation; authoritative for provider-status claims, not automatically for unpublished mechanism details.
- **P4 PREPRINT:** arXiv or non-peer-reviewed manuscript. Useful prior art, never promoted to peer-reviewed status.
- **P5 SECONDARY:** press/news/blog discussion not authored by the system provider or paper authors. May motivate a search, but cannot establish secret or technical implementation facts.

Every bibliography row in a publishable report MUST carry one of these ranks. Conflicting P1/P2 implementation evidence is investigated as a version/implementation difference; conflicting P3 versus P5 provider-status claims are resolved in favor of P3 for technical status until newer primary evidence appears.

### S4 — Required prior art

- Cheng et al., Self-Information Rewrite Attack (SIRA), ICML 2025: `https://openreview.net/forum?id=fE3kgW7kMp`
- Diaa et al., Optimizing Adaptive Attacks against Watermarks for Language Models, ICML 2025: `https://openreview.net/forum?id=AsODat0dkE`
- Chang, Hassani, Shokri, Watermark Smoothing Attacks: `https://openreview.net/forum?id=1AYrzmDK4V`
- Pang et al., No Free Lunch in LLM Watermarking, NeurIPS 2024: `https://openreview.net/forum?id=rIOl7KbSkv`
- Omidi, Dong, Wang, On Google's SynthID-Text... **[P4 PREPRINT]**, arXiv:2603.03410: `https://arxiv.org/abs/2603.03410`
- Han et al., Robustness Assessment and Enhancement of Text Watermarking for Google's SynthID **[P4 PREPRINT]**, arXiv:2508.20228: `https://arxiv.org/abs/2508.20228`
- Tamim, Khan, AI Watermark Evidence Fails Forensic Readiness **[P4 PREPRINT]**, arXiv:2607.16010: `https://arxiv.org/abs/2607.16010`

These are baselines/cautions, not our results. SIRA already covers self-information/high-entropy localization with neural rewriting; adaptive paraphraser work already exists; smoothing already exists; simple synonym/copy-paste/paraphrase robustness studies already exist; layer-inflation analysis already exists. Version 1 novelty cannot consist merely of rediscovering those ideas.

# 3. Mechanism model and rejected avalanche theory


Let generated token IDs be `x_1...x_T`; let `H` be context width, `n=H+1` an n-gram observation length in implementations using `H` prior tokens plus the current token, `m` watermark depth, and `G_t=(g_1,...,g_m)` the recovered watermark-value vector for an eligible observation.

The exact function that produces `G_t` is adapter-specific. Generic code MUST call the adapter and must not reproduce a guessed hash.

### Generation abstraction

A statistical generative watermark changes the sampling procedure so that pseudorandom watermark values subtly influence which candidate token is selected. The final text contains no requirement for zero-width characters, metadata, or a visible marker. Detection retokenizes observed text and reconstructs statistical observations.

### Detection abstraction

Required open detector families:

1. Mean score over valid g-values.
2. Weighted Mean using source-defined layer weights.
3. Bayesian detector trained for the relevant watermark configuration.

For every score record: raw score, direction, detector checkpoint/configuration, valid-observation count, threshold, target FPR, decision, and standardized margin. A raw score by itself is not a calibrated authorship probability.


### Detector/configuration compatibility is a first-class invariant

Before scoring, `adapter.detector_compatibility(watermark_config, detector_config)` MUST return an explicit structured result. A detector may be `SUPPORTED`, `UNSUPPORTED`, or `UNVERIFIED`; only `SUPPORTED` combinations enter confirmatory tables. For current Transformers Bayesian detection, non-distortionary Tournament/Bernoulli(0.5) compatibility is required by source. A distortionary configuration is never force-fed into that Bayesian detector merely because tensor shapes match.

### Bayesian posterior is prior-dependent

The Transformers Bayesian detector includes a configurable `base_rate` prior. Therefore its output is not a provider-independent probability that “this text was written by AI.” The same likelihood evidence can yield different posteriors under different priors. Version 1 treats the posterior as a detector-native score and evaluates it at externally calibrated FPR thresholds. `base_rate`, trained parameters, checkpoint hash, and threshold bundle are all part of detector identity.

### Generated-continuation boundary

The reproducible benchmark scores the generated continuation, not the prompt, unless an experiment explicitly studies prompt contamination. Generation records MUST preserve the exact token boundary between prompt/chat-template tokens and generated response tokens. If raw generation token IDs are available, they are the canonical source; do not decode the full conversation and re-tokenize it to rediscover the boundary.

For chat models, record:

- raw user/system messages;
- exact chat-template version or tokenizer revision;
- templated prompt token IDs;
- generated continuation token IDs;
- BOS/EOS/special-token behavior;
- whether the detector receives special tokens.

A prompt-included detector run is a separate diagnostic condition and MUST be labeled `PROMPT_CONTAMINATED`; it cannot replace the clean continuation-only primary result.

### Text-only round-trip track

Real-world investigators may possess only decoded text, not original generation token IDs. That is a distinct evaluation track. For every sample, compute `decode(original_generated_ids) -> encode(text)` and report whether token IDs round-trip exactly. If not, preserve both sequences and evaluate a `TEXT_ONLY_REENCODED` condition separately. Never silently substitute re-encoded tokens for original generation tokens.

### Repeated contexts

The open implementations account for repeated contexts. Every robustness result MUST therefore separate changes due to g-values from changes due to validity/repetition masks. A transform that mainly makes contexts repeat is not allowed to masquerade as ordinary observation replacement.

### REJECTED — global hash avalanche

A previously considered theory claimed that changing one token would change all subsequent watermark observations. That is false for a finite sliding context. With a five-token n-gram, an interior substitution directly changes only overlapping windows containing the edited token; later windows can become fully identical again once the edited token leaves the context. Insertions/deletions shift alignment but can also resynchronize.

Therefore the research unit is **aligned watermark observations**, not downstream character position. Index-by-index suffix comparison is prohibited.

# 4. Frozen rejection and uncertainty ledger


| ID | Status | Statement | Required action |
|---|---|---|---|
| R001 | REJECTED | one edit permanently avalanches all downstream observations | use explicit token/n-gram alignment |
| R002 | REJECTED | global mean near 0.5 proves removal | require calibrated multi-detector evaluation |
| R003 | REJECTED | synonym count alone is a meaningful cost | report token edits + observation replacement + fidelity |
| R004 | REJECTED | public demo keys represent production keys | held-out random benchmark keys only |
| R005 | REJECTED | one successful sample proves weakness | corpus-level preregistered evidence required |
| R006 | REJECTED | one threshold works at every text length | calibrate/validate FPR by length policy |
| R007 | REJECTED | Bayesian posterior 0.5 is a universal watermark threshold | posterior depends on prior/model; use frozen fixed-FPR calibration |
| R008 | REJECTED | any SynthID Bayesian detector can score distortionary configurations | require explicit detector/config compatibility |
| R009 | REJECTED | prompt tokens may be mixed into generated text without changing interpretation | preserve continuation boundary; prompt-contaminated runs are diagnostic only |
| R010 | REJECTED | decoded-text re-tokenization is always identical to original generated token IDs | measure round-trip and separate text-only track |
| R007 | REJECTED | neural paraphraser evidence proves a deterministic no-AI method | neural attacks are prior-art baselines only |
| R008 | REJECTED | perplexity or “sounds human” proves semantic fidelity | hard invariants + blind human review |
| U001 | UNKNOWN | Claude's internal watermark construction | external-validation-only |
| U002 | UNKNOWN | Claude secret key/configuration | never infer/brute-force |
| U003 | UNKNOWN | Claude detector calibration/threshold | wait for documented interface |
| U004 | UNKNOWN | open SynthID-to-Claude transfer | empirical question |
| H001 | HYPOTHESIS | observation replacement predicts detector degradation better than word edits | E07/E08 |
| H002 | HYPOTHESIS | spaced edits replace more non-overlapping observations than clustered edits | E10 |
| H003 | HYPOTHESIS | key-blind coverage scheduling beats random edits per edit cost | E11/E16 |
| H004 | HYPOTHESIS | Bayesian detection is materially more robust than Mean in some regimes | E18 |
| H005 | HYPOTHESIS | tokenizer-specific transforms do not fully transfer | E17 |
| H006 | HYPOTHESIS | at least one structural topology effect transfers across two open SynthID tracks | E26 |

# 5. Research questions and metrics


### Research questions

RQ1: What fraction of valid original observations is preserved/replaced/dropped/added for each edit class?  
RQ2: How does calibrated detector power change versus **realized observation replacement**?  
RQ3: Where do Mean, Weighted Mean, and Bayesian detectors disagree?  
RQ4: Does an effect survive held-out keys never exposed to transformation tuning?  
RQ5: Does it survive a different tokenizer/model family?  
RQ6: How does it scale at 64/128/256/512/1024 generated tokens?  
RQ7: Does it transfer across prose/technical/conversational/structured domains?  
RQ8: What is the fidelity-versus-detection Pareto frontier?  
RQ9: How much score change is mask/denominator change rather than g-value drift?  
RQ10: Which effects transfer between DeepMind reference and maintained Transformers implementations?

### Observation metrics

After deterministic alignment:

- `N_orig_valid`
- `N_new_valid`
- `N_preserved`
- `N_replaced`
- `N_dropped`
- `N_added`
- `N_mask_changed`
- `alignment_ambiguous_count`

`preservation_ratio=N_preserved/N_orig_valid`  
`replacement_ratio=N_replaced/N_orig_valid`  
`drop_ratio=N_dropped/N_orig_valid`

### Text-cost metrics

Character Levenshtein; word edit distance; tokenizer-specific token edit distance; insertions/deletions/substitutions; changed sentence fraction; punctuation/capitalization edits; length ratio; protected-number/URL/email/code/quote/entity preservation.

### Detector metrics

Raw score; fixed-FPR threshold; TPR/FPR; ROC-AUC; PR-AUC where appropriate; score quantiles; valid-observation count; standardized margin; paired margin drop; bootstrap CI.

Headline FPRs: 5% and 1%. A 0.1% headline is permitted only with a negative calibration set large enough to estimate it responsibly (10,000 negatives is an absolute bare minimum for raw empirical resolution and more is preferred).

### Conditional versus unconditional removal metrics

Always report both:

`P(transformed not detected | pristine detected)` and  
`P(transformed detected | true watermarked)`.

A high conditional removal percentage is misleading when pristine TPR is weak; this is a central lesson from later robustness literature.

# 6. Architecture


```text
watermark-fracture-lab/
  spec.md
  README.md
  pyproject.toml
  lockfile
  source_pins/
  configs/
  wfl/
    adapters/
    tokenize/
    observations/
    detectors/
    transforms/
    fidelity/
    optimization/
    corpus/
    experiments/
    reports/
  data/manifests/
  tests/unit/
  tests/property/
  tests/golden/
  tests/integration/
  tests/regression/
  scripts/
```

### Adapter protocol

```python
class WatermarkAdapter(Protocol):
    def tokenize(self, text: str) -> list[int]: ...
    def valid_mask(self, token_ids: list[int]) -> list[bool]: ...
    def g_values(self, token_ids: list[int]): ...
    def score(self, token_ids: list[int], detector_id: str): ...
    def configuration_fingerprint(self) -> str: ...
```

Generic observation code may depend only on this interface. It MUST NOT import a specific reference hash.

### Component separation

- corpus generation creates immutable watermarked/unwatermarked samples;
- detector training is separate from calibration;
- calibration freezes thresholds before perturbation outcomes;
- observation construction is separate from transformation;
- key-blind scheduler cannot receive g-values/detector scores;
- reporting cannot refit detectors/thresholds.

# 7. Core data schema


`RunManifest` MUST record run ID, UTC date, code commit, dirty-worktree flag, Python/platform/library versions, adapter/source commit, model/tokenizer IDs and immutable revisions, watermark/detector/corpus/transform/experiment hashes, and every seed.

`TextRecord` MUST record sample ID, domain, prompt ID, class label, exact text SHA-256, token IDs/token hash, generation seed and generation parameters.

`ObservationRecord` MUST record sample ID, observation index, token start/end, full n-gram token tuple, context tuple, current token, valid/repeated/EOS flags, and g-vector.

`AlignmentRecord` MUST record original/transformed IDs, complete edit alignment or content-addressed edit script, ambiguity count, edit distance, and algorithm version.

`ObservationDiff` state is one of: `PRESERVED_VALID`, `PRESERVED_MASK_CHANGED`, `REPLACED_VALID`, `REPLACED_MASK_CHANGED`, `DROPPED`, `ADDED`, `AMBIGUOUS`.

`DetectorResult` MUST contain detector ID/checkpoint hash, raw score, score direction, valid observations, threshold ID/value, target FPR, decision, standardized margin.

`TransformationTrace` MUST contain rule/schedule versions, exact operations, precondition failures, protected-span violations, seed, input/output SHA-256. Same input+config+seed+versions MUST yield byte-identical output.

# 8. Observation alignment algorithm


### Token alignment

Use deterministic minimum-edit alignment. For sequences within normal benchmark lengths a full dynamic-programming Levenshtein alignment is acceptable; for larger sequences use Hirschberg or a validated equivalent. Stable tie order: exact match, substitution, deletion, insertion. Persist ambiguity count.

### Conserved runs

Build maximal runs in which original token position `i..i+r` maps to transformed position `j..j+r` with identical token IDs and unit increments. An n-gram is preserved only when all tokens map through one such contiguous run and validity conditions are satisfied.

### G-value drift

For a matched replaced observation of depth `m`:

`g_hamming = sum_l [g_l_original != g_l_transformed]`  
`g_hamming_rate = g_hamming/m`.

Report per-depth signed bias changes and the distribution of Hamming rates. Never assume replaced n-grams produce independent random vectors; measure it.

### Substitution coverage geometry

For a substitution at token index `i`, n-gram starts directly touched are bounded by `max(0,i-n+1)..min(i,N-n)`. Union intervals exactly capture touched original windows for substitution-only edits before source-specific validity masks. Insertions/deletions require full alignment.

### Key-blind separation

The T1 scheduler may read text, public tokenizer output, candidate spans, protected spans, edit costs, and n-gram interval geometry. It MUST NOT receive key, g-values, detector score/decision, or an external detector response. Enforce via distinct typed input objects.

# 9. Deterministic no-AI transform engine


### Protected spans

Freeze URLs, emails, IP literals, numbers unless a formatting experiment explicitly opts out, dates, currency, fenced/inline code, Markdown destinations, protected quotations, file paths, CLI flags, configurable identifiers, citations, mathematical expressions, and user-marked entities. Candidate transforms overlapping them are rejected before application.

### Families

**TIER 0 FORMAT:** structure changes with wording preserved, e.g. bullet/numbered formatting where cell/sentence content is byte-preserved.  
**TIER 1 SURFACE:** punctuation/orthography/contraction rules with explicit grammar contracts.  
**TIER 2 LEXICAL:** only sense-specific allowlisted templates with negative contexts. Dictionary synonym membership alone is insufficient.  
**TIER 3 SYNTAX:** closed grammar templates such as safe sentence splitting/parenthetical formatting, with stronger human review.  
**TIER 4 EXPERIMENTAL:** exploratory only until audited.

### Contractions

Rules like `do not <-> don't` are allowed only in unambiguous contexts; forms such as `'s`/`'d` that cannot be deterministically resolved are blocked. All-caps warnings can be excluded because contracting them can alter emphasis/style.

### Lexical rules

Each has ID/version, exact pattern, replacement, POS/construction constraints, protected-span exclusion, ambiguity blacklist, risk tier, at least five positive and five negative fixtures, case/punctuation/boundary tests, and tokenizer-retokenization fixtures.

### Schedules

- `RANDOM_VALID`
- `LEFT_TO_RIGHT`
- `CLUSTERED`
- `EVEN_SPACING`
- `FAMILY_ROUND_ROBIN`
- `COVERAGE_GREEDY_KEY_BLIND`

All apply the same candidate pool in matched comparisons where possible.

### Realized budgets

Request budgets may use char/word/token edit ratios or target observation touch, but final analysis always bins **realized** token edits and observation replacement after complete retokenization/alignment. If an applied batch exceeds budget, deterministically roll back the last operation(s), recompute, and trace the rollback.

# 10. Fidelity protocol


Hard invariants, unless a dedicated experiment opts out: numeric value, URL, email, code, designated quotation, marked entity, negation, modality, math, citation identifiers. Zero hard-invariant violations are allowed in headline results.

Deterministic distance metrics measure magnitude only; they do not prove semantic equivalence.

### Blind human adjudication

Reviewers receive original/transformed in randomized order and answer whether factual claims, quantities/names/dates/conditions/negations/obligations are preserved; whether any implication is added/removed; whether grammar is acceptable; and assign `equivalent`, `minor non-material difference`, `material difference`, or `cannot judge`.

At least two reviewers per audited sample; disagreements go to a third. Audit at least 50 randomly selected outputs per headline family×budget×domain cell where feasible, stratified by detector-degradation quartile. Recommended headline gate: >=95% `equivalent` or `minor non-material difference`, zero known hard-invariant violations. Publish the confidence interval and sample count.

Perplexity/embedding similarity can exist only in a separate AI-permitted diagnostics branch and cannot override human-identified semantic damage.

# 11. Detector training and calibration


### Mean/Weighted Mean

Wrappers must match pinned upstream outputs on golden g tensors/masks. Tests include all-zero/all-one/alternating matrices, mixed masks, one valid observation, zero-valid error behavior, multiple depths.

### Bayesian

Train configuration-specific detectors on independent watermarked/unwatermarked data. Partition detector train, validation, threshold calibration, attack development, and final evaluation by prompt family. Evaluation examples may never occur in training/calibration.

Record init/order seeds, optimizer, LR schedule, epochs, checkpoint selection rule, framework/device/dtype, training hashes. Checkpoint selection cannot use attack performance.

### Calibration sequence

1. freeze detector checkpoint;
2. create negative calibration set;
3. compute/freeze thresholds at target FPRs;
4. hash threshold bundle;
5. seal final corpus/keys;
6. only then run perturbation evaluation.

Thresholds cannot be changed after transformed outcomes are seen.

### Statistical inference

Primary independent unit is the **text sample**, not token observations. Use paired sample-level bootstrap for original-vs-transformed differences. Development: >=2,000 replicates; final: 10,000. Report 95% intervals. Prespecify multiple-testing control for confirmatory hypotheses. Publish practical effect sizes, not only p-values.

# 12. Corpus design


Domains: general explanatory prose; technical explanation; conversational prose; structured/instructional text. Prompt provenance/license must be recorded.

**Version-1 language scope is English unless a separate language-specific transform ruleset passes the same deterministic grammar fixtures and human-fidelity protocol.** The SynthID paper's multilingual evaluation does not imply that this project's English deterministic transformations transfer to other languages. Multilingual watermark robustness is a future, separately preregistered extension.

Length targets after prompt removal: 64, 128, 256, 512, 1024 tokens. Do not pad early-EOS text with filler; regenerate under a prespecified policy or analyze by realized length.

Minimum two open model/tokenizer families. Recommended initial reproduction path: a GPT-2 family track and a Gemma family track supported by public SynthID examples, with exact immutable IDs/revisions resolved in implementation configs.

Watermarked/unwatermarked controls use matched temperature/top-k/top-p/max tokens/seed policy/model precision/device except the watermark intervention. Record all fields.

A feasible confirmatory target is 200 watermarked base samples per model×domain×length core cell plus matched negatives, yielding 8,000 watermarked bases for 2×4×5×200. Final N is power-analysis driven and frozen before held-out evaluation.

Deduplicate exact normalized outputs and keep prompt-template families within one partition to avoid leakage.

# 13. Threat models and key split


T0 — natural perturbation; no watermark knowledge.  
T1 — scheme-aware, key-blind; knows public tokenizer/n-gram geometry but no key/g/detector feedback. **Primary structural threat model.**  
T2 — detector-family-aware but no per-sample oracle. Secondary.  
T3 — key-aware white box with g-values/scores. Optional upper bound, never a key-blind claim.  
T4 — proprietary black box. One-shot/preregistered external evaluation only by default.

Create `DEV_KEYS`, `VALIDATION_KEYS`, `TEST_KEYS` satisfying implementation requirements. Freeze test-key hash before development finishes. Ideally test keys are injected only by CI/second person for E20. If test g-values influence rule/schedule tuning, the test set is contaminated and must be rotated.

Headline “key-blind structural weakness” eligibility requires T0/T1, held-out keys, fixed transform policy, fixed detector calibration, and fidelity pass.

# 14. Prior-art novelty guardrails


The original SynthID supplement already demonstrates weakening under deletion/paraphrasing; therefore “editing weakens detection” is not new.

SIRA already uses self-information/high entropy to locate likely carrier positions and a neural model to rewrite; therefore high-entropy targeting is prior art.

Adaptive paraphraser optimization already exists; any detector-oracle optimizer added here is an adaptive baseline, not a new category by itself.

Watermark smoothing with a weaker LM already exists; this project’s main path deliberately excludes that neural mechanism.

Synonym substitution, copy/paste dilution, paraphrasing, and back-translation have been evaluated against SynthID implementations; synonym replacement alone is not novelty.

Omidi et al. analyze tournament-layer behavior and a Mean-score layer-inflation weakness; layer inflation is a baseline, not our finding.

Potential contribution if supported: precise aligned observation-topology accounting, deterministic no-AI perturbations, key-blind coverage scheduling, held-out-key generalization, multi-detector fixed-FPR evaluation, and strict fidelity controls across two open implementation tracks.

# 15. Experiment registry

Every experiment below produces a manifest, sample-level rows, observation rows or content-addressed equivalent, detector rows, summary JSON, audit Markdown, and SHA-256 list. A result may establish only its stated objective.

### 15.0 Common experiment execution protocol

Every E00–E30 experiment follows this protocol unless its own section explicitly adds a stricter step:

1. verify corpus SHA-256;
2. resolve immutable adapter/model/tokenizer/watermark/detector/threshold identities;
3. verify clean code/dependency state and experiment classification;
4. derive deterministic sample/condition seeds;
5. execute without threshold or hidden-config changes;
6. persist texts/tokens/alignment/observations/masks/g summaries/detector scores;
7. compute realized edit and observation metrics after retokenization;
8. apply fidelity gates before outcome filtering and retain failure rows;
9. aggregate at sample level with prespecified paired statistics;
10. export manifests, rows, summary, audit, and hashes.

Experiment sections below specify the variable, controls, evidence gate and falsification condition; those unique fields are normative.

## E00 — Source conformance

**Objective:** Verify each adapter reproduces pinned upstream masks, g-values and detector outputs.

**Independent variable(s):** source revision / adapter.  
**Controls/strata:** golden tensors and upstream calls.  
**Evidence criterion:** exact integers; floating values within justified tight tolerance.  
**Falsification/failure rule:** Any mismatch blocks every downstream experiment for that adapter.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E00 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E01 — Matched generation controls

**Objective:** Prove watermark on/off corpora differ only in intended watermark intervention and stochastic draw.

**Independent variable(s):** watermark enabled.  
**Controls/strata:** prompt/model/sampling settings.  
**Evidence criterion:** manifest parity on non-watermark parameters.  
**Falsification/failure rule:** Parameter drift invalidates corpus.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E01 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E02 — Pristine detectability

**Objective:** Establish detector power before perturbation.

**Independent variable(s):** class label.  
**Controls/strata:** model/domain/length/key/detector.  
**Evidence criterion:** TPR/FPR/AUC and distributions reported.  
**Falsification/failure rule:** Weak pristine TPR => underpowered cell, not easy removal.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E02 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E03 — Repeated-context sensitivity

**Objective:** Quantify denominator/mask behavior under controlled repetition.

**Independent variable(s):** repetition density.  
**Controls/strata:** length/domain.  
**Evidence criterion:** mask changes match source behavior.  
**Falsification/failure rule:** Unexpected mask behavior triggers adapter debugging.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E03 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E04 — Single-substitution locality

**Objective:** Validate local observation damage for one substitution.

**Independent variable(s):** edit position.  
**Controls/strata:** n-gram length/sequence length.  
**Evidence criterion:** changed windows agree with alignment/geometry.  
**Falsification/failure rule:** Persistent unexplained suffix change rejects implementation.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E04 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E05 — Insertion resynchronization

**Objective:** Measure index shift and later preserved suffix observations.

**Independent variable(s):** insert position/count.  
**Controls/strata:** length.  
**Evidence criterion:** conserved suffix n-grams recovered.  
**Falsification/failure rule:** Index-only all-suffix destruction is implementation failure.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E05 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E06 — Deletion resynchronization

**Objective:** Mirror E05 for deletion.

**Independent variable(s):** delete position/count.  
**Controls/strata:** length.  
**Evidence criterion:** conserved suffix recovered.  
**Falsification/failure rule:** Failure blocks observation metrics.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E06 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E07 — Predictor comparison

**Objective:** Compare word-edit rate and observation replacement as predictors of margin drop.

**Independent variable(s):** transform/budget.  
**Controls/strata:** held-out samples.  
**Evidence criterion:** lower held-out prediction error for supported metric.  
**Falsification/failure rule:** No superiority claim if dev-only.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E07 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E08 — Replacement dose response

**Objective:** Estimate detector curves vs realized replacement.

**Independent variable(s):** replacement bin.  
**Controls/strata:** detector/model/length.  
**Evidence criterion:** curves + uncertainty; monotonicity measured.  
**Falsification/failure rule:** Non-monotonic result must remain visible.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E08 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E09 — Random baseline

**Objective:** Create seeded non-optimized transform baseline.

**Independent variable(s):** budget.  
**Controls/strata:** same candidate pool.  
**Evidence criterion:** baseline exists for all optimizer claims.  
**Falsification/failure rule:** Missing baseline invalidates “better” claims.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E09 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E10 — Spacing topology

**Objective:** Compare clustered vs evenly spaced edits at matched cost.

**Independent variable(s):** schedule.  
**Controls/strata:** same candidates/cost.  
**Evidence criterion:** paired coverage/detector comparison.  
**Falsification/failure rule:** Unmatched cost must be adjusted or comparison withheld.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E10 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E11 — Key-blind greedy coverage

**Objective:** Test interval-union scheduling without secret feedback.

**Independent variable(s):** scheduler.  
**Controls/strata:** same candidates/budget.  
**Evidence criterion:** higher realized replacement per edit, including held-out keys.  
**Falsification/failure rule:** Any g/score access contaminates T1.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E11 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E12 — Surface transform battery

**Objective:** Measure whitespace/punctuation/orthography tokenization sensitivity.

**Independent variable(s):** rule family.  
**Controls/strata:** tokenizer/domain.  
**Evidence criterion:** rule-specific token/observation effects.  
**Falsification/failure rule:** Semantic/code mutation rejects output.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E12 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E13 — Contraction battery

**Objective:** Measure unambiguous contraction/expansion effects.

**Independent variable(s):** rule/density.  
**Controls/strata:** domain.  
**Evidence criterion:** fidelity pass + observation curve.  
**Falsification/failure rule:** Ambiguous morphology rejects candidate.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E13 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E14 — Length scaling

**Objective:** Measure normalized perturbation at 64–1024 tokens.

**Independent variable(s):** length.  
**Controls/strata:** model/domain/detector.  
**Evidence criterion:** matched replacement comparisons.  
**Falsification/failure rule:** Raw edit count across lengths prohibited.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E14 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E15 — Domain transfer

**Objective:** Test genre dependence.

**Independent variable(s):** domain.  
**Controls/strata:** same policy/budget.  
**Evidence criterion:** all four domain effects shown.  
**Falsification/failure rule:** One-domain effect labeled domain-specific.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E15 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E16 — Held-out key transfer

**Objective:** Evaluate frozen policy on unseen random keys.

**Independent variable(s):** key split.  
**Controls/strata:** all core strata.  
**Evidence criterion:** effect reproduces on TEST_KEYS.  
**Falsification/failure rule:** Any test-key tuning invalidates run.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E16 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E17 — Tokenizer transfer

**Objective:** Measure same text perturbation under different tokenizer families.

**Independent variable(s):** tokenizer/model.  
**Controls/strata:** text-level perturbation.  
**Evidence criterion:** token/observation/detector interactions shown.  
**Falsification/failure rule:** Tokenizer-specific effect not universal.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E17 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E18 — Detector disagreement

**Objective:** Compare Mean/Weighted/Bayesian paired degradation.

**Independent variable(s):** detector.  
**Controls/strata:** same samples.  
**Evidence criterion:** standardized margins and TPR@FPR.  
**Falsification/failure rule:** Mean-only weakness not full detector failure.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E18 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E19 — Per-depth drift

**Objective:** Measure every watermark layer rather than global mean only.

**Independent variable(s):** depth.  
**Controls/strata:** transform/budget.  
**Evidence criterion:** per-depth means/covariance summaries.  
**Falsification/failure rule:** Global mean alone insufficient.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E19 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E20 — Sealed confirmatory run

**Objective:** Execute frozen policy on untouched corpus/keys.

**Independent variable(s):** none after seal.  
**Controls/strata:** all preregistered strata.  
**Evidence criterion:** primary table produced from immutable bundle.  
**Falsification/failure rule:** Post-hoc change makes run exploratory.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E20 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E21 — Independent rerun

**Objective:** Repeat confirmatory experiment with fresh generation seeds/environment.

**Independent variable(s):** generation seed.  
**Controls/strata:** same frozen policy.  
**Evidence criterion:** direction/practical magnitude reproduce.  
**Falsification/failure rule:** Failure downgrades strongest claim.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E21 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E22 — Transformed-negative control

**Objective:** Check detector distribution shift on non-watermarked model output.

**Independent variable(s):** transform condition.  
**Controls/strata:** negative class.  
**Evidence criterion:** FPR shift quantified.  
**Falsification/failure rule:** Large shift changes interpretation.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E22 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E23 — Human-control stress

**Objective:** Apply transforms to human text where licensing allows.

**Independent variable(s):** transform condition.  
**Controls/strata:** human controls.  
**Evidence criterion:** false-positive behavior shown.  
**Falsification/failure rule:** Surge treated as detector shift, not success.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E23 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E24 — Protected-span stress

**Objective:** Fuzz transform engine around immutable spans.

**Independent variable(s):** adversarial text fixture.  
**Controls/strata:** every transform family.  
**Evidence criterion:** zero protected violations.  
**Falsification/failure rule:** Any violation blocks family release.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E24 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E25 — Blind fidelity audit

**Objective:** Human-check semantic preservation.

**Independent variable(s):** family/budget/domain.  
**Controls/strata:** stratified random outputs.  
**Evidence criterion:** preregistered fidelity gate.  
**Falsification/failure rule:** Material meaning change excludes result.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E25 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E26 — Open adapter transfer

**Objective:** Compare DeepMind reference vs maintained Transformers implementation.

**Independent variable(s):** adapter.  
**Controls/strata:** conceptually matched configs when valid.  
**Evidence criterion:** directional effects reported separately.  
**Falsification/failure rule:** No forced equivalence of internal parameters.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E26 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E27 — Public-demo sanity reproduction

**Objective:** Reproduce documented demo pipeline only as a sanity check.

**Independent variable(s):** demo config.  
**Controls/strata:** supported public model.  
**Evidence criterion:** generation/detection functional + archived.  
**Falsification/failure rule:** Never label demo as production.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E27 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E28 — Prior-art baseline table

**Objective:** Run feasible comparable non-neural baselines under our calibration.

**Independent variable(s):** baseline.  
**Controls/strata:** same corpus.  
**Evidence criterion:** random deletion/simple lexical controls contextualized.  
**Falsification/failure rule:** Do not fabricate unavailable neural reproduction.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E28 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E29 — White-box upper bound

**Objective:** Optional T3 comparison to quantify key-blind gap.

**Independent variable(s):** T1 vs T3.  
**Controls/strata:** same fidelity/edit budget.  
**Evidence criterion:** reported as upper bound only.  
**Falsification/failure rule:** Cannot support T1 claim.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E29 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

## E30 — External proprietary validation

**Objective:** Optional one-shot evaluation of already-frozen policy through official interface.

**Independent variable(s):** external system.  
**Controls/strata:** fixed texts/policy.  
**Evidence criterion:** date/version/interface recorded.  
**Falsification/failure rule:** No internal inference or iterative oracle tuning.

**Procedure:** follow §15.0 Common experiment execution protocol.

**Interpretation boundary:** E30 cannot by itself establish proprietary-system transfer. Confirmatory claims require the corresponding held-out, detector, model/tokenizer, fidelity, and rerun gates.

# 16. Confirmatory matrix and estimands


Core balanced matrix target: `2 models × 4 domains × 5 lengths × 200 watermarked = 8,000` watermarked base samples plus matched negatives. Transform multipliers are controlled by using a minimal confirmatory schedule set: random, even spacing, and key-blind coverage greedy, sharing candidate pools where possible.

Realized observation-replacement bins: `0–5%`, `>5–15%`, `>15–25%`, `>25–35%`, `>35–50%`, `>50%`.

Primary estimands:

1. TPR change at 1% FPR.
2. Standardized detector-margin drop.
3. Observation replacement per normalized token edit.
4. Conditional pristine-positive decision loss.
5. Unconditional transformed TPR.

Secondary: ROC-AUC change, per-depth drift, detector disagreement, mask-change fraction.

If no valid transformation exists under a requested budget, emit `NO_ELIGIBLE_TRANSFORM`; never invent an operation. Eligibility rates are part of the result.

# 17. Preregistration and sealing


The confirmatory YAML committed before held-out access MUST resolve: spec revision, source commits, immutable models/tokenizers, domains, length buckets, detectors, target FPRs, transform ruleset hash, schedules, realized replacement bins, primary outcomes, fidelity gate, bootstrap settings, multiple-testing method, sealed test-key hash, sealed test-corpus hash.

Sequence is mandatory:

1. DEV experiments.
2. Validation experiments/hyperparameter selection.
3. Power analysis and final N.
4. Freeze transform rules/scheduler/budgets.
5. Freeze detectors/checkpoints.
6. Freeze thresholds.
7. Commit preregistration.
8. Seal test keys/corpus.
9. E20 exactly once.
10. E21 independent rerun.

If a software bug is found during E20, stop; document; invalidate; fix; create a fresh seal if outcomes could have influenced the fix. Do not patch-and-continue.

# 18. Key-blind coverage scheduler


For substitution-like candidate `c`, estimate affected original n-gram interval `I_c` and edit cost `w_c`. The T1 objective is maximize `|union I_c|` subject to budget and non-overlap constraints. It contains no g-value or detector term.

Greedy baseline: repeatedly choose candidate maximizing `|I_c minus covered| / cost(c)`, stable tie-break by candidate ID; stop before budget violation. After text application, fully retokenize and compute realized observation replacement.

For small candidate sets, implement an exact dynamic-programming or integer-programming diagnostic to quantify greedy regret. This does not change the main scheduler; it tells whether a null result is due to poor interval selection.

Compare `TEXT_ONLY` and `TOKENIZER_AWARE_PUBLIC` scheduling in E17. The first uses character/word geometry only; the second may use public benchmark tokenizer/n-gram geometry but remains key-blind.

# 19. Software verification


### Unit tests

Alignment: identical; one substitution beginning/middle/end; insertion; deletion; two adjacent edits; two distant edits; repeated-token ties; total replacement; empty.  
Observation: n=2/3/5; every edit position; overlap/non-overlap; suffix resynchronization; synthetic mask-only change.  
Coverage: interval-union equality against brute force for substitution-only sequences; monotonic union; budget enforcement.  
Protected spans: randomized URLs/emails/numbers/code/Markdown/quotes/paths.  
Determinism: every rule and scheduler replayed many times.  
Detector wrappers: golden upstream fixtures.

### Property tests

If token sequence is unchanged, replacement ratio is zero and deterministic adapter g-values match. For a pure substitution without mask changes, every preserved full n-gram has identical g-values. For substitution-only edit sets, interval-union touched windows equal brute-force changed n-grams.

### Integration

Tiny end-to-end pipeline: generate -> score -> observe -> transform -> align -> rescore -> aggregate -> report -> rerun and compare hashes where deterministic.

### Regression

Every bug requires minimized failing fixture, failing test before fix, permanent regression case. Never “fix” a source mismatch by arbitrarily widening numerical tolerance.

# 20. CLI contract


No consumer `remove-watermark` command exists. Explicit research phases:

```text
wfl source verify
wfl corpus generate --config ...
wfl detector train --config ...
wfl detector calibrate --config ...
wfl observe build --run ...
wfl transform enumerate --ruleset ...
wfl transform apply --schedule ... --budget ...
wfl compare observations --original ... --transformed ...
wfl experiment run --id E20 --prereg ...
wfl experiment aggregate --run ...
wfl report build --run ...
wfl audit release --run ...
```

Confirmatory `experiment run` refuses config overrides, threshold changes, missing seals, source-pin mismatches, dirty working tree unless exact diff is captured, or output-directory collisions.

Exit codes: 0 success; 2 config; 3 source mismatch; 4 reproducibility/audit; 5 fidelity invariant; 6 calibration N insufficient; 7 detector training/calibration; 8 sealed-data contamination.

# 21. Result reporting


Every headline row includes adapter, source commit, model/tokenizer revisions, domain, length, detector, target FPR, pristine TPR, transformed TPR, delta+CI, N, median realized observation replacement, token edit ratio, eligibility and fidelity-pass rates.

Required plots: TPR vs observation replacement; standardized margin vs replacement; replacement vs token edit ratio; schedule coverage efficiency; length panels; detector disagreement; per-depth drift; transformed-negative distributions; fidelity Pareto frontier; distribution of effects across held-out keys.

Forbidden: hand-entered headline numbers; threshold refitting in plotting code; cherry-picked lengths; omitting fidelity failures; treating Bayesian posterior as probability of authorship; claiming proprietary transfer from an open score.

Every headline table also reports: `POLICY_ALL` eligibility-adjusted effect, eligible-only effect, pristine-positive conditional loss, achieved calibration FPR with exact CI, baseline TPR gate status, detector/config compatibility status, prompt-boundary mode, and whether token IDs are original-generation or text-only re-encoded.

Every figure has metadata with source-result hash, filter, grouping, statistic, CI method, script commit.

# 22. Data provenance and reproducibility


Prompt/source license and collection provenance are mandatory. Large corpora/model weights are not committed unless appropriate; manifests and hashes are.

Shard deterministically by sample ID hash. Cache expensive immutable generation/detector-training artifacts using content-addressed keys. Atomic writes prevent partial-run contamination.

Release bundle:

```text
MANIFEST.json
SOURCE_PINS.json
PREREGISTRATION.yaml
THRESHOLDS.json
SUMMARY.json
TABLES/
FIGURES/
RESULT_SHARDS/
FIDELITY_AUDIT/
KNOWN_LIMITATIONS.md
REPRODUCE.md
SHA256SUMS
```

Clean-room reproduction: clone release tag, verify sources, create locked environment, obtain immutable model revisions, verify data hashes, regenerate or verify corpus, reproduce detector/calibration, run E00, execute preregistered experiment, aggregate/report/audit, compare metrics/hashes. Hardware sampling nondeterminism is reported; it is not hidden by silently changing model versions.

# 23. Failure-mode catalog

The following failures are first-class data and audit states, not edge notes.

### 23.0 Common failure audit policy

Every applicable failure class is counted in the aggregate summary. A post-release discovery produces a corrected, newly hashed result-bundle revision; previously published artifacts are never silently overwritten.

## F01 — Weak pristine baseline

**Signature:** Pristine positives already fail often.  
**Required response:** Mark cell underpowered; do not present conditional removal as robustness break.

Apply §23.0 failure audit policy.

## F02 — Calibration leakage

**Signature:** Threshold selected after transformed outcomes.  
**Required response:** Invalidate run and rebuild with fresh sealed split.

Apply §23.0 failure audit policy.

## F03 — Key leakage

**Signature:** TEST_KEYS/g-values influence policy.  
**Required response:** Invalidate key-generalization claim and rotate keys.

Apply §23.0 failure audit policy.

## F04 — Tokenizer drift

**Signature:** Revision change alters token IDs.  
**Required response:** Source-pin check fails; regenerate dependent artifacts.

Apply §23.0 failure audit policy.

## F05 — Adapter conflation

**Signature:** Reference hash assumed for Transformers.  
**Required response:** Move logic behind adapter; conformance test required.

Apply §23.0 failure audit policy.

## F06 — Index-only suffix damage

**Signature:** Insertion appears to destroy all suffix windows.  
**Required response:** Use minimal alignment and conserved contiguous runs.

Apply §23.0 failure audit policy.

## F07 — Semantic drift

**Signature:** Transform changes material meaning.  
**Required response:** Reject from headline set; preserve failure row.

Apply §23.0 failure audit policy.

## F08 — Protected-span mutation

**Signature:** Number/URL/code/etc changes.  
**Required response:** Hard failure and regression test.

Apply §23.0 failure audit policy.

## F09 — Repeated-context gaming

**Signature:** Score falls mostly because valid denominator shrinks.  
**Required response:** Decompose mask effect and label separately.

Apply §23.0 failure audit policy.

## F10 — Negative distribution shift

**Signature:** Transforms also strongly move negatives.  
**Required response:** Report specificity/FPR shift; revise interpretation.

Apply §23.0 failure audit policy.

## F11 — Eligibility bias

**Signature:** Only easy samples are transformed.  
**Required response:** Report eligibility and define estimand explicitly.

Apply §23.0 failure audit policy.

## F12 — Length confounding

**Signature:** Transform shortens text substantially.  
**Required response:** Match/stratify effective valid length.

Apply §23.0 failure audit policy.

## F13 — Multiple-testing fishing

**Signature:** Best of many dev rules reported as primary.  
**Required response:** Label exploratory; validate on sealed set.

Apply §23.0 failure audit policy.

## F14 — Bayesian data leakage

**Signature:** Eval prompts occur in detector train.  
**Required response:** Retrain on group-disjoint partitions.

Apply §23.0 failure audit policy.

## F15 — Wrong independent unit

**Signature:** Tokens treated as independent replicates.  
**Required response:** Use text sample as primary inferential unit.

Apply §23.0 failure audit policy.

## F16 — Demo-key overfit

**Signature:** Public example key tuned.  
**Required response:** Held-out random key result is primary.

Apply §23.0 failure audit policy.

## F17 — Hidden neural dependency

**Signature:** Library calls embedding/model service.  
**Required response:** Dependency audit fails main no-AI track.

Apply §23.0 failure audit policy.

## F18 — Fidelity selection bias

**Signature:** Only attack-success texts reviewed.  
**Required response:** Random stratification by condition/degradation quartile.

Apply §23.0 failure audit policy.

## F19 — Cross-model duplication

**Signature:** Duplicate outputs contaminate strata.  
**Required response:** Deduplicate and preserve provenance.

Apply §23.0 failure audit policy.

## F20 — External oracle optimization

**Signature:** Repeated provider queries tune policy.  
**Required response:** Classify as T4 adaptive, not T1.

Apply §23.0 failure audit policy.

## F21 — Floating tolerance laundering

**Signature:** Tolerance widened to hide mismatch.  
**Required response:** Diagnose dtype/device/version.

Apply §23.0 failure audit policy.

## F22 — Chart value invention

**Signature:** Paper plot eyeballed as exact data.  
**Required response:** Omit or label digitized estimate with method.

Apply §23.0 failure audit policy.

## F23 — Claude parameter assumption

**Signature:** Open parameter copied to proprietary target.  
**Required response:** Claim lint hard-fails.

Apply §23.0 failure audit policy.

## F24 — Survivorship bias

**Signature:** Failed transform rows omitted.  
**Required response:** All reason codes counted.

Apply §23.0 failure audit policy.

## F25 — License failure

**Signature:** Redistributed corpus lacks rights.  
**Required response:** Replace or release hashes/reconstruction only.

Apply §23.0 failure audit policy.

# 24. Architecture decision records

These decisions are frozen until new primary evidence or a formal spec revision supersedes them.

## ADR001 — Research harness over bypass product

**Context:** A one-click remover hides assumptions and encourages score chasing.  
**Decision:** Keep explicit generation/observation/transform/calibration/report phases.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR002 — Observation replacement as mechanistic variable

**Context:** Word changes map inconsistently to tokenizer n-grams.  
**Decision:** Use aligned valid observation preservation/replacement.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR003 — Three detector families

**Context:** Mean-only success can fail against Bayesian evidence.  
**Decision:** Require Mean/Weighted/Bayesian.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR004 — Key-blind main threat model

**Context:** Key-aware optimization overfits pseudorandom partitions.  
**Decision:** Seal held-out keys; T1 is headline threat model.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR005 — No neural transformation

**Context:** Constraint plus extensive neural-attack prior art.  
**Decision:** Finite rules/structure/coverage + human fidelity.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR006 — Separate reference and Transformers adapters

**Context:** Implementation details differ.  
**Decision:** No generic hash assumptions.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR007 — Proprietary systems opaque

**Context:** Internal parameters unavailable.  
**Decision:** Only documented external validation.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR008 — Fixed-FPR calibration first

**Context:** Raw scores/default thresholds incomparable.  
**Decision:** Freeze thresholds before perturbation.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR009 — Human semantic review

**Context:** No-AI rule excludes semantic neural judges.  
**Decision:** Hard invariants + blinded human adjudication.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

## ADR010 — Preserve negative/null results

**Context:** Robustness work is vulnerable to cherry-picking.  
**Decision:** All rows/reasons published or accounted for.  
**Reopen only if:** a primary-source change, reproducibility failure, or explicit project-constraint change invalidates the premise. A replacement ADR must cite the superseded decision.

# 25. Formal metric appendix


For token sequences `A=(a_1..a_N)` and `B=(b_1..b_M)`, compute unit-cost minimum edit distance with stable tie-breaking. Derive equal-token mapping.

For n-gram `o_i=(a_i..a_{i+n-1})`, preservation requires all `n` token positions map to consecutive transformed positions with identical IDs. Absolute position does not define identity.

Let adapter mask `v_i`. Original valid set is `{o_i:v_i=1}`. Generic code never reconstructs a source-specific repetition mask from assumptions; adapter supplies it.

For matched replaced observation and depth `m`, `h_i=(1/m) sum_l [g_il != g'_jl]`. Publish average/distribution plus per-depth signed drift.

Coverage efficiency: `N_replaced / max(1, token_edit_distance)`. Publish alternative denominators separately.

Conditional decision-loss and unconditional TPR are both mandatory.

For standardized detector margins, paired drop `d_i=m_original_i-m_transformed_i`; report distribution and paired bootstrap CI.

For held-out key `k`, estimate `delta_k`; publish mean, IQR/SD, and key-level distribution so one weak key cannot carry a general claim.

# 26. Bayesian detector training protocol


A Bayesian detector checkpoint is treated as configuration-specific unless a primary source and validation demonstrate portability. Positive train data are watermarked under that config; negatives are matched unwatermarked generations. Do not train baseline detectors on attacked positives unless running a separate defense-retraining study.

Partition by prompt family: detector train, detector validation, threshold calibration, attack development, final test. Freeze model selection before attack test. Record seeds/optimizer/schedule/epochs/device/dtype/data hashes.

Sanity checks: label permutation approaches chance; all-zero masks rejected; shuffled g-patterns reduce signal; calibrated negatives meet target FPR within uncertainty; train/validation leakage audit clean.

A future “robust detector” branch may train on transformed positives, but it is a defense experiment and cannot retroactively replace the baseline after main attack results are observed.

# 27. Configuration hashing and immutability


YAML is human input; canonical JSON is hashed. Canonicalization: UTF-8, sorted keys, no NaN/Infinity, stable number representation, explicit path policy, no secrets in public manifests.

Artifact identity is derived from stage algorithm version + all input hashes + canonical configuration hash. Raw outputs are immutable. A rerun writes a new content-addressed artifact or confirms existing hash.

Required configs: source pins, model, tokenizer, watermark, detector, calibration, ruleset, schedule, corpus, experiment, statistics, human-audit sampling. Confirmatory configs contain no `TODO`, `TBD`, unresolved angle-bracket placeholders, or floating model branches.

# 28. Milestones and hard gates


**M0 Source freeze:** repo skeleton, lockfile, pins, licenses, spec, CI. Gate: commits machine-verifiable.  
**M1 Adapters:** DeepMind then Transformers conformance. Gate: E00.  
**M2 Observation engine:** alignment/diff/masks. Gate: E04–E06 + property tests.  
**M3 Corpus/calibration:** dev corpus, Bayesian training, fixed FPR baselines. Gate: E02.  
**M4 Transforms:** protected spans + narrow surface/contraction rules. Gate: zero invariant failures, deterministic replay, initial human audit.  
**M5 Schedulers:** random/spacing/coverage. Gate: typed T1 interface contains no secret fields.  
**M6 Development experiments:** E07–E19 using DEV/VALIDATION only; power analysis. No break claim.  
**M7 Seal:** final rules/scheduler/N/thresholds/hypotheses/test hashes committed.  
**M8 E20:** one confirmatory run. Bug => invalidate, not patch.  
**M9 E21:** independent rerun with fresh generation seeds.  
**M10 Release:** code, manifests, aggregates, fidelity audit, null results, limitations, hashes. No GUI required.

# 29. Definition of done


Version 1 is done only when both adapters pass source conformance; detector/watermark compatibility is explicit; prompt/continuation/chat-template boundaries are reproducible; original-token and text-only re-encoding tracks are distinguishable; observation alignment passes substitution/insertion/deletion and brute-force property tests; masks and per-depth g drift are separated; compatible Mean/Weighted/Bayesian detectors are reproduced/trained/calibrated; calibration uncertainty and achieved FPR CIs are reported; pristine baselines pass the preregistered interpretability floor or are explicitly excluded from removal claims; no neural dependency exists in the main transform decision path; protected spans and deterministic traces work; random/even/coverage schedules exist; `POLICY_ALL` and eligible-only effects are both reported; length/domain/key/tokenizer/adapter/detector transfer experiments run; human fidelity gate runs; sealed held-out run and independent rerun complete; every headline result reports fixed FPR, TPR, N, length, adapter, model, detector identity, compatibility status, observation replacement, edit cost, eligibility, fidelity, prompt-boundary mode and calibration uncertainty; null results, contamination status, failures and hashes are released.

Website, browser extension, and one-click remover are explicitly outside version 1.

# 30. Component contracts

Each component is independently versioned. Any behavior change that can alter result rows increments its algorithm version and invalidates dependent caches.

### 30.0 Common component contract

Every component is tested on normal, empty, boundary, malformed, replay, and serialization cases. Components touching upstream watermark logic compare against pinned upstream behavior rather than guessed constants. Components never silently repair scientifically meaningful invalid input: they fail with a reason code preserved in the run ledger. Any behavior change that can alter result rows increments the component algorithm version and invalidates dependent caches.

## C01 — `SourcePinRegistry`

**Purpose:** immutable upstream identity.  
**Mandatory behavior:** resolve commit; hash critical files; record license; reject floating branch.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C02 — `AdapterRegistry`

**Purpose:** implementation-specific watermark interface.  
**Mandatory behavior:** construct adapter; validate config; expose masks/g-values/scores; fingerprint source.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C03 — `TokenizerFacade`

**Purpose:** tokenization provenance.  
**Mandatory behavior:** encode without silent truncation; separate prompt/generated IDs; hash arrays.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C04 — `ObservationBuilder`

**Purpose:** source-native observation rows.  
**Mandatory behavior:** derive spans; attach masks/g-vectors; validate shape/depth.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C05 — `TokenAligner`

**Purpose:** deterministic edit alignment.  
**Mandatory behavior:** edit script; equal mapping; ambiguity count; algorithm version.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C06 — `ObservationAligner`

**Purpose:** observation identity/diff.  
**Mandatory behavior:** contiguous mapping; preservation/replacement/drop; mask decomposition.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C07 — `ProtectedSpanExtractor`

**Purpose:** immutable content guard.  
**Mandatory behavior:** URL/email/number/code/quote/path/entity spans; merge overlaps.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C08 — `TransformRegistry`

**Purpose:** versioned deterministic rules.  
**Mandatory behavior:** enumerate; precondition; apply; trace; no network/model inference.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C09 — `CandidateScheduler`

**Purpose:** budgeted operation selection.  
**Mandatory behavior:** random; spacing; key-blind coverage; stable ties.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C10 — `FidelityValidator`

**Purpose:** content invariants/edit metrics.  
**Mandatory behavior:** canonical values; compare; reason codes; human status separate.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C11 — `DetectorCalibrator`

**Purpose:** immutable thresholds.  
**Mandatory behavior:** null quantiles; empirical FPR; robust scale; threshold hash.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C12 — `ExperimentRunner`

**Purpose:** sealed execution.  
**Mandatory behavior:** resolve manifests; per-sample seeds; sharding; atomic writes.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C13 — `Aggregator`

**Purpose:** paired statistics.  
**Mandatory behavior:** stratify; bootstrap; TPR/AUC/margins; never refit threshold.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C14 — `ReportBuilder`

**Purpose:** traceable tables/figures.  
**Mandatory behavior:** read result rows; figure metadata; limitations; claim lint.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C15 — `ReleaseAuditor`

**Purpose:** integrity enforcement.  
**Mandatory behavior:** source check; seal check; placeholder scan; completeness; hashes.

**Verification:** apply §30.0 plus any component-specific upstream conformance test.

## C16 — `CompatibilityGate`

**Purpose:** prevent scientifically invalid detector/watermark combinations.

**Required behavior:** resolve implementation revision, watermark mode, g-distribution assumptions, detector family, checkpoint metadata and source compatibility; return `SUPPORTED`, `UNSUPPORTED`, or `UNVERIFIED` with source evidence; fail confirmatory runs closed on the latter two states.

**Testing:** include a valid non-distortionary Transformers Bayesian fixture, a deliberately incompatible distortionary fixture, missing metadata, and a source-version mismatch.

## C17 — `BoundaryLedger`

**Purpose:** make prompt/chat-template/generated-token boundaries impossible to lose silently.

**Required behavior:** store canonical generated token IDs, prompt token IDs, special-token policy, decode/re-encode token hash, round-trip status and detector-input token hash.

**Testing:** left/right padding, BOS/EOS variants, multi-turn chat templates, Unicode whitespace, empty continuation, early EOS and decode/re-encode mismatch.

## C18 — `SealManager`

**Purpose:** enforce the confirmatory data firewall.

**Required behavior:** create/verify `SEAL.json`, manage encrypted or CI-injected test key material, write append-only access events, reject development-mode reads of sealed artifacts, and emit contamination reason codes.

**Testing:** valid confirmatory access, premature dev access, hash mismatch, replay, post-unseal code mismatch, and corrupted audit log.

# 31. Hypothesis catalog

All statuses are HYPOTHESIS at spec freeze; none is a result.

## H01 — Substitution locality

**Claim:** Interior substitution changes only overlapping token n-grams apart from mask effects.  
**Primary test:** E04.  
**Promotion evidence:** Local diff matches alignment.  
**Falsification/downgrade:** Unexplained persistent suffix drift.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H02 — Resynchronization

**Claim:** Insertion/deletion can recover conserved suffix observations.  
**Primary test:** E05/E06.  
**Promotion evidence:** Conserved runs recovered.  
**Falsification/downgrade:** Exact conserved suffix still classified destroyed.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H03 — Observation predictor

**Claim:** Replacement ratio predicts margin drop better than word edit ratio.  
**Primary test:** E07/E08.  
**Promotion evidence:** Lower held-out error.  
**Falsification/downgrade:** No advantage.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H04 — Spacing efficiency

**Claim:** Even spacing replaces more observations per edit than clustering.  
**Primary test:** E10.  
**Promotion evidence:** Positive paired efficiency.  
**Falsification/downgrade:** No difference/reverse.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H05 — Greedy structural gain

**Claim:** Key-blind interval greedy beats random coverage per edit.  
**Primary test:** E11/E16.  
**Promotion evidence:** Held-out gain.  
**Falsification/downgrade:** Dev-only/no gain.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H06 — Bayesian robustness difference

**Claim:** Bayesian resists some transforms more than Mean.  
**Primary test:** E18.  
**Promotion evidence:** Practical paired difference.  
**Falsification/downgrade:** No consistent difference.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H07 — Depth information

**Claim:** Similar global means can hide different depth patterns/Bayesian evidence.  
**Primary test:** E19.  
**Promotion evidence:** Matched means but different depth/score.  
**Falsification/downgrade:** Bayesian fully explained by global mean.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H08 — Length interaction

**Claim:** Longer text retains more evidence at matched replacement in some regimes.  
**Primary test:** E14.  
**Promotion evidence:** Length interaction.  
**Falsification/downgrade:** No interaction.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H09 — Tokenizer interaction

**Claim:** Surface transforms produce tokenizer-dependent observation damage.  
**Primary test:** E17.  
**Promotion evidence:** Material interaction.  
**Falsification/downgrade:** Near-identical effects.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H10 — Domain eligibility

**Claim:** Safe candidate density changes attainable frontier by domain.  
**Primary test:** E15.  
**Promotion evidence:** Eligibility/coverage differs.  
**Falsification/downgrade:** No difference.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H11 — Specific degradation

**Claim:** Positive evidence drops more than negative score distribution moves.  
**Primary test:** E22.  
**Promotion evidence:** Positive paired drop dominates.  
**Falsification/downgrade:** Negative shift comparable/larger.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H12 — Adapter transfer

**Claim:** At least one topology effect appears in both open implementations.  
**Primary test:** E26.  
**Promotion evidence:** Same directional effect.  
**Falsification/downgrade:** Implementation-specific.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H13 — No-AI structural weakness

**Claim:** A fidelity-passing T1 policy materially reduces calibrated Bayesian TPR across held-out keys at moderate cost.  
**Primary test:** E20/E21.  
**Promotion evidence:** All preregistered gates pass.  
**Falsification/downgrade:** Any core gate fails.

Even if supported, scope is limited to tested open configurations until direct evidence establishes transfer.

## H14 — Policy-all effect survives eligibility accounting

**Status:** HYPOTHESIS.  
**Claim:** the principal transformation effect remains practically meaningful when ineligible source texts are retained as unchanged outputs in `POLICY_ALL`.  
**Promotion evidence:** preregistered policy-all effect passes the calibrated detector, fidelity, held-out-key and rerun gates.  
**Falsification/downgrade:** effect exists only in a narrow eligible subset; report eligible-only mechanism without deployable policy claim.

## H15 — Calibration uncertainty does not explain the headline effect

**Status:** HYPOTHESIS.  
**Claim:** detector degradation remains material when threshold-estimation uncertainty is propagated.  
**Promotion evidence:** nested calibration/evaluation sensitivity interval remains beyond the preregistered practical-equivalence bound.  
**Falsification/downgrade:** effect disappears or becomes indeterminate after calibration uncertainty.

## H16 — Text-only re-encoding preserves the direction of the open-benchmark effect

**Status:** HYPOTHESIS.  
**Claim:** the transformation effect is not an artifact of privileged access to original generated token IDs.  
**Promotion evidence:** text-only re-encoded track shows the same directional calibrated effect with disclosed token-round-trip mismatch rates.  
**Falsification/downgrade:** effect is canonical-token-only; scope the finding accordingly.

# 32. Mandatory ablations

Ablations are secondary unless preregistered as primary. Change only the named factor from the parent configuration.

### 32.0 Common ablation protocol

Change only the named factor. Report pristine/transformed detector behavior, observation metrics, edit/fidelity metrics, N, and CI. Interpretation is limited to sensitivity of the tested open configuration; ablations never infer proprietary parameters.

## A01 — n-gram length

**Purpose:** vary supported n-gram length on controlled open configs; measure locality/robustness tradeoff.  
**Protocol:** §32.0.

## A02 — watermark depth

**Purpose:** vary layer/key count; compare Mean/Bayesian; layer-inflation is prior art.  
**Protocol:** §32.0.

## A03 — context history

**Purpose:** vary history capacity where supported; measure repetition masking.  
**Protocol:** §32.0.

## A04 — sampling parameters

**Purpose:** temperature/top-k/top-p effects under matched controls.  
**Protocol:** §32.0.

## A05 — candidate density

**Purpose:** same budget under low/high number of valid transform spans.  
**Protocol:** §32.0.

## A06 — edit clustering continuum

**Purpose:** sweep pairwise edit distance at fixed cost.  
**Protocol:** §32.0.

## A07 — edit operation type

**Purpose:** substitution vs insertion/deletion at matched token edit distance.  
**Protocol:** §32.0.

## A08 — mask-frozen synthetic diagnostic

**Purpose:** analysis-only isolate g drift; never call it actual detector behavior.  
**Protocol:** §32.0.

## A09 — layer weighting

**Purpose:** unweighted vs source-default weighted aggregation.  
**Protocol:** §32.0.

## A10 — number of benchmark keys

**Purpose:** estimate key heterogeneity/stability.  
**Protocol:** §32.0.

## A11 — fidelity inclusion tier

**Purpose:** strict equivalent-only vs equivalent+minor.  
**Protocol:** §32.0.

## A12 — negative class type

**Purpose:** model negatives vs human controls.  
**Protocol:** §32.0.

## A13 — greedy regret

**Purpose:** greedy vs exact coverage optimum on small candidate sets.  
**Protocol:** §32.0.

## A14 — tokenizer awareness

**Purpose:** text-only vs tokenizer-aware key-blind scheduling.  
**Protocol:** §32.0.

## A15 — rule-family removal

**Purpose:** drop each transform family in turn.  
**Protocol:** §32.0.

## A16 — domain removal

**Purpose:** pooled effect sensitivity to each domain.  
**Protocol:** §32.0.

## A17 — length weighting

**Purpose:** equal-cell vs sample-count pooling.  
**Protocol:** §32.0.

## A18 — calibration pooling

**Purpose:** per-length vs validated pooled thresholds.  
**Protocol:** §32.0.

## A19 — Bayesian training seed

**Purpose:** detector-training variance.  
**Protocol:** §32.0.

## A20 — generation seed

**Purpose:** independent generation variance.  
**Protocol:** §32.0.

## A21 — prompt contamination

Compare continuation-only scoring with deliberately prompt-included scoring to quantify why prompt boundary must be controlled. Diagnostic only; prompt-contaminated scores cannot replace primary results.

## A22 — original token IDs versus decoded/re-encoded IDs

Measure token round-trip mismatch and detector sensitivity to re-encoding. Report by tokenizer/model and transformation family.

## A23 — Bayesian base-rate prior

For the same frozen likelihood checkpoint, vary declared prior only as a detector-semantics diagnostic. Show that posterior shifts do not imply changed watermark evidence. Fixed-FPR calibrated decisions remain the main benchmark.

## A24 — calibration tail stability

Repeat threshold construction across independent negative calibration shards; quantify threshold/FPR variability at 5%, 1%, and any attempted 0.1% operating point.

## A25 — analysis-population sensitivity

Compare `POLICY_ALL`, `ELIGIBLE_ONLY`, and `PRISTINE_POSITIVE` estimands so survivorship and weak-baseline effects are visible.

# 33. Execution checklists

These are release gates, not suggestions.

## Before coding

- [ ] freeze source pins and licenses.
- [ ] create adapter protocol.
- [ ] create terminology/epistemic labels.
- [ ] set CI placeholder/claim lint.
- [ ] lock dependencies.

## Before generation

- [ ] freeze model/tokenizer revisions.
- [ ] freeze prompt splits.
- [ ] freeze generation settings/seeds.
- [ ] smoke-test EOS/length.
- [ ] capture hardware/software.

## Before detector training

- [ ] verify group-disjoint prompts.
- [ ] match positive/negative generation settings.
- [ ] verify g/masks against goldens.
- [ ] freeze training seed policy.
- [ ] freeze checkpoint selection.

## Before calibration

- [ ] freeze checkpoint.
- [ ] verify negative N supports FPR.
- [ ] compute thresholds without transformed positives.
- [ ] hash threshold bundle.
- [ ] inspect null diagnostics.

## Before transform development

- [ ] protected-span extractor.
- [ ] hard-invariant validator.
- [ ] positive/negative fixtures per rule.
- [ ] dependency audit for neural calls.
- [ ] deterministic candidate enumeration.

## Before held-out run

- [ ] verify every detector/watermark pair is `SUPPORTED` by `CompatibilityGate`.
- [ ] verify canonical continuation boundaries and text-only re-encoding hashes are frozen.
- [ ] freeze `POLICY_ALL`, `ELIGIBLE_ONLY`, and pristine-positive estimands.
- [ ] freeze threshold comparison operator and exact-FPR CI method.
- [ ] verify baseline TPR interpretability-floor policy.
- [ ] create and hash `SEAL.json`; verify dev process cannot read sealed artifacts.

- [ ] freeze ruleset.
- [ ] freeze scheduler/budgets.
- [ ] freeze hypotheses/statistics.
- [ ] freeze thresholds.
- [ ] seal corpus/keys.
- [ ] preflight release audit.

## After held-out run

- [ ] no tuning thresholds/rules.
- [ ] aggregate every preregistered cell.
- [ ] report failures/eligibility.
- [ ] blind human fidelity audit.
- [ ] independent rerun.

## Before publication

- [ ] regenerate tables from rows.
- [ ] verify figure metadata.
- [ ] source/claim lint.
- [ ] archive hashes.
- [ ] publish limitations/null results.

# 34. Anti-fabrication and research integrity


No numerical effectiveness claim enters documentation before a signed result bundle supports it. Schema examples must be explicitly labeled examples. Tables/figures are code-generated from immutable rows. Figure metadata stores result hash and filters. If chart values are manually digitized from a paper, label them `DIGITIZED_ESTIMATE` and document method/error; do not type an eyeballed value as exact.

Use uncertainty language: “observed in,” “supports,” “did not reproduce,” “consistent with,” “unknown for proprietary implementation.” Avoid “universal,” “guaranteed,” “undetectable,” or “proves Claude” without logically sufficient evidence.

If an external detector is unavailable, record `EXTERNAL_INTERFACE_UNAVAILABLE`; never simulate a result and label it Claude.

A current provider-deployment claim must cite a current primary provider source in the provider-status record. Secondary reports cannot be promoted to VERIFIED technical status by repetition.

Release signature hashes spec, code commit, source pins, corpus, detector checkpoints, threshold bundle, preregistration and result artifacts.

# 35. Machine-readable reason codes


`OK`, `NO_ELIGIBLE_TRANSFORM`, `REALIZED_BUDGET_EXCEEDED`, `PROTECTED_SPAN_CONFLICT`, `HARD_INVARIANT_FAILURE`, `ALIGNMENT_AMBIGUOUS`, `TOKENIZATION_FAILURE`, `GENERATION_EARLY_EOS`, `DETECTOR_SCORE_NA`, `ZERO_VALID_OBSERVATIONS`, `CALIBRATION_MISSING`, `SOURCE_PIN_MISMATCH`, `SEALED_KEY_CONTAMINATION`, `HUMAN_FIDELITY_MATERIAL_CHANGE`, `UPSTREAM_API_CHANGED`, `EXTERNAL_INTERFACE_UNAVAILABLE`, `PROMPT_CONTAMINATED`, `TEXT_ONLY_REENCODE_MISMATCH`, `DETECTOR_CONFIG_UNSUPPORTED`, `DETECTOR_CONFIG_UNVERIFIED`, `BASELINE_TPR_BELOW_FLOOR`, `SEALED_DATA_CONTAMINATION`, `CALIBRATION_TAIL_UNDERRESOLVED`.

Every aggregate exposes counts by reason code. Null/NA fields require a reason; silent row deletion is forbidden.

# 36. First implementation tasks — exact order


1. Initialize repo/CI.  
2. Add and protect this spec.  
3. Implement source-pin schema.  
4. Pin DeepMind commit.  
5. Pin Transformers commit.  
6. Capture environment.  
7. Canonical config hashing.  
8. Adapter protocol.  
9. DeepMind adapter.  
10. DeepMind g/mask goldens.  
11. Mean/Weighted goldens.  
12. Small Bayesian fixture/checkpoint.  
13. Transformers adapter.  
14. Transformers goldens.  
15. Token alignment.  
16. Conserved runs.  
17. Observation mapping.  
18. Diff/mask decomposition.  
19. Brute-force/property tests.  
20. Protected-span extractor.  
21. Surface/contraction rules only.  
22. Candidate registry/traces.  
23. Random/left-to-right schedules.  
24. Coverage intervals.  
25. Even/cluster/greedy schedules.  
26. Tiny dev corpus.  
27. Calibrate and run E02–E11.  
28. Fix every observation/detector bug before broadening rules.  
29. Add lexical/syntax rules gradually with fidelity audit.  
30. Scale to preregistered confirmatory corpus.

This order is intentional: broad paraphrase logic before observation/calibration correctness only creates misleading data faster.

# 37. Causal estimands and analysis populations

The project must distinguish **what a transformation can do when applicable** from **what a deployable fixed policy does over arbitrary source text**. Failing to separate these estimands creates eligibility/survivorship bias.

## 37.1 Paired source-text causal unit

For transformation evaluation, the source text is the primary paired unit. Let `Y_i(0)` be detector outcome for pristine source text `i` and `Y_i(a)` the outcome after frozen policy `a`. The primary continuous effect is paired margin drop `Y_i(0)-Y_i(a)`; the primary decision effect is change in detection at a fixed pre-calibrated FPR threshold.

Generation of watermarked versus unwatermarked text is **not** treated as an exact paired counterfactual merely because the random seed is the same: watermarking changes the sampling distribution. Those corpora are matched by prompt/configuration and analyzed as controlled groups. Transformation effects, by contrast, are paired within an already-generated source text.

## 37.2 Policy-effect population (ITT analogue)

`POLICY_ALL`: apply the frozen policy to every source text. If no admissible transform exists, the output is the unchanged source text and the row is recorded as `NO_ELIGIBLE_TRANSFORM`. This answers: “What happens if this deterministic policy is deployed on arbitrary text from the benchmark distribution?”

The `POLICY_ALL` estimand is mandatory for every headline attack/robustness claim. Ineligible samples cannot disappear from the denominator.

## 37.3 Eligible-only population

`ELIGIBLE_ONLY`: analyze only source texts having at least one fidelity-admissible transform at the requested budget. This answers a different mechanistic question: “Among texts the policy can actually modify, what is its effect?”

Every report shows both `POLICY_ALL` and `ELIGIBLE_ONLY`. The eligible-only result may be stronger, but it may not be presented as universal policy effectiveness.

## 37.4 Pristine-positive conditional population

`PRISTINE_POSITIVE`: source texts detected before transformation. Report conditional loss `P(post=negative | pristine=positive)` only alongside unconditional transformed TPR. This prevents a weak pristine detector from creating an inflated “removal rate.”

## 37.5 Clustering and repeated variants

If multiple transformation budgets/schedules derive from the same source, statistical resampling MUST cluster by `source_sample_id`. If multiple generations derive from the same prompt family, confirmatory sensitivity analysis clusters by prompt family as well. Treating each transformed variant or token as independent is forbidden.

# 38. Prompt, tokenization, and boundary correctness

## 38.1 Canonical token source hierarchy

1. Original generation token IDs captured from `generate()` are canonical for the reproducible generation track.
2. Token IDs produced by the exact pinned tokenizer from decoded response text are canonical only for the text-only track.
3. Token IDs from a different tokenizer revision are a cross-tokenizer experiment, never an implementation detail.

## 38.2 Chat-template identity

A model ID is insufficient. Chat-template behavior can change token boundaries. Record tokenizer revision, serialized chat template or its content hash, special-token map, padding side, BOS/EOS policy, and prompt length after templating.

## 38.3 Boundary property tests

Required tests:

- prompt-only tokens never appear in primary detector input;
- response boundary remains exact under left padding and batching;
- special tokens are handled exactly as source detector expects;
- multi-turn templates do not shift continuation slicing;
- decoded/re-encoded text mismatch produces a separate condition rather than overwriting canonical IDs;
- Unicode normalization is not applied unless explicitly configured;
- no `.strip()`/whitespace cleanup occurs before canonical token scoring.

## 38.4 EOS semantics

EOS masks are adapter-defined. Generic code must not approximate “everything after first EOS” unless the source adapter itself does so. Tests include early EOS, no EOS, EOS-like literal text, padding equal to EOS, and batched sequences with unequal realized lengths.

# 39. Detector compatibility, priors, and score semantics

## 39.1 Compatibility matrix

Every adapter publishes a machine-readable matrix keyed by `(watermark_mode, g_distribution, depth, detector_family, implementation_revision)`.

Example status fields:

```yaml
status: SUPPORTED | UNSUPPORTED | UNVERIFIED
source: <primary source identifier>
reason: <human-readable explanation>
validated_by: [golden_test_ids]
```

Confirmatory execution fails closed on `UNVERIFIED` rather than assuming compatibility.

## 39.2 Distortionary versus non-distortionary tracks

Non-distortionary and distortionary Tournament configurations are separate experimental families. Their quality/detectability trade-offs differ, and a detector documented only for one family cannot be generalized to the other. Aggregated “SynthID robustness” tables MUST expose watermark mode as a column.

## 39.3 Posterior/prior separation

For Bayesian detectors, store:

- trained likelihood parameters/checkpoint hash;
- configured base rate/prior;
- detector-native posterior;
- likelihood-derived or log-odds diagnostic if exposed;
- calibration threshold and empirical FPR.

Do not interpret `posterior=0.9` as 90% probability of AI authorship unless the deployment prior and model are actually justified for that population. In this benchmark, posterior is a score subjected to frequentist FPR calibration.

## 39.4 Detector identity hash

`detector_identity_hash = SHA256(adapter_revision || detector_source_revision || detector_config_canonical_json || checkpoint_sha256 || tokenizer_revision || watermark_config_hash || calibration_bundle_hash)`

No table may merge rows with different detector identity hashes into one detector label without an explicit meta-analysis.

# 40. Calibration uncertainty, threshold construction, and power

## 40.1 Conservative finite-sample threshold

For score orientation where larger means more watermarked, choose a deterministic threshold from the negative calibration scores such that the observed exceedance rate under the exact comparison operator (`>` or `>=`) does not exceed target `alpha`. The operator is part of threshold metadata. Ties are not broken randomly in the confirmatory path. If ties prevent exact alpha, use the conservative achievable FPR and report it.

Never linearly interpolate a score threshold and then report an unobserved empirical FPR as if directly measured.

## 40.2 Calibration uncertainty

For every frozen threshold, report the exact binomial confidence interval for empirical FPR (Clopper–Pearson or another prespecified exact method). The target is a design goal; the achieved empirical FPR and uncertainty are observed facts.

For final headline intervals, provide two uncertainty views:

1. **Threshold-conditional:** threshold fixed to the released calibration bundle; bootstrap evaluation source samples.
2. **Calibration-propagated sensitivity:** nested resampling of negative calibration examples to rebuild the threshold, plus clustered resampling of evaluation source texts.

If these materially disagree, the report highlights calibration instability.

## 40.3 Resolution rule for rare FPRs

A 0.1% FPR claim requires enough independent negative calibration/evaluation examples to resolve tail behavior. `N=10,000` is only a bare empirical starting point (about ten expected exceedances at 0.1% if perfectly calibrated), not proof of precision. Final sample size is set by the desired confidence interval width, not by the label “10k.” Zero observed false positives are reported with an exact upper confidence bound rather than as “0% true FPR.”

## 40.4 Baseline interpretability floor

Default core-cell eligibility for an attack/robustness headline is pristine `TPR >= 0.80` at the primary 1% FPR operating point. This is a study-design interpretability floor, not a property of SynthID. A different floor may be preregistered before held-out evaluation, but never changed afterward. Cells below the floor remain scientifically useful as detector-baseline failures and are reported descriptively; they cannot support a dramatic removal-rate claim.

## 40.5 Power analysis

Final confirmatory `N` is simulation-based from development data using the actual paired/clustered design:

- resample prompt/source clusters;
- resample held-out-like keys from development/validation key pools;
- preserve pristine/transformed pairing;
- estimate power for the preregistered practical effect at the chosen multiplicity correction;
- choose `N` before sealed test access.

For generalized key claims, use at least 16 independent held-out benchmark keys and prefer 32 or more when compute permits. Balance sample weight across keys so a single weak key cannot dominate the aggregate. This minimum is a methodological requirement of this project, not a claim about provider key diversity.

# 41. Data firewall and contamination protocol

## 41.1 Physical/logical separation

Use distinct artifact roots and credentials for:

- `DETECTOR_TRAIN`
- `CALIBRATION`
- `ATTACK_DEV`
- `VALIDATION_KEYS`
- `SEALED_TEST`

A process running development transforms has no filesystem/API permission to read sealed key material or sealed result shards.

## 41.2 Seal record

Before E20, create `SEAL.json` containing hashes of test prompt manifest, test-key encrypted bundle, transform ruleset, scheduler code/config, detector checkpoints, threshold bundles, statistical plan, and spec revision. Sign or content-hash the seal. The confirmatory runner verifies all hashes before revealing test material.

## 41.3 Access log

Every sealed-data read writes an append-only audit event with run ID, actor/process identity, timestamp, artifact hash, and purpose. Unexpected pre-run access yields `SEALED_DATA_CONTAMINATION` and invalidates the claim.

## 41.4 Bug-after-unseal policy

If a bug discovered after unsealing could have influenced transform policy, thresholds, sample inclusion, or interpretation:

1. mark the run `CONTAMINATED`;
2. preserve all artifacts;
3. fix the bug with a regression test;
4. create new held-out keys and, when outcome information could influence text policy, a new test corpus partition;
5. preregister a replacement run.

Do not patch the result in place.

# 42. Cross-implementation conformance matrix

The project maintains an explicit matrix rather than calling both tracks “SynthID” and assuming equivalence.

Required rows include:

- g-value generation primitive;
- watermark configuration fields;
- context-history handling;
- repeated-context behavior;
- first-ngram handling;
- sampling-table use;
- generation score update/tournament realization;
- EOS mask behavior;
- detector families available;
- Bayesian compatibility limitations;
- tokenizer/model integration path;
- prompt-removal responsibility;
- device/dtype sensitivities found in reproduction;
- upstream tests copied/reproduced;
- upstream license.

Each cell has `SAME`, `DIFFERENT`, `NOT_APPLICABLE`, or `UNVERIFIED`, plus source evidence. A cross-adapter result is claim-eligible only after all mechanism fields that affect the tested outcome are either reproduced or explicitly isolated as differences.

# 43. Kill criteria and branch-stop rules

The project is not allowed to keep polishing a hypothesis after its core evidence fails.

## 43.1 Avalanche branch

Killed permanently unless a new implementation with genuinely unbounded history is introduced. Finite sliding-context SynthID experiments use explicit observation alignment.

## 43.2 “Mean-only break” branch

If a transformation degrades Mean but not calibrated Bayesian detection, report a simple-detector weakness and stop calling it a general SynthID break. Further work may study detector disagreement, not relabel the result.

## 43.3 Coverage-greedy novelty branch

If `COVERAGE_GREEDY_KEY_BLIND` does not improve realized observation replacement per edit over matched random/even baselines on validation and held-out keys, kill the claim that topology-aware scheduling is a useful optimizer. Keep the observation-analysis tooling.

## 43.4 Fidelity branch

If the upper confidence bound on material semantic-change rate violates the preregistered fidelity limit, that transform family is ineligible for headline results until the rule set changes and is re-audited on fresh samples.

## 43.5 Baseline detector branch

If pristine detector power is below the preregistered interpretability floor, stop reporting “removal success” for that cell. Diagnose configuration, length, training, and calibration or classify the detector baseline as weak.

## 43.6 Cross-key branch

If effect direction is highly heterogeneous and the aggregate is carried by a minority of keys, downgrade from general structural weakness to key-heterogeneous effect. Do not average the heterogeneity away.

## 43.7 Proprietary-transfer branch

Without a primary provider specification or documented detector interface, no engineering effort is spent guessing proprietary parameters. The open benchmark remains complete without this branch.

# 44. Publication-grade evidence ladder

Use the highest level whose gates all pass:

- **L0 MECHANISM REPRODUCTION:** source conformance only.
- **L1 OBSERVATION EFFECT:** deterministic edits measurably replace/mask observations.
- **L2 CALIBRATED DETECTOR EFFECT:** detector degradation at frozen FPR with negative controls.
- **L3 HELD-OUT KEY STRUCTURAL EFFECT:** L2 plus sealed key-blind transfer.
- **L4 MODEL/TOKENIZER GENERALIZATION:** L3 plus at least two open model/tokenizer families.
- **L5 OPEN-IMPLEMENTATION GENERALIZATION:** L4 plus both pinned SynthID implementation tracks and compatible strong detectors.
- **L6 EXTERNAL OBSERVED TRANSFER:** L5 plus preregistered one-shot evaluation through an official proprietary detector interface. L6 still describes external observed behavior only; it does not reveal the proprietary mechanism.

A paper title/abstract cannot use a stronger scope than the achieved level. “Breaks SynthID” is disallowed unless the exact scope and detector family are stated. “Breaks Claude” is disallowed without L6 evidence specific to Claude and provider-authorized/official detection semantics.

# 45. Final frozen plan


1. Pin and reproduce two open SynthID implementation tracks.  
2. Build a detector/configuration compatibility matrix and reject unsupported combinations.  
3. Preserve exact prompt/continuation/tokenizer boundaries and create a separate text-only re-encoding track.  
4. Train detectors where required and calibrate fixed-FPR thresholds before robustness evaluation.  
5. Quantify calibration uncertainty and enforce the pristine-baseline interpretability floor.  
6. Build exact token/observation alignment and reject avalanche shortcuts.  
7. Build deterministic no-AI transformations with hard protected spans and auditable traces.  
8. Define both `POLICY_ALL` and `ELIGIBLE_ONLY` estimands so transform eligibility cannot create survivorship bias.  
9. Compare matched random/clustered/even/coverage-aware key-blind schedules.  
10. Analyze realized observation replacement, mask changes, and per-depth g drift rather than edit counts alone.  
11. Evaluate every compatible Mean, Weighted Mean and Bayesian detector at frozen FPR operating points.  
12. Seal held-out keys/test corpus behind a logged data firewall.  
13. Test length/domain/model/tokenizer/adapter transfer and key-level heterogeneity.  
14. Audit transformed negatives and human controls for detector distribution shift.  
15. Run blinded human semantic-fidelity review with hard invariant gates.  
16. Preregister, execute the confirmatory run once, and invalidate rather than patch contaminated runs.  
17. Independently rerun from a clean environment with fresh generation seeds.  
18. Publish Pareto frontiers, calibration uncertainty, eligibility, heterogeneity, nulls, failures, and hashes.  
19. Apply kill criteria when a hypothesis fails instead of endlessly tuning it.  
20. Treat proprietary validation as separate opaque evidence only, controlled by current primary provider documentation.

The final scientific question is: **How does controlled textual change alter the topology and statistical content of valid watermark observations, and how much fidelity-preserving change is required before calibrated detector power materially degrades?**



## 45.1 Revision-2 primary verification notes

Revision 2 was hardened against the following primary-source facts at the freeze date:

- Nature 2024 describes SynthID-Text as a generation-time sampling watermark and reports production use in Gemini/Gemini Advanced; this does not disclose current provider secret keys.
- Current Hugging Face Transformers documentation/source exposes `SynthIDTextWatermarkingConfig`, sampling-table parameters, a SynthID logits processor, and Bayesian detector classes.
- The pinned Transformers Bayesian source states compatibility with non-distortionary Tournament watermarking using Bernoulli(0.5) g-values and includes a configurable `base_rate` prior.
- The pinned Transformers SynthID detector constructs EOS and context-repetition masks and computes g-values from supplied token IDs; prompt/continuation slicing is therefore an input-provenance responsibility of this harness.
- The Anthropic Transparency Hub source checked on 2026-08-15 does not provide a Claude text-watermark technical specification; this spec therefore keeps Claude mechanism/deployment details UNKNOWN rather than importing secondary claims.

These are source-status statements, not experimental outcomes.

# Appendix A. Deterministic test matrix

Every case below becomes a named automated fixture. These are not filler: they define boundary behavior needed to prevent false watermark-damage measurements.

### A.0 Common fixture contract

Each named fixture is the smallest deterministic input isolating the stated case. It records fixture text/token IDs and configuration hash; asserts deterministic replay, valid shapes, explicit reason code, stable hashes, no silent normalization, and the named subsystem invariant; and compares to pinned upstream behavior whenever watermark internals are involved. Any fixture that discovers a bug is preserved as a permanent minimized regression case rather than deleted after the fix.

## T001 — Alignment: identical 1-token

**Fixture focus:** `Alignment` subsystem; isolate `identical 1-token`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T002 — Alignment: identical 256-token

**Fixture focus:** `Alignment` subsystem; isolate `identical 256-token`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T003 — Alignment: substitution first

**Fixture focus:** `Alignment` subsystem; isolate `substitution first`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T004 — Alignment: substitution middle

**Fixture focus:** `Alignment` subsystem; isolate `substitution middle`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T005 — Alignment: substitution last

**Fixture focus:** `Alignment` subsystem; isolate `substitution last`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T006 — Alignment: two adjacent substitutions

**Fixture focus:** `Alignment` subsystem; isolate `two adjacent substitutions`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T007 — Alignment: two distant substitutions

**Fixture focus:** `Alignment` subsystem; isolate `two distant substitutions`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T008 — Alignment: insertion first

**Fixture focus:** `Alignment` subsystem; isolate `insertion first`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T009 — Alignment: insertion middle

**Fixture focus:** `Alignment` subsystem; isolate `insertion middle`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T010 — Alignment: insertion last

**Fixture focus:** `Alignment` subsystem; isolate `insertion last`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T011 — Alignment: deletion first

**Fixture focus:** `Alignment` subsystem; isolate `deletion first`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T012 — Alignment: deletion middle

**Fixture focus:** `Alignment` subsystem; isolate `deletion middle`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T013 — Alignment: deletion last

**Fixture focus:** `Alignment` subsystem; isolate `deletion last`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T014 — Alignment: insert then exact suffix

**Fixture focus:** `Alignment` subsystem; isolate `insert then exact suffix`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T015 — Alignment: delete then exact suffix

**Fixture focus:** `Alignment` subsystem; isolate `delete then exact suffix`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T016 — Alignment: repeated token tie

**Fixture focus:** `Alignment` subsystem; isolate `repeated token tie`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T017 — Alignment: alternating repeated tokens

**Fixture focus:** `Alignment` subsystem; isolate `alternating repeated tokens`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T018 — Alignment: empty to nonempty

**Fixture focus:** `Alignment` subsystem; isolate `empty to nonempty`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T019 — Alignment: nonempty to empty

**Fixture focus:** `Alignment` subsystem; isolate `nonempty to empty`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T020 — Alignment: complete substitution

**Fixture focus:** `Alignment` subsystem; isolate `complete substitution`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T021 — Observations: n=2 edit first

**Fixture focus:** `Observations` subsystem; isolate `n=2 edit first`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T022 — Observations: n=3 edit middle

**Fixture focus:** `Observations` subsystem; isolate `n=3 edit middle`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T023 — Observations: n=5 edit middle

**Fixture focus:** `Observations` subsystem; isolate `n=5 edit middle`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T024 — Observations: n=5 edit near beginning

**Fixture focus:** `Observations` subsystem; isolate `n=5 edit near beginning`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T025 — Observations: n=5 edit near end

**Fixture focus:** `Observations` subsystem; isolate `n=5 edit near end`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T026 — Observations: two edits overlapping windows

**Fixture focus:** `Observations` subsystem; isolate `two edits overlapping windows`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T027 — Observations: two edits disjoint windows

**Fixture focus:** `Observations` subsystem; isolate `two edits disjoint windows`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T028 — Observations: mask-only synthetic change

**Fixture focus:** `Observations` subsystem; isolate `mask-only synthetic change`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T029 — Observations: replaced but coincident g-vector

**Fixture focus:** `Observations` subsystem; isolate `replaced but coincident g-vector`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T030 — Observations: zero valid observations

**Fixture focus:** `Observations` subsystem; isolate `zero valid observations`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T031 — Observations: one valid observation

**Fixture focus:** `Observations` subsystem; isolate `one valid observation`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T032 — Observations: repeated context newly created

**Fixture focus:** `Observations` subsystem; isolate `repeated context newly created`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T033 — Observations: repeated context removed

**Fixture focus:** `Observations` subsystem; isolate `repeated context removed`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T034 — Observations: early EOS

**Fixture focus:** `Observations` subsystem; isolate `early EOS`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T035 — Observations: all suffix conserved after resync

**Fixture focus:** `Observations` subsystem; isolate `all suffix conserved after resync`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T036 — Protected spans: URL trailing period

**Fixture focus:** `Protected spans` subsystem; isolate `URL trailing period`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T037 — Protected spans: URL query parameters

**Fixture focus:** `Protected spans` subsystem; isolate `URL query parameters`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T038 — Protected spans: email parentheses

**Fixture focus:** `Protected spans` subsystem; isolate `email parentheses`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T039 — Protected spans: IPv4

**Fixture focus:** `Protected spans` subsystem; isolate `IPv4`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T040 — Protected spans: IPv6

**Fixture focus:** `Protected spans` subsystem; isolate `IPv6`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T041 — Protected spans: negative integer

**Fixture focus:** `Protected spans` subsystem; isolate `negative integer`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T042 — Protected spans: decimal

**Fixture focus:** `Protected spans` subsystem; isolate `decimal`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T043 — Protected spans: currency

**Fixture focus:** `Protected spans` subsystem; isolate `currency`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T044 — Protected spans: percentage

**Fixture focus:** `Protected spans` subsystem; isolate `percentage`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T045 — Protected spans: ISO date

**Fixture focus:** `Protected spans` subsystem; isolate `ISO date`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T046 — Protected spans: inline code

**Fixture focus:** `Protected spans` subsystem; isolate `inline code`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T047 — Protected spans: fenced Python

**Fixture focus:** `Protected spans` subsystem; isolate `fenced Python`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T048 — Protected spans: fenced JSON

**Fixture focus:** `Protected spans` subsystem; isolate `fenced JSON`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T049 — Protected spans: Markdown destination

**Fixture focus:** `Protected spans` subsystem; isolate `Markdown destination`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T050 — Protected spans: quoted sentence

**Fixture focus:** `Protected spans` subsystem; isolate `quoted sentence`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T051 — Protected spans: POSIX path

**Fixture focus:** `Protected spans` subsystem; isolate `POSIX path`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T052 — Protected spans: Windows path

**Fixture focus:** `Protected spans` subsystem; isolate `Windows path`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T053 — Protected spans: CLI flag

**Fixture focus:** `Protected spans` subsystem; isolate `CLI flag`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T054 — Protected spans: citation marker

**Fixture focus:** `Protected spans` subsystem; isolate `citation marker`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T055 — Protected spans: math expression

**Fixture focus:** `Protected spans` subsystem; isolate `math expression`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T056 — Transforms: no candidate

**Fixture focus:** `Transforms` subsystem; isolate `no candidate`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T057 — Transforms: one contraction

**Fixture focus:** `Transforms` subsystem; isolate `one contraction`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T058 — Transforms: two nonoverlap contractions

**Fixture focus:** `Transforms` subsystem; isolate `two nonoverlap contractions`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T059 — Transforms: overlapping lexical candidates

**Fixture focus:** `Transforms` subsystem; isolate `overlapping lexical candidates`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T060 — Transforms: all-caps block

**Fixture focus:** `Transforms` subsystem; isolate `all-caps block`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T061 — Transforms: Unicode apostrophe

**Fixture focus:** `Transforms` subsystem; isolate `Unicode apostrophe`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T062 — Transforms: sentence start casing

**Fixture focus:** `Transforms` subsystem; isolate `sentence start casing`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T063 — Transforms: newline boundary

**Fixture focus:** `Transforms` subsystem; isolate `newline boundary`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T064 — Transforms: Markdown bullet

**Fixture focus:** `Transforms` subsystem; isolate `Markdown bullet`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T065 — Transforms: numbered list

**Fixture focus:** `Transforms` subsystem; isolate `numbered list`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T066 — Transforms: budget exact

**Fixture focus:** `Transforms` subsystem; isolate `budget exact`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T067 — Transforms: budget one over

**Fixture focus:** `Transforms` subsystem; isolate `budget one over`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T068 — Transforms: rollback last op

**Fixture focus:** `Transforms` subsystem; isolate `rollback last op`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T069 — Transforms: stable random replay

**Fixture focus:** `Transforms` subsystem; isolate `stable random replay`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T070 — Transforms: stable greedy tie

**Fixture focus:** `Transforms` subsystem; isolate `stable greedy tie`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T071 — Transforms: candidate conflict graph

**Fixture focus:** `Transforms` subsystem; isolate `candidate conflict graph`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T072 — Transforms: protected conflict

**Fixture focus:** `Transforms` subsystem; isolate `protected conflict`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T073 — Transforms: lexical negative context

**Fixture focus:** `Transforms` subsystem; isolate `lexical negative context`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T074 — Transforms: syntax precondition fail

**Fixture focus:** `Transforms` subsystem; isolate `syntax precondition fail`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T075 — Transforms: reapply idempotence

**Fixture focus:** `Transforms` subsystem; isolate `reapply idempotence`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T076 — Detectors: all-zero g

**Fixture focus:** `Detectors` subsystem; isolate `all-zero g`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T077 — Detectors: all-one g

**Fixture focus:** `Detectors` subsystem; isolate `all-one g`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T078 — Detectors: alternating g

**Fixture focus:** `Detectors` subsystem; isolate `alternating g`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T079 — Detectors: mixed depth vectors

**Fixture focus:** `Detectors` subsystem; isolate `mixed depth vectors`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T080 — Detectors: depth=1

**Fixture focus:** `Detectors` subsystem; isolate `depth=1`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T081 — Detectors: depth=2

**Fixture focus:** `Detectors` subsystem; isolate `depth=2`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T082 — Detectors: depth=30

**Fixture focus:** `Detectors` subsystem; isolate `depth=30`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T083 — Detectors: single valid mask

**Fixture focus:** `Detectors` subsystem; isolate `single valid mask`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T084 — Detectors: mixed mask

**Fixture focus:** `Detectors` subsystem; isolate `mixed mask`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T085 — Detectors: zero mask error

**Fixture focus:** `Detectors` subsystem; isolate `zero mask error`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T086 — Detectors: long repetition mask

**Fixture focus:** `Detectors` subsystem; isolate `long repetition mask`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T087 — Detectors: EOS mask

**Fixture focus:** `Detectors` subsystem; isolate `EOS mask`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T088 — Detectors: threshold exact tie

**Fixture focus:** `Detectors` subsystem; isolate `threshold exact tie`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T089 — Detectors: score just below threshold

**Fixture focus:** `Detectors` subsystem; isolate `score just below threshold`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T090 — Detectors: score just above threshold

**Fixture focus:** `Detectors` subsystem; isolate `score just above threshold`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T091 — Detectors: negative calibration quantile

**Fixture focus:** `Detectors` subsystem; isolate `negative calibration quantile`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T092 — Detectors: paired margin drop

**Fixture focus:** `Detectors` subsystem; isolate `paired margin drop`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T093 — Detectors: key-stratified aggregation

**Fixture focus:** `Detectors` subsystem; isolate `key-stratified aggregation`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T094 — Detectors: length-stratified aggregation

**Fixture focus:** `Detectors` subsystem; isolate `length-stratified aggregation`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

## T095 — Detectors: label permutation Bayesian sanity

**Fixture focus:** `Detectors` subsystem; isolate `label permutation Bayesian sanity`. Apply §A.0. The expected state transition/mapping must be asserted explicitly in the test, not inferred from a snapshot name.

# Appendix B. Result field contracts

Confirmatory rows missing required groups are invalid unless a nullable field has a machine-readable reason code.

### B.0 Common schema rule

Required fields hard-fail validation unless explicitly nullable; every null has a reason code. Large/sensitive content may be referenced by SHA-256 plus artifact locator, with redistribution status documented. Scientifically meaningful values are never inferred later from filenames.

## RF01 — `identity`

**Required:** run_id, experiment_id, condition_id, sample_id, pair_id.  
**Purpose:** joins/provenance.

**Validation:** §B.0.

## RF02 — `source`

**Required:** adapter_id, source_commit, adapter_config_hash.  
**Purpose:** implementation identity.

**Validation:** §B.0.

## RF03 — `model`

**Required:** model_id, model_revision, tokenizer_id, tokenizer_revision.  
**Purpose:** generation/tokenization identity.

**Validation:** §B.0.

## RF04 — `watermark`

**Required:** watermark_config_hash, key_split, key_id.  
**Purpose:** benchmark watermark identity.

**Validation:** §B.0.

## RF05 — `generation`

**Required:** seed, temperature, top_k, top_p, realized length.  
**Purpose:** matched sampling.

**Validation:** §B.0.

## RF06 — `text`

**Required:** input/output hashes, char/word/token counts.  
**Purpose:** content integrity.

**Validation:** §B.0.

## RF07 — `transform`

**Required:** ruleset hash, schedule, budget, operation trace.  
**Purpose:** perturbation provenance.

**Validation:** §B.0.

## RF08 — `fidelity`

**Required:** hard pass, reason codes, edit metrics, human status.  
**Purpose:** quality gate.

**Validation:** §B.0.

## RF09 — `alignment`

**Required:** algorithm version, edit-script hash, ambiguity count.  
**Purpose:** mapping integrity.

**Validation:** §B.0.

## RF10 — `observation`

**Required:** valid/preserved/replaced/dropped/added/mask counts.  
**Purpose:** mechanism accounting.

**Validation:** §B.0.

## RF11 — `gvalues`

**Required:** depth, per-depth summaries, matched Hamming.  
**Purpose:** signal accounting.

**Validation:** §B.0.

## RF12 — `detector`

**Required:** detector/checkpoint, threshold, FPR, raw score, margin, decision.  
**Purpose:** detection semantics.

**Validation:** §B.0.

## RF13 — `statistics`

**Required:** stratum, bootstrap group, hypothesis class.  
**Purpose:** inference.

**Validation:** §B.0.

## RF14 — `audit`

**Required:** worker version, timestamp, artifact hashes.  
**Purpose:** reproduction.

**Validation:** §B.0.

# Appendix C. Code review invariants


Reject a PR if generic observation code imports an implementation hash directly; T1 scheduler receives g/detector fields; threshold is a source-code magic number; corpus lacks immutable model revision; aggregation silently drops failed transforms; semantic rule lacks negative-context tests; protected spans are detected only after editing; RNG is global/unrecorded; plotting recomputes thresholds; fidelity sample selection depends on attack success; a unit test asserts a guessed proprietary parameter; raw results are overwritten in place.

Every experiment-logic review answers:

1. What hypothesis does this change enable?
2. Does it change the estimand?
3. Does it touch sealed data?
4. Does it alter calibration?
5. Does it add neural/AI decision dependencies?
6. Can it cause semantic drift?
7. Are failure rows preserved?
8. Do hashes/versions remain sufficient to reproduce behavior?

# Appendix D. Date-sensitive proprietary-source rule


This specification is frozen 2026-08-15. Product deployments can change. Before any current-provider claim, re-check primary provider documentation, record retrieval date, separate rollout status from algorithm details, and never rewrite historical open-source results as current production facts.

At the revision-2 freeze, the Anthropic Transparency Hub page checked by this project does not publish a Claude text-watermark mechanism and describes Anthropic as continuing to explore watermarking developments. Therefore this spec does **not** assert that Claude currently uses a particular text watermark. If a later primary Anthropic source announces deployment, record its exact date and scope and update only the provider-status record; do not back-propagate SynthID implementation assumptions into Claude.

Current-provider status records expire after 30 days for publication wording and must be refreshed. Mechanism claims require primary technical disclosure, not merely a product announcement. Secondary reporting can motivate a primary-source check but cannot establish secret configuration.

