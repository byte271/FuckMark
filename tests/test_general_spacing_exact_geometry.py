from __future__ import annotations

import hashlib
import re
from dataclasses import replace

import pytest

from fuckmark.experiments.general_spacing_exact_geometry import (
    diagnose_selected_candidate_geometry,
    diagnose_unselected_exact_marginals,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import GeneralWordSpacingRule


class SpaceSensitiveTokenizer:
    def _pieces(self, text: str) -> tuple[tuple[str, tuple[int, int]], ...]:
        words = tuple(re.finditer(r"[A-Za-z]+", text))
        if not words:
            return ()
        output: list[tuple[str, tuple[int, int]]] = []
        previous_end = 0
        for index, match in enumerate(words):
            start, end = match.span()
            if index == 0:
                if start != 0:
                    raise ValueError("fixture text must start with a word")
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

    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        return [self._token_id(piece) for piece, _ in self._pieces(text)]

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
        return_offsets_mapping: bool = False,
    ) -> dict[str, object]:
        pieces = self._pieces(text)
        output: dict[str, object] = {
            "input_ids": [self._token_id(piece) for piece, _ in pieces],
        }
        if return_offsets_mapping:
            output["offset_mapping"] = [offset for _, offset in pieces]
        return output


def _registry() -> TransformRegistry:
    return TransformRegistry(
        (GeneralWordSpacingRule.create("surface-space-after-any-word"),)
    )


def _fixture():
    text = "alpha beta gamma delta epsilon zeta"
    registry = _registry()
    enumeration = registry.enumerate(text)
    return text, registry, enumeration


def _diagnose(word: str):
    text, registry, enumeration = _fixture()
    candidate = next(value for value in enumeration.candidates if value.source_text == word)
    return diagnose_selected_candidate_geometry(
        source_sample_id=f"fixture-{word}",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        selected_candidate_ids=(candidate.candidate_id,),
        tokenizer=SpaceSensitiveTokenizer(),
        tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
        ngram_len=3,
    )


def test_general_spacing_proxy_overstates_interior_boundary_destruction() -> None:
    diagnostic = _diagnose("gamma")
    assert diagnostic.root_observation_count == 4
    assert diagnostic.proxy_covered_observation_count == 3
    assert diagnostic.exact_destroyed_observation_count == 2
    assert diagnostic.exact_surviving_observation_count == 2
    assert diagnostic.exact_minus_proxy_count == -1
    assert diagnostic.proxy_coverage_ratio == 0.75
    assert diagnostic.exact_destruction_ratio == 0.5
    assert diagnostic.detector_access_observed is False
    assert diagnostic.secret_access_observed is False


def test_general_spacing_proxy_matches_boundary_case_without_extra_left_window() -> None:
    diagnostic = _diagnose("alpha")
    assert diagnostic.root_observation_count == 4
    assert diagnostic.proxy_covered_observation_count == 1
    assert diagnostic.exact_destroyed_observation_count == 1
    assert diagnostic.exact_minus_proxy_count == 0


def test_zero_proxy_marginal_can_hide_positive_exact_destruction_gain() -> None:
    text, registry, enumeration = _fixture()
    gamma = next(value for value in enumeration.candidates if value.source_text == "gamma")
    diagnostic = diagnose_unselected_exact_marginals(
        source_sample_id="fixture-hidden-gain",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        selected_candidate_ids=(gamma.candidate_id,),
        tokenizer=SpaceSensitiveTokenizer(),
        tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
        ngram_len=3,
    )
    rows_by_word = {
        next(value.source_text for value in enumeration.candidates if value.candidate_id == row.candidate_id): row
        for row in diagnostic.rows
    }
    beta = rows_by_word["beta"]
    assert beta.proxy_marginal_gain == 0
    assert beta.exact_marginal_gain == 1
    assert beta.hidden_exact_gain is True
    assert diagnostic.hidden_exact_gain_count >= 1
    assert diagnostic.maximum_hidden_exact_gain >= 1
    assert diagnostic.detector_access_observed is False
    assert diagnostic.secret_access_observed is False


def test_exact_spacing_geometry_diagnostic_hash_is_tamper_evident() -> None:
    diagnostic = _diagnose("gamma")
    with pytest.raises(ValueError, match="diagnostic_hash"):
        replace(diagnostic, diagnostic_hash="0" * 64)
