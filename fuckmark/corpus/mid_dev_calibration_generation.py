from __future__ import annotations

from ..hashing import sha256_json, sha256_text
from .mid_dev_calibration import (
    MidDevCalibrationArtifact,
    MidDevCalibrationError,
    build_mid_dev_calibration_artifact,
    build_mid_dev_calibration_prompt_records,
    calibration_seed_for_prompt,
    calibration_target_length_for_prompt,
)
from .mid_dev_generation import MidDevGenerationBackend, _build_sample
from .schema import WatermarkLabel


def build_real_mid_dev_calibration(
    backend: MidDevGenerationBackend,
    *,
    corpus_id: str = "fuckmark-mid-dev-length-calibration-v1",
) -> MidDevCalibrationArtifact:
    prompts = build_mid_dev_calibration_prompt_records()
    samples = []
    seen_text_hashes: set[str] = set()
    seen_token_hashes: set[str] = set()
    for prompt in prompts:
        seed = calibration_seed_for_prompt(prompt.prompt_id)
        target_length = calibration_target_length_for_prompt(prompt.prompt_id)
        generated = backend.generate(
            prompt.text,
            seed,
            target_length,
            watermarked=False,
        )
        if len(generated.continuation_token_ids) != target_length:
            raise MidDevCalibrationError(
                f"exact-length calibration generation failed for {prompt.prompt_id}"
            )
        text_hash = sha256_text(generated.text)
        token_hash = sha256_json(generated.continuation_token_ids)
        if text_hash in seen_text_hashes or token_hash in seen_token_hashes:
            raise MidDevCalibrationError("MidDev calibration generation duplicated an earlier negative")
        sample = _build_sample(
            prompt=prompt,
            label=WatermarkLabel.UNWATERMARKED,
            generated=generated,
            backend=backend,
            seed=seed,
            target_length=target_length,
        )
        samples.append(sample)
        seen_text_hashes.add(text_hash)
        seen_token_hashes.add(token_hash)
    return build_mid_dev_calibration_artifact(corpus_id, prompts, samples)
