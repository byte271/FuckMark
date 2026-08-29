from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.gate_v2 import gate_v2_confirmation_artifact_path
from fuckmark.cycle8.letter_mix import (
    HISTORICAL_DUAL_LAYER_MIX_CARRIERS,
    apply_historical_dual_layer_letter_mix,
    apply_historical_mark_letter_mix,
)
from fuckmark.experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.product.visible_projection import project_visible_v1


ARMS = (
    "identity",
    "historical_mark_raw",
    "historical_mark_mn_strip",
    "historical_mark_di_strip",
    "dual_layer_raw",
    "dual_layer_mn_strip",
    "dual_layer_di_strip",
)


def _load_watermarked(seed_base: int, limit: int) -> list[dict[str, object]]:
    artifact = json.loads(Path(gate_v2_confirmation_artifact_path(seed_base)).read_text(encoding="utf-8"))
    rows = [sample for sample in artifact["samples"] if sample["label"] == "watermarked"]
    if limit > 0:
        rows = rows[:limit]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(prog="dual-layer-stress-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed-base", type=int, default=1_200_000)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/cycle8-dual-layer-stress-exploratory-2026-08-28/scorecard.json"),
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
        live = apply_historical_dual_layer_letter_mix(source)
        if project_visible_v1(live, HISTORICAL_DUAL_LAYER_MIX_CARRIERS) != source:
            raise RuntimeError("historical dual-layer mix changed visible text")
        payloads = {
            "identity": source,
            "historical_mark_raw": historical,
            "historical_mark_mn_strip": strip_nonspacing_marks(historical),
            "historical_mark_di_strip": strip_default_ignorable(historical),
            "dual_layer_raw": live,
            "dual_layer_mn_strip": strip_nonspacing_marks(live),
            "dual_layer_di_strip": strip_default_ignorable(live),
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
        "algorithm_version": "cycle8-dual-layer-stress-exploratory-v1",
        "role": "exploratory_rescore_of_frozen_sources",
        "confirmation_rewritten": False,
        "spent_confirmation_corpora_not_reused_for_generation": True,
        "source_corpus": gate_v2_confirmation_artifact_path(arguments.seed_base),
        "seed_base": arguments.seed_base,
        "watermarked_rows": total,
        "threshold": CYCLE6_THRESHOLD,
        "device": arguments.device,
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
    report = {**payload, "scorecard_hash": sha256_json(payload)}
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["effectiveness"], indent=2, sort_keys=True))
    print("wrote", arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
