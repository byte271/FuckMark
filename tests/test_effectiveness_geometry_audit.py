from __future__ import annotations

import hashlib
import re

import pytest

from fuckmark.experiments.effectiveness_geometry_audit import build_effectiveness_geometry_audit
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

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
        return_offsets_mapping: bool = False,
    ):
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
        "plan_hash": sha256_text("fixture-plan"),
        "ruleset_hash": registry.ruleset_hash,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "variants": [
            {
                "variant_hash": sha256_text("fixture-variant"),
                "source_sample_id": "fixture-source",
                "source_text_hash": sha256_text(text),
                "enumeration_hash": enumeration.enumeration_hash,
                "selected_candidate_ids": [gamma.candidate_id],
                "transformed_text_hash": sha256_text(transformed.output_text),
                "transform_trace_hash": transformed.trace.trace_hash,
                "scheduler_covered_interval_size": 3,
            }
        ],
    }
    return text, registry, plan


def test_plan_level_audit_captures_proxy_overstatement_and_hidden_exact_gain() -> None:
    text, registry, plan = _fixture()
    artifact = build_effectiveness_geometry_audit(
        plan=plan,
        source_texts={"fixture-source": text},
        registry=registry,
        tokenizer=SpaceSensitiveTokenizer(),
        tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
        ngram_len=3,
    )
    summary = artifact["summary"]
    row = artifact["rows"][0]
    assert summary["variant_count"] == 1
    assert summary["proxy_covered_observation_count"] == 3
    assert summary["exact_destroyed_observation_count"] == 2
    assert summary["exact_minus_proxy_count"] == -1
    assert summary["proxy_overstatement_row_count"] == 1
    assert summary["hidden_exact_gain_row_count"] == 1
    assert summary["hidden_exact_gain_candidate_count"] >= 1
    assert row["hidden_exact_gain_count"] >= 1
    assert artifact["selection_detector_access_observed"] is False
    assert artifact["selection_secret_access_observed"] is False


def test_plan_level_audit_rejects_transform_replay_drift() -> None:
    text, registry, plan = _fixture()
    plan["variants"][0]["transformed_text_hash"] = "0" * 64
    with pytest.raises(ValueError, match="transformed_text_hash"):
        build_effectiveness_geometry_audit(
            plan=plan,
            source_texts={"fixture-source": text},
            registry=registry,
            tokenizer=SpaceSensitiveTokenizer(),
            tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
            ngram_len=3,
        )


def test_plan_level_audit_rejects_contaminated_selection_attestation() -> None:
    text, registry, plan = _fixture()
    plan["detector_access_observed"] = True
    with pytest.raises(ValueError, match="detector-blind"):
        build_effectiveness_geometry_audit(
            plan=plan,
            source_texts={"fixture-source": text},
            registry=registry,
            tokenizer=SpaceSensitiveTokenizer(),
            tokenizer_identity_hash=sha256_text("space-sensitive-tokenizer-v1"),
            ngram_len=3,
        )
