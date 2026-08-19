from __future__ import annotations

import pytest

from fuckmark.corpus.generation import GenerationParameters, WatermarkCondition
from fuckmark.corpus.identity import ModelTokenizerIdentity, PaddingSide
from fuckmark.corpus.sample import CorpusSample
from fuckmark.corpus.schema import CorpusDomain, CorpusSplit, KeySplit, WatermarkLabel
from fuckmark.corpus.tokenization import GenerationTokenRecord, TextOnlyTokenRecord
from fuckmark.experiments.detector_opportunity_audit import (
    CalibrationRegimeMode,
    DetectorOpportunityAuditError,
    build_detector_opportunity_audit_artifact,
    build_detector_opportunity_audit_row,
    freeze_calibration_regime_decision,
)
from fuckmark.hashing import sha256_json, sha256_text


def _model() -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id="test/model", model_revision="a" * 40, tokenizer_id="test/tokenizer", tokenizer_revision="b" * 40,
        chat_template_present=False, chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_json({"eos_token_id": 2, "pad_token_id": 0}),
        padding_side=PaddingSide.LEFT, bos_token_id=1, eos_token_id=2, pad_token_id=0,
        add_bos_token=False, add_eos_token=False,
    )


def _sample(sample_id: str, target_length: int, text_only_ids: tuple[int, ...], *, text: str) -> CorpusSample:
    model = _model()
    continuation = tuple(range(1000, 1000 + target_length))
    generation_tokens = GenerationTokenRecord.create(
        input_token_ids=(9,), attention_mask=(1,), generated_sequence_ids=(9,) + continuation,
        continuation_start_index=1, continuation_token_ids=continuation, prompt_length_after_templating=1,
        model_tokenizer_identity_hash=model.identity_hash,
    )
    text_only_tokens = TextOnlyTokenRecord.create(
        source_text_sha256=sha256_text(text), token_ids=text_only_ids, model_tokenizer_identity_hash=model.identity_hash,
    )
    generation = GenerationParameters.create(
        seed=target_length, seed_policy_id="test-opportunity-audit-seed-v1", temperature=1.0,
        top_k=0, top_p=1.0, max_new_tokens=target_length, do_sample=True, dtype="float32",
        device="cpu", backend_id="test-backend", backend_version="v1",
    )
    watermark = WatermarkCondition.create(
        watermark_config_hash=sha256_json({"ngram_len": 3, "context_history_size": 16}),
        key_split=KeySplit.DEV, key_id="dev-test-key",
    )
    return CorpusSample.create(
        sample_id=sample_id, match_id=f"match-{sample_id}", prompt_id=f"prompt-{sample_id}",
        prompt_family_id="cal-test", domain=CorpusDomain.GENERAL_EXPLANATORY,
        split=CorpusSplit.THRESHOLD_CALIBRATION, label=WatermarkLabel.UNWATERMARKED, text=text,
        model=model, generation=generation, watermark=watermark, target_length=target_length,
        generation_tokens=generation_tokens, text_only_tokens=text_only_tokens,
    )


def test_row_separates_generation_text_only_and_effective_observation_counts() -> None:
    token_ids = (10, 11, 12, 10, 11, 13, 2, 99)
    sample = _sample("cal-128-a", 128, token_ids, text="abcdefgh")
    row = build_detector_opportunity_audit_row(sample, ngram_len=3, context_history_size=16, retokenize=lambda text: token_ids)
    assert row.requested_generation_length == 128
    assert row.generation_continuation_token_count == 128
    assert row.text_only_token_count == 8
    assert row.root_candidate_observation_count == 6
    assert row.root_valid_eligible_observation_count == 3
    assert row.repeated_context_masked_count == 1
    assert row.eos_masked_count == 2
    assert row.tokenizer_round_trip_ok is True
    assert row.model_revision == "a" * 40
    assert row.tokenizer_revision == "b" * 40


def test_row_records_round_trip_failure_without_hiding_it() -> None:
    token_ids = (10, 11, 12, 13, 14)
    sample = _sample("cal-128-b", 128, token_ids, text="roundtrip")
    row = build_detector_opportunity_audit_row(sample, ngram_len=3, context_history_size=16, retokenize=lambda text: (10, 11, 12, 99))
    assert row.tokenizer_round_trip_ok is False


def test_artifact_requires_both_nominal_strata_and_preserves_quantiles() -> None:
    sample_128 = _sample("cal-128-c", 128, (10, 11, 12, 13, 14, 15, 16, 17), text="one")
    sample_256 = _sample("cal-256-c", 256, (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31), text="two")
    tokens_by_text = {sample_128.text: sample_128.text_only_tokens.token_ids, sample_256.text: sample_256.text_only_tokens.token_ids}
    artifact = build_detector_opportunity_audit_artifact((sample_256, sample_128), ngram_len=3, context_history_size=16, retokenize=tokens_by_text.__getitem__)
    assert tuple(row.sample_id for row in artifact.rows) == ("cal-128-c", "cal-256-c")
    assert tuple(summary.nominal_target_length for summary in artifact.summaries) == (128, 256)
    assert artifact.summaries[0].text_only_tokens.median == 8.0
    assert artifact.summaries[1].eligible_observations.median == 10.0
    assert artifact.tokenizer_round_trip_all_ok is True
    with pytest.raises(DetectorOpportunityAuditError):
        build_detector_opportunity_audit_artifact((sample_128,), ngram_len=3, context_history_size=16, retokenize=tokens_by_text.__getitem__)


def test_regime_decision_keeps_nominal_strata_when_opportunity_is_separated() -> None:
    sample_128 = _sample("cal-128-d", 128, (10, 11, 12, 13, 14, 15, 16, 17), text="alpha")
    sample_256 = _sample("cal-256-d", 256, (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31), text="beta")
    tokens = {sample_128.text: sample_128.text_only_tokens.token_ids, sample_256.text: sample_256.text_only_tokens.token_ids}
    decision = freeze_calibration_regime_decision(build_detector_opportunity_audit_artifact(
        (sample_128, sample_256), ngram_len=3, context_history_size=16, retokenize=tokens.__getitem__,
    ))
    assert decision.mode is CalibrationRegimeMode.NOMINAL_TARGET_LENGTH
    assert decision.eligible_bin_upper_bounds == ()
    assert decision.regime_id_for(128, 6) == "nominal-128"
    assert decision.regime_id_for(256, 10) == "nominal-256"


def test_regime_decision_falls_back_when_effective_opportunity_overlaps() -> None:
    token_ids = (10, 11, 12, 13, 14, 15, 16, 17)
    sample_128 = _sample("cal-128-e", 128, token_ids, text="gamma")
    sample_256 = _sample("cal-256-e", 256, token_ids, text="delta")
    tokens = {sample_128.text: token_ids, sample_256.text: token_ids}
    decision = freeze_calibration_regime_decision(build_detector_opportunity_audit_artifact(
        (sample_128, sample_256), ngram_len=3, context_history_size=16, retokenize=tokens.__getitem__,
    ))
    assert decision.mode is CalibrationRegimeMode.ELIGIBLE_OBSERVATION_BINS
    assert decision.nominal_strata_pass is False
    assert decision.eligible_bin_upper_bounds == ()
    assert decision.regime_id_for(128, 6) == "eligible-00"


def test_regime_freeze_rejects_round_trip_failures() -> None:
    sample_128 = _sample("cal-128-f", 128, (10, 11, 12, 13, 14, 15, 16, 17), text="epsilon")
    sample_256 = _sample("cal-256-f", 256, (20, 21, 22, 23, 24, 25, 26, 27), text="zeta")
    tokens = {sample_128.text: sample_128.text_only_tokens.token_ids, sample_256.text: (20, 21, 22, 99)}
    artifact = build_detector_opportunity_audit_artifact((sample_128, sample_256), ngram_len=3, context_history_size=16, retokenize=tokens.__getitem__)
    assert artifact.tokenizer_round_trip_all_ok is False
    with pytest.raises(DetectorOpportunityAuditError):
        freeze_calibration_regime_decision(artifact)
