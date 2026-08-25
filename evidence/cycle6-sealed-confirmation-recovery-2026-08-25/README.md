# Cycle 6 sealed confirmation — recovered formal result

These files freeze the first completed Cycle 6 v2 effectiveness confirmation.

They are **spent confirmation data**. Do not use them as a development or tuning set.

## Formal outcome

**NONZERO_RESIDUAL**

This is not 0/192. It is not INVALID_CONTROL.

Human fidelity was not evaluated. `human_fidelity_claim_authorized` remains false.

## Provenance

| Binding | Value |
| --- | --- |
| Frozen scientific commit | `bfd9a4d81f0561a17f5ac4daa3858e97ebd811f1` |
| Orchestration / recovery commit | `1e86be770ae231046055647689a4836d221d8274` |
| Source freeze workflow | Cycle6 Sealed Confirmation #16, run `32873260399` |
| Recovery workflow | Cycle6 Frozen Artifact Recovery #1, run `32886342498` |
| v2 contract hash | `8bff80151c1be33a9f4bedf0b00abab1fffd9b04c0572aef1381be58530e1cef` |
| Cross-check artifact hash | `8a65367d6aebecd26028150a58722c69cd47deb55df15e7dca24a56366306207` |
| Aggregate artifact hash | `30577aafaffd0c50f0ddb384a4509eb0bb93e4374bf39704869ddbf5053186a4` |
| Recovery manifest hash | `d0639498103b2322576c99108d00a3eed7a6d99f317491fab558e6b49055ff99` |

Recovered freeze artifacts (unmodified; generated before any detector scoring):

| Seed | GitHub artifact ID | Artifact digest |
| --- | --- | --- |
| 760000 | `9573956498` | `sha256:79ee80808758d2ee143b4a41dc7e0104d9261d4873e7af37cac8a6ba2e5925d3` |
| 770000 | `9573829301` | `sha256:c75717dc3538abadbd33997b883c5f15e0bc15e155b2be5eab870ccb82aa5807` |
| 780000 | `9573952748` | `sha256:2900ed5f61057b7fff5f1e42b855a11322441fb1e53fd48da39ad9fff1482821` |

Corpus / plan hashes were unchanged from the local run-16 cross-check that used orchestration commit `bfd9a4d`:

| Seed | Corpus artifact hash | Plan hash | Score evidence hash |
| --- | --- | --- | --- |
| 760000 | `d507802fec23d8f4b9ad0a4250131800d2baa3e4f85fa070c8678f50d598bb32` | `706483a4229af16ba07fd6d18c9ee3da00ff9ee1b321dd1d0dbefb54416c28a4` | `23c675ce87d5d52693f590bd8352d9d25e19f1ce8804bc9a38be8a61d90f0aac` |
| 770000 | `2a24b04cead31427cd175e957f441b80b6e7c3febb9e6e08d2f4b78daab5f567` | `b534c4c96df7688967573c41a55e222d023790672c99c6e09f3c9f221581c871` | `48fe588b72ce66b6439d368d707bec7e0a2b57f0e907f3135f91caff0ce0592f` |
| 780000 | `5ee089d76fd61c31081a3085c85f2cef93c64b5f9e8452bce92ad630672c2c79` | `8915dfc129fe3b8d144f9e48dbf20da6bd8190179ec8cc009576afb017546415` | `52e021a7d81faa78746d65fe4832d8986fd0220a2675f844c8804538b7f6f460` |

GitHub recovery artifacts:

| Name | Artifact ID | Digest |
| --- | --- | --- |
| `cycle6-recovery-formal-bundle` | `9577810822` | `sha256:5c8a748eef21e7a892eee21b59cbad745fe71887f6f4e5250e0b223063df6cb3` |
| `cycle6-recovery-confirmation-aggregate` | `9577800471` | `sha256:66fea2807319979d30611bdff908db9aef5bea8316a9f4ccf5c90e157e0f9f30` |
| `cycle6-recovery-freeze-cross-check` | `9577726314` | `sha256:279973d5da80ebbef0aac24807a327826e830929c628b9cbae12aa00fa93ed94` |

The v2 contract file was not rewritten after seeing scores. The preregistered contract hash above is the measurement identity of this result.

## Counts

Sanitizer arms: `raw`, `nfkc`, `cf_strip`, `nfkc_cf_strip`.

| Corpus | Pristine WM detected | Transformed WM detected (all arms) | Transformed UW detected | Transformed WM mean score |
| --- | --- | --- | --- | --- |
| 760000 | 61/64 | 2/64 | 0/64 | 0.5142216742112525 |
| 770000 | 61/64 | 2/64 | 0/64 | 0.5178186502122408 |
| 780000 | 61/64 | 3/64 | 0/64 | 0.5243260826512628 |
| Pooled | valid (`>= 60` per corpus) | **7/192** | 0/192 | — |

Threshold remains `0.5570987654320988`, comparison `>=`, GPT-2 revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. Residual scores are identical across the four sanitizer arms.

## Residual inventory (forensic only)

These confirmation rows are spent. Do not retune Cycle 6 on them.

| Seed | Sample ID | Domain | Score | Budget exhausted | Ops | Intact windows | Tuple-leak windows | Closure-free |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 760000 | `tiny-dev-attack_development-conversational_prose-30-watermarked` | conversational_prose | 0.5576713076713077 | true | 14 | 14 | 14 | false |
| 760000 | `tiny-dev-attack_development-structured_instructional-26-watermarked` | structured_instructional | 0.5752952055768956 | true | 14 | 11 | 11 | false |
| 770000 | `tiny-dev-attack_development-conversational_prose-33-watermarked` | conversational_prose | 0.5572254806125774 | true | 14 | 4 | 7 | false |
| 770000 | `tiny-dev-attack_development-structured_instructional-28-watermarked` | structured_instructional | 0.5622513008876645 | true | 14 | 6 | 9 | false |
| 780000 | `tiny-dev-attack_development-conversational_prose-34-watermarked` | conversational_prose | 0.5590021840021839 | true | 14 | 9 | 9 | false |
| 780000 | `tiny-dev-attack_development-general_explanatory-26-watermarked` | general_explanatory | 0.5576599326599326 | false | 7 | 0 | 4 | false |
| 780000 | `tiny-dev-attack_development-general_explanatory-31-watermarked` | general_explanatory | 0.5697515697515697 | true | 14 | 11 | 11 | false |

### Claim labels

- **VERIFIED:** pooled transformed-watermarked detection 7/192 under the frozen detector/threshold/sanitizers; matched unwatermarked 0/192; pristine controls 61/64 per corpus.
- **SOURCE-BOUND:** residual geometry above is from the frozen plans bound to commit `bfd9a4d` and the scored evidence artifacts listed here.
- **HYPOTHESIS:** 6/7 residuals look like B14 budget exhaustion with leftover leak windows; 1/7 used only 7 operations and still leaked tuples. This is not a license to raise the budget on these rows.
- **REJECTED:** ZERO_RESIDUAL, human-fidelity validation, universal watermark removal, proprietary-detector transfer.
- **UNKNOWN:** whether a whitespace-collapse-resistant, detector-blind transform family can clear a *new* confirmation corpus.

Development 0/16 results on seeds 720000/730000 remain development-only. They are not this formal result.

## Next cycle constraint

Cycle 7 must use a new development seed ledger. These 760000/770000/780000 corpora and their residual rows are confirmation-spent.
