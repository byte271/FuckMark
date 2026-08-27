from __future__ import annotations

import argparse
from pathlib import Path

import torch

from .config import canonical_json_text
from .corpus.schema import CorpusDomain
from .corpus.tiny_dev_generation import TINY_DEV_PAIR_SEED_STRIDE
from .cycle8.control_carrier import apply_required_sanitizer_bundle, required_sanitizers_keep
from .cycle8.control_mix import CONTROL_MIX_APPROVED_CARRIERS, apply_control_alternating_mix
from .cycle8.ledger import CYCLE8_CONTROL_MIX_EXPLORATORY_ROLE, assert_cycle8_development_seed, role_for_seed_base
from .cycle8_deepmind_transfer_hf import _processor, official_score
from .cycle8_hf import _CYCLE8_TEMPLATES
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from .hashing import sha256_file, sha256_json, sha256_text
from .product.domain import is_supported_product_domain_v1
from .product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from .seeds.ledger import (
    CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE,
    CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC,
    assert_new_cycle8_control_mix_generation_seed,
)
from .synthid_smoke_deepmind import DeepMindSynthIDSmokeBackend


_MODEL_ID = "openai-community/gpt2"
_MAX_ATTEMPTS = 64
_PAIR_COUNT = 16


def generate_control_mix_corpus(
    seed_base: int,
    *,
    pair_count: int = _PAIR_COUNT,
    out_dir: Path,
) -> dict[str, object]:
    assert_new_cycle8_control_mix_generation_seed(seed_base)
    if role_for_seed_base(seed_base) != CYCLE8_CONTROL_MIX_EXPLORATORY_ROLE:
        raise ValueError("seed_base role does not match the Cycle 8 ledger")
    assert_cycle8_development_seed(seed_base, role=CYCLE8_CONTROL_MIX_EXPLORATORY_ROLE)
    used_topic = CYCLE8_CONTROL_MIX_EXPLORATORY_TOPIC
    backend = DeepMindSynthIDSmokeBackend(
        _MODEL_ID,
        device="cpu",
        max_new_tokens=64,
        temperature=0.8,
        top_k=50,
        top_p=0.95,
    )
    processor, ngram_len, keys_depth = _processor(torch.device("cpu"))
    domains = tuple(CorpusDomain)
    samples: list[dict[str, object]] = []
    for pair_index in range(pair_count):
        domain = domains[pair_index % len(domains)]
        prompt = _CYCLE8_TEMPLATES[domain].format(topic=used_topic)
        pair_seed_base = seed_base + pair_index * TINY_DEV_PAIR_SEED_STRIDE
        accepted = None
        for attempt in range(_MAX_ATTEMPTS):
            seed = pair_seed_base + attempt
            try:
                unwatermarked = backend.generate(prompt, seed, watermarked=False)
                watermarked = backend.generate(prompt, seed, watermarked=True)
            except RuntimeError:
                continue
            uw_ids = backend._tokenizer.encode(unwatermarked, add_special_tokens=False)
            wm_ids = backend._tokenizer.encode(watermarked, add_special_tokens=False)
            if len(uw_ids) != 64 or len(wm_ids) != 64:
                continue
            if unwatermarked == watermarked:
                continue
            if not is_supported_product_domain_v1(unwatermarked) or not is_supported_product_domain_v1(watermarked):
                continue
            accepted = (seed, unwatermarked, watermarked)
            break
        if accepted is None:
            raise RuntimeError(f"failed pair {pair_index} {domain.value}")
        seed, unwatermarked, watermarked = accepted
        print(f"pair {pair_index} {domain.value} seed {seed}", flush=True)
        for label, text in (("unwatermarked", unwatermarked), ("watermarked", watermarked)):
            samples.append(
                {
                    "sample_id": f"cycle8-{seed_base}-{pair_index:02d}-{domain.value}-{label}",
                    "domain": domain.value,
                    "label": label,
                    "seed": seed,
                    "pair_index": pair_index,
                    "text": text,
                    "text_sha256": sha256_text(text),
                }
            )
    rows = []
    identity_wm = control_wm = identity_uw = control_uw = 0
    n_wm = n_uw = 0
    control_wm_max = None
    visible_pass = True
    sanitizer_keep = True
    for sample in samples:
        source = str(sample["text"])
        control = apply_control_alternating_mix(source)
        visible_ok = is_carrier_insertion_v1(
            source, control, CONTROL_MIX_APPROVED_CARRIERS
        ) and project_visible_v1(control, CONTROL_MIX_APPROVED_CARRIERS) == source
        visible_pass = visible_pass and visible_ok
        keep = required_sanitizers_keep(control) and apply_required_sanitizer_bundle(control) == control
        sanitizer_keep = sanitizer_keep and keep
        identity_score, identity_tokens = official_score(backend, processor, ngram_len, source)
        control_score, control_tokens = official_score(backend, processor, ngram_len, control)
        identity_detected = identity_score >= CYCLE6_THRESHOLD
        control_detected = control_score >= CYCLE6_THRESHOLD
        if sample["label"] == "watermarked":
            n_wm += 1
            identity_wm += int(identity_detected)
            control_wm += int(control_detected)
            control_wm_max = control_score if control_wm_max is None else max(control_wm_max, control_score)
        else:
            n_uw += 1
            identity_uw += int(identity_detected)
            control_uw += int(control_detected)
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
            }
        )
        print(
            f"{sample['sample_id']} identity={identity_score:.6f} control={control_score:.6f}",
            flush=True,
        )
    payload = {
        "algorithm_version": "cycle8-control-mix-exploratory-v1",
        "seed_base": seed_base,
        "topic": used_topic,
        "pair_count": pair_count,
        "seen_corpus": False,
        "independent_generation": True,
        "product_authorized": False,
        "confirmation_rewritten": False,
        "mix_freeze_confirmation": False,
        "mix_gate_not_rewritten": True,
        "second_model": False,
        "second_configuration": True,
        "evidence_label": "HYPOTHESIS",
        "model": _MODEL_ID,
        "generation": "synthid_text.SynthIDGPT2LMHeadModel",
        "detector": "synthid_text.logits_processing.SynthIDLogitsProcessor",
        "keys_depth": keys_depth,
        "threshold": CYCLE6_THRESHOLD,
        "visible_pass": visible_pass,
        "required_sanitizers_keep": sanitizer_keep,
        "effectiveness": {
            "identity_wm": {"detected": identity_wm, "n": n_wm, "rate": f"{identity_wm}/{n_wm}"},
            "control_mix_wm": {"detected": control_wm, "n": n_wm, "rate": f"{control_wm}/{n_wm}"},
            "identity_uw": {"detected": identity_uw, "n": n_uw, "rate": f"{identity_uw}/{n_uw}"},
            "control_mix_uw": {"detected": control_uw, "n": n_uw, "rate": f"{control_uw}/{n_uw}"},
            "control_mix_wm_max_score": control_wm_max,
        },
        "do_not_generate_950000": True,
        "rows": rows,
    }
    payload["scorecard_hash"] = sha256_json({key: value for key, value in payload.items() if key != "scorecard_hash"})
    out_dir.mkdir(parents=True, exist_ok=True)
    write_canonical_json_fsynced(out_dir / "scorecard.json", payload)
    write_canonical_json_fsynced(
        out_dir / "samples.json",
        {"samples": samples, "seed_base": seed_base, "topic": used_topic, "pair_count": pair_count},
    )
    sums = [f"{sha256_file(out_dir / name)}  {name}" for name in ("scorecard.json", "samples.json")]
    (out_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(canonical_json_text({key: value for key, value in payload.items() if key != "rows"}), flush=True)
    if seed_base != CYCLE8_CONTROL_MIX_EXPLORATORY_SEED_BASE:
        raise ValueError("unexpected control-mix seed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-base", type=int, required=True)
    parser.add_argument("--pair-count", type=int, default=_PAIR_COUNT)
    parser.add_argument("--out-dir", type=str, required=True)
    args = parser.parse_args()
    generate_control_mix_corpus(args.seed_base, pair_count=args.pair_count, out_dir=Path(args.out_dir))


if __name__ == "__main__":
    main()
