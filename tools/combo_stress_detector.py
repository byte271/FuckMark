from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.gate_v2 import gate_v2_confirmation_artifact_path
from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    apply_historical_dual_layer_letter_mix,
    apply_historical_mark_letter_mix,
    apply_letter_alternating_mix,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.product.visible_projection import project_visible_v1


ARMS = (
    "identity",
    "historical_mark_mn_us",
    "historical_dual_mn_us",
    "triple_raw",
    "triple_mn_strip",
    "triple_di_strip",
    "triple_us",
    "triple_mn_us",
    "triple_di_us",
    "triple_us_mn",
    "triple_bundle",
    "triple_bundle_us",
)


def _load_watermarked(seed_base: int, limit: int) -> list[dict[str, object]]:
    artifact = json.loads(Path(gate_v2_confirmation_artifact_path(seed_base)).read_text(encoding="utf-8"))
    rows = [sample for sample in artifact["samples"] if sample["label"] == "watermarked"]
    if limit > 0:
        rows = rows[:limit]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(prog="combo-stress-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, default=1_200_000)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/cycle8-combo-stress-exploratory-2026-08-28/scorecard.json"),
    )
    arguments = parser.parse_args()
    from fuckmark.cycle7_stage_a_hf import _adapter_and_tokenizer, _score_text

    _backend, tokenizer, adapter, _identity, eos = _adapter_and_tokenizer(arguments.device)
    samples = _load_watermarked(arguments.seed_base, arguments.limit)
    detected = {arm: 0 for arm in ARMS}
    restores = {arm: 0 for arm in ARMS}
    rows: list[dict[str, object]] = []
    for sample in samples:
        source = str(sample["text"])
        historical = apply_historical_mark_letter_mix(source)
        dual = apply_historical_dual_layer_letter_mix(source)
        live = apply_letter_alternating_mix(source)
        if project_visible_v1(live, LETTER_MIX_APPROVED_CARRIERS) != source:
            raise RuntimeError("triple-layer mix changed visible text")
        payloads = {
            "identity": source,
            "historical_mark_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(historical)),
            "historical_dual_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(dual)),
            "triple_raw": live,
            "triple_mn_strip": strip_nonspacing_marks(live),
            "triple_di_strip": strip_default_ignorable(live),
            "triple_us": lm_watermarking_unicode_sanitizer(live),
            "triple_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(live)),
            "triple_di_us": lm_watermarking_unicode_sanitizer(strip_default_ignorable(live)),
            "triple_us_mn": strip_nonspacing_marks(lm_watermarking_unicode_sanitizer(live)),
            "triple_bundle": apply_required_sanitizer_bundle(live),
            "triple_bundle_us": lm_watermarking_unicode_sanitizer(apply_required_sanitizer_bundle(live)),
        }
        scored: dict[str, object] = {}
        for arm, text in payloads.items():
            score = _score_text(f"{sample['sample_id']}-{arm}", text, tokenizer, adapter, eos)
            hit = score >= CYCLE6_THRESHOLD
            restored = text == source
            detected[arm] += int(hit)
            restores[arm] += int(restored)
            scored[arm] = {
                "score": score,
                "detected": hit,
                "restores_source": restored,
                "text_sha256": sha256_text(text),
            }
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "source_sha256": sample["text_sha256"],
                "arms": scored,
            }
        )
    total = len(samples)
    payload = {
        "algorithm_version": "cycle8-combo-stress-exploratory-v1",
        "role": "exploratory_rescore_of_frozen_sources",
        "confirmation_rewritten": False,
        "spent_confirmation_corpora_not_reused_for_generation": True,
        "source_corpus": gate_v2_confirmation_artifact_path(arguments.seed_base),
        "seed_base": arguments.seed_base,
        "watermarked_rows": total,
        "threshold": CYCLE6_THRESHOLD,
        "device": arguments.device,
        "mechanism_id": "u034f-ufe00-cc-me-letter-alt-v1",
        "effectiveness": {
            arm: {
                "detected": detected[arm],
                "rate": f"{detected[arm]}/{total}",
                "restores_source": restores[arm],
            }
            for arm in ARMS
        },
        "rows": rows,
    }
    body = {key: value for key, value in payload.items() if key != "scorecard_hash"}
    report = {**payload, "scorecard_hash": sha256_json(body)}
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["effectiveness"], ensure_ascii=False, indent=2, sort_keys=True))
    print("scorecard_hash", report["scorecard_hash"])
    print("wrote", arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
