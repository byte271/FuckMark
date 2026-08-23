from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusDomain, CorpusSplit, KeySplit, WatermarkLabel
from .tiny_dev import TINY_DEV_DOMAINS, TINY_DEV_TARGET_LENGTH, TinyDevCorpusError


MEASUREMENT_CALIBRATION_CORPUS_VERSION = "measurement-calibration-corpus-v1"
MEASUREMENT_CALIBRATION_MANIFEST_VERSION = "measurement-calibration-manifest-v1"
MEASUREMENT_CALIBRATION_PROMPT_SOURCE_ID = "fuckmark-measurement-calibration-prompts-v1"
MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN = 40
MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT = 8
MEASUREMENT_CALIBRATION_SAMPLE_COUNT = (
    MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN
    * len(TINY_DEV_DOMAINS)
    * MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT
)
MEASUREMENT_CALIBRATION_NEGATIVE_COUNT = 1024
MEASUREMENT_CALIBRATION_AUDIT_COUNT = (
    MEASUREMENT_CALIBRATION_SAMPLE_COUNT - MEASUREMENT_CALIBRATION_NEGATIVE_COUNT
)


_MEASUREMENT_CALIBRATION_TOPICS = (
    "artifact retention",
    "audit trails",
    "binary outcomes",
    "blinding procedures",
    "carryover effects",
    "categorical drift",
    "causal language",
    "censoring rules",
    "checklist discipline",
    "codebook stability",
    "cohort definitions",
    "comparison validity",
    "compute budgets",
    "concept drift",
    "consent records",
    "contamination checks",
    "data dictionaries",
    "decision rules",
    "definitional clarity",
    "distribution shift",
    "documentation debt",
    "effect direction",
    "endpoint choice",
    "enumeration order",
    "exclusion criteria",
    "external validity",
    "fair comparison",
    "follow-up windows",
    "group assignment",
    "hypothesis registries",
    "inclusion criteria",
    "interrater agreement",
    "label leakage",
    "latent confounding",
    "lookup tables",
    "matching strategies",
    "metadata quality",
    "missingness patterns",
    "operationalization",
    "ownership boundaries",
)


def measurement_calibration_topics() -> tuple[str, ...]:
    return _MEASUREMENT_CALIBRATION_TOPICS


@dataclass(frozen=True, slots=True)
class MeasurementCalibrationManifest:
    algorithm_version: str
    corpus_id: str
    language: str
    prompts: tuple[PromptRecord, ...]
    samples: tuple[CorpusSample, ...]
    prompt_manifest_hash: str
    sample_manifest_hash: str
    manifest_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != MEASUREMENT_CALIBRATION_MANIFEST_VERSION:
            raise ValueError("unsupported measurement calibration manifest version")
        require_clean_string("corpus_id", self.corpus_id)
        require_clean_string("language", self.language)
        if not isinstance(self.prompts, tuple) or not isinstance(self.samples, tuple):
            raise TypeError("prompts and samples must be tuples")
        _validate_measurement_calibration_manifest(self)
        for name in (
            "prompt_manifest_hash",
            "sample_manifest_hash",
            "manifest_hash",
        ):
            require_sha256(name, getattr(self, name))
        payload = {
            "algorithm_version": self.algorithm_version,
            "corpus_id": self.corpus_id,
            "language": self.language,
            "prompt_manifest_hash": self.prompt_manifest_hash,
            "sample_manifest_hash": self.sample_manifest_hash,
            "sample_count": len(self.samples),
        }
        if self.manifest_hash != sha256_json(payload):
            raise ValueError("manifest_hash does not match measurement calibration manifest")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_id": self.corpus_id,
            "language": self.language,
            "prompts": self.prompts,
            "samples": self.samples,
            "prompt_manifest_hash": self.prompt_manifest_hash,
            "sample_manifest_hash": self.sample_manifest_hash,
            "manifest_hash": self.manifest_hash,
        }


def build_measurement_calibration_manifest(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
    language: str = "en",
) -> MeasurementCalibrationManifest:
    require_clean_string("corpus_id", corpus_id)
    prompt_tuple = tuple(sorted(prompts, key=lambda value: value.prompt_id))
    sample_tuple = tuple(sorted(samples, key=lambda value: value.sample_id))
    prompt_manifest_hash = sha256_json(tuple(value.record_hash for value in prompt_tuple))
    sample_manifest_hash = sha256_json(tuple(value.record_hash for value in sample_tuple))
    payload = {
        "algorithm_version": MEASUREMENT_CALIBRATION_MANIFEST_VERSION,
        "corpus_id": corpus_id,
        "language": language,
        "prompt_manifest_hash": prompt_manifest_hash,
        "sample_manifest_hash": sample_manifest_hash,
        "sample_count": len(sample_tuple),
    }
    return MeasurementCalibrationManifest(
        algorithm_version=MEASUREMENT_CALIBRATION_MANIFEST_VERSION,
        corpus_id=corpus_id,
        language=language,
        prompts=prompt_tuple,
        samples=sample_tuple,
        prompt_manifest_hash=prompt_manifest_hash,
        sample_manifest_hash=sample_manifest_hash,
        manifest_hash=sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class MeasurementCalibrationCorpus:
    algorithm_version: str
    manifest: MeasurementCalibrationManifest
    target_length: int
    topic_count_per_domain: int
    seeds_per_prompt: int
    sample_count: int
    negative_count: int
    audit_count: int
    model_identity_hash: str
    generation_matching_signature_hash: str
    watermark_condition_hash: str
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != MEASUREMENT_CALIBRATION_CORPUS_VERSION:
            raise ValueError("unsupported measurement calibration corpus version")
        if not isinstance(self.manifest, MeasurementCalibrationManifest):
            raise TypeError("manifest must be a MeasurementCalibrationManifest")
        if self.target_length != TINY_DEV_TARGET_LENGTH:
            raise ValueError("measurement calibration target length must be 64")
        if self.topic_count_per_domain != MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN:
            raise ValueError("measurement calibration topic count is frozen")
        if self.seeds_per_prompt != MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT:
            raise ValueError("measurement calibration seed count is frozen")
        if self.sample_count != MEASUREMENT_CALIBRATION_SAMPLE_COUNT:
            raise ValueError("measurement calibration sample count is frozen")
        if self.negative_count != MEASUREMENT_CALIBRATION_NEGATIVE_COUNT:
            raise ValueError("measurement calibration negative count is frozen")
        if self.audit_count != MEASUREMENT_CALIBRATION_AUDIT_COUNT:
            raise ValueError("measurement calibration audit count is frozen")
        for name in (
            "model_identity_hash",
            "generation_matching_signature_hash",
            "watermark_condition_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        _validate_measurement_calibration_manifest(self.manifest)
        payload = self._payload()
        if self.artifact_hash != sha256_json(payload):
            raise ValueError("artifact_hash does not match measurement calibration corpus")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "manifest_hash": self.manifest.manifest_hash,
            "target_length": self.target_length,
            "topic_count_per_domain": self.topic_count_per_domain,
            "seeds_per_prompt": self.seeds_per_prompt,
            "sample_count": self.sample_count,
            "negative_count": self.negative_count,
            "audit_count": self.audit_count,
            "model_identity_hash": self.model_identity_hash,
            "generation_matching_signature_hash": self.generation_matching_signature_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
        }

    def calibration_samples(self) -> tuple[CorpusSample, ...]:
        ordered = tuple(sorted(self.manifest.samples, key=lambda sample: sample.sample_id))
        return ordered[: self.negative_count]

    def audit_samples(self) -> tuple[CorpusSample, ...]:
        ordered = tuple(sorted(self.manifest.samples, key=lambda sample: sample.sample_id))
        return ordered[self.negative_count :]


def _validate_measurement_calibration_manifest(manifest: MeasurementCalibrationManifest) -> None:
    prompts = manifest.prompts
    samples = manifest.samples
    if len(samples) != MEASUREMENT_CALIBRATION_SAMPLE_COUNT:
        raise TinyDevCorpusError(
            f"measurement calibration corpus must contain exactly {MEASUREMENT_CALIBRATION_SAMPLE_COUNT} samples"
        )
    prompt_ids = tuple(value.prompt_id for value in prompts)
    if len(set(prompt_ids)) != len(prompt_ids):
        raise TinyDevCorpusError("measurement calibration prompt IDs must be unique")
    prompt_texts = tuple(value.text for value in prompts)
    if len(set(prompt_texts)) != len(prompt_texts):
        raise TinyDevCorpusError("measurement calibration prompt texts must be unique")
    family_splits: dict[str, set[CorpusSplit]] = defaultdict(set)
    for prompt in prompts:
        family_splits[prompt.prompt_family_id].add(prompt.split)
    if any(len(splits) != 1 for splits in family_splits.values()):
        raise TinyDevCorpusError("measurement calibration prompt families must not cross splits")
    if any(sample.split is not CorpusSplit.THRESHOLD_CALIBRATION for sample in samples):
        raise TinyDevCorpusError("measurement calibration samples must use the calibration split")
    if any(sample.label is not WatermarkLabel.UNWATERMARKED for sample in samples):
        raise TinyDevCorpusError("measurement calibration samples must be unwatermarked")
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in samples):
        raise TinyDevCorpusError("measurement calibration samples must record DEV key split")
    if any(sample.target_length != TINY_DEV_TARGET_LENGTH for sample in samples):
        raise TinyDevCorpusError("measurement calibration samples must target 64 continuation tokens")
    domains = {sample.domain for sample in samples}
    if domains != set(TINY_DEV_DOMAINS):
        raise TinyDevCorpusError("measurement calibration must cover the frozen four-domain profile")
    if len({sample.sample_id for sample in samples}) != len(samples):
        raise TinyDevCorpusError("measurement calibration sample IDs must be unique")
    if len({sample.text_sha256 for sample in samples}) != len(samples):
        raise TinyDevCorpusError("measurement calibration texts must be unique")
    if len({sample.generation_tokens.continuation_token_hash for sample in samples}) != len(samples):
        raise TinyDevCorpusError("measurement calibration continuations must be unique")
    prompt_by_id = {value.prompt_id: value for value in prompts}
    for sample in samples:
        prompt = prompt_by_id.get(sample.prompt_id)
        if prompt is None:
            raise TinyDevCorpusError("measurement calibration sample references an unknown prompt")
        if sample.prompt_family_id != prompt.prompt_family_id or sample.domain is not prompt.domain:
            raise TinyDevCorpusError("measurement calibration sample metadata does not match its prompt")
    if len(set(prompt_by_id) - {sample.prompt_id for sample in samples}):
        raise TinyDevCorpusError("measurement calibration manifest contains unused prompts")


def build_measurement_calibration_corpus(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> MeasurementCalibrationCorpus:
    require_clean_string("corpus_id", corpus_id)
    manifest = build_measurement_calibration_manifest(corpus_id, prompts, samples)
    model_hashes = {sample.model.identity_hash for sample in manifest.samples}
    generation_hashes = {sample.generation.matching_signature_hash for sample in manifest.samples}
    watermark_hashes = {sample.watermark.condition_hash for sample in manifest.samples}
    if len(model_hashes) != 1 or len(generation_hashes) != 1 or len(watermark_hashes) != 1:
        raise TinyDevCorpusError("measurement calibration must use exactly one identity triple")
    payload = {
        "algorithm_version": MEASUREMENT_CALIBRATION_CORPUS_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "target_length": TINY_DEV_TARGET_LENGTH,
        "topic_count_per_domain": MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN,
        "seeds_per_prompt": MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT,
        "sample_count": len(manifest.samples),
        "negative_count": MEASUREMENT_CALIBRATION_NEGATIVE_COUNT,
        "audit_count": MEASUREMENT_CALIBRATION_AUDIT_COUNT,
        "model_identity_hash": next(iter(model_hashes)),
        "generation_matching_signature_hash": next(iter(generation_hashes)),
        "watermark_condition_hash": next(iter(watermark_hashes)),
    }
    return MeasurementCalibrationCorpus(
        algorithm_version=MEASUREMENT_CALIBRATION_CORPUS_VERSION,
        manifest=manifest,
        target_length=TINY_DEV_TARGET_LENGTH,
        topic_count_per_domain=MEASUREMENT_CALIBRATION_TOPICS_PER_DOMAIN,
        seeds_per_prompt=MEASUREMENT_CALIBRATION_SEEDS_PER_PROMPT,
        sample_count=len(manifest.samples),
        negative_count=MEASUREMENT_CALIBRATION_NEGATIVE_COUNT,
        audit_count=MEASUREMENT_CALIBRATION_AUDIT_COUNT,
        model_identity_hash=next(iter(model_hashes)),
        generation_matching_signature_hash=next(iter(generation_hashes)),
        watermark_condition_hash=next(iter(watermark_hashes)),
        artifact_hash=sha256_json(payload),
    )
