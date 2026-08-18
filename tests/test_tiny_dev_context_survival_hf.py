from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

from fuckmark.corpus import CorpusSplit, WatermarkLabel
from fuckmark.experiments.context_survival_plan import (
    COVERAGE_POLICY,
    EXACT_B1_POLICY,
    GREEDY_POLICY,
    STATEFUL_RANDOM_POLICY,
    SUCCESS,
    _select_result_state,
    _stateful_random,
    build_context_survival_plan,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.state_search import SearchResult, SearchState, SearchTransition
from fuckmark.tiny_dev_context_survival_hf import PAIR_STATUS_MATCHED, _paired_random_comparisons


def _state(
    text: str,
    *,
    depth: int,
    surviving: int,
    newly_masked: int = 0,
    visible_cost: int | None = None,
    risk: int = 1,
    operation_hashes: tuple[str, ...] | None = None,
    ancestor_text_hashes: tuple[str, ...] | None = None,
) -> SearchState:
    operations = operation_hashes if operation_hashes is not None else tuple(
        sha256_text(f"operation-{index}-{text}") for index in range(depth)
    )
    ancestors = ancestor_text_hashes if ancestor_text_hashes is not None else tuple(
        sha256_text(f"ancestor-{index}-{text}") for index in range(depth)
    )
    return SearchState.create(
        root_source_hash=sha256_text("root"),
        text=text,
        depth=depth,
        operation_hashes=operations,
        ancestor_text_hashes=ancestors,
        root_tokenization_hash=sha256_text("root-tokens"),
        current_tokenization_hash=sha256_text("current-tokens:" + text),
        survival_report_hash=sha256_text("survival:" + text),
        enumeration_hash=sha256_text("enumeration:" + text),
        hard_invariant_report_hash=sha256_text("hard:" + text),
        surviving_root_observations=surviving,
        newly_masked_count=newly_masked,
        highest_risk_tier=0 if depth == 0 else risk,
        visible_cost=depth if visible_cost is None else visible_cost,
        token_edit_distance=depth,
    )


def _transition(parent: SearchState, child: SearchState, index: int) -> SearchTransition:
    operation_hash = child.operation_hashes[-1]
    return SearchTransition.create(
        parent=parent,
        candidate_hash=sha256_text(f"candidate-{index}-{parent.text}-{child.text}"),
        operation_hash=operation_hash,
        visible_cost_delta=1,
        child=child,
    )


class _Expander:
    def __init__(self, mapping):
        self.mapping = mapping

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def secret_access_observed(self) -> bool:
        return False

    def expand(self, state):
        return self.mapping.get(state.text_hash, ())


class _Tokenizer:
    def _pieces(self, text):
        return tuple(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text))

    def encode(self, text, add_special_tokens=True):
        return [
            int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
            for match in self._pieces(text)
        ]

    def __call__(self, text, add_special_tokens=True, return_offsets_mapping=False):
        matches = self._pieces(text)
        ids = [
            int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
            for match in matches
        ]
        output = {"input_ids": ids}
        if return_offsets_mapping:
            output["offset_mapping"] = [(match.start(), match.end()) for match in matches]
        return output


def _fake_corpus():
    tokenizer = _Tokenizer()
    identity_hash = sha256_text("fake-tokenizer")
    samples = []
    for index in range(8):
        text = f"We do not know and the result is clear item {index}."
        label = WatermarkLabel.WATERMARKED if index < 4 else WatermarkLabel.UNWATERMARKED
        samples.append(
            SimpleNamespace(
                sample_id=f"sample-{index}",
                split=CorpusSplit.ATTACK_DEVELOPMENT,
                label=label,
                text=text,
                text_sha256=sha256_text(text),
                prompt_family_id="fake-prompt",
                domain=SimpleNamespace(value="technical"),
                model=SimpleNamespace(identity_hash=identity_hash, eos_token_id=0),
                text_only_tokens=SimpleNamespace(token_ids=tuple(tokenizer.encode(text, add_special_tokens=False))),
            )
        )
    corpus = SimpleNamespace(
        artifact_hash=sha256_text("fake-corpus"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(
            samples=tuple(samples),
            manifest_hash=sha256_text("fake-manifest"),
        ),
    )
    return corpus, tokenizer


def test_exact_state_selection_uses_frozen_frontier_order() -> None:
    root = _state("root text", depth=0, surviving=10, risk=0)
    first = _state(
        "first",
        depth=1,
        surviving=7,
        newly_masked=0,
        operation_hashes=(sha256_text("op-first"),),
        ancestor_text_hashes=(root.text_hash,),
    )
    second = _state(
        "second",
        depth=1,
        surviving=7,
        newly_masked=2,
        operation_hashes=(sha256_text("op-second"),),
        ancestor_text_hashes=(root.text_hash,),
    )
    states = (first, second)
    payload = {
        "algorithm_version": "context-survival-exact-v1",
        "root_state_hash": root.search_state_hash,
        "budget": 1,
        "state_hashes": tuple(value.search_state_hash for value in states),
        "frontier_hashes": tuple(value.search_state_hash for value in states),
        "expanded_state_count": 1,
        "pruned_state_count": 0,
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    result = SearchResult(
        algorithm_version=payload["algorithm_version"],
        root_state_hash=root.search_state_hash,
        budget=1,
        states=states,
        frontier=states,
        expanded_state_count=1,
        pruned_state_count=0,
        detector_access_observed=False,
        secret_access_observed=False,
        result_hash=sha256_json(payload),
    )
    selected, status = _select_result_state(result, 1)
    assert status == SUCCESS
    assert selected == second


def test_stateful_random_replays_exactly() -> None:
    root = _state("root", depth=0, surviving=10, risk=0)
    child_a = _state(
        "a",
        depth=1,
        surviving=8,
        operation_hashes=(sha256_text("op-a"),),
        ancestor_text_hashes=(root.text_hash,),
    )
    child_b = _state(
        "b",
        depth=1,
        surviving=7,
        operation_hashes=(sha256_text("op-b"),),
        ancestor_text_hashes=(root.text_hash,),
    )
    grandchild = _state(
        "c",
        depth=2,
        surviving=5,
        operation_hashes=(child_a.operation_hashes[0], sha256_text("op-c")),
        ancestor_text_hashes=(root.text_hash, child_a.text_hash),
    )
    mapping = {
        root.text_hash: (_transition(root, child_a, 1), _transition(root, child_b, 2)),
        child_a.text_hash: (_transition(child_a, grandchild, 3),),
    }
    expander = _Expander(mapping)
    first = _stateful_random(expander, root, 2, 1234)
    second = _stateful_random(expander, root, 2, 1234)
    assert first == second


def test_plan_builder_is_deterministic_and_detector_blind() -> None:
    corpus, tokenizer = _fake_corpus()
    first = build_context_survival_plan(
        corpus,
        tokenizer,
        ngram_len=2,
        context_history_size=4,
        budgets=(1,),
        random_seed_count=2,
        beam_width=2,
        source_code_commit="test-commit",
    )
    second = build_context_survival_plan(
        corpus,
        tokenizer,
        ngram_len=2,
        context_history_size=4,
        budgets=(1,),
        random_seed_count=2,
        beam_width=2,
        source_code_commit="test-commit",
    )
    assert first["plan_hash"] == second["plan_hash"]
    assert first["variants"] == second["variants"]
    assert first["detector_access_observed"] is False
    assert first["secret_access_observed"] is False
    assert len(first["source_diagnostics"]) == 8
    policies = {row["schedule_policy"] for row in first["variants"]}
    assert STATEFUL_RANDOM_POLICY in policies
    assert COVERAGE_POLICY in policies
    assert GREEDY_POLICY in policies
    assert EXACT_B1_POLICY in policies


def test_plan_module_has_no_detector_or_secret_imports() -> None:
    path = Path(__file__).parents[1] / "fuckmark" / "experiments" / "context_survival_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = ("detector", "bayesian", "g_value", "gvalue", "watermark_key", "secret")
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert all(not any(value in name.lower() for value in forbidden) for name in names)


def test_random_comparison_aggregates_replicates_within_source() -> None:
    base = {
        "source_sample_id": "wm-1",
        "source_label": WatermarkLabel.WATERMARKED.value,
        "budget": 2,
        "realized_edit_cost": 2,
        "status": SUCCESS,
        "destroyed_root_observation_count": 4,
        "exact_survival_ratio": 0.6,
        "margin_drop": 0.1,
    }
    rows = (
        {**base, "schedule_policy": STATEFUL_RANDOM_POLICY, "exact_survival_ratio": 0.7, "margin_drop": 0.05},
        {**base, "schedule_policy": STATEFUL_RANDOM_POLICY, "exact_survival_ratio": 0.5, "margin_drop": 0.15},
        {**base, "schedule_policy": GREEDY_POLICY, "exact_survival_ratio": 0.4, "margin_drop": 0.2},
    )
    pairs = _paired_random_comparisons(rows)
    assert len(pairs) == 1
    assert pairs[0]["status"] == PAIR_STATUS_MATCHED
    assert pairs[0]["matched_random_count"] == 2
    assert abs(pairs[0]["delta_survival"] - 0.2) < 1e-12
    assert abs(pairs[0]["delta_margin"] - 0.1) < 1e-12