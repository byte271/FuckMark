from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.ledger import CYCLE8_EXPLORATORY_SEED_BASE
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.corpus.schema import WatermarkLabel
from fuckmark.experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from fuckmark.hashing import sha256_text
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters

H16_EXPLORATORY_VERSION = "cycle8-h16-real-sanitizer-exploratory-v1"

VARIANTS = (
    ("raw", lambda text: text),
    ("nfkc", nfkc_normalize),
    ("cf_strip", strip_unicode_format_characters),
    ("lm_watermarking_unicode_sanitizer", lm_watermarking_unicode_sanitizer),
    ("required_bundle", apply_required_sanitizer_bundle),
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="h16-real-sanitizer-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, default=CYCLE8_EXPLORATORY_SEED_BASE)
    parser.add_argument("--pair-count", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=64)
    parser.add_argument("--out", type=Path, default=Path("evidence/h16-local/real-sanitizer-detector.json"))
    arguments = parser.parse_args()

    from fuckmark.cycle7_stage_a_hf import _adapter_and_tokenizer, _score_text
    from fuckmark.cycle8_hf import _generate_cycle8_samples

    backend, tokenizer, adapter, _identity_hash, eos = _adapter_and_tokenizer(arguments.device)
    samples = _generate_cycle8_samples(
        backend,
        arguments.seed_base,
        arguments.max_attempts,
        pair_count=arguments.pair_count,
    )

    rows = []
    for sample in samples:
        source = str(sample["text"])
        mixed = apply_letter_alternating_mix(source)
        pristine = _score_text(f"{sample['sample_id']}-pristine", source, tokenizer, adapter, eos)
        variants = {}
        for variant_id, function in VARIANTS:
            cleaned = function(mixed)
            score = _score_text(
                f"{sample['sample_id']}-mix-{variant_id}", cleaned, tokenizer, adapter, eos
            )
            variants[variant_id] = {
                "score": score,
                "detected": score >= CYCLE6_THRESHOLD,
                "restores_source": cleaned == source,
                "text_hash": sha256_text(cleaned),
            }
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "pristine_score": pristine,
                "pristine_detected": pristine >= CYCLE6_THRESHOLD,
                "variants": variants,
            }
        )

    watermarked = [row for row in rows if row["label"] == WatermarkLabel.WATERMARKED.value]
    unwatermarked = [row for row in rows if row["label"] == WatermarkLabel.UNWATERMARKED.value]
    summary = {
        "watermarked_rows": len(watermarked),
        "unwatermarked_rows": len(unwatermarked),
        "pristine_watermarked_detected": sum(bool(row["pristine_detected"]) for row in watermarked),
        "pristine_unwatermarked_detected": sum(bool(row["pristine_detected"]) for row in unwatermarked),
    }
    for variant_id, _ in VARIANTS:
        summary[f"{variant_id}_watermarked_detected"] = sum(
            bool(row["variants"][variant_id]["detected"]) for row in watermarked
        )
        summary[f"{variant_id}_restores_source"] = sum(
            bool(row["variants"][variant_id]["restores_source"]) for row in rows
        )

    payload = {
        "algorithm_version": H16_EXPLORATORY_VERSION,
        "role": "exploratory_only_not_confirmation",
        "seed_base": arguments.seed_base,
        "pair_count": arguments.pair_count,
        "threshold": CYCLE6_THRESHOLD,
        "variants": [variant_id for variant_id, _ in VARIANTS],
        "summary": summary,
        "rows": rows,
        "product_authorized": False,
        "spent_confirmation_corpora_not_reused": True,
    }
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"threshold {CYCLE6_THRESHOLD}")
    print(f"watermarked rows {summary['watermarked_rows']}, unwatermarked rows {summary['unwatermarked_rows']}")
    print(f"pristine watermarked detected {summary['pristine_watermarked_detected']}/{summary['watermarked_rows']}")
    for variant_id, _ in VARIANTS:
        detected = summary[f"{variant_id}_watermarked_detected"]
        restores = summary[f"{variant_id}_restores_source"]
        print(
            f"  mix + {variant_id:36} watermarked detected "
            f"{detected}/{summary['watermarked_rows']}  restores source {restores}/{len(rows)}"
        )
    print("wrote", arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
