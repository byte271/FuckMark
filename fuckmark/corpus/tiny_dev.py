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


TINY_DEV_CORPUS_ALGORITHM_VERSION = "tiny-dev-corpus-v1"
TINY_DEV_TARGET_LENGTH = 64
TINY_DEV_PAIRS_PER_CELL = 1
TINY_DEV_SPLITS = (
    CorpusSplit.THRESHOLD_CALIBRATION,
    CorpusSplit.ATTACK_DEVELOPMENT,
)
TINY_DEV_DOMAINS = tuple(CorpusDomain)


class TinyDevCorpusError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TinyDevCorpusCell:
    split: CorpusSplit
    domain: CorpusDomain
    pair_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.split, CorpusSplit):
            raise TypeError("split must be a CorpusSplit")
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("pair_count", self.pair_count)
        if self.pair_count != TINY_DEV_PAIRS_PER_CELL:
            raise ValueError("tiny development corpus cells must contain exactly one matched pair")


@dataclass(frozen=True, slots=True)
class TinyDevCorpusArtifact:
    algorithm_version: str
    manifest: CorpusManifest
    target_length: int
    pairs_per_cell: int
    required_splits: tuple[CorpusSplit, ...]
    required_domains: tuple[CorpusDomain, ...]
    model_identity_hash: str
    generation_matching_signature_hash: str
    watermark_condition_hash: str
    cells: tuple[TinyDevCorpusCell, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_CORPUS_ALGORITHM_VERSION:
            raise ValueError("unsupported tiny development corpus algorithm version")
        if not isinstance(self.manifest, CorpusManifest):
            raise TypeError("manifest must be a CorpusManifest")
        require_int("target_length", self.target_length)
        if self.target_length != TINY_DEV_TARGET_LENGTH or self.target_length not in TARGET_LENGTHS:
            raise ValueError("tiny development corpus target length must be 64")
        require_int("pairs_per_cell", self.pairs_per_cell)
        if self.pairs_per_cell != TINY_DEV_PAIRS_PER_CELL:
            raise ValueError("tiny development corpus pairs_per_cell must be one")
        if self.required_splits != TINY_DEV_SPLITS:
            raise ValueError("tiny development corpus split profile does not match the frozen profile")
        if self.required_domains != TINY_DEV_DOMAINS:
            raise ValueError("tiny development corpus domain profile does not match the frozen profile")
        require_sha256("model_identity_hash", self.model_identity_hash)
        require_sha256("generation_matching_signature_hash", self.generation_matching_signature_hash)
        require_sha256("watermark_condition_hash", self.watermark_condition_hash)
        if not isinstance(self.cells, tuple):
            raise TypeError("cells must be a tuple")
        if any(not isinstance(value, TinyDevCorpusCell) for value in self.cells):
            raise TypeError("cells must contain TinyDevCorpusCell values")
        expected_cells = tuple(
            TinyDevCorpusCell(split, domain, TINY_DEV_PAIRS_PER_CELL)
            for split in TINY_DEV_SPLITS
            for domain in TINY_DEV_DOMAINS
        )
        if self.cells != expected_cells:
            raise ValueError("tiny development corpus cells do not match the frozen split/domain matrix")
        _validate_tiny_dev_manifest(
            self.manifest,
            self.model_identity_hash,
            self.generation_matching_signature_hash,
            self.watermark_condition_hash,
        )
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self._payload()):
            raise ValueError("artifact_hash does not match tiny development corpus artifact")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "manifest_hash": self.manifest.manifest_hash,
            "target_length": self.target_length,
            "pairs_per_cell": self.pairs_per_cell,
            "required_splits": tuple(value.value for value in self.required_splits),
            "required_domains": tuple(value.value for value in self.required_domains),
            "model_identity_hash": self.model_identity_hash,
            "generation_matching_signature_hash": self.generation_matching_signature_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "cells": self.cells,
        }


def _validate_tiny_dev_manifest(
    manifest: CorpusManifest,
    model_identity_hash: str,
    generation_matching_signature_hash: str,
    watermark_condition_hash: str,
) -> None:
    prompts = manifest.prompts
    samples = manifest.samples
    expected_pair_count = len(TINY_DEV_SPLITS) * len(TINY_DEV_DOMAINS) * TINY_DEV_PAIRS_PER_CELL
    if len(samples) != expected_pair_count * 2:
        raise TinyDevCorpusError("tiny development corpus must contain exactly sixteen samples")
    if len({sample.match_id for sample in samples}) != expected_pair_count:
        raise TinyDevCorpusError("tiny development corpus must contain exactly eight matched pairs")
    if len(prompts) != expected_pair_count:
        raise TinyDevCorpusError("tiny development corpus must contain exactly one prompt per matched pair")
    allowed_splits = set(TINY_DEV_SPLITS)
    allowed_domains = set(TINY_DEV_DOMAINS)
    if any(prompt.split not in allowed_splits for prompt in prompts):
        raise TinyDevCorpusError("tiny development prompts may use only calibration or attack-development splits")
    if any(prompt.domain not in allowed_domains for prompt in prompts):
        raise TinyDevCorpusError("tiny development prompts must use the frozen four-domain profile")
    if any(sample.split not in allowed_splits for sample in samples):
        raise TinyDevCorpusError("tiny development samples may use only calibration or attack-development splits")
    if any(sample.domain not in allowed_domains for sample in samples):
        raise TinyDevCorpusError("tiny development samples must use the frozen four-domain profile")
    if any(sample.target_length != TINY_DEV_TARGET_LENGTH for sample in samples):
        raise TinyDevCorpusError("tiny development samples must target 64 continuation tokens")
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in samples):
        raise TinyDevCorpusError("tiny development samples must use DEV_KEYS only")
    if {sample.model.identity_hash for sample in samples} != {model_identity_hash}:
        raise TinyDevCorpusError("tiny development corpus must use one frozen model/tokenizer identity")
    if {sample.generation.matching_signature_hash for sample in samples} != {
        generation_matching_signature_hash
    }:
        raise TinyDevCorpusError("tiny development corpus must use one matched generation-parameter signature")
    if {sample.watermark.condition_hash for sample in samples} != {watermark_condition_hash}:
        raise TinyDevCorpusError("tiny development corpus must use one frozen DEV watermark condition")
    prompt_counts = Counter(sample.prompt_id for sample in samples)
    if any(prompt_counts[prompt.prompt_id] != 2 for prompt in prompts):
        raise TinyDevCorpusError("each tiny development prompt must bind exactly one matched on/off pair")
    cell_pairs: Counter[tuple[CorpusSplit, CorpusDomain]] = Counter()
    seen_match_ids: set[str] = set()
    for sample in samples:
        if sample.match_id in seen_match_ids:
            continue
        seen_match_ids.add(sample.match_id)
        cell_pairs[(sample.split, sample.domain)] += 1
    expected_cells = {
        (split, domain): TINY_DEV_PAIRS_PER_CELL
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    }
    if dict(cell_pairs) != expected_cells:
        raise TinyDevCorpusError("tiny development corpus must contain one matched pair in every split/domain cell")


def build_tiny_dev_corpus(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> TinyDevCorpusArtifact:
    require_clean_string("corpus_id", corpus_id)
    manifest = build_corpus_manifest(corpus_id, prompts, samples)
    model_hashes = {sample.model.identity_hash for sample in manifest.samples}
    generation_hashes = {sample.generation.matching_signature_hash for sample in manifest.samples}
    watermark_hashes = {sample.watermark.condition_hash for sample in manifest.samples}
    if len(model_hashes) != 1:
        raise TinyDevCorpusError("tiny development corpus must use exactly one model/tokenizer identity")
    if len(generation_hashes) != 1:
        raise TinyDevCorpusError("tiny development corpus must use exactly one generation matching signature")
    if len(watermark_hashes) != 1:
        raise TinyDevCorpusError("tiny development corpus must use exactly one watermark condition")
    model_identity_hash = next(iter(model_hashes))
    generation_matching_signature_hash = next(iter(generation_hashes))
    watermark_condition_hash = next(iter(watermark_hashes))
    _validate_tiny_dev_manifest(
        manifest,
        model_identity_hash,
        generation_matching_signature_hash,
        watermark_condition_hash,
    )
    cells = tuple(
        TinyDevCorpusCell(split, domain, TINY_DEV_PAIRS_PER_CELL)
        for split in TINY_DEV_SPLITS
        for domain in TINY_DEV_DOMAINS
    )
    payload = {
        "algorithm_version": TINY_DEV_CORPUS_ALGORITHM_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "target_length": TINY_DEV_TARGET_LENGTH,
        "pairs_per_cell": TINY_DEV_PAIRS_PER_CELL,
        "required_splits": tuple(value.value for value in TINY_DEV_SPLITS),
        "required_domains": tuple(value.value for value in TINY_DEV_DOMAINS),
        "model_identity_hash": model_identity_hash,
        "generation_matching_signature_hash": generation_matching_signature_hash,
        "watermark_condition_hash": watermark_condition_hash,
        "cells": cells,
    }
    return TinyDevCorpusArtifact(
        TINY_DEV_CORPUS_ALGORITHM_VERSION,
        manifest,
        TINY_DEV_TARGET_LENGTH,
        TINY_DEV_PAIRS_PER_CELL,
        TINY_DEV_SPLITS,
        TINY_DEV_DOMAINS,
        model_identity_hash,
        generation_matching_signature_hash,
        watermark_condition_hash,
        cells,
        sha256_json(payload),
    )
