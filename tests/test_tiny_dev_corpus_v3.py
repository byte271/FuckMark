from __future__ import annotations

from collections import defaultdict

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSplit,
    GenerationParameters,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    WatermarkCondition,
    WatermarkLabel,
    TINY_DEV_V3_CORPUS_ALGORITHM_VERSION,
    TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN,
    build_tiny_dev_v3_prompt_records,
    build_real_tiny_dev_v3_corpus,
    parse_tiny_dev_v3_corpus_json,
)
from fuckmark.corpus.tiny_dev_generation import (
    TINY_DEV_SEED_POLICY_ID,
    TinyDevGeneratedContinuation,
    build_tiny_dev_prompt_records,
)
from fuckmark.corpus.tiny_dev_io_v3 import load_tiny_dev_corpus_by_version_json
from fuckmark.hashing import sha256_json, sha256_text


class FakeTinyDevV3Backend:
    def __init__(self) -> None:
        self._model = ModelTokenizerIdentity.create(
            model_id="example/tiny-dev-model",
            model_revision="a" * 40,
            tokenizer_id="example/tiny-dev-tokenizer",
            tokenizer_revision="b" * 40,
            chat_template_present=False,
            chat_template_hash=sha256_text(""),
            special_token_map_hash=sha256_json({"eos_token": "<eos>", "pad_token": "<pad>"}),
            padding_side=PaddingSide.LEFT,
            bos_token_id=None,
            eos_token_id=2,
            pad_token_id=0,
            add_bos_token=False,
            add_eos_token=False,
        )
        self._watermark = WatermarkCondition.create(
            sha256_json({"ngram_len": 5, "keys": (1, 2, 3)}),
            KeySplit.DEV,
            "dev-test-key",
        )

    @property
    def model_identity(self) -> ModelTokenizerIdentity:
        return self._model

    @property
    def watermark_condition(self) -> WatermarkCondition:
        return self._watermark

    def generation_parameters(self, seed: int) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id=TINY_DEV_SEED_POLICY_ID,
            temperature=0.8,
            top_k=50,
            top_p=0.95,
            max_new_tokens=64,
            do_sample=True,
            dtype="float32",
            device="cpu",
            backend_id="fake-tiny-dev",
            backend_version="1",
        )

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> TinyDevGeneratedContinuation:
        prompt_token = 10 + (sum(prompt.encode("utf-8")) % 1000)
        label_offset = 100_000 if watermarked else 200_000
        continuation = tuple(
            label_offset + ((seed * 131 + index) % 90_000)
            for index in range(64)
        )
        text = (
            f"{'watermarked' if watermarked else 'control'} output for "
            f"{sha256_text(prompt)[:12]} seed {seed}"
        )
        text_only = tuple(300_000 + ((seed * 17 + index) % 80_000) for index in range(16))
        return TinyDevGeneratedContinuation(
            text=text,
            input_token_ids=(prompt_token, prompt_token + 1),
            attention_mask=(1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=text_only,
        )


def test_v3_prompt_records_preserve_v2_calibration_and_extend_attack() -> None:
    v2 = build_tiny_dev_prompt_records()
    v3 = build_tiny_dev_v3_prompt_records(16)
    v2_calibration = {prompt.text for prompt in v2 if prompt.split is CorpusSplit.THRESHOLD_CALIBRATION}
    v3_calibration = {prompt.text for prompt in v3 if prompt.split is CorpusSplit.THRESHOLD_CALIBRATION}
    assert v2_calibration == v3_calibration
    v2_attack = {prompt.text for prompt in v2 if prompt.split is CorpusSplit.ATTACK_DEVELOPMENT}
    v3_one = build_tiny_dev_v3_prompt_records(1)
    v3_one_attack = {prompt.text for prompt in v3_one if prompt.split is CorpusSplit.ATTACK_DEVELOPMENT}
    assert v2_attack == v3_one_attack
    counts: defaultdict[tuple[CorpusSplit, CorpusDomain], int] = defaultdict(int)
    for prompt in v3:
        counts[(prompt.split, prompt.domain)] += 1
    for domain in CorpusDomain:
        assert counts[(CorpusSplit.THRESHOLD_CALIBRATION, domain)] == 25
        assert counts[(CorpusSplit.ATTACK_DEVELOPMENT, domain)] == 16
    assert len({prompt.prompt_id for prompt in v3}) == 164
    assert len({prompt.prompt_family_id for prompt in v3}) == 164


@pytest.mark.parametrize("count", (0, -1, TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN + 1))
def test_v3_prompt_records_reject_out_of_range_attack_pairs(count: int) -> None:
    with pytest.raises((ValueError, Exception)):
        build_tiny_dev_v3_prompt_records(count)


def test_real_v3_runner_builds_parameterized_paired_corpus() -> None:
    backend = FakeTinyDevV3Backend()
    artifact = build_real_tiny_dev_v3_corpus(
        backend,
        seed_base=5000,
        attack_pairs_per_domain=8,
    )
    assert artifact.algorithm_version == TINY_DEV_V3_CORPUS_ALGORITHM_VERSION
    assert artifact.attack_pairs_per_domain == 8
    assert artifact.calibration_pairs_per_domain == 25
    assert len(artifact.manifest.prompts) == 132
    assert len(artifact.manifest.samples) == 264
    attack_watermarked = [
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
        and sample.label is WatermarkLabel.WATERMARKED
    ]
    assert len(attack_watermarked) == 32
    assert all(sample.watermark.key_split is KeySplit.DEV for sample in artifact.manifest.samples)
    assert len({sample.text_sha256 for sample in artifact.manifest.samples}) == 264


def test_v3_corpus_json_replays_canonically_and_version_dispatch_loads() -> None:
    backend = FakeTinyDevV3Backend()
    artifact = build_real_tiny_dev_v3_corpus(
        backend,
        seed_base=9000,
        attack_pairs_per_domain=2,
    )
    text = canonical_json_text(artifact) + "\n"
    replay = parse_tiny_dev_v3_corpus_json(text)
    assert replay == artifact
    assert replay.artifact_hash == artifact.artifact_hash


def test_v3_builder_rejects_mismatched_prompt_profile() -> None:
    from fuckmark.corpus import build_tiny_dev_v3_corpus

    backend = FakeTinyDevV3Backend()
    prompts = build_tiny_dev_v3_prompt_records(4)
    with pytest.raises(Exception):
        build_tiny_dev_v3_corpus(
            "mismatch-corpus",
            prompts,
            (),
            attack_pairs_per_domain=8,
        )


def test_version_dispatch_loader_rejects_unknown_version(tmp_path) -> None:
    bad = tmp_path / "corpus.json"
    bad.write_text('{"algorithm_version": "tiny-dev-corpus-v9"}', encoding="utf-8")
    with pytest.raises(Exception):
        load_tiny_dev_corpus_by_version_json(bad)
