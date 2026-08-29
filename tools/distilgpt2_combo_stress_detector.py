from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import transformers
from transformers import SynthIDTextWatermarkLogitsProcessor

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.letter_mix import (
    HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS,
    apply_historical_dual_layer_letter_mix,
    apply_historical_triple_layer_letter_mix,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.detectors.mean import weighted_mean_score
from fuckmark.experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.product.visible_projection import project_visible_v1


ARMS = (
    "identity",
    "historical_dual_mn_us",
    "triple_raw",
    "triple_mn_us",
    "triple_di_us",
    "triple_bundle_us",
)
_SAMPLES = Path("evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/samples.json")
_MODEL_ID = "distilbert/distilgpt2"
_NGRAM_LEN = 5
_KEYS = (
    654,
    400,
    836,
    123,
    340,
    443,
    597,
    160,
    57,
    29,
    590,
    639,
    13,
    715,
    468,
    990,
    966,
    226,
    324,
    585,
    118,
    504,
    421,
    521,
    129,
    669,
    732,
    225,
    90,
    960,
)


def _processor(device: torch.device) -> SynthIDTextWatermarkLogitsProcessor:
    return SynthIDTextWatermarkLogitsProcessor(
        ngram_len=_NGRAM_LEN,
        keys=list(_KEYS),
        sampling_table_size=65536,
        sampling_table_seed=0,
        context_history_size=1024,
        device=device,
    )


def _score_text(tokenizer, processor, text: str) -> float:
    ids = tokenizer.encode(text, add_special_tokens=False)
    tensor = torch.tensor([ids], dtype=torch.long, device=processor.device)
    g_values = processor.compute_g_values(tensor)
    context_mask = processor.compute_context_repetition_mask(tensor)
    eos_mask = processor.compute_eos_token_mask(tensor, eos_token_id=tokenizer.eos_token_id)[
        :, _NGRAM_LEN - 1 :
    ]
    mask = torch.logical_and(context_mask, eos_mask)
    return weighted_mean_score(g_values[0].tolist(), [bool(value) for value in mask[0].tolist()])


def main() -> int:
    parser = argparse.ArgumentParser(prog="distilgpt2-combo-stress-detector")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/cycle8-distilgpt2-combo-stress-exploratory-2026-08-28/scorecard.json"),
    )
    arguments = parser.parse_args()
    payload = json.loads(_SAMPLES.read_text(encoding="utf-8"))
    samples = [row for row in payload["samples"] if row["label"] == "watermarked"]
    if arguments.limit > 0:
        samples = samples[: arguments.limit]
    tokenizer = transformers.AutoTokenizer.from_pretrained(_MODEL_ID)
    processor = _processor(torch.device(arguments.device))
    detected = {arm: 0 for arm in ARMS}
    restores = {arm: 0 for arm in ARMS}
    rows: list[dict[str, object]] = []
    for sample in samples:
        source = str(sample["text"])
        dual = apply_historical_dual_layer_letter_mix(source)
        live = apply_historical_triple_layer_letter_mix(source)
        if project_visible_v1(live, HISTORICAL_TRIPLE_LAYER_MIX_CARRIERS) != source:
            raise RuntimeError("historical triple-layer mix changed visible text")
        texts = {
            "identity": source,
            "historical_dual_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(dual)),
            "triple_raw": live,
            "triple_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(live)),
            "triple_di_us": lm_watermarking_unicode_sanitizer(strip_default_ignorable(live)),
            "triple_bundle_us": lm_watermarking_unicode_sanitizer(apply_required_sanitizer_bundle(live)),
        }
        scored: dict[str, object] = {}
        for arm, text in texts.items():
            score = _score_text(tokenizer, processor, text)
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
        rows.append({"sample_id": sample["sample_id"], "source_sha256": sample["text_sha256"], "arms": scored})
    total = len(samples)
    report_body = {
        "algorithm_version": "cycle8-distilgpt2-combo-stress-exploratory-v1",
        "role": "exploratory_rescore_of_frozen_second_model_sources",
        "confirmation_rewritten": False,
        "frozen_second_model_scorecard_not_rewritten": True,
        "source_corpus": str(_SAMPLES),
        "seed_base": int(payload["seed_base"]),
        "model": _MODEL_ID,
        "watermarked_rows": total,
        "threshold": CYCLE6_THRESHOLD,
        "device": arguments.device,
        "mechanism_id": "u034f-ufe00-cc-me-letter-alt-v1",
        "detector": "transformers.SynthIDTextWatermarkLogitsProcessor",
        "keys_depth": len(_KEYS),
        "sampling_table_size": 65536,
        "evidence_label": "HYPOTHESIS",
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
    report = {**report_body, "scorecard_hash": sha256_json(report_body)}
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["effectiveness"], ensure_ascii=False, indent=2, sort_keys=True))
    print("scorecard_hash", report["scorecard_hash"])
    print("wrote", arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
