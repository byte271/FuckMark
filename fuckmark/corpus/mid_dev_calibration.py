from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev import MID_DEV_PROMPT_FAMILIES, MID_DEV_TARGET_LENGTHS
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusSplit, KeySplit, WatermarkLabel


MID_DEV_CALIBRATION_ALGORITHM_VERSION = "mid-dev-length-calibration-corpus-v2"
MID_DEV_CALIBRATION_MANIFEST_VERSION = "mid-dev-calibration-manifest-v1"
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


_MID_DEV_CALIBRATION_PROMPT_IDS = tuple(
    value.prompt_id for value in build_mid_dev_calibration_prompt_records()
)
_MID_DEV_CALIBRATION_SEED_BY_PROMPT_ID = {
    prompt_id: MID_DEV_CALIBRATION_SEED_BASE + index
    for index, prompt_id in enumerate(_MID_DEV_CALIBRATION_PROMPT_IDS)
}


def calibration_target_length_for_prompt(prompt_id: str) -> int:
    require_clean_string("prompt_id", prompt_id)
    for value in MID_DEV_TARGET_LENGTHS:
        if prompt_id.startswith(f"middev-cal-{value}-"):
            return value
    raise MidDevCalibrationError("prompt_id does not bind a MidDev calibration target length")


def calibration_seed_for_prompt(prompt_id: str) -> int:
    require_clean_string("prompt_id", prompt_id)
    try:
        return _MID_DEV_CALIBRATION_SEED_BY_PROMPT_ID[prompt_id]
    except KeyError as error:
        raise MidDevCalibrationError("prompt_id is not part of the frozen MidDev calibration matrix") from error


@dataclass(frozen=True, slots=True)
class MidDevCalibrationManifest:
    corpus_id: str
    language: str
    prompts: tuple[PromptRecord, ...]
    samples: tuple[CorpusSample, ...]
    prompt_manifest_hash: str
    sample_manifest_hash: str
    manifest_hash: str
    algorithm_version: str = MID_DEV_CALIBRATION_MANIFEST_VERSION

    def __post_init__(self) -> None:
        require_clean_string("corpus_id", self.corpus_id)
        require_clean_string("language", self.language)
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.language != "en":
            raise ValueError("MidDev calibration language must be en")
        if self.algorithm_version != MID_DEV_CALIBRATION_MANIFEST_VERSION:
            raise ValueError("unsupported MidDev calibration manifest version")
        if not isinstance(self.prompts, tuple) or not isinstance(self.samples, tuple):
            raise TypeError("MidDev calibration prompts and samples must be tuples")
        if tuple(sorted(self.prompts, key=lambda value: value.prompt_id)) != self.prompts:
            raise ValueError("MidDev calibration prompts must use canonical prompt_id ordering")
        if tuple(sorted(self.samples, key=lambda value: value.sample_id)) != self.samples:
            raise ValueError("MidDev calibration samples must use canonical sample_id ordering")
        if any(not isinstance(value, PromptRecord) for value in self.prompts):
            raise TypeError("MidDev calibration prompts must contain PromptRecord values")
        if any(not isinstance(value, CorpusSample) for value in self.samples):
            raise TypeError("MidDev calibration samples must contain CorpusSample values")
        require_sha256("prompt_manifest_hash", self.prompt_manifest_hash)
        require_sha256("sample_manifest_hash", self.sample_manifest_hash)
        require_sha256("manifest_hash", self.manifest_hash)
        _validate_calibration_records(self.prompts, self.samples)
        expected_prompt_hash = sha256_json(tuple(value.record_hash for value in self.prompts))
        expected_sample_hash = sha256_json(tuple(value.record_hash for value in self.samples))
        if self.prompt_manifest_hash != expected_prompt_hash:
            raise ValueError("prompt_manifest_hash does not match calibration prompts")
        if self.sample_manifest_hash != expected_sample_hash:
            raise ValueError("sample_manifest_hash does not match calibration samples")
        if self.manifest_hash != sha256_json(self.payload()):
            raise ValueError("manifest_hash does not match MidDev calibration manifest")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_id": self.corpus_id,
            "language": self.language,
            "prompts": self.prompts,
            "samples": self.samples,
            "prompt_manifest_hash": self.prompt_manifest_hash,
            "sample_manifest_hash": self.sample_manifest_hash,
        }


@dataclass(frozen=True, slots=True)
class MidDevCalibrationArtifact:
    algorithm_version: str
    manifest: MidDevCalibrationManifest
    target_lengths: tuple[int, ...]
    negatives_per_length: int
    source_profile_hash: str
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev calibration algorithm version")
        if not isinstance(self.manifest, MidDevCalibrationManifest):
            raise TypeError("manifest must be MidDevCalibrationManifest")
        if self.target_lengths != MID_DEV_TARGET_LENGTHS:
            raise ValueError("MidDev calibration target lengths must be 128/256")
        require_int("negatives_per_length", self.negatives_per_length)
        if self.negatives_per_length != MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
            raise ValueError("MidDev calibration requires exactly 100 negatives per length")
        require_sha256("source_profile_hash", self.source_profile_hash)
        require_sha256("artifact_hash", self.artifact_hash)
        _validate_calibration_records(self.manifest.prompts, self.manifest.samples)
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


def _validate_calibration_records(
    prompts: tuple[PromptRecord, ...],
    samples: tuple[CorpusSample, ...],
) -> None:
    expected = len(MID_DEV_TARGET_LENGTHS) * MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH
    if len(prompts) != expected or len(samples) != expected:
        raise MidDevCalibrationError("MidDev calibration must contain exactly 200 prompts and negatives")
    if len({value.prompt_id for value in prompts}) != expected:
        raise MidDevCalibrationError("MidDev calibration prompt IDs must be unique")
    if len({value.record_hash for value in prompts}) != expected:
        raise MidDevCalibrationError("MidDev calibration prompt records must be unique")
    if len({value.text_sha256 for value in prompts}) != expected:
        raise MidDevCalibrationError("MidDev calibration prompt texts must be unique")
    if len({value.sample_id for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration sample IDs must be unique")
    if len({value.record_hash for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration sample records must be unique")
    if len({value.text_sha256 for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration generated texts must be unique")
    if len({value.generation_tokens.continuation_token_hash for value in samples}) != expected:
        raise MidDevCalibrationError("MidDev calibration generated token sequences must be unique")
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
    used_prompt_ids: set[str] = set()
    for sample in samples:
        prompt = prompt_by_id.get(sample.prompt_id)
        if prompt is None:
            raise MidDevCalibrationError("MidDev calibration sample references an unknown prompt")
        used_prompt_ids.add(sample.prompt_id)
        expected_length = calibration_target_length_for_prompt(prompt.prompt_id)
        if sample.target_length != expected_length:
            raise MidDevCalibrationError("MidDev calibration sample length does not match prompt stratum")
        if sample.generation.seed != calibration_seed_for_prompt(prompt.prompt_id):
            raise MidDevCalibrationError("MidDev calibration sample seed drifted")
        if (
            sample.prompt_family_id != prompt.prompt_family_id
            or sample.domain is not prompt.domain
            or sample.split is not prompt.split
            or sample.language != prompt.language
        ):
            raise MidDevCalibrationError("MidDev calibration sample prompt metadata drifted")
    if used_prompt_ids != set(prompt_by_id):
        raise MidDevCalibrationError("MidDev calibration contains unused prompts")
    model_hashes = {value.model.identity_hash for value in samples}
    watermark_hashes = {value.watermark.condition_hash for value in samples}
    if len(model_hashes) != 1 or len(watermark_hashes) != 1:
        raise MidDevCalibrationError("MidDev calibration mixed model or watermark identities")


def build_mid_dev_calibration_manifest(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> MidDevCalibrationManifest:
    require_clean_string("corpus_id", corpus_id)
    prompt_tuple = tuple(sorted(tuple(prompts), key=lambda value: value.prompt_id))
    sample_tuple = tuple(sorted(tuple(samples), key=lambda value: value.sample_id))
    _validate_calibration_records(prompt_tuple, sample_tuple)
    prompt_manifest_hash = sha256_json(tuple(value.record_hash for value in prompt_tuple))
    sample_manifest_hash = sha256_json(tuple(value.record_hash for value in sample_tuple))
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MANIFEST_VERSION,
        "corpus_id": corpus_id,
        "language": "en",
        "prompts": prompt_tuple,
        "samples": sample_tuple,
        "prompt_manifest_hash": prompt_manifest_hash,
        "sample_manifest_hash": sample_manifest_hash,
    }
    return MidDevCalibrationManifest(
        corpus_id=corpus_id,
        language="en",
        prompts=prompt_tuple,
        samples=sample_tuple,
        prompt_manifest_hash=prompt_manifest_hash,
        sample_manifest_hash=sample_manifest_hash,
        manifest_hash=sha256_json(payload),
    )


def build_mid_dev_calibration_artifact(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> MidDevCalibrationArtifact:
    manifest = build_mid_dev_calibration_manifest(corpus_id, prompts, samples)
    profile = {
        "algorithm_version": MID_DEV_CALIBRATION_ALGORITHM_VERSION,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "negatives_per_length": MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
        "family_counts": MID_DEV_CALIBRATION_FAMILY_COUNTS,
        "family_ids": tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES),
        "prompt_source_hash": _prompt_source_hash(),
        "seed_base": MID_DEV_CALIBRATION_SEED_BASE,
        "manifest_algorithm_version": MID_DEV_CALIBRATION_MANIFEST_VERSION,
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
