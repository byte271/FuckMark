from __future__ import annotations

import hashlib
import re

import pytest

from fuckmark.experiments.effectiveness_exact_greedy_audit import build_effectiveness_exact_greedy_audit
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
                for position in range(previous_end, start - 1):
                    output.append((" ", (position, position + 1)))
                output.append((text[start - 1:end], (start - 1, end)))
            previous_end = end
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


def _fixture():
    text = "alpha beta gamma delta epsilon zeta"
    registry = TransformRegistry(
        (GeneralWordSpacingRule.create(CONTENT_REGION_GENERAL_SPACING_RULE_ID),)
    )
    enumeration = registry.enumerate(text)
    gamma = next(candidate for candidate in enumeration.candidates if candidate.source_text == "gamma")
    transformed = registry.apply(enumeration, (gamma.candidate_id,))
    plan = {
        "plan_hash": sha256_text("fixture-exact-greedy-plan"),
        "ruleset_hash": registry.ruleset_hash,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "variants": [
            {
                "variant_hash": sha256_text("fixture-exact-greedy-variant"),
                "source_sample_id": "fixture-source",
                "source_label": "watermarked",
                "domain": "fixture",
                "source_text_hash": sha256_text(text),
                "enumeration_hash": enumeration.enumeration_hash,
                "candidate_count": len(enumeration.candidates),
                "budget": 2,
                "realized_edit_cost": 1,
                "selected_candidate_ids": [gamma.candidate_id],
                "transformed_text_hash": sha256_text(transformed.output_text),
            }
        ],
    }
    return text, registry, plan


def test_paired_exact_greedy_audit_improves_known_proxy_fixture() -> None:
    text, registry, plan = _fixture()
    artifact = build_effectiveness_exact_greedy_audit(
        plan=plan,
        source_texts={"fixture-source": text},
        registry=registry,
        tokenizer=SpaceSensitiveTokenizer(),
        tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
        ngram_len=3,
    )
    row = artifact["rows"][0]
    summary = artifact["summary"]
    assert row["baseline_exact_destroyed_observation_count"] == 2
    assert row["exact_greedy_destroyed_observation_count"] == 4
    assert row["exact_destruction_gain"] == 2
    assert row["same_selected_set"] is False
    assert summary["improved_row_count"] == 1
    assert summary["regressed_row_count"] == 0
    assert summary["exact_destruction_gain"] == 2
    assert artifact["detector_access_observed"] is False
    assert artifact["secret_access_observed"] is False


def test_paired_exact_greedy_audit_rejects_source_hash_drift() -> None:
    text, registry, plan = _fixture()
    plan["variants"][0]["source_text_hash"] = "0" * 64
    with pytest.raises(ValueError, match="source text hash"):
        build_effectiveness_exact_greedy_audit(
            plan=plan,
            source_texts={"fixture-source": text},
            registry=registry,
            tokenizer=SpaceSensitiveTokenizer(),
            tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
            ngram_len=3,
        )


def test_paired_exact_greedy_audit_rejects_contaminated_baseline() -> None:
    text, registry, plan = _fixture()
    plan["secret_access_observed"] = True
    with pytest.raises(ValueError, match="detector-blind and key-blind"):
        build_effectiveness_exact_greedy_audit(
            plan=plan,
            source_texts={"fixture-source": text},
            registry=registry,
            tokenizer=SpaceSensitiveTokenizer(),
            tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
            ngram_len=3,
        )
