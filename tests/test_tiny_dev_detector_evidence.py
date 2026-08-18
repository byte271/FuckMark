from __future__ import annotations

from dataclasses import replace

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.corpus import (
    CorpusSample,
    GenerationParameters,
    GenerationTokenRecord,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    WatermarkCondition,
    WatermarkLabel,
    build_tiny_dev_corpus,
)
from fuckmark.corpus.tiny_dev_generation import build_tiny_dev_prompt_records
from fuckmark.detectors import DetectorFamily
from fuckmark.experiments.tiny_dev_detector_evidence import (
    TINY_DEV_DETECTOR_STATUS,
    TINY_DEV_HEADLINE_FPRS,
    TINY_DEV_PRIMARY_FPR,
    TinyDevDetectorEvidenceError,
    build_tiny_dev_detector_evidence,
    primary_baseline_statuses,
)
from fuckmark.hashing import sha256_json, sha256_text


_WATERMARK_HASH = sha256_json({"fixture": "tiny-dev-detector"})


def _model() -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id="fixture/model",
        model_revision="a" * 40,
        tokenizer_id="fixture/tokenizer",
        tokenizer_revision="b" * 40,
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_json({"eos_token": "<eos>"}),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=2,
        pad_token_id=None,
        add_bos_token=False,
        add_eos_token=False,
    )


def _generation(seed: int) -> GenerationParameters:
    return GenerationParameters.create(
        seed=seed,
        seed_policy_id="fixture-paired-seed-v1",
        temperature=0.8,
        top_k=50,
        top_p=0.95,
        max_new_tokens=64,
        do_sample=True,
        dtype="float32",
        device="cpu",
        backend_id="fixture",
        backend_version="1",
    )


def _tokens(identity: ModelTokenizerIdentity, pair_index: int, label_offset: int) -> GenerationTokenRecord:
    continuation = tuple(
        1000 + ((pair_index * 104729 + label_offset * 100003 + index * index * 7919 + index * 997) % 1_000_000)
        for index in range(64)
    )
    input_ids = (101, 102, 103)
    return GenerationTokenRecord.create(
        input_token_ids=input_ids,
        attention_mask=(1, 1, 1),
        generated_sequence_ids=input_ids + continuation,
        continuation_start_index=len(input_ids),
        continuation_token_ids=continuation,
        prompt_length_after_templating=3,
        model_tokenizer_identity_hash=identity.identity_hash,
    )


def _artifact():
    identity = _model()
    watermark = WatermarkCondition.create(_WATERMARK_HASH, KeySplit.DEV, "fixture-dev-key")
    prompts = build_tiny_dev_prompt_records()
    samples = []
    for pair_index, prompt in enumerate(prompts):
        generation = _generation(50_000 + pair_index)
        for label, offset in (
            (WatermarkLabel.UNWATERMARKED, 0),
            (WatermarkLabel.WATERMARKED, 1),
        ):
            tokens = _tokens(identity, pair_index, offset)
            samples.append(
                CorpusSample.create(
                    sample_id=f"{prompt.prompt_id}-{label.value}",
                    match_id=f"match-{prompt.prompt_id}",
                    prompt_id=prompt.prompt_id,
                    prompt_family_id=prompt.prompt_family_id,
                    domain=prompt.domain,
                    split=prompt.split,
                    label=label,
                    text=f"fixture {label.value} output {pair_index}",
                    model=identity,
                    generation=generation,
                    watermark=watermark,
                    target_length=64,
                    generation_tokens=tokens,
                )
            )
    return build_tiny_dev_corpus("fixture-real-tiny-dev", prompts, samples)


def _adapter() -> DeepMindReferenceAdapter:
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=5,
            keys=(11, 23, 37, 41, 53, 67, 79, 83, 97),
            context_history_size=1024,
        )
    )


def test_tiny_dev_detector_evidence_uses_real_generation_tracks_and_fixed_fprs() -> None:
    source = _artifact()
    result = build_tiny_dev_detector_evidence(
        source,
        _adapter(),
        expected_watermark_config_hash=_WATERMARK_HASH,
    )
    assert result.tiny_dev_artifact_hash == source.artifact_hash
    assert result.corpus_manifest_hash == source.manifest.manifest_hash
    assert result.headline_fprs == TINY_DEV_HEADLINE_FPRS
    assert result.primary_fpr == TINY_DEV_PRIMARY_FPR
    assert result.scientific_status == TINY_DEV_DETECTOR_STATUS
    assert tuple(value.detector_family for value in result.family_evidence) == (
        DetectorFamily.MEAN,
        DetectorFamily.WEIGHTED_MEAN,
    )
    for family in result.family_evidence:
        assert len(family.calibration_evidence) == 100
        assert len(family.attack_evidence) == 8
        assert family.calibration_bundle.scope.corpus_id == "fixture-real-tiny-dev"
        assert family.calibration_bundle.scope.token_track == "original-generation-token-ids"
        assert tuple(value.target_fpr for value in family.calibration_bundle.thresholds) == (0.05, 0.01)
        assert tuple(value.target_fpr for value in family.threshold_evaluations) == (0.05, 0.01)
        for evaluation in family.threshold_evaluations:
            assert len(evaluation.positive_results) == 4
            assert len(evaluation.negative_results) == 4
            assert evaluation.pristine_baseline.sample_count == 4


def test_tiny_dev_detector_evidence_fails_closed_on_wrong_watermark_contract() -> None:
    with pytest.raises(TinyDevDetectorEvidenceError, match="watermark configuration"):
        build_tiny_dev_detector_evidence(
            _artifact(),
            _adapter(),
            expected_watermark_config_hash="0" * 64,
        )


def test_tiny_dev_detector_evidence_hash_is_tamper_evident() -> None:
    result = build_tiny_dev_detector_evidence(
        _artifact(),
        _adapter(),
        expected_watermark_config_hash=_WATERMARK_HASH,
    )
    with pytest.raises(ValueError, match="artifact_hash"):
        replace(result, artifact_hash="0" * 64)


def test_primary_baseline_statuses_cover_both_detector_families() -> None:
    result = build_tiny_dev_detector_evidence(
        _artifact(),
        _adapter(),
        expected_watermark_config_hash=_WATERMARK_HASH,
    )
    statuses = primary_baseline_statuses(result)
    assert tuple(value[0] for value in statuses) == (
        DetectorFamily.MEAN,
        DetectorFamily.WEIGHTED_MEAN,
    )
