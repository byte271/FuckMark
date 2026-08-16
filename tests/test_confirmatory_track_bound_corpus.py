from dataclasses import replace

import pytest

from confirmatory_helpers import (
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.corpus import CorpusSample, WatermarkCondition, build_corpus_manifest
from fuckmark.experiments import ConfirmatoryCorpusSealError, build_confirmatory_corpus_seal
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.hashing import sha256_text


def _replace_watermark(sample: CorpusSample, watermark: WatermarkCondition) -> CorpusSample:
    return CorpusSample.create(
        sample_id=sample.sample_id,
        match_id=sample.match_id,
        prompt_id=sample.prompt_id,
        prompt_family_id=sample.prompt_family_id,
        domain=sample.domain,
        split=sample.split,
        label=sample.label,
        text=sample.text,
        model=sample.model,
        generation=sample.generation,
        watermark=watermark,
        target_length=sample.target_length,
        generation_tokens=sample.generation_tokens,
        text_only_tokens=sample.text_only_tokens,
        prompt_boundary_mode=sample.prompt_boundary_mode,
        language=sample.language,
    )


def test_public_corpus_seal_accepts_exact_sealed_generation_tracks() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    corpus = confirmatory_manifest(inputs)
    keys = confirmatory_test_key_manifest(inputs)
    inputs = replace(
        inputs,
        sealed_test_key_hash=keys.manifest_hash,
        sealed_test_corpus_hash=corpus.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    seal = build_confirmatory_corpus_seal(preregistration, corpus, keys)
    assert seal.corpus_manifest_hash == corpus.manifest_hash


def test_public_corpus_seal_rejects_internally_valid_unknown_watermark_configuration() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    corpus = confirmatory_manifest(inputs)
    first = corpus.samples[0]
    pair_id = first.match_id
    unknown = WatermarkCondition.create(
        sha256_text("unknown-confirmatory-watermark-config"),
        first.watermark.key_split,
        first.watermark.key_id,
    )
    changed_samples = tuple(
        _replace_watermark(sample, unknown) if sample.match_id == pair_id else sample
        for sample in corpus.samples
    )
    changed_corpus = build_corpus_manifest(
        corpus.corpus_id,
        corpus.prompts,
        changed_samples,
        language=corpus.language,
        deduplication_policy=corpus.deduplication_policy,
    )
    keys = confirmatory_test_key_manifest(inputs)
    changed_inputs = replace(
        inputs,
        sealed_test_key_hash=keys.manifest_hash,
        sealed_test_corpus_hash=changed_corpus.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(changed_inputs)
    with pytest.raises(ConfirmatoryCorpusSealError, match="outside the sealed generation tracks"):
        build_confirmatory_corpus_seal(preregistration, changed_corpus, keys)
