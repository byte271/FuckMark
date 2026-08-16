from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from .records import CorpusSample, CorpusSplit, DeduplicationPolicy, PromptRecord, WatermarkLabel


CORPUS_MANIFEST_ALGORITHM_VERSION = "fuckmark-corpus-manifest-v1"


class CorpusIntegrityError(ValueError):
    pass


class CorpusLeakageError(CorpusIntegrityError):
    pass


class CorpusPairingError(CorpusIntegrityError):
    pass


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    corpus_id: str
    language: str
    deduplication_policy: DeduplicationPolicy
    prompts: tuple[PromptRecord, ...]
    samples: tuple[CorpusSample, ...]
    prompt_manifest_hash: str
    sample_manifest_hash: str
    manifest_hash: str
    algorithm_version: str = CORPUS_MANIFEST_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        require_clean_string("corpus_id", self.corpus_id)
        require_clean_string("language", self.language)
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.language != "en":
            raise ValueError("FuckMark v0.1.0 corpus language must be en")
        if self.algorithm_version != CORPUS_MANIFEST_ALGORITHM_VERSION:
            raise ValueError("unsupported corpus manifest algorithm version")
        if not isinstance(self.deduplication_policy, DeduplicationPolicy):
            raise TypeError("deduplication_policy must be a DeduplicationPolicy")
        if self.deduplication_policy is not DeduplicationPolicy.EXACT_UTF8:
            raise ValueError("unsupported corpus deduplication policy")
        if not isinstance(self.prompts, tuple):
            raise TypeError("prompts must be a tuple")
        if not isinstance(self.samples, tuple):
            raise TypeError("samples must be a tuple")
        if not self.prompts:
            raise ValueError("prompts must not be empty")
        if not self.samples:
            raise ValueError("samples must not be empty")
        if any(not isinstance(value, PromptRecord) for value in self.prompts):
            raise TypeError("prompts must contain PromptRecord values")
        if any(not isinstance(value, CorpusSample) for value in self.samples):
            raise TypeError("samples must contain CorpusSample values")
        if tuple(sorted(self.prompts, key=lambda value: value.prompt_id)) != self.prompts:
            raise ValueError("prompts must use canonical prompt_id ordering")
        if tuple(sorted(self.samples, key=lambda value: value.sample_id)) != self.samples:
            raise ValueError("samples must use canonical sample_id ordering")
        require_sha256("prompt_manifest_hash", self.prompt_manifest_hash)
        require_sha256("sample_manifest_hash", self.sample_manifest_hash)
        require_sha256("manifest_hash", self.manifest_hash)
        _validate_prompt_set(self.prompts)
        _validate_sample_set(self.samples)
        _validate_references(self.prompts, self.samples)
        _validate_prompt_family_partitions(self.prompts)
        _validate_pairs(self.samples)
        expected_prompt_hash = sha256_json(tuple(value.record_hash for value in self.prompts))
        expected_sample_hash = sha256_json(tuple(value.record_hash for value in self.samples))
        if self.prompt_manifest_hash != expected_prompt_hash:
            raise ValueError("prompt_manifest_hash does not match prompt records")
        if self.sample_manifest_hash != expected_sample_hash:
            raise ValueError("sample_manifest_hash does not match sample records")
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match corpus manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_id": self.corpus_id,
            "language": self.language,
            "deduplication_policy": self.deduplication_policy.value,
            "prompts": self.prompts,
            "samples": self.samples,
            "prompt_manifest_hash": self.prompt_manifest_hash,
            "sample_manifest_hash": self.sample_manifest_hash,
        }

    def samples_for_split(self, split: CorpusSplit) -> tuple[CorpusSample, ...]:
        if not isinstance(split, CorpusSplit):
            raise TypeError("split must be a CorpusSplit")
        return tuple(value for value in self.samples if value.split is split)


def _validate_prompt_set(prompts: tuple[PromptRecord, ...]) -> None:
    ids = tuple(value.prompt_id for value in prompts)
    hashes = tuple(value.record_hash for value in prompts)
    text_hashes = tuple(value.text_sha256 for value in prompts)
    if len(set(ids)) != len(ids):
        raise CorpusIntegrityError("prompt IDs must be unique")
    if len(set(hashes)) != len(hashes):
        raise CorpusIntegrityError("prompt records must be unique")
    if len(set(text_hashes)) != len(text_hashes):
        raise CorpusLeakageError("exact UTF-8 prompt texts must not appear under multiple prompt identities")


def _validate_sample_set(samples: tuple[CorpusSample, ...]) -> None:
    ids = tuple(value.sample_id for value in samples)
    record_hashes = tuple(value.record_hash for value in samples)
    text_hashes = tuple(value.text_sha256 for value in samples)
    generation_token_hashes = tuple(value.generation_tokens.continuation_token_hash for value in samples)
    if len(set(ids)) != len(ids):
        raise CorpusIntegrityError("sample IDs must be unique")
    if len(set(record_hashes)) != len(record_hashes):
        raise CorpusIntegrityError("sample records must be unique")
    if len(set(text_hashes)) != len(text_hashes):
        raise CorpusIntegrityError("exact UTF-8 sample outputs must be deduplicated before manifest construction")
    if len(set(generation_token_hashes)) != len(generation_token_hashes):
        raise CorpusIntegrityError("generated continuation token sequences must be unique across corpus samples")


def _validate_references(prompts: tuple[PromptRecord, ...], samples: tuple[CorpusSample, ...]) -> None:
    prompt_by_id = {value.prompt_id: value for value in prompts}
    used_prompt_ids: set[str] = set()
    for sample in samples:
        prompt = prompt_by_id.get(sample.prompt_id)
        if prompt is None:
            raise CorpusIntegrityError(f"sample references unknown prompt_id {sample.prompt_id}")
        used_prompt_ids.add(sample.prompt_id)
        if (
            sample.prompt_family_id != prompt.prompt_family_id
            or sample.domain is not prompt.domain
            or sample.split is not prompt.split
            or sample.language != prompt.language
        ):
            raise CorpusIntegrityError("sample prompt metadata does not match the referenced prompt record")
    unused = sorted(set(prompt_by_id) - used_prompt_ids)
    if unused:
        raise CorpusIntegrityError(f"corpus manifest contains unused prompts: {unused}")


def _validate_prompt_family_partitions(prompts: tuple[PromptRecord, ...]) -> None:
    family_splits: dict[str, set[CorpusSplit]] = defaultdict(set)
    for prompt in prompts:
        family_splits[prompt.prompt_family_id].add(prompt.split)
    leaking = sorted(family for family, splits in family_splits.items() if len(splits) != 1)
    if leaking:
        raise CorpusLeakageError(f"prompt families cross corpus partitions: {leaking}")


def _pair_signature(sample: CorpusSample) -> tuple[object, ...]:
    return (
        sample.prompt_id,
        sample.prompt_family_id,
        sample.domain,
        sample.split,
        sample.language,
        sample.model.identity_hash,
        sample.generation_tokens.input_token_hash,
        sample.generation_tokens.attention_mask,
        sample.generation_tokens.prompt_length_after_templating,
        sample.generation_tokens.continuation_start_index,
        sample.generation.matching_signature_hash,
        sample.watermark.condition_hash,
        sample.target_length,
        sample.prompt_boundary_mode,
        sample.text_only_tokens is not None,
    )


def _validate_pairs(samples: tuple[CorpusSample, ...]) -> None:
    groups: dict[str, list[CorpusSample]] = defaultdict(list)
    for sample in samples:
        groups[sample.match_id].append(sample)
    for match_id, group in sorted(groups.items()):
        if len(group) != 2:
            raise CorpusPairingError(f"match_id {match_id} must contain exactly two controlled-group samples")
        labels = {value.label for value in group}
        if labels != {WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED}:
            raise CorpusPairingError(f"match_id {match_id} must contain one watermarked and one unwatermarked sample")
        if _pair_signature(group[0]) != _pair_signature(group[1]):
            raise CorpusPairingError(f"match_id {match_id} does not preserve matched non-watermark generation parameters")


def build_corpus_manifest(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
    language: str = "en",
    deduplication_policy: DeduplicationPolicy = DeduplicationPolicy.EXACT_UTF8,
) -> CorpusManifest:
    if not isinstance(prompts, Sequence) or isinstance(prompts, (str, bytes, bytearray)):
        raise TypeError("prompts must be a sequence")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes, bytearray)):
        raise TypeError("samples must be a sequence")
    prompt_tuple = tuple(sorted(tuple(prompts), key=lambda value: value.prompt_id if isinstance(value, PromptRecord) else ""))
    sample_tuple = tuple(sorted(tuple(samples), key=lambda value: value.sample_id if isinstance(value, CorpusSample) else ""))
    prompt_manifest_hash = sha256_json(tuple(value.record_hash for value in prompt_tuple if isinstance(value, PromptRecord)))
    sample_manifest_hash = sha256_json(tuple(value.record_hash for value in sample_tuple if isinstance(value, CorpusSample)))
    payload = {
        "algorithm_version": CORPUS_MANIFEST_ALGORITHM_VERSION,
        "corpus_id": corpus_id,
        "language": language,
        "deduplication_policy": deduplication_policy.value if isinstance(deduplication_policy, DeduplicationPolicy) else deduplication_policy,
        "prompts": prompt_tuple,
        "samples": sample_tuple,
        "prompt_manifest_hash": prompt_manifest_hash,
        "sample_manifest_hash": sample_manifest_hash,
    }
    return CorpusManifest(
        corpus_id=corpus_id,
        language=language,
        deduplication_policy=deduplication_policy,
        prompts=prompt_tuple,
        samples=sample_tuple,
        prompt_manifest_hash=prompt_manifest_hash,
        sample_manifest_hash=sample_manifest_hash,
        manifest_hash=sha256_json(payload),
    )
