from __future__ import annotations

from .mid_dev import MID_DEV_TARGET_LENGTHS, MidDevAttackArtifact
from .schema import KeySplit


class MidDevExperimentIdentityError(ValueError):
    pass


def validate_mid_dev_experiment_identity(artifact: MidDevAttackArtifact) -> None:
    if not isinstance(artifact, MidDevAttackArtifact):
        raise TypeError("artifact must be a MidDevAttackArtifact")
    samples = artifact.manifest.samples
    model_hashes = {sample.model.identity_hash for sample in samples}
    watermark_hashes = {sample.watermark.condition_hash for sample in samples}
    watermark_config_hashes = {sample.watermark.watermark_config_hash for sample in samples}
    key_ids = {sample.watermark.key_id for sample in samples}
    if len(model_hashes) != 1:
        raise MidDevExperimentIdentityError("MidDev corpus must use one model/tokenizer identity")
    if len(watermark_hashes) != 1 or len(watermark_config_hashes) != 1 or len(key_ids) != 1:
        raise MidDevExperimentIdentityError("MidDev corpus must use one DEV watermark condition")
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in samples):
        raise MidDevExperimentIdentityError("MidDev corpus must use DEV_KEYS only")
    if any(
        sample.generation_tokens.model_tokenizer_identity_hash != sample.model.identity_hash
        for sample in samples
    ):
        raise MidDevExperimentIdentityError("generation token track identity drifted")
    if any(
        sample.text_only_tokens is None
        or sample.text_only_tokens.model_tokenizer_identity_hash != sample.model.identity_hash
        for sample in samples
    ):
        raise MidDevExperimentIdentityError("text-only token track identity drifted")
    signatures_by_length: dict[int, set[str]] = {}
    for sample in samples:
        signatures_by_length.setdefault(sample.target_length, set()).add(
            sample.generation.matching_signature_hash
        )
    if set(signatures_by_length) != set(MID_DEV_TARGET_LENGTHS):
        raise MidDevExperimentIdentityError("MidDev generation signatures do not cover frozen lengths")
    if any(len(values) != 1 for values in signatures_by_length.values()):
        raise MidDevExperimentIdentityError(
            "MidDev generation parameters must be fixed within each target length"
        )
