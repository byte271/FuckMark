# Cycle 8 validation detector evidence (seed 910000)

Held-out validation after freezing U+034F space-carrier x1. Not confirmation. Topic: `invisible carrier validation`. No retune.

Headline (4 watermarked + 4 unwatermarked):

| Arm | WM detected raw | UW detected raw | WM detected after Cf-strip |
| --- | ---: | ---: | ---: |
| identity | 3/4 | 0/4 | 3/4 |
| U+034F x1 | 0/4 | 0/4 | 0/4 |
| U+034F x8 | 0/4 | 0/4 | 0/4 |
| U+200C x1 | 0/4 | 0/4 | 3/4 |

Visible projection pass rate: `32/32`.

Do not promote U+034F into `release_transform_registry()`. Do not inspect confirmation-reserved seeds.
