from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean
import json
import unicodedata

from .benchmark import fixtures
from .engine import reconstruct_frames
from .planner import DEFAULT_VIEWS, reference, residual_counts, objective


def run(samples=128):
    from fuckmark.cli import process_text
    from fuckmark.product.visible_projection import project_visible_v1
    restored = unchanged = 0
    before = []
    after = []
    for _, segments, budget in fixtures(samples):
        source = ' '.join(segments)
        legacy = process_text(source)
        cleaned_legacy = project_visible_v1(legacy)
        restored += cleaned_legacy == source
        current = reconstruct_frames(segments, budget=budget)
        cleaned_current = project_visible_v1(unicodedata.normalize('NFKC', current.text))
        unchanged += cleaned_current == current.text
        refs, sizes = reference(source, DEFAULT_VIEWS)
        before.append(float(objective(residual_counts(cleaned_legacy, refs, DEFAULT_VIEWS), sizes, 0, ())[0]))
        after.append(float(objective(residual_counts(cleaned_current, refs, DEFAULT_VIEWS), sizes, 0, ())[0]))
    return {
        'samples': samples,
        'control': 'exact deletion of the known legacy FuckMark carriers, not an arbitrary real-world detector preprocessing chain',
        'legacy_source_restored': restored,
        'new_plain_text_survives_nfkc_and_known_carrier_deletion': unchanged,
        'legacy_mean_worst_source_window_retention_after_inverse': mean(before),
        'new_mean_worst_source_window_retention_after_inverse': mean(after),
        'watermark_detector_run': False,
        'watermark_removal_verified': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
