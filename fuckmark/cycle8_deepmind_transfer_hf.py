from __future__ import annotations

import argparse
from pathlib import Path

import torch
from synthid_text import logits_processing, synthid_mixin

from .config import canonical_json_text
from .corpus.schema import CorpusDomain
from .corpus.tiny_dev_generation import TINY_DEV_PAIR_SEED_STRIDE
from .cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from .cycle8.ledger import (
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_ROLE,
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_ROLE,
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_ROLE,
    CYCLE8_EXPLORATORY_ROLE,
    assert_cycle8_development_seed,
    role_for_seed_base,
)
from .cycle8_hf import _CYCLE8_TEMPLATES
from .detectors.mean import weighted_mean_score
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from .hashing import sha256_file, sha256_json, sha256_text
from .product.domain import is_supported_product_domain_v1
from .product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from .seeds.ledger import (
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC,
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC,
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE,
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC,
    assert_new_cycle8_deepmind_transfer_generation_seed,
)
from .synthid_smoke_deepmind import DeepMindSynthIDSmokeBackend


_MODEL_ID = "openai-community/gpt2"
_MAX_ATTEMPTS = 64
_PAIR_COUNT = 64
_ROLES = {
    CYCLE8_DEEPMIND_TRANSFER_PRIMARY_SEED_BASE: (
        CYCLE8_DEEPMIND_TRANSFER_PRIMARY_ROLE,
        CYCLE8_DEEPMIND_TRANSFER_PRIMARY_TOPIC,
    ),
    CYCLE8_DEEPMIND_TRANSFER_REPLICATION_SEED_BASE: (
        CYCLE8_DEEPMIND_TRANSFER_REPLICATION_ROLE,
        CYCLE8_DEEPMIND_TRANSFER_REPLICATION_TOPIC,
    ),
    CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_SEED_BASE: (
        CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_ROLE,
        CYCLE8_DEEPMIND_TRANSFER_HOLDOUT_TOPIC,
    ),
}


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


def official_score(backend, processor, ngram_len: int, text: str) -> tuple[float, int]:
    ids = backend._tokenizer.encode(text, add_special_tokens=False)
    tensor = torch.tensor([ids], dtype=torch.long)
    g_values = processor.compute_g_values(tensor)
    context_mask = processor.compute_context_repetition_mask(tensor)
    eos_mask = processor.compute_eos_token_mask(tensor, eos_token_id=backend._tokenizer.eos_token_id)[
        :, ngram_len - 1 :
    ]
    mask = torch.logical_and(context_mask, eos_mask)
    score = weighted_mean_score(g_values[0].tolist(), [bool(value) for value in mask[0].tolist()])
    return score, len(ids)


def generate_deepmind_mix_corpus(
    seed_base: int,
    *,
    pair_count: int = _PAIR_COUNT,
    out_dir: Path,
    topic: str | None = None,
) -> dict[str, object]:
    if seed_base == 920000:
        role = CYCLE8_EXPLORATORY_ROLE
        used_topic = topic or "invisible carrier development"
        assert_cycle8_development_seed(seed_base, role=role)
    else:
        assert_new_cycle8_deepmind_transfer_generation_seed(seed_base)
        role, default_topic = _ROLES[seed_base]
        used_topic = topic or default_topic
        if role_for_seed_base(seed_base) != role:
            raise ValueError("seed_base role does not match the Cycle 8 ledger")
        assert_cycle8_development_seed(seed_base, role=role)
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
    identity_wm = mix_wm = identity_uw = mix_uw = 0
    n_wm = n_uw = 0
    mix_wm_max = None
    for sample in samples:
        source = str(sample["text"])
        transformed = apply_letter_alternating_mix(source)
        visible_ok = is_carrier_insertion_v1(
            source, transformed, LETTER_MIX_APPROVED_CARRIERS
        ) and project_visible_v1(transformed, LETTER_MIX_APPROVED_CARRIERS) == source
        identity_score, identity_tokens = official_score(backend, processor, ngram_len, source)
        mix_score, mix_tokens = official_score(backend, processor, ngram_len, transformed)
        identity_detected = identity_score >= CYCLE6_THRESHOLD
        mix_detected = mix_score >= CYCLE6_THRESHOLD
        if sample["label"] == "watermarked":
            n_wm += 1
            identity_wm += int(identity_detected)
            mix_wm += int(mix_detected)
            mix_wm_max = mix_score if mix_wm_max is None else max(mix_wm_max, mix_score)
        else:
            n_uw += 1
            identity_uw += int(identity_detected)
            mix_uw += int(mix_detected)
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "label": sample["label"],
                "domain": sample["domain"],
                "source_sha256": sample["text_sha256"],
                "visible_ok": visible_ok,
                "identity": {
                    "score": identity_score,
                    "detected": identity_detected,
                    "n_tokens": identity_tokens,
                },
                "mix": {
                    "score": mix_score,
                    "detected": mix_detected,
                    "n_tokens": mix_tokens,
                    "text_sha256": sha256_text(transformed),
                },
            }
        )
    payload = {
        "algorithm_version": "cycle8-mix-deepmind-30key-transfer-v1",
        "seed_base": seed_base,
        "topic": used_topic,
        "pair_count": pair_count,
        "product_authorized": False,
        "confirmation_rewritten": False,
        "mix_freeze_confirmation": False,
        "second_model": False,
        "second_configuration": True,
        "evidence_label": "HYPOTHESIS",
        "model": _MODEL_ID,
        "generation": "synthid_text.SynthIDGPT2LMHeadModel",
        "detector": "synthid_text.logits_processing.SynthIDLogitsProcessor",
        "keys_depth": keys_depth,
        "threshold": CYCLE6_THRESHOLD,
        "effectiveness": {
            "identity_wm": {"detected": identity_wm, "n": n_wm, "rate": f"{identity_wm}/{n_wm}"},
            "mix_wm": {"detected": mix_wm, "n": n_wm, "rate": f"{mix_wm}/{n_wm}"},
            "identity_uw": {"detected": identity_uw, "n": n_uw, "rate": f"{identity_uw}/{n_uw}"},
            "mix_uw": {"detected": mix_uw, "n": n_uw, "rate": f"{mix_uw}/{n_uw}"},
            "mix_wm_max_score": mix_wm_max,
        },
        "visible_pass": all(bool(row["visible_ok"]) for row in rows),
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
    sums = []
    for name in ("scorecard.json", "samples.json"):
        sums.append(f"{sha256_file(out_dir / name)}  {name}")
    (out_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(canonical_json_text({key: value for key, value in payload.items() if key != "rows"}), flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-mix-deepmind-transfer")
    parser.add_argument("--seed-base", type=int, required=True)
    parser.add_argument("--pair-count", type=int, default=_PAIR_COUNT)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--topic", type=str, default=None)
    args = parser.parse_args(argv)
    generate_deepmind_mix_corpus(
        args.seed_base,
        pair_count=args.pair_count,
        out_dir=args.out_dir,
        topic=args.topic,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
