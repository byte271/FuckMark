from __future__ import annotations

import sys

sys.path.insert(0, ".")

PROMPT_5 = "Explain what happens inside a microwave oven when it runs."
SEED = 710_000 + 5 + 1


def main() -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, SynthIDTextWatermarkingConfig

    from fuckmark.experiments.cover_greedy_v3 import (
        _conflict_map,
        _root_eligible_windows,
        _token_index_ranges,
    )
    from fuckmark.geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
    from fuckmark.geometry.repetition import PublicRepetitionGeometry
    from fuckmark.hashing import sha256_json
    from fuckmark.transforms import content_region_coverage_transform_registry

    model_id = "openai-community/gpt2"
    revision = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision)
    model.eval()
    wm = SynthIDTextWatermarkingConfig(ngram_len=5, keys=[654, 400, 836, 123, 340, 443, 597, 160, 57])

    torch.manual_seed(SEED)
    encoded = tokenizer(PROMPT_5, return_tensors="pt")
    with torch.inference_mode():
        out = model.generate(
            **encoded,
            do_sample=True, temperature=0.8, top_k=50, top_p=0.95,
            min_new_tokens=64, max_new_tokens=64,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            watermarking_config=wm,
        )
    text = tokenizer.decode(out[0, encoded["input_ids"].shape[1]:], skip_special_tokens=True)
    print("text:", repr(text))

    repetition = PublicRepetitionGeometry.create(ngram_len=5, context_history_size=1024)
    config = GeometryConfig.create(
        tokenizer_identity_hash="0" * 64,
        ngram_len=5,
        repetition_mask_policy_id=repetition.policy_id,
    )
    engine = CounterfactualGeometryEngine(tokenizer=tokenizer, config=config, eligibility_policy=repetition.eligibility_policy)
    root = engine.build_root(source_sample_id="diag5", source_text=text)
    elig = _root_eligible_windows(root.root_tokens, repetition)
    win_idx = tuple(i for i, f in enumerate(elig) if f)
    print("root_tokens=", len(root.root_tokens), "windows=", len(win_idx))

    registry = content_region_coverage_transform_registry()
    enum = registry.enumerate(text)
    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tuple((int(s), int(e)) for s, e in enc["offset_mapping"])
    print("offset_input_ids_match_root:", tuple(enc["input_ids"]) == root.root_tokens)

    cover = {}
    for c in enum.candidates:
        t = _token_index_ranges(offsets, c.start, c.end, 1)
        first, last = min(t), max(t)
        lo = max(0, last - 4)
        hi = min(first, len(root.root_tokens) - 5)
        cover[c.candidate_id] = {i for i in win_idx if lo <= i <= hi and any(off in t for off in range(i, i + 5))}

    conflicts = _conflict_map(enum)
    sel, uncovered = set(), set(win_idx)
    for step in range(16):
        opts = [c.candidate_id for c in enum.candidates
                if c.candidate_id not in sel and not (conflicts[c.candidate_id] & sel) and cover[c.candidate_id] & uncovered]
        if not opts:
            print(f"step {step}: NO OPTIONS (uncovered={len(uncovered)})")
            break
        best_gain = max(len(cover[cid] & uncovered) for cid in opts)
        best = min(cid for cid in opts if len(cover[cid] & uncovered) == best_gain)
        sel.add(best)
        uncovered -= cover[best]
        cand = next(c for c in enum.candidates if c.candidate_id == best)
        print(f"step {step}: gain={best_gain} uncovered_now={len(uncovered)} rule={cand.rule_id} span=({cand.start},{cand.end}) src={cand.source_text!r}")
        if best_gain <= 0:
            break

    try:
        transformed = registry.apply(enum, tuple(sorted(sel)))
        print("apply OK, output len:", len(transformed.output_text))
    except Exception as exc:
        print("apply FAILED:", type(exc).__name__, str(exc)[:200])
        return 0

    exact = engine.evaluate_output(
        root=root, current_text=text, output_text=transformed.output_text,
        candidate_id="diag", rule_hash=registry.ruleset_hash, visible_cost_class=0, family="diag", tier=0,
    )
    print("survivors_after_static:", exact.surviving_count)

    remaining = [c.candidate_id for c in enum.candidates if c.candidate_id not in sel]
    ok = fail = 0
    gains = []
    for cid in remaining[:10]:
        try:
            trial = registry.apply(enum, tuple(sorted((*sel, cid))))
            t_exact = engine.evaluate_output(
                root=root, current_text=text, output_text=trial.output_text,
                candidate_id="d2", rule_hash=registry.ruleset_hash, visible_cost_class=0, family="diag", tier=0,
            )
            gains.append((cid[:8], exact.surviving_count - t_exact.surviving_count))
            ok += 1
        except Exception as exc:
            fail += 1
            if fail <= 2:
                print("trial failed:", type(exc).__name__, str(exc)[:160])
    print(f"trials ok={ok} fail={fail} gains={gains}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
