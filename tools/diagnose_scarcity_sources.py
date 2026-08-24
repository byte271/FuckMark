from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, ".")

PROMPTS = {
    5: "Explain what happens inside a microwave oven when it runs.",
    12: "Discuss why farmers rotate crops between fields each year.",
}
SEED_BASE = 710_000


def main() -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from fuckmark.geometry.repetition import PublicRepetitionGeometry
    from fuckmark.transforms import content_region_coverage_transform_registry
    from fuckmark.transforms.effectiveness_profile import zrd_destruction_transform_registry

    model_id = "openai-community/gpt2"
    revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision)
    model.eval()
    watermark_config = None
    from transformers import SynthIDTextWatermarkingConfig

    watermark_config = SynthIDTextWatermarkingConfig(ngram_len=5, keys=[654, 400, 836, 123, 340, 443, 597, 160, 57])

    repetition = PublicRepetitionGeometry.create(ngram_len=5, context_history_size=1024)

    for index, prompt in PROMPTS.items():
        torch.manual_seed(SEED_BASE + index + 1)
        encoded = tokenizer(prompt, return_tensors="pt")
        with torch.inference_mode():
            output = model.generate(
                **encoded,
                do_sample=True,
                temperature=0.8,
                top_k=50,
                top_p=0.95,
                min_new_tokens=64,
                max_new_tokens=64,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                watermarking_config=watermark_config,
            )
        text = tokenizer.decode(output[0, encoded["input_ids"].shape[1]:], skip_special_tokens=True)
        print(f"\n===== sample {index} ({len(text)} chars) =====")
        print(repr(text[:400]))

        for label, registry in (("coverage", content_region_coverage_transform_registry()), ("zrd", zrd_destruction_transform_registry())):
            enum = registry.enumerate(text)
            by_rule = Counter(c.rule_id.split("-")[0] + "-" + c.rule_id.split("-")[1] if c.rule_id.startswith(("contract", "expand")) else c.rule_id for c in enum.candidates)
            rejections = Counter(r.reason.value for r in enum.rejections)
            conflicts = Counter()
            for conflict in enum.conflicts:
                conflicts["pairs"] += 1
            deg = Counter()
            for c in enum.candidates:
                n = sum(1 for k in enum.conflicts if k.first_candidate_id == c.candidate_id or k.second_candidate_id == c.candidate_id)
                deg[n] += 1
            print(f"[{label}] candidates={len(enum.candidates)} rejections={dict(rejections)} conflict_pairs={conflicts['pairs']}")
            print(f"    top_rules={by_rule.most_common(8)}")
            print(f"    conflict_degree_histogram={sorted(deg.items())[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
