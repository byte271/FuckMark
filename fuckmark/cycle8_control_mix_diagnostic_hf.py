from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from synthid_text import logits_processing, synthid_mixin
from transformers import AutoTokenizer

from .config import canonical_json_text
from .cycle8.control_carrier import apply_required_sanitizer_bundle, required_sanitizers_keep
from .cycle8.control_mix import CONTROL_MIX_APPROVED_CARRIERS, apply_control_alternating_mix
from .cycle8.letter_mix import apply_letter_alternating_mix
from .cycle8_deepmind_transfer_hf import official_score
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from .hashing import sha256_json, sha256_text
from .product.visible_projection import is_carrier_insertion_v1, project_visible_v1


_MODEL_ID = "openai-community/gpt2"
_SOURCE_SAMPLES = "evidence/cycle8-mix-deepmind-30key-920000-n16-2026-08-27/samples.json"


class _TokenizerBackend:
    def __init__(self, tokenizer) -> None:
        self._tokenizer = tokenizer


def _processor(device: torch.device):
    cfg = dict(synthid_mixin.DEFAULT_WATERMARKING_CONFIG)
    keys = list(cfg["keys"])
    return (
        logits_processing.SynthIDLogitsProcessor(
            ngram_len=int(cfg["ngram_len"]),
            keys=keys,
            sampling_table_size=int(cfg["sampling_table_size"]),
            sampling_table_seed=int(cfg["sampling_table_seed"]),
            context_history_size=int(cfg["context_history_size"]),
            temperature=0.8,
            top_k=50,
            device=device,
        ),
        int(cfg["ngram_len"]),
        len(keys),
    )


def score_control_mix_diagnostic(
    *,
    samples_path: Path | None = None,
    out_dir: Path,
) -> dict[str, object]:
    source_path = Path(samples_path) if samples_path is not None else Path(_SOURCE_SAMPLES)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    samples = list(payload["samples"])
    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
    backend = _TokenizerBackend(tokenizer)
    processor, ngram_len, keys_depth = _processor(device)
    identity_wm = control_wm = mix_wm = identity_uw = control_uw = mix_uw = 0
    n_wm = n_uw = 0
    control_wm_max = None
    visible_pass = True
    sanitizer_keep = True
    rows = []
    for sample in samples:
        source = str(sample["text"])
        control = apply_control_alternating_mix(source)
        mix = apply_letter_alternating_mix(source)
        visible_ok = is_carrier_insertion_v1(
            source, control, CONTROL_MIX_APPROVED_CARRIERS
        ) and project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS) == source
        visible_pass = visible_pass and visible_ok
        keep = required_sanitizers_keep(control) and apply_required_sanitizer_bundle(control) == control
        sanitizer_keep = sanitizer_keep and keep
        identity_score, identity_tokens = official_score(backend, processor, ngram_len, source)
        control_score, control_tokens = official_score(backend, processor, ngram_len, control)
        mix_score, mix_tokens = official_score(backend, processor, ngram_len, mix)
        identity_detected = identity_score >= CYCLE6_THRESHOLD
        control_detected = control_score >= CYCLE6_THRESHOLD
        mix_detected = mix_score >= CYCLE6_THRESHOLD
        if sample["label"] == "watermarked":
            n_wm += 1
            identity_wm += int(identity_detected)
            control_wm += int(control_detected)
            mix_wm += int(mix_detected)
            control_wm_max = control_score if control_wm_max is None else max(control_wm_max, control_score)
        else:
            n_uw += 1
            identity_uw += int(identity_detected)
            control_uw += int(control_detected)
            mix_uw += int(mix_detected)
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "source_sha256": sample["text_sha256"],
                "visible_ok": visible_ok,
                "required_sanitizers_keep": keep,
                "identity": {
                    "score": identity_score,
                    "detected": identity_detected,
                    "n_tokens": identity_tokens,
                },
                "control_mix": {
                    "score": control_score,
                    "detected": control_detected,
                    "n_tokens": control_tokens,
                    "text_sha256": sha256_text(control),
                },
                "mix": {
                    "score": mix_score,
                    "detected": mix_detected,
                    "n_tokens": mix_tokens,
                    "text_sha256": sha256_text(mix),
                },
            }
        )
        print(
            f"{sample['sample_id']} identity={identity_score:.6f} control={control_score:.6f} mix={mix_score:.6f}",
            flush=True,
        )
    report = {
        "algorithm_version": "cycle8-control-mix-diagnostic-v1",
        "seed_base": 920000,
        "source_samples": _SOURCE_SAMPLES,
        "seen_corpus": True,
        "independent_generation": False,
        "product_authorized": False,
        "confirmation_rewritten": False,
        "mix_freeze_confirmation": False,
        "mix_gate_not_rewritten": True,
        "evidence_label": "HYPOTHESIS",
        "model": _MODEL_ID,
        "detector": "synthid_text.logits_processing.SynthIDLogitsProcessor",
        "keys_depth": keys_depth,
        "threshold": CYCLE6_THRESHOLD,
        "pair_count": n_wm,
        "visible_pass": visible_pass,
        "required_sanitizers_keep": sanitizer_keep,
        "effectiveness": {
            "identity_wm": {"detected": identity_wm, "n": n_wm, "rate": f"{identity_wm}/{n_wm}"},
            "control_mix_wm": {"detected": control_wm, "n": n_wm, "rate": f"{control_wm}/{n_wm}"},
            "mix_wm": {"detected": mix_wm, "n": n_wm, "rate": f"{mix_wm}/{n_wm}"},
            "identity_uw": {"detected": identity_uw, "n": n_uw, "rate": f"{identity_uw}/{n_uw}"},
            "control_mix_uw": {"detected": control_uw, "n": n_uw, "rate": f"{control_uw}/{n_uw}"},
            "mix_uw": {"detected": mix_uw, "n": n_uw, "rate": f"{mix_uw}/{n_uw}"},
            "control_mix_wm_max_score": control_wm_max,
        },
        "do_not_generate_950000": True,
        "rows": rows,
    }
    body = {key: value for key, value in report.items()}
    report["scorecard_hash"] = sha256_json(body)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(out_dir / "scorecard.json", report)
    write_canonical_json_fsynced(
        out_dir / "summary.json",
        {key: value for key, value in report.items() if key != "rows"},
    )
    print(canonical_json_text({key: value for key, value in report.items() if key != "rows"}), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--samples", default=_SOURCE_SAMPLES)
    args = parser.parse_args()
    score_control_mix_diagnostic(samples_path=Path(args.samples), out_dir=Path(args.out_dir))


if __name__ == "__main__":
    main()
