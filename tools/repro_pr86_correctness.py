from __future__ import annotations

import sys

sys.path.insert(0, ".")

from fuckmark.experiments.cover_greedy_v3 import (
    _conflict_map,
    _root_eligible_windows,
    _token_index_ranges,
)
from fuckmark.geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
from fuckmark.geometry.repetition import PublicRepetitionGeometry
from fuckmark.transforms import content_region_coverage_transform_registry


class Tok:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode("utf-8"))

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        data = text.encode("utf-8")
        r = {"input_ids": list(data)}
        if return_offsets_mapping:
            r["offset_mapping"] = [(i, i + 1) for i in range(len(data))]
        return r


TEXTS = {
    "prose": (
        "Careful testing matters before any claim becomes knowledge. A single result "
        "cannot overturn a body of evidence. Repetition across labs makes findings durable."
    ),
    "repeat-heavy": (
        "The panel said the result was clear. The panel said the method was sound. "
        "The panel said the panel said enough. Reviewers agreed the reviewers agreed."
    ),
    "contraction-dense": (
        "It is not true that the model did not improve. The system does not drift, "
        "and it will not fail when samples are not balanced. It is stable."
    ),
}


def diagnose(name: str, text: str, budget: int = 16) -> None:
    tok = Tok()
    registry = content_region_coverage_transform_registry()
    enum = registry.enumerate(text)
    rep = PublicRepetitionGeometry.create(ngram_len=5, context_history_size=1024)
    cfg = GeometryConfig.create(
        tokenizer_identity_hash="0" * 64,
        ngram_len=5,
        repetition_mask_policy_id=rep.policy_id,
    )
    eng = CounterfactualGeometryEngine(tokenizer=tok, config=cfg, eligibility_policy=rep.eligibility_policy)
    root = eng.build_root(source_sample_id=name, source_text=text)
    encoded = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tuple((int(s), int(e)) for s, e in encoded["offset_mapping"])
    elig = _root_eligible_windows(root.root_tokens, rep)
    win_idx = tuple(i for i, f in enumerate(elig) if f)

    def touched(idx_set):
        return None

    cover = {}
    for c in enum.candidates:
        t = _token_index_ranges(offsets, c.start, c.end, 1)
        first, last = min(t), max(t)
        lo = max(0, last - 4)
        hi = min(first, len(root.root_tokens) - 5)
        cover[c.candidate_id] = {i for i in win_idx if lo <= i <= hi and any(
            off in t for off in range(i, i + 5)
        )}
    conflicts = _conflict_map(enum)
    sel, uncovered, spent = set(), set(win_idx), 0
    while spent < budget:
        opts = [cid for cid, _ in [(c.candidate_id, c) for c in enum.candidates]
                if cid not in sel and not (conflicts[cid] & sel) and cover[cid] & uncovered]
        if not opts:
            break
        best = max(opts, key=lambda cid: (len(cover[cid] & uncovered), [-ord(x) for x in cid]))
        best_gain = len(cover[best] & uncovered)
        best = min(cid for cid in opts if len(cover[cid] & uncovered) == best_gain)
        sel.add(best)
        uncovered -= cover[best]
        spent += 1
    transformed = registry.apply(enum, tuple(sorted(sel)))
    exact = eng.evaluate_output(
        root=root, current_text=text, output_text=transformed.output_text,
        candidate_id="diag", rule_hash=registry.ruleset_hash,
        visible_cost_class=0, family="diag", tier=0,
    )
    survivors = exact.surviving_count
    blocked = []
    if survivors > 0 and spent < budget:
        for c in enum.candidates:
            cid = c.candidate_id
            if cid in sel or (conflicts[cid] & sel):
                continue
            if cover[cid] & uncovered:
                continue
            trial_ids = tuple(sorted((*sel, cid)))
            try:
                trial_out = registry.apply(enum, trial_ids)
            except Exception:
                continue
            trial_exact = eng.evaluate_output(
                root=root, current_text=text, output_text=trial_out.output_text,
                candidate_id="diag", rule_hash=registry.ruleset_hash,
                visible_cost_class=0, family="diag", tier=0,
            )
            if trial_exact.surviving_count < survivors:
                blocked.append((cid, survivors - trial_exact.surviving_count))
    print(f"[{name}] candidates={len(enum.candidates)} selected={len(sel)} "
          f"uncovered_after_static={len(uncovered)} survivors={survivors} "
          f"budget_left={budget - spent}")
    if blocked:
        top = sorted(blocked, key=lambda x: -x[1])[:5]
        print(f"    BLOCKED-BY-GATE improvements available: {top}")


for label, txt in TEXTS.items():
    diagnose(label, txt)
