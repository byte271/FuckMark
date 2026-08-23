from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .manifest import CorpusManifest, build_corpus_manifest
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusDomain, CorpusSplit, KeySplit, TARGET_LENGTHS
from .tiny_dev import (
    TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
    TINY_DEV_SPLITS,
    TINY_DEV_TARGET_LENGTH,
    TINY_DEV_DOMAINS,
    TinyDevCorpusError,
)


TINY_DEV_V3_CORPUS_ALGORITHM_VERSION = "tiny-dev-corpus-v3"
TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN = 16


def _validate_attack_pairs_per_domain(attack_pairs_per_domain: int) -> None:
    require_int("attack_pairs_per_domain", attack_pairs_per_domain)
    if attack_pairs_per_domain < 1 or attack_pairs_per_domain > TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN:
        raise TinyDevCorpusError(
            "v3 attack pairs per domain must lie between 1 and "
            f"{TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN}"
        )


@dataclass(frozen=True, slots=True)
class TinyDevV3CorpusCell:
    split: CorpusSplit
    domain: CorpusDomain
    pair_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.split, CorpusSplit):
            raise TypeError("split must be a CorpusSplit")
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("pair_count", self.pair_count)
        if self.pair_count < 1:
            raise ValueError("tiny development v3 corpus cell pair count must be positive")


@dataclass(frozen=True, slots=True)
class TinyDevV3CorpusArtifact:
    algorithm_version: str
    manifest: CorpusManifest
    target_length: int
    calibration_pairs_per_domain: int
    attack_pairs_per_domain: int
    required_splits: tuple[CorpusSplit, ...]
    required_domains: tuple[CorpusDomain, ...]
    model_identity_hash: str
    generation_matching_signature_hash: str
    watermark_condition_hash: str
    cells: tuple[TinyDevV3CorpusCell, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_V3_CORPUS_ALGORITHM_VERSION:
            raise ValueError("unsupported tiny development v3 corpus algorithm version")
        if not isinstance(self.manifest, CorpusManifest):
            raise TypeError("manifest must be a CorpusManifest")
        require_int("target_length", self.target_length)
        if self.target_length != TINY_DEV_TARGET_LENGTH or self.target_length not in TARGET_LENGTHS:
            raise ValueError("tiny development v3 corpus target length must be 64")
        require_int("calibration_pairs_per_domain", self.calibration_pairs_per_domain)
        if self.calibration_pairs_per_domain != TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN:
            raise ValueError("v3 calibration pair count must match the frozen calibration profile")
        _validate_attack_pairs_per_domain(self.attack_pairs_per_domain)
        if self.required_splits != TINY_DEV_SPLITS:
            raise ValueError("tiny development v3 corpus split profile does not match the frozen profile")
        if self.required_domains != TINY_DEV_DOMAINS:
            raise ValueError("tiny development v3 corpus domain profile does not match the frozen profile")
        require_sha256("model_identity_hash", self.model_identity_hash)
        require_sha256("generation_matching_signature_hash", self.generation_matching_signature_hash)
        require_sha256("watermark_condition_hash", self.watermark_condition_hash)
        if not isinstance(self.cells, tuple):
            raise TypeError("cells must be a tuple")
        if any(not isinstance(value, TinyDevV3CorpusCell) for value in self.cells):
            raise TypeError("cells must contain TinyDevV3CorpusCell values")
        expected_cells = _expected_v3_cells(self.attack_pairs_per_domain)
        if self.cells != expected_cells:
            raise ValueError("tiny development v3 corpus cells do not match the parameterized matrix")
        _validate_v3_manifest(
            self.manifest,
            self.model_identity_hash,
            self.generation_matching_signature_hash,
            self.watermark_condition_hash,
            self.attack_pairs_per_domain,
        )
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self._payload()):
            raise ValueError("artifact_hash does not match tiny development v3 corpus artifact")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "manifest_hash": self.manifest.manifest_hash,
            "target_length": self.target_length,
            "calibration_pairs_per_domain": self.calibration_pairs_per_domain,
            "attack_pairs_per_domain": self.attack_pairs_per_domain,
            "required_splits": tuple(value.value for value in self.required_splits),
            "required_domains": tuple(value.value for value in self.required_domains),
            "model_identity_hash": self.model_identity_hash,
            "generation_matching_signature_hash": self.generation_matching_signature_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "cells": self.cells,
        }


def _expected_v3_cells(attack_pairs_per_domain: int) -> tuple[TinyDevV3CorpusCell, ...]:
    return tuple(
        TinyDevV3CorpusCell(split, domain, _v3_pairs_for_split(split, attack_pairs_per_domain))
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    )


def _v3_pairs_for_split(split: CorpusSplit, attack_pairs_per_domain: int) -> int:
    if split is CorpusSplit.THRESHOLD_CALIBRATION:
        return TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN
    if split is CorpusSplit.ATTACK_DEVELOPMENT:
        return attack_pairs_per_domain
    raise TinyDevCorpusError("split is outside the frozen tiny development profile")


def _validate_v3_manifest(
    manifest: CorpusManifest,
    model_identity_hash: str,
    generation_matching_signature_hash: str,
    watermark_condition_hash: str,
    attack_pairs_per_domain: int,
) -> None:
    prompts = manifest.prompts
    samples = manifest.samples
    expected_pair_count = sum(
        _v3_pairs_for_split(split, attack_pairs_per_domain) * len(TINY_DEV_DOMAINS)
        for split in TINY_DEV_SPLITS
    )
    expected_sample_count = expected_pair_count * 2
    if len(samples) != expected_sample_count:
        raise TinyDevCorpusError(
            f"tiny development v3 corpus must contain exactly {expected_sample_count} samples"
        )
    if len({sample.match_id for sample in samples}) != expected_pair_count:
        raise TinyDevCorpusError(
            f"tiny development v3 corpus must contain exactly {expected_pair_count} matched pairs"
        )
    if len(prompts) != expected_pair_count:
        raise TinyDevCorpusError("tiny development v3 corpus must contain exactly one prompt per matched pair")
    allowed_splits = set(TINY_DEV_SPLITS)
    allowed_domains = set(TINY_DEV_DOMAINS)
    if any(prompt.split not in allowed_splits for prompt in prompts):
        raise TinyDevCorpusError("tiny development v3 prompts may use only calibration or attack-development splits")
    if any(prompt.domain not in allowed_domains for prompt in prompts):
        raise TinyDevCorpusError("tiny development v3 prompts must use the frozen four-domain profile")
    if any(sample.split not in allowed_splits for sample in samples):
        raise TinyDevCorpusError("tiny development v3 samples may use only calibration or attack-development splits")
    if any(sample.domain not in allowed_domains for sample in samples):
        raise TinyDevCorpusError("tiny development v3 samples must use the frozen four-domain profile")
    if any(sample.target_length != TINY_DEV_TARGET_LENGTH for sample in samples):
        raise TinyDevCorpusError("tiny development v3 samples must target 64 continuation tokens")
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in samples):
        raise TinyDevCorpusError("tiny development v3 samples must use DEV_KEYS only")
    if {sample.model.identity_hash for sample in samples} != {model_identity_hash}:
        raise TinyDevCorpusError("tiny development v3 corpus must use one frozen model/tokenizer identity")
    if {sample.generation.matching_signature_hash for sample in samples} != {
        generation_matching_signature_hash
    }:
        raise TinyDevCorpusError("tiny development v3 corpus must use one matched generation-parameter signature")
    if {sample.watermark.condition_hash for sample in samples} != {watermark_condition_hash}:
        raise TinyDevCorpusError("tiny development v3 corpus must use one frozen DEV watermark condition")
    prompt_counts = Counter(sample.prompt_id for sample in samples)
    if any(prompt_counts[prompt.prompt_id] != 2 for prompt in prompts):
        raise TinyDevCorpusError("each tiny development v3 prompt must bind exactly one matched on/off pair")
    cell_pairs: Counter[tuple[CorpusSplit, CorpusDomain]] = Counter()
    seen_match_ids: set[str] = set()
    for sample in samples:
        if sample.match_id in seen_match_ids:
            continue
        seen_match_ids.add(sample.match_id)
        cell_pairs[(sample.split, sample.domain)] += 1
    expected_cells = {
        (split, domain): _v3_pairs_for_split(split, attack_pairs_per_domain)
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    }
    if dict(cell_pairs) != expected_cells:
        raise TinyDevCorpusError("tiny development v3 corpus split/domain pair counts do not match the profile")
    calibration_negatives = sum(
        1
        for sample in samples
        if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
        and sample.label.value == "unwatermarked"
    )
    if calibration_negatives < 100:
        raise TinyDevCorpusError("tiny development v3 corpus must contain at least 100 calibration negatives")


def build_tiny_dev_v3_corpus(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
    *,
    attack_pairs_per_domain: int,
) -> TinyDevV3CorpusArtifact:
    require_clean_string("corpus_id", corpus_id)
    _validate_attack_pairs_per_domain(attack_pairs_per_domain)
    manifest = build_corpus_manifest(corpus_id, prompts, samples)
    model_hashes = {sample.model.identity_hash for sample in manifest.samples}
    generation_hashes = {sample.generation.matching_signature_hash for sample in manifest.samples}
    watermark_hashes = {sample.watermark.condition_hash for sample in manifest.samples}
    if len(model_hashes) != 1:
        raise TinyDevCorpusError("tiny development v3 corpus must use exactly one model/tokenizer identity")
    if len(generation_hashes) != 1:
        raise TinyDevCorpusError("tiny development v3 corpus must use exactly one generation matching signature")
    if len(watermark_hashes) != 1:
        raise TinyDevCorpusError("tiny development v3 corpus must use exactly one watermark condition")
    model_identity_hash = next(iter(model_hashes))
    generation_matching_signature_hash = next(iter(generation_hashes))
    watermark_condition_hash = next(iter(watermark_hashes))
    _validate_v3_manifest(
        manifest,
        model_identity_hash,
        generation_matching_signature_hash,
        watermark_condition_hash,
        attack_pairs_per_domain,
    )
    cells = _expected_v3_cells(attack_pairs_per_domain)
    payload = {
        "algorithm_version": TINY_DEV_V3_CORPUS_ALGORITHM_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "target_length": TINY_DEV_TARGET_LENGTH,
        "calibration_pairs_per_domain": TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
        "attack_pairs_per_domain": attack_pairs_per_domain,
        "required_splits": tuple(value.value for value in TINY_DEV_SPLITS),
        "required_domains": tuple(value.value for value in TINY_DEV_DOMAINS),
        "model_identity_hash": model_identity_hash,
        "generation_matching_signature_hash": generation_matching_signature_hash,
        "watermark_condition_hash": watermark_condition_hash,
        "cells": cells,
    }
    return TinyDevV3CorpusArtifact(
        TINY_DEV_V3_CORPUS_ALGORITHM_VERSION,
        manifest,
        TINY_DEV_TARGET_LENGTH,
        TINY_DEV_CALIBRATION_PAIRS_PER_DOMAIN,
        attack_pairs_per_domain,
        TINY_DEV_SPLITS,
        TINY_DEV_DOMAINS,
        model_identity_hash,
        generation_matching_signature_hash,
        watermark_condition_hash,
        cells,
        sha256_json(payload),
    )
