# Cycle 8 replication detector evidence (seed 900000)

Development replication after freezing U+034F space-carrier x1 from seed `890000`. Not confirmation. Topic: `invisible carrier replication`.

Same detector-blind arms. No retune.

Headline (4 watermarked + 4 unwatermarked):

| Arm | WM detected raw | UW detected raw | WM detected after Cf-strip |
| --- | ---: | ---: | ---: |
| identity | 4/4 | 0/4 | 4/4 |
| U+034F x1 | 0/4 | 0/4 | 0/4 |
| U+034F x8 | 0/4 | 0/4 | 0/4 |
| U+200C x1 | 0/4 | 0/4 | 4/4 |

Visible projection pass rate: `32/32`.

U+034F x8 overflowed the GPT-2 1024-token context on one technical-explanation sample (1055 tokens). Prefer x1. x8 scores on that row are not a clean observation.

Do not promote U+034F into the product CLI.
