from __future__ import annotations

from .adapters import HuggingFaceSynthIDAdapter
from .corpus import CorpusSample, CorpusSplit, WatermarkLabel
from .detectors import CalibrationScope, ComparisonOperator, calibrate_detector, weighted_mean_evidence
from .native_observations import build_native_observations


TEXT_ONLY_CALIBRATION_POPULATION_ID = "tiny-dev-threshold-calibration-unwatermarked-text-only-v1"
TEXT_ONLY_LENGTH_POLICY_ID = "target-64-text-only-unpadded-v1"
TEXT_ONLY_TOKEN_TRACK = "text_only"
TEXT_ONLY_PROMPT_BOUNDARY_MODE = "continuation_only"
PRIMARY_TARGET_FPR = 0.01


class TextOnlyCalibrationError(ValueError):
    pass


def calibration_negatives(corpus) -> tuple[CorpusSample, ...]:
    values = tuple(
        sorted(
            (
                sample
                for sample in corpus.manifest.samples
                if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
                and sample.label is WatermarkLabel.UNWATERMARKED
            ),
            key=lambda value: value.sample_id,
        )
    )
    if len(values) != 100:
        raise TextOnlyCalibrationError("text-only calibration requires exactly 100 negative samples")
    return values


def encode_text(tokenizer, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        if len(ids) != 1:
            raise TextOnlyCalibrationError("unexpected batched tokenizer output")
        ids = ids[0]
    output = tuple(int(value) for value in ids)
    if not output:
        raise TextOnlyCalibrationError("tokenizer produced an empty transformed token sequence")
    return output


def text_only_weighted_evidence(sample: CorpusSample, adapter: HuggingFaceSynthIDAdapter):
    if sample.text_only_tokens is None:
        raise TextOnlyCalibrationError(f"sample {sample.sample_id} lacks text-only tokens")
    eos = sample.model.eos_token_id
    if eos is None:
        raise TextOnlyCalibrationError("tokenizer must define eos_token_id")
    batch = build_native_observations(sample.sample_id, sample.text_only_tokens.token_ids, eos, adapter)
    return weighted_mean_evidence(batch)


def text_only_calibration(corpus, adapter: HuggingFaceSynthIDAdapter):
    negatives = calibration_negatives(corpus)
    evidence = tuple(text_only_weighted_evidence(sample, adapter) for sample in negatives)
    scope = CalibrationScope.create(
        corpus_id=corpus.manifest.corpus_id,
        population_id=TEXT_ONLY_CALIBRATION_POPULATION_ID,
        length_policy_id=TEXT_ONLY_LENGTH_POLICY_ID,
        token_track=TEXT_ONLY_TOKEN_TRACK,
        prompt_boundary_mode=TEXT_ONLY_PROMPT_BOUNDARY_MODE,
    )
    return calibrate_detector(
        evidence,
        scope,
        target_fprs=(0.05, PRIMARY_TARGET_FPR),
        comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        confidence_level=0.95,
    )


def threshold_for_fpr(bundle, target_fpr: float):
    return next(value for value in bundle.thresholds if value.target_fpr == target_fpr)
