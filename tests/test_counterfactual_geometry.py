from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import pytest

from fuckmark.geometry import CounterfactualGeometryEngine, GeometryConfig, GeometryResourceLimitError
from fuckmark.hashing import sha256_text


class ToyTokenizer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        self.calls.append((text, add_special_tokens))
        pieces = re.findall(r"[A-Za-z]+|\d+|[^\w\s]", text)
        return [int.from_bytes(hashlib.sha256(piece.encode()).digest()[:4], "big") for piece in pieces]


def _engine(*, ngram_len: int = 3, policy=None, cache: bool = True, max_cells: int = 4_500_000):
    tokenizer = ToyTokenizer()
    config = GeometryConfig.create(
        tokenizer_identity_hash=sha256_text("toy-tokenizer-v1"),
        ngram_len=ngram_len,
        repetition_mask_policy_id="test-policy-v1" if policy else "all-eligible-v1",
    )
    return tokenizer, CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=config,
        eligibility_policy=policy,
        enable_cache=cache,
        max_alignment_cells=max_cells,
    )


def _evaluate(engine, root, output: str, *, current: str | None = None, candidate: str = "test"):
    return engine.evaluate_output(
        root=root,
        current_text=root.source_text if current is None else current,
        output_text=output,
        candidate_id=candidate,
        rule_hash=sha256_text("rule:" + candidate),
        visible_cost_class=0,
        family="test-family",
        tier=0,
    )


def test_identity_replay_hash_and_generated_only_tokenization() -> None:
    tokenizer, engine = _engine()
    root = engine.build_root(source_sample_id="identity", source_text="A B C D E")
    first = _evaluate(engine, root, root.source_text, candidate="identity")
    second = _evaluate(engine, root, root.source_text, candidate="identity")
    assert first.survival_ratio == 1.0
    assert first.destroyed_count == 0
    assert first.geometry_hash == second.geometry_hash
    assert first.counterfactual_hash == second.counterfactual_hash
    assert engine.cache_hit_count > 0
    assert tokenizer.calls
    assert all(add_special_tokens is False for _, add_special_tokens in tokenizer.calls)
    assert engine.detector_access_observed is False


def test_local_substitution_destroys_only_crossing_windows() -> None:
    _, engine = _engine(ngram_len=3)
    root = engine.build_root(source_sample_id="substitution", source_text="A B C D E F G")
    result = _evaluate(engine, root, "A B C X E F G")
    assert result.root_observation_count == 5
    assert result.surviving_count == 2
    assert result.destroyed_count == 3
    assert result.unmapped_count == 3


def test_insertion_allows_distant_contexts_to_resume() -> None:
    _, engine = _engine(ngram_len=3)
    root = engine.build_root(source_sample_id="insertion", source_text="A B C D E F G")
    result = _evaluate(engine, root, "A B X C D E F G")
    assert result.root_observation_count == 5
    assert result.surviving_count == 3
    assert result.destroyed_count == 2
    assert result.token_edit_distance == 1


def test_deletion_allows_distant_contexts_to_resume() -> None:
    _, engine = _engine(ngram_len=3)
    root = engine.build_root(source_sample_id="deletion", source_text="A B C D E F G")
    result = _evaluate(engine, root, "A B D E F G")
    assert result.root_observation_count == 5
    assert result.surviving_count == 2
    assert result.destroyed_count == 3
    assert result.token_edit_distance == 1


def test_duplicate_occurrence_is_not_recovered_from_another_copy() -> None:
    _, engine = _engine(ngram_len=3)
    root = engine.build_root(source_sample_id="duplicate", source_text="A B C X A B C")
    result = _evaluate(engine, root, "X A B C")
    # The first A-B-C occurrence was deleted. Its identical surviving sibling cannot stand in for it.
    assert result.root_observation_count == 5
    assert result.surviving_count == 2
    assert result.destroyed_count == 3


def test_ambiguous_duplicate_alignment_fails_closed() -> None:
    _, engine = _engine(ngram_len=2)
    root = engine.build_root(source_sample_id="ambiguous", source_text="A B A B")
    result = _evaluate(engine, root, "A B")
    assert result.surviving_count == 0
    assert result.destroyed_count == 3
    assert result.ambiguous_count > 0


def test_public_mask_callback_can_create_newly_masked_root_observation() -> None:
    def unique_windows_only(tokens, config):
        windows = [tuple(tokens[i : i + config.ngram_len]) for i in range(len(tokens) - config.ngram_len + 1)]
        return tuple(windows.count(window) == 1 for window in windows)

    _, engine = _engine(ngram_len=2, policy=unique_windows_only)
    root = engine.build_root(source_sample_id="mask", source_text="A B C D")
    result = _evaluate(engine, root, "A B C D A B")
    assert result.newly_masked_count == 1
    assert result.surviving_count == 2
    assert result.destroyed_count == 1


def test_same_final_text_has_same_geometry_across_paths() -> None:
    _, engine = _engine(ngram_len=2)
    root = engine.build_root(source_sample_id="path", source_text="A B C D")
    first = _evaluate(engine, root, "A X C D", current="A B C D", candidate="path-one")
    second = _evaluate(engine, root, "A X C D", current="A Y C D", candidate="path-two")
    assert first.geometry_hash == second.geometry_hash
    assert first.survival_report.report_hash == second.survival_report.report_hash
    assert first.counterfactual_hash != second.counterfactual_hash


def test_cache_on_and_off_produce_identical_geometry() -> None:
    _, cached = _engine(ngram_len=2, cache=True)
    _, uncached = _engine(ngram_len=2, cache=False)
    root_cached = cached.build_root(source_sample_id="cache", source_text="A B C D E")
    root_uncached = uncached.build_root(source_sample_id="cache", source_text="A B C D E")
    a = _evaluate(cached, root_cached, "A B X C D E")
    b = _evaluate(uncached, root_uncached, "A B X C D E")
    assert a.geometry_hash == b.geometry_hash
    assert a.survival_report.report_hash == b.survival_report.report_hash


def test_resource_limit_is_explicit_and_deterministic() -> None:
    _, engine = _engine(ngram_len=2, max_cells=20)
    root = engine.build_root(source_sample_id="limit", source_text="A B C")
    with pytest.raises(GeometryResourceLimitError, match="exceeding max_alignment_cells=20"):
        _evaluate(engine, root, "A B C D E")


def test_hard_invariant_failure_is_rejected_before_geometry() -> None:
    _, engine = _engine(ngram_len=2)
    root = engine.build_root(source_sample_id="hard", source_text="A B C")
    with pytest.raises(ValueError, match="hard invariants must pass"):
        engine.evaluate_output(
            root=root,
            current_text=root.source_text,
            output_text="A X C",
            candidate_id="bad",
            rule_hash=sha256_text("bad"),
            visible_cost_class=0,
            family="test-family",
            tier=0,
            hard_invariant_status="FAIL",
        )


def test_geometry_package_has_no_detector_imports() -> None:
    package = Path(__file__).parents[1] / "fuckmark" / "geometry"
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all("detector" not in name.lower() for name in names), (path, names)
