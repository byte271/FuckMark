from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .generation import WatermarkCondition
from .manifest import CorpusManifest, build_corpus_manifest
from .mid_dev import MID_DEV_PROMPT_FAMILIES, MID_DEV_TARGET_LENGTHS
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusSplit, KeySplit, WatermarkLabel


MID_DEV_CALIBRATION_ALGORITHM_VERSION = "mid-dev-length-calibration-corpus-v1"
MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH = 100
MID_DEV_CALIBRATION_SEED_BASE = 610_000
MID_DEV_CALIBRATION_SOURCE_ID = "fuckmark-mid-dev-length-calibration-prompts-v1"
MID_DEV_CALIBRATION_LICENSE_ID = "LicenseRef-FuckMark-Unspecified"
MID_DEV_CALIBRATION_PROVENANCE = "fuckmark/corpus/mid_dev_calibration.py"
MID_DEV_CALIBRATION_FAMILY_COUNTS = (17, 17, 17, 16, 17, 16)


class MidDevCalibrationError(ValueError):
    pass


def _prompt_source_hash() -> str:
    return sha256_json(
        {
            "algorithm_version": MID_DEV_CALIBRATION_ALGORITHM_VERSION,
            "source_id": MID_DEV_CALIBRATION_SOURCE_ID,
            "license_id": MID_DEV_CALIBRATION_LICENSE_ID,
            "provenance": MID_DEV_CALIBRATION_PROVENANCE,
            "target_lengths": MID_DEV_TARGET_LENGTHS,
            "family_counts": MID_DEV_CALIBRATION_FAMILY_COUNTS,
            "family_ids": tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES),
            "seed_base": MID_DEV_CALIBRATION_SEED_BASE,
        }
    )


def build_mid_dev_calibration_prompt_records() -> tuple[PromptRecord, ...]:
    if sum(MID_DEV_CALIBRATION_FAMILY_COUNTS) != MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
        raise RuntimeError("MidDev calibration family counts do not sum to 100")
    source_hash = _prompt_source_hash()
    output: list[PromptRecord] = []
    global_index = 0
    for target_length in MID_DEV_TARGET_LENGTHS:
        for family, family_count in zip(MID_DEV_PROMPT_FAMILIES, MID_DEV_CALIBRATION_FAMILY_COUNTS):
            for local_index in range(family_count):
                prompt_id = (
                    f"middev-cal-{target_length}-{family.family_id}-{local_index:03d}"
                )
                topic = (
                    f"ordinary measurement scenario {global_index:03d} involving routine planning, "
                    f"documentation, comparison, and follow-up"
                )
                output.append(
                    PromptRecord.create(
                        prompt_id=prompt_id,
                        prompt_family_id=f"cal-{family.family_id}",
                        domain=family.domain,
                        split=CorpusSplit.THRESHOLD_CALIBRATION,
                        source_id=MID_DEV_CALIBRATION_SOURCE_ID,
                        source_hash=source_hash,
                        license_id=MID_DEV_CALIBRATION_LICENSE_ID,
                        provenance=MID_DEV_CALIBRATION_PROVENANCE,
                        text=family.template.format(
                            topic=topic,
                            target_length=target_length,
                        ),
                    )
                )
                global_index += 1
    return tuple(sorted(output, key=lambda value: value.prompt_id))


def calibration_target_length_for_prompt(prompt_id: str) -> int:
    require_clean_string("prompt_id", prompt_id)
    for value in MID_DEV_TARGET_LENGTHS:
        if prompt_id.startswith(f"middev-cal-{value}-"):
            return value
    raise MidDevCalibrationError("prompt_id does not bind a MidDev calibration target length")


def calibration_seed_for_prompt(prompt_id: str) -> int:
    require_clean_string("prompt_id", prompt_id)
    prompt_ids = tuple(value.prompt_id for value in build_mid_dev_calibration_prompt_records())
    try:
        index = prompt_ids.index(prompt_id)
    except ValueError as error:
        raise MidDevCalibrationError("prompt_id is not part of the frozen MidDev calibration matrix") from error
    return MID_DEV_CALIBRATION_SEED_BASE + index


@dataclass(frozen=True, slots=True)
class MidDevCalibrationArtifact:
    algorithm_version: str
    manifest: CorpusManifest
    target_lengths: tuple[int, ...]
    negatives_per_length: int
    source_profile_hash: str
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev calibration algorithm version")
        if not isinstance(self.manifest, CorpusManifest):
            raise TypeError("manifest must be CorpusManifest")
        if self.target_lengths != MID_DEV_TARGET_LENGTHS:
            raise ValueError("MidDev calibration target lengths must be 128/256")
        require_int("negatives_per_length", self.negatives_per_length)
        if self.negatives_per_length != MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
            raise ValueError("MidDev calibration requires exactly 100 negatives per length")
        require_sha256("source_profile_hash", self.source_profile_hash)
        require_sha256("artifact_hash", self.artifact_hash)
        _validate_calibration_manifest(self.manifest)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match MidDev calibration artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "manifest_hash": self.manifest.manifest_hash,
            "target_lengths": self.target_lengths,
            "negatives_per_length": self.negatives_per_length,
            "source_profile_hash": self.source_profile_hash,
        }


def _validate_calibration_manifest(manifest: CorpusManifest) -> None:
    prompts = manifest.prompts
    samples = manifest.samples
    expected = len(MID_DEV_TARGET_LENGTHS) * MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH
    if len(prompts) != expected or len(samples) != expected:
        raise MidDevCalibrationError("MidDev calibration must contain exactly 200 prompts and negatives")
    if len({value.prompt_id for value in prompts}) != expected:
        raise MidDevCalibrationError("MidDev calibration prompt IDs must be unique")
    if len({value.text_sha256 for value in prompts}) != expected:
        raise MidDevCalibrationError("MidDev calibration prompt texts must be unique")
    if len({value.sample_id for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration sample IDs must be unique")
    if len({value.text_sha256 for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration generated texts must be unique")
    if any(value.split is not CorpusSplit.THRESHOLD_CALIBRATION for value in prompts):
        raise MidDevCalibrationError("MidDev calibration prompts must use threshold-calibration split")
    if any(value.split is not CorpusSplit.THRESHOLD_CALIBRATION for value in samples):
        raise MidDevCalibrationError("MidDev calibration samples must use threshold-calibration split")
    if any(value.label is not WatermarkLabel.UNWATERMARKED for value in samples):
        raise MidDevCalibrationError("MidDev calibration samples must all be unwatermarked negatives")
    if any(value.watermark.key_split is not KeySplit.DEV for value in samples):
        raise MidDevCalibrationError("MidDev calibration samples must use DEV_KEYS")
    length_counts = Counter(value.target_length for value in samples)
    if length_counts != Counter({128: 100, 256: 100}):
        raise MidDevCalibrationError("MidDev calibration must contain 100 negatives at each length")
    prompt_by_id = {value.prompt_id: value for value in prompts}
    for sample in samples:
        prompt = prompt_by_id.get(sample.prompt_id)
        if prompt is None:
            raise MidDevCalibrationError("MidDev calibration sample references an unknown prompt")
        expected_length = calibration_target_length_for_prompt(prompt.prompt_id)
        if sample.target_length != expected_length:
            raise MidDevCalibrationError("MidDev calibration sample length does not match prompt stratum")
        if sample.generation.seed != calibration_seed_for_prompt(prompt.prompt_id):
            raise MidDevCalibrationError("MidDev calibration sample seed drifted")
        if sample.prompt_family_id != prompt.prompt_family_id or sample.domain is not prompt.domain:
            raise MidDevCalibrationError("MidDev calibration sample prompt metadata drifted")
    model_hashes = {value.model.identity_hash for value in samples}
    watermark_hashes = {value.watermark.condition_hash for value in samples}
    if len(model_hashes) != 1 or len(watermark_hashes) != 1:
        raise MidDevCalibrationError("MidDev calibration mixed model or watermark identities")


def build_mid_dev_calibration_artifact(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> MidDevCalibrationArtifact:
    require_clean_string("corpus_id", corpus_id)
    manifest = build_corpus_manifest(corpus_id, prompts, samples)
    _validate_calibration_manifest(manifest)
    profile = {
        "algorithm_version": MID_DEV_CALIBRATION_ALGORITHM_VERSION,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "negatives_per_length": MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
        "family_counts": MID_DEV_CALIBRATION_FAMILY_COUNTS,
        "family_ids": tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES),
        "prompt_source_hash": _prompt_source_hash(),
        "seed_base": MID_DEV_CALIBRATION_SEED_BASE,
    }
    source_profile_hash = sha256_json(profile)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_ALGORITHM_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "negatives_per_length": MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
        "source_profile_hash": source_profile_hash,
    }
    return MidDevCalibrationArtifact(
        MID_DEV_CALIBRATION_ALGORITHM_VERSION,
        manifest,
        MID_DEV_TARGET_LENGTHS,
        MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
        source_profile_hash,
        sha256_json(payload),
    )
