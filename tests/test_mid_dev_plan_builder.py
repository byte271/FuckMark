from __future__ import annotations

import hashlib
import os
import re

import pytest

from fuckmark.corpus.generation import GenerationParameters, WatermarkCondition
from fuckmark.corpus.identity import ModelTokenizerIdentity, PaddingSide
from fuckmark.corpus.mid_dev_generation import (
    MID_DEV_SEED_POLICY_ID,
    MidDevGeneratedContinuation,
    build_real_mid_dev_corpus,
)
from fuckmark.corpus.schema import KeySplit
from fuckmark.experiments.mid_dev_context_survival import (
    MID_DEV_BUDGETS,
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
)
from fuckmark.experiments.mid_dev_plan_builder import build_mid_dev_context_survival_plan
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.beam_v2 import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


pytestmark = pytest.mark.skipif(
    os.environ.get("FUCKMARK_RUN_MIDDEV_FULL_MATRIX") != "1",
    reason="full MidDev matrix runs in its dedicated workflow",
)


class _PlannerTokenizer:
    def _pieces(self, text: str):
        return tuple(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text))

    def encode(self, text: str, add_special_tokens: bool = True):
        return [
            int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
            for match in self._pieces(text)
        ]

    def __call__(
        self,
        text: str,
        add_special_tokens: bool = True,
        return_offsets_mapping: bool = False,
    ):
        matches = self._pieces(text)
        output = {
            "input_ids": [
                int.from_bytes(hashlib.sha256(match.group(0).encode()).digest()[:4], "big")
                for match in matches
            ]
        }
        if return_offsets_mapping:
            output["offset_mapping"] = [(match.start(), match.end()) for match in matches]
        return output


class _PlannerBackend:
    def __init__(self, tokenizer: _PlannerTokenizer) -> None:
        revision = "b" * 40
        self._tokenizer = tokenizer
        self._identity = ModelTokenizerIdentity.create(
            model_id="fake-middev-planner-model",
            model_revision=revision,
            tokenizer_id="fake-middev-planner-model",
            tokenizer_revision=revision,
            chat_template_present=False,
            chat_template_hash=sha256_text(""),
            special_token_map_hash=sha256_json({}),
            padding_side=PaddingSide.LEFT,
            bos_token_id=1,
            eos_token_id=2,
            pad_token_id=2,
            add_bos_token=False,
            add_eos_token=False,
        )
        self._watermark = WatermarkCondition.create(
            sha256_text("fake-middev-planner-watermark"),
            KeySplit.DEV,
            "fake-middev-planner-dev-key",
        )

    @property
    def model_identity(self) -> ModelTokenizerIdentity:
        return self._identity

    @property
    def watermark_condition(self) -> WatermarkCondition:
        return self._watermark

    def generation_parameters(self, seed: int, target_length: int) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id=MID_DEV_SEED_POLICY_ID,
            temperature=0.8,
            top_k=50,
            top_p=0.95,
            max_new_tokens=target_length,
            do_sample=True,
            dtype="float32",
            device="cpu",
            backend_id="fake-middev-planner",
            backend_version="v1",
        )

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation:
        label = "watermarked" if watermarked else "control"
        text = f"We do not know. Source {seed} {label}."
        text_only = tuple(self._tokenizer.encode(text, add_special_tokens=False))
        base = seed * 1000 + (100_000_000 if watermarked else 200_000_000)
        continuation = tuple(base + index for index in range(target_length))
        return MidDevGeneratedContinuation(
            text=text,
            input_token_ids=(11, 12, 13),
            attention_mask=(1, 1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=text_only,
        )


def test_full_fake_middev_planner_emits_complete_detector_blind_matrix() -> None:
    tokenizer = _PlannerTokenizer()
    artifact = build_real_mid_dev_corpus(_PlannerBackend(tokenizer))
    plan, traces = build_mid_dev_context_survival_plan(
        artifact,
        tokenizer,
        source_code_commit="c" * 40,
    )
    expected_rows_per_sample = 1 + len(MID_DEV_BUDGETS) * (2 + MID_DEV_RANDOM_REPLICATES + 1) + 2
    assert expected_rows_per_sample == 79
    assert len(plan.rows) == 72 * 79 == 5688
    assert len(plan.quality_rows) == len(plan.rows)
    assert len(plan.compute_rows) == len(plan.rows)
    assert len(traces.traces) == len(plan.rows)
    assert plan.selection_attestation.attested_expander_count == 72
    assert plan.selection_attestation.detector_access_observed is False
    assert plan.selection_attestation.secret_access_observed is False
    assert plan.selection_attestation.detector_query_count == 0
    assert plan.selection_attestation.secret_query_count == 0
    assert plan.selection_config.beam_algorithm_version == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
    assert traces.plan_hash == plan.plan_hash
    assert {row.selection_trace_hash for row in plan.rows} == {
        trace.trace_hash for trace in traces.traces
    }

    sample_ids = {row.sample_id for row in plan.rows}
    assert len(sample_ids) == 72
    for sample_id in sample_ids:
        sample_rows = tuple(row for row in plan.rows if row.sample_id == sample_id)
        assert len(sample_rows) == 79
        no_op = tuple(row for row in sample_rows if row.condition is MidDevCondition.NO_OP)
        assert len(no_op) == 1
        for budget in MID_DEV_BUDGETS:
            random_rows = tuple(
                row
                for row in sample_rows
                if row.condition is MidDevCondition.RANDOM_SAFE and row.budget == budget
            )
            assert len(random_rows) == MID_DEV_RANDOM_REPLICATES
            assert {row.replicate for row in random_rows} == set(range(MID_DEV_RANDOM_REPLICATES))
            beam_rows = tuple(
                row
                for row in sample_rows
                if row.condition is MidDevCondition.CONTEXT_SURVIVAL_BEAM and row.budget == budget
            )
            assert len(beam_rows) == (1 if budget in (4, 6) else 0)
