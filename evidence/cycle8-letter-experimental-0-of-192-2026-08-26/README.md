# Cycle 8 letter-x1 experimental 0/192

Development-only tally. Not confirmation. Not a freeze. Letter-x1 is not in `release_transform_registry()`. Public CLI remains empty.

This directory does not re-score the detector. It records that three already-scored 64-pair letter-x1 artifacts are each 0 raw transformed WM.

## Composition

| Corpus | Kind | Pairs | Letter-x1 raw WM | Artifact hash |
| --- | --- | ---: | ---: | --- |
| `930000` n=64 | seen diagnostic rescore | 64 | 0 | `bc440e8a8ffce27b4b759e0ebe46ba8bfc2b88fce896c8100add69ce56a5c89b` |
| `940000` n=64 | seen diagnostic rescore | 64 | 0 | `e61ae665b82936b64a6996463c5c90baf3cd0c921e49886d4896346edcc3d9f9` |
| `970000` n=64 | independent, reserved before generation | 64 | 0 | `6e3c67efc4ece996d8dd8389b26614746ed6488b5f0f466c7a8157ef5af38c1b` |
| **Total** | **128 seen + 64 independent** | **192** | **0** | see `tally.json` |

128 of 192 pairs are diagnostic rescored of seen corpora used while developing letter-x1 (especially the frozen space-x1 residual on `930000`). 64 of 192 are independent seed `970000`. Seed `960000` letter diagnostic 0/16 is extra and is not counted in this 192.

Frozen space-x1 facts remain: `930000` n=64 **1/64**, `940000` n=64 **0/64** (combined **1/128**), `960000` n=16 **1/16**. Do not rewrite those as zero.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
