from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import replace
from pathlib import Path

import pytest

from fuckmark.experiments.exact_survival_greedy import schedule_exact_survival_greedy
from fuckmark.hashing import sha256_text
from fuckmark.transforms.effectiveness_profile import CONTENT_REGION_GENERAL_SPACING_RULE_ID
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import GeneralWordSpacingRule


class SpaceSensitiveTokenizer:
    def _pieces(self, text: str):
        words = tuple(re.finditer(r"[A-Za-z]+", text))
        output = []
        previous_end = 0
        for index, match in enumerate(words):
            start, end = match.span()
            if index == 0:
                output.append((match.group(), (start, end)))
            else:
                gap = text[previous_end:start]
                if not gap or any(character != " " for character in gap):
                    raise ValueError("fixture tokenizer only supports space-separated words")
                for position in range(previous_end, start - 1):
                    output.append((" ", (position, position + 1)))
                output.append((text[start - 1:end], (start - 1, end)))
            previous_end = end
        if previous_end != len(text):
            raise ValueError("fixture text must end with a word")
        return tuple(output)

    @staticmethod
    def _token_id(piece: str) -> int:
        return int.from_bytes(hashlib.sha256(piece.encode()).digest()[:4], "big")

    def encode(self, text: str, *, add_special_tokens: bool = True):
        return [self._token_id(piece) for piece, _ in self._pieces(text)]

    def __call__(self, text: str, *, add_special_tokens: bool = True, return_offsets_mapping: bool = False):
        pieces = self._pieces(text)
        output = {"input_ids": [self._token_id(piece) for piece, _ in pieces]}
        if return_offsets_mapping:
            output["offset_mapping"] = [offset for _, offset in pieces]
        return output


def _result(*, budget: int = 2):
    text = "alpha beta gamma delta epsilon zeta"
    registry = TransformRegistry(
        (GeneralWordSpacingRule.create(CONTENT_REGION_GENERAL_SPACING_RULE_ID),)
    )
    enumeration = registry.enumerate(text)
    result = schedule_exact_survival_greedy(
        source_sample_id="fixture-exact-greedy",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=SpaceSensitiveTokenizer(),
        tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
        ngram_len=3,
        budget=budget,
    )
    return text, registry, enumeration, result


def test_exact_survival_greedy_reaches_full_root_destruction_under_fixture_budget() -> None:
    _, _, _, result = _result(budget=2)
    assert result.root_observation_count == 4
    assert result.exact_destroyed_observation_count == 4
    assert result.exact_surviving_observation_count == 0
    assert result.selected_candidate_count <= 2
    assert result.exact_destruction_ratio == 1.0
    assert result.detector_access_observed is False
    assert result.secret_access_observed is False


def test_exact_survival_greedy_steps_have_strict_positive_monotonic_gain() -> None:
    _, _, _, result = _result(budget=3)
    previous = 0
    total_gain = 0
    for index, step in enumerate(result.steps):
        assert step.step_index == index
        assert step.marginal_exact_destruction > 0
        assert step.exact_destroyed_count > previous
        total_gain += step.marginal_exact_destruction
        previous = step.exact_destroyed_count
    assert total_gain == result.exact_destroyed_observation_count
    assert result.policy_saturated is True


def test_exact_survival_greedy_is_deterministic() -> None:
    _, _, _, first = _result(budget=2)
    _, _, _, second = _result(budget=2)
    assert first.selection_order == second.selection_order
    assert first.selected_candidate_ids == second.selected_candidate_ids
    assert first.result_hash == second.result_hash


def test_exact_survival_greedy_result_hash_is_tamper_evident() -> None:
    _, _, _, result = _result(budget=2)
    with pytest.raises(ValueError, match="result_hash"):
        replace(result, result_hash="0" * 64)


def test_exact_survival_greedy_module_has_no_detector_imports() -> None:
    path = Path(__file__).parents[1] / "fuckmark" / "experiments" / "exact_survival_greedy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert all("detector" not in name.lower() for name in names), names
