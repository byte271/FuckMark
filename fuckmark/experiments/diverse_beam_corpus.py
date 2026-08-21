from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .._validation import (
    normalize_token_sequence,
    require_bool,
    require_clean_string,
    require_int,
    require_sha256,
)
from ..corpus.generation import GenerationParameters, WatermarkCondition
from ..corpus.identity import ModelTokenizerIdentity
from ..corpus.mid_dev import MID_DEV_PROMPT_FAMILIES
from ..corpus.mid_dev_generation import MidDevGeneratedContinuation
from ..corpus.schema import KeySplit, require_exact_text
from ..hashing import sha256_json, sha256_text

DIVERSE_BEAM_CORPUS_PROFILE_VERSION = "diverse-beam-real-corpus-profile-v1"
DIVERSE_BEAM_GENERATION_SHARD_VERSION = "diverse-beam-generation-shard-v1"
DIVERSE_BEAM_FROZEN_CORPUS_VERSION = "diverse-beam-frozen-corpus-v1"
DIVERSE_BEAM_TARGET_LENGTHS = (128, 256)
DIVERSE_BEAM_GENERATED_PER_LENGTH = 320
DIVERSE_BEAM_ANALYSIS_PER_LENGTH = 250
DIVERSE_BEAM_GENERATION_SHARD_COUNT = 32
DIVERSE_BEAM_GENERATION_SEED_BASE = 1_270_000
DIVERSE_BEAM_GENERATION_SEED_STRIDE = 10_000
DIVERSE_BEAM_PROMPT_SOURCE_ID = "fuckmark-diverse-beam-real-corpus-prompts-v1"
DIVERSE_BEAM_PROMPT_LICENSE_ID = "LicenseRef-FuckMark-Unspecified"
DIVERSE_BEAM_PROMPT_PROVENANCE = "fuckmark/experiments/diverse_beam_corpus.py"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SUBJECTS = (
    "reproducible seed handling",
    "calibration drift monitoring",
    "held-out evaluation design",
    "tokenization change control",
    "protected-content preservation",
    "matched negative controls",
    "model revision pinning",
    "deterministic artifact replay",
    "multiple-testing control",
    "measurement uncertainty",
    "failure provenance",
    "domain-shift diagnosis",
    "prompt-boundary handling",
    "candidate enumeration",
    "semantic fidelity review",
    "edit-budget accounting",
    "confidence-interval reporting",
    "selection-leakage prevention",
    "independent source grouping",
    "null-result interpretation",
)
_CONTEXTS = (
    "a small laboratory study",
    "a production rollout",
    "a cross-domain benchmark",
    "a replicated academic experiment",
    "a multilingual data pipeline",
    "a long-running monitoring service",
    "a constrained offline evaluation",
    "a collaborative research project",
    "a public reproducibility package",
    "a high-volume batch process",
    "a safety-critical validation review",
    "a resource-limited deployment",
    "an independently audited trial",
    "a versioned software migration",
    "a noisy real-world dataset",
    "a predeclared comparison study",
)


class DiverseBeamGenerationBackend(Protocol):
    @property
    def model_identity(self) -> ModelTokenizerIdentity: ...

    @property
    def watermark_condition(self) -> WatermarkCondition: ...

    def generation_parameters(
        self, seed: int, target_length: int
    ) -> GenerationParameters: ...

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation: ...


@dataclass(frozen=True, slots=True)
class DiverseBeamPromptSpec:
    ordinal: int
    sample_id: str
    prompt_family_id: str
    domain: str
    prompt_text: str
    prompt_text_hash: str
    target_length: int
    seed: int
    record_hash: str

    def __post_init__(self) -> None:
        require_int("ordinal", self.ordinal)
        require_int("target_length", self.target_length)
        require_int("seed", self.seed)
        if self.ordinal < 0 or self.seed < 0:
            raise ValueError("prompt ordinal and seed must be non-negative")
        if self.target_length not in DIVERSE_BEAM_TARGET_LENGTHS:
            raise ValueError("prompt target length is outside the frozen profile")
        for name in ("sample_id", "prompt_family_id", "domain"):
            require_clean_string(name, getattr(self, name))
        require_exact_text("prompt_text", self.prompt_text)
        require_sha256("prompt_text_hash", self.prompt_text_hash)
        require_sha256("record_hash", self.record_hash)
        if self.prompt_text_hash != sha256_text(self.prompt_text):
            raise ValueError("prompt text hash mismatch")
        if self.record_hash != sha256_json(self.payload()):
            raise ValueError("prompt record hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": DIVERSE_BEAM_CORPUS_PROFILE_VERSION,
            "ordinal": self.ordinal,
            "sample_id": self.sample_id,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain,
            "prompt_text_hash": self.prompt_text_hash,
            "target_length": self.target_length,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class DiverseBeamGeneratedSample:
    algorithm_version: str
    ordinal: int
    sample_id: str
    prompt_family_id: str
    domain: str
    prompt_text_hash: str
    target_length: int
    seed: int
    text: str
    text_hash: str
    continuation_token_ids: tuple[int, ...]
    continuation_token_hash: str
    text_only_token_ids: tuple[int, ...]
    text_only_token_hash: str
    generation_config_hash: str
    generation_matching_signature_hash: str
    model_identity_hash: str
    watermark_condition_hash: str
    label: str
    key_split: str
    record_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != DIVERSE_BEAM_GENERATION_SHARD_VERSION:
            raise ValueError("unsupported generated sample version")
        require_int("ordinal", self.ordinal)
        require_int("target_length", self.target_length)
        require_int("seed", self.seed)
        if self.ordinal < 0 or self.seed < 0:
            raise ValueError("sample ordinal and seed must be non-negative")
        if self.target_length not in DIVERSE_BEAM_TARGET_LENGTHS:
            raise ValueError("sample target length is outside the frozen profile")
        for name in ("sample_id", "prompt_family_id", "domain", "label", "key_split"):
            require_clean_string(name, getattr(self, name))
        if self.label != "watermarked" or self.key_split != KeySplit.DEV.value:
            raise ValueError("Diverse Beam samples must be watermarked with DEV_KEYS")
        require_exact_text("text", self.text)
        for name in (
            "prompt_text_hash",
            "text_hash",
            "continuation_token_hash",
            "text_only_token_hash",
            "generation_config_hash",
            "generation_matching_signature_hash",
            "model_identity_hash",
            "watermark_condition_hash",
            "record_hash",
        ):
            require_sha256(name, getattr(self, name))
        continuation = normalize_token_sequence(
            "continuation_token_ids", self.continuation_token_ids
        )
        text_only = normalize_token_sequence(
            "text_only_token_ids", self.text_only_token_ids
        )
        object.__setattr__(self, "continuation_token_ids", continuation)
        object.__setattr__(self, "text_only_token_ids", text_only)
        if len(continuation) != self.target_length:
            raise ValueError("continuation token count does not match target length")
        if not text_only:
            raise ValueError("text-only token track must not be empty")
        if self.text_hash != sha256_text(self.text):
            raise ValueError("generated text hash mismatch")
        if self.continuation_token_hash != sha256_json(continuation):
            raise ValueError("continuation token hash mismatch")
        if self.text_only_token_hash != sha256_json(text_only):
            raise ValueError("text-only token hash mismatch")
        if self.record_hash != sha256_json(self.payload()):
            raise ValueError("generated sample record hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": DIVERSE_BEAM_GENERATION_SHARD_VERSION,
            "ordinal": self.ordinal,
            "sample_id": self.sample_id,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain,
            "prompt_text_hash": self.prompt_text_hash,
            "target_length": self.target_length,
            "seed": self.seed,
            "text": self.text,
            "text_hash": self.text_hash,
            "continuation_token_ids": self.continuation_token_ids,
            "continuation_token_hash": self.continuation_token_hash,
            "text_only_token_ids": self.text_only_token_ids,
            "text_only_token_hash": self.text_only_token_hash,
            "generation_config_hash": self.generation_config_hash,
            "generation_matching_signature_hash": self.generation_matching_signature_hash,
            "model_identity_hash": self.model_identity_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "label": self.label,
            "key_split": self.key_split,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "record_hash": self.record_hash}


@dataclass(frozen=True, slots=True)
class DiverseBeamGenerationShard:
    algorithm_version: str
    source_code_commit: str
    prompt_profile_hash: str
    shard_index: int
    shard_count: int
    model_identity_hash: str
    watermark_condition_hash: str
    generation_key_access_required: bool
    detector_access_observed: bool
    samples: tuple[DiverseBeamGeneratedSample, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != DIVERSE_BEAM_GENERATION_SHARD_VERSION:
            raise ValueError("unsupported Diverse Beam generation shard version")
        if _GIT_SHA_RE.fullmatch(self.source_code_commit) is None:
            raise ValueError("source_code_commit must be a lowercase Git SHA")
        require_sha256("prompt_profile_hash", self.prompt_profile_hash)
        require_int("shard_index", self.shard_index)
        require_int("shard_count", self.shard_count)
        if self.shard_count != DIVERSE_BEAM_GENERATION_SHARD_COUNT:
            raise ValueError("generation shard count drifted from the frozen profile")
        if not 0 <= self.shard_index < self.shard_count:
            raise ValueError("generation shard index is out of range")
        require_sha256("model_identity_hash", self.model_identity_hash)
        require_sha256("watermark_condition_hash", self.watermark_condition_hash)
        require_bool(
            "generation_key_access_required", self.generation_key_access_required
        )
        require_bool("detector_access_observed", self.detector_access_observed)
        if not self.generation_key_access_required or self.detector_access_observed:
            raise ValueError("generation access attestations are inconsistent")
        if not isinstance(self.samples, tuple) or any(
            not isinstance(value, DiverseBeamGeneratedSample) for value in self.samples
        ):
            raise TypeError("samples must contain DiverseBeamGeneratedSample values")
        expected = tuple(
            value
            for value in build_diverse_beam_prompt_specs()
            if value.ordinal % self.shard_count == self.shard_index
        )
        if tuple(value.sample_id for value in self.samples) != tuple(
            value.sample_id for value in expected
        ):
            raise ValueError("generation shard sample membership drifted")
        for sample, prompt in zip(self.samples, expected):
            if (
                sample.ordinal,
                sample.prompt_family_id,
                sample.domain,
                sample.prompt_text_hash,
                sample.target_length,
                sample.seed,
            ) != (
                prompt.ordinal,
                prompt.prompt_family_id,
                prompt.domain,
                prompt.prompt_text_hash,
                prompt.target_length,
                prompt.seed,
            ):
                raise ValueError("generated sample does not bind its frozen prompt")
            if sample.model_identity_hash != self.model_identity_hash:
                raise ValueError("generation shard mixed model identities")
            if sample.watermark_condition_hash != self.watermark_condition_hash:
                raise ValueError("generation shard mixed watermark conditions")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.prompt_profile_hash != diverse_beam_prompt_profile_hash():
            raise ValueError("generation shard prompt profile hash drifted")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("generation shard artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_code_commit": self.source_code_commit,
            "prompt_profile_hash": self.prompt_profile_hash,
            "shard_index": self.shard_index,
            "shard_count": self.shard_count,
            "model_identity_hash": self.model_identity_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "generation_key_access_required": self.generation_key_access_required,
            "detector_access_observed": self.detector_access_observed,
            "samples": tuple(value.as_dict() for value in self.samples),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "artifact_hash": self.artifact_hash}


@dataclass(frozen=True, slots=True)
class DiverseBeamFrozenCorpus:
    algorithm_version: str
    source_code_commit: str
    prompt_profile_hash: str
    generation_shard_hashes: tuple[str, ...]
    model_identity_hash: str
    watermark_condition_hash: str
    generated_sample_count: int
    duplicate_text_only_count: int
    duplicate_token_only_count: int
    duplicate_text_and_token_count: int
    duplicate_excluded_count: int
    surplus_unique_excluded_count: int
    eligible_sample_count: int
    target_lengths: tuple[int, ...]
    samples_per_target_length: int
    frozen_before_search: bool
    detector_score_selection_observed: bool
    planner_secret_access_observed: bool
    samples: tuple[DiverseBeamGeneratedSample, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != DIVERSE_BEAM_FROZEN_CORPUS_VERSION:
            raise ValueError("unsupported Diverse Beam frozen corpus version")
        if _GIT_SHA_RE.fullmatch(self.source_code_commit) is None:
            raise ValueError("source_code_commit must be a lowercase Git SHA")
        require_sha256("prompt_profile_hash", self.prompt_profile_hash)
        if self.prompt_profile_hash != diverse_beam_prompt_profile_hash():
            raise ValueError("frozen corpus prompt profile hash drifted")
        if not isinstance(self.generation_shard_hashes, tuple):
            raise TypeError("generation_shard_hashes must be a tuple")
        if len(self.generation_shard_hashes) != DIVERSE_BEAM_GENERATION_SHARD_COUNT:
            raise ValueError("frozen corpus requires every generation shard")
        if len(set(self.generation_shard_hashes)) != len(self.generation_shard_hashes):
            raise ValueError("generation shard hashes must be unique")
        for value in self.generation_shard_hashes:
            require_sha256("generation_shard_hash", value)
        for name in (
            "model_identity_hash",
            "watermark_condition_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "generated_sample_count",
            "duplicate_text_only_count",
            "duplicate_token_only_count",
            "duplicate_text_and_token_count",
            "duplicate_excluded_count",
            "surplus_unique_excluded_count",
            "eligible_sample_count",
            "samples_per_target_length",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        expected_generated = (
            len(DIVERSE_BEAM_TARGET_LENGTHS) * DIVERSE_BEAM_GENERATED_PER_LENGTH
        )
        expected_eligible = (
            len(DIVERSE_BEAM_TARGET_LENGTHS) * DIVERSE_BEAM_ANALYSIS_PER_LENGTH
        )
        if self.generated_sample_count != expected_generated:
            raise ValueError("generated sample count drifted from the frozen profile")
        if self.eligible_sample_count != expected_eligible:
            raise ValueError("eligible sample count drifted from the frozen profile")
        if self.samples_per_target_length != DIVERSE_BEAM_ANALYSIS_PER_LENGTH:
            raise ValueError("per-length sample count drifted from the frozen profile")
        if self.target_lengths != DIVERSE_BEAM_TARGET_LENGTHS:
            raise ValueError("target lengths drifted from the frozen profile")
        if self.duplicate_excluded_count != (
            self.duplicate_text_only_count
            + self.duplicate_token_only_count
            + self.duplicate_text_and_token_count
        ):
            raise ValueError("duplicate exclusion accounting is inconsistent")
        if self.generated_sample_count != (
            self.duplicate_excluded_count
            + self.surplus_unique_excluded_count
            + self.eligible_sample_count
        ):
            raise ValueError("frozen corpus sample accounting is inconsistent")
        for name in (
            "frozen_before_search",
            "detector_score_selection_observed",
            "planner_secret_access_observed",
        ):
            require_bool(name, getattr(self, name))
        if (
            not self.frozen_before_search
            or self.detector_score_selection_observed
            or self.planner_secret_access_observed
        ):
            raise ValueError("frozen corpus access attestations are inconsistent")
        if not isinstance(self.samples, tuple) or any(
            not isinstance(value, DiverseBeamGeneratedSample) for value in self.samples
        ):
            raise TypeError("samples must contain DiverseBeamGeneratedSample values")
        if len(self.samples) != self.eligible_sample_count:
            raise ValueError("frozen corpus sample length mismatch")
        expected_order = tuple(
            sorted(
                self.samples, key=lambda value: (value.target_length, value.sample_id)
            )
        )
        if self.samples != expected_order:
            raise ValueError("frozen corpus samples must be canonically ordered")
        if len({value.sample_id for value in self.samples}) != len(self.samples):
            raise ValueError("frozen corpus sample IDs must be unique")
        if len({value.text_hash for value in self.samples}) != len(self.samples):
            raise ValueError("frozen corpus generated texts must be unique")
        if len({value.continuation_token_hash for value in self.samples}) != len(
            self.samples
        ):
            raise ValueError("frozen corpus continuation token tracks must be unique")
        counts = Counter(value.target_length for value in self.samples)
        if counts != Counter(
            {value: self.samples_per_target_length for value in self.target_lengths}
        ):
            raise ValueError("frozen corpus target-length cells are incomplete")
        if {value.model_identity_hash for value in self.samples} != {
            self.model_identity_hash
        }:
            raise ValueError("frozen corpus mixed model identities")
        if {value.watermark_condition_hash for value in self.samples} != {
            self.watermark_condition_hash
        }:
            raise ValueError("frozen corpus mixed watermark conditions")
        prompts = {
            value.sample_id: value for value in build_diverse_beam_prompt_specs()
        }
        for sample in self.samples:
            prompt = prompts.get(sample.sample_id)
            if prompt is None:
                raise ValueError("frozen corpus contains an unknown sample ID")
            if (
                sample.ordinal,
                sample.prompt_family_id,
                sample.domain,
                sample.prompt_text_hash,
                sample.target_length,
                sample.seed,
            ) != (
                prompt.ordinal,
                prompt.prompt_family_id,
                prompt.domain,
                prompt.prompt_text_hash,
                prompt.target_length,
                prompt.seed,
            ):
                raise ValueError("frozen sample does not bind its prompt profile")
        for target_length in self.target_lengths:
            signatures = {
                value.generation_matching_signature_hash
                for value in self.samples
                if value.target_length == target_length
            }
            if len(signatures) != 1:
                raise ValueError(
                    "frozen corpus mixed generation settings within a length cell"
                )
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("frozen corpus artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_code_commit": self.source_code_commit,
            "prompt_profile_hash": self.prompt_profile_hash,
            "generation_shard_hashes": self.generation_shard_hashes,
            "model_identity_hash": self.model_identity_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "generated_sample_count": self.generated_sample_count,
            "duplicate_text_only_count": self.duplicate_text_only_count,
            "duplicate_token_only_count": self.duplicate_token_only_count,
            "duplicate_text_and_token_count": self.duplicate_text_and_token_count,
            "duplicate_excluded_count": self.duplicate_excluded_count,
            "surplus_unique_excluded_count": self.surplus_unique_excluded_count,
            "eligible_sample_count": self.eligible_sample_count,
            "target_lengths": self.target_lengths,
            "samples_per_target_length": self.samples_per_target_length,
            "frozen_before_search": self.frozen_before_search,
            "detector_score_selection_observed": self.detector_score_selection_observed,
            "planner_secret_access_observed": self.planner_secret_access_observed,
            "samples": tuple(value.as_dict() for value in self.samples),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "artifact_hash": self.artifact_hash}


def build_diverse_beam_prompt_specs() -> tuple[DiverseBeamPromptSpec, ...]:
    output = []
    for length_index, target_length in enumerate(DIVERSE_BEAM_TARGET_LENGTHS):
        for source_index in range(DIVERSE_BEAM_GENERATED_PER_LENGTH):
            ordinal = length_index * DIVERSE_BEAM_GENERATED_PER_LENGTH + source_index
            family = MID_DEV_PROMPT_FAMILIES[
                (source_index + length_index) % len(MID_DEV_PROMPT_FAMILIES)
            ]
            subject = _SUBJECTS[source_index // len(_CONTEXTS)]
            context = _CONTEXTS[source_index % len(_CONTEXTS)]
            prompt_text = family.template.format(
                topic=f"{subject} in {context}",
                target_length=target_length,
            )
            sample_id = f"diverse-beam-ab-{target_length}-{source_index:05d}"
            seed = (
                DIVERSE_BEAM_GENERATION_SEED_BASE
                + length_index * DIVERSE_BEAM_GENERATION_SEED_STRIDE
                + source_index
            )
            payload = {
                "algorithm_version": DIVERSE_BEAM_CORPUS_PROFILE_VERSION,
                "ordinal": ordinal,
                "sample_id": sample_id,
                "prompt_family_id": family.family_id,
                "domain": family.domain.value,
                "prompt_text_hash": sha256_text(prompt_text),
                "target_length": target_length,
                "seed": seed,
            }
            output.append(
                DiverseBeamPromptSpec(
                    ordinal=ordinal,
                    sample_id=sample_id,
                    prompt_family_id=family.family_id,
                    domain=family.domain.value,
                    prompt_text=prompt_text,
                    prompt_text_hash=payload["prompt_text_hash"],
                    target_length=target_length,
                    seed=seed,
                    record_hash=sha256_json(payload),
                )
            )
    return tuple(output)


def diverse_beam_prompt_profile_hash() -> str:
    return sha256_json(
        {
            "algorithm_version": DIVERSE_BEAM_CORPUS_PROFILE_VERSION,
            "source_id": DIVERSE_BEAM_PROMPT_SOURCE_ID,
            "license_id": DIVERSE_BEAM_PROMPT_LICENSE_ID,
            "provenance": DIVERSE_BEAM_PROMPT_PROVENANCE,
            "target_lengths": DIVERSE_BEAM_TARGET_LENGTHS,
            "generated_per_length": DIVERSE_BEAM_GENERATED_PER_LENGTH,
            "analysis_per_length": DIVERSE_BEAM_ANALYSIS_PER_LENGTH,
            "seed_base": DIVERSE_BEAM_GENERATION_SEED_BASE,
            "seed_stride": DIVERSE_BEAM_GENERATION_SEED_STRIDE,
            "subjects": _SUBJECTS,
            "contexts": _CONTEXTS,
            "prompt_record_hashes": tuple(
                value.record_hash for value in build_diverse_beam_prompt_specs()
            ),
        }
    )


def _generated_sample(
    prompt: DiverseBeamPromptSpec,
    generated: MidDevGeneratedContinuation,
    parameters: GenerationParameters,
    model_identity_hash: str,
    watermark_condition_hash: str,
) -> DiverseBeamGeneratedSample:
    if (
        parameters.seed != prompt.seed
        or parameters.max_new_tokens != prompt.target_length
    ):
        raise ValueError("generation parameters do not bind the frozen prompt")
    continuation = tuple(generated.continuation_token_ids)
    text_only = tuple(generated.text_only_token_ids)
    payload = {
        "algorithm_version": DIVERSE_BEAM_GENERATION_SHARD_VERSION,
        "ordinal": prompt.ordinal,
        "sample_id": prompt.sample_id,
        "prompt_family_id": prompt.prompt_family_id,
        "domain": prompt.domain,
        "prompt_text_hash": prompt.prompt_text_hash,
        "target_length": prompt.target_length,
        "seed": prompt.seed,
        "text": generated.text,
        "text_hash": sha256_text(generated.text),
        "continuation_token_ids": continuation,
        "continuation_token_hash": sha256_json(continuation),
        "text_only_token_ids": text_only,
        "text_only_token_hash": sha256_json(text_only),
        "generation_config_hash": parameters.config_hash,
        "generation_matching_signature_hash": parameters.matching_signature_hash,
        "model_identity_hash": model_identity_hash,
        "watermark_condition_hash": watermark_condition_hash,
        "label": "watermarked",
        "key_split": KeySplit.DEV.value,
    }
    return DiverseBeamGeneratedSample(**payload, record_hash=sha256_json(payload))


def generate_diverse_beam_shard(
    backend: DiverseBeamGenerationBackend,
    *,
    shard_index: int,
    shard_count: int,
    source_code_commit: str,
) -> DiverseBeamGenerationShard:
    require_int("shard_index", shard_index)
    require_int("shard_count", shard_count)
    if shard_count != DIVERSE_BEAM_GENERATION_SHARD_COUNT:
        raise ValueError("shard_count must match the frozen generation profile")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index is out of range")
    if _GIT_SHA_RE.fullmatch(source_code_commit) is None:
        raise ValueError("source_code_commit must be a lowercase Git SHA")
    model = backend.model_identity
    condition = backend.watermark_condition
    if condition.key_split is not KeySplit.DEV:
        raise ValueError("Diverse Beam generation requires DEV_KEYS")
    samples = []
    for prompt in build_diverse_beam_prompt_specs():
        if prompt.ordinal % shard_count != shard_index:
            continue
        parameters = backend.generation_parameters(prompt.seed, prompt.target_length)
        generated = backend.generate(
            prompt.prompt_text,
            prompt.seed,
            prompt.target_length,
            watermarked=True,
        )
        samples.append(
            _generated_sample(
                prompt,
                generated,
                parameters,
                model.identity_hash,
                condition.condition_hash,
            )
        )
    payload = {
        "algorithm_version": DIVERSE_BEAM_GENERATION_SHARD_VERSION,
        "source_code_commit": source_code_commit,
        "prompt_profile_hash": diverse_beam_prompt_profile_hash(),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "model_identity_hash": model.identity_hash,
        "watermark_condition_hash": condition.condition_hash,
        "generation_key_access_required": True,
        "detector_access_observed": False,
        "samples": tuple(value.as_dict() for value in samples),
    }
    return DiverseBeamGenerationShard(
        algorithm_version=DIVERSE_BEAM_GENERATION_SHARD_VERSION,
        source_code_commit=source_code_commit,
        prompt_profile_hash=payload["prompt_profile_hash"],
        shard_index=shard_index,
        shard_count=shard_count,
        model_identity_hash=model.identity_hash,
        watermark_condition_hash=condition.condition_hash,
        generation_key_access_required=True,
        detector_access_observed=False,
        samples=tuple(samples),
        artifact_hash=sha256_json(payload),
    )


def freeze_diverse_beam_corpus(
    shards: Sequence[DiverseBeamGenerationShard],
) -> DiverseBeamFrozenCorpus:
    materialized = tuple(sorted(shards, key=lambda value: value.shard_index))
    if len(materialized) != DIVERSE_BEAM_GENERATION_SHARD_COUNT:
        raise ValueError("freezing requires every generation shard")
    if tuple(value.shard_index for value in materialized) != tuple(
        range(DIVERSE_BEAM_GENERATION_SHARD_COUNT)
    ):
        raise ValueError("generation shard indices must be complete")
    if len({value.source_code_commit for value in materialized}) != 1:
        raise ValueError("generation shards mixed source commits")
    if len({value.model_identity_hash for value in materialized}) != 1:
        raise ValueError("generation shards mixed model identities")
    if len({value.watermark_condition_hash for value in materialized}) != 1:
        raise ValueError("generation shards mixed watermark conditions")
    samples = tuple(
        sorted(
            (sample for shard in materialized for sample in shard.samples),
            key=lambda value: value.sample_id,
        )
    )
    expected_ids = {value.sample_id for value in build_diverse_beam_prompt_specs()}
    if (
        len(samples) != len(expected_ids)
        or {value.sample_id for value in samples} != expected_ids
    ):
        raise ValueError(
            "generation shards do not cover the frozen prompt profile exactly"
        )
    seen_text: set[str] = set()
    seen_tokens: set[str] = set()
    retained = []
    duplicate_text_only = 0
    duplicate_token_only = 0
    duplicate_both = 0
    for sample in samples:
        text_seen = sample.text_hash in seen_text
        tokens_seen = sample.continuation_token_hash in seen_tokens
        if text_seen or tokens_seen:
            if text_seen and tokens_seen:
                duplicate_both += 1
            elif text_seen:
                duplicate_text_only += 1
            else:
                duplicate_token_only += 1
            continue
        seen_text.add(sample.text_hash)
        seen_tokens.add(sample.continuation_token_hash)
        retained.append(sample)
    selected = []
    for target_length in DIVERSE_BEAM_TARGET_LENGTHS:
        cell = tuple(
            value for value in retained if value.target_length == target_length
        )
        if len(cell) < DIVERSE_BEAM_ANALYSIS_PER_LENGTH:
            raise ValueError(
                f"underpowered Diverse Beam corpus at target length {target_length}: {len(cell)} unique samples"
            )
        selected.extend(cell[:DIVERSE_BEAM_ANALYSIS_PER_LENGTH])
    frozen_samples = tuple(
        sorted(selected, key=lambda value: (value.target_length, value.sample_id))
    )
    duplicate_total = duplicate_text_only + duplicate_token_only + duplicate_both
    source_code_commit = materialized[0].source_code_commit
    model_identity_hash = materialized[0].model_identity_hash
    watermark_condition_hash = materialized[0].watermark_condition_hash
    payload = {
        "algorithm_version": DIVERSE_BEAM_FROZEN_CORPUS_VERSION,
        "source_code_commit": source_code_commit,
        "prompt_profile_hash": diverse_beam_prompt_profile_hash(),
        "generation_shard_hashes": tuple(value.artifact_hash for value in materialized),
        "model_identity_hash": model_identity_hash,
        "watermark_condition_hash": watermark_condition_hash,
        "generated_sample_count": len(samples),
        "duplicate_text_only_count": duplicate_text_only,
        "duplicate_token_only_count": duplicate_token_only,
        "duplicate_text_and_token_count": duplicate_both,
        "duplicate_excluded_count": duplicate_total,
        "surplus_unique_excluded_count": len(retained) - len(frozen_samples),
        "eligible_sample_count": len(frozen_samples),
        "target_lengths": DIVERSE_BEAM_TARGET_LENGTHS,
        "samples_per_target_length": DIVERSE_BEAM_ANALYSIS_PER_LENGTH,
        "frozen_before_search": True,
        "detector_score_selection_observed": False,
        "planner_secret_access_observed": False,
        "samples": tuple(value.as_dict() for value in frozen_samples),
    }
    return DiverseBeamFrozenCorpus(
        algorithm_version=DIVERSE_BEAM_FROZEN_CORPUS_VERSION,
        source_code_commit=source_code_commit,
        prompt_profile_hash=payload["prompt_profile_hash"],
        generation_shard_hashes=payload["generation_shard_hashes"],
        model_identity_hash=model_identity_hash,
        watermark_condition_hash=watermark_condition_hash,
        generated_sample_count=len(samples),
        duplicate_text_only_count=duplicate_text_only,
        duplicate_token_only_count=duplicate_token_only,
        duplicate_text_and_token_count=duplicate_both,
        duplicate_excluded_count=duplicate_total,
        surplus_unique_excluded_count=len(retained) - len(frozen_samples),
        eligible_sample_count=len(frozen_samples),
        target_lengths=DIVERSE_BEAM_TARGET_LENGTHS,
        samples_per_target_length=DIVERSE_BEAM_ANALYSIS_PER_LENGTH,
        frozen_before_search=True,
        detector_score_selection_observed=False,
        planner_secret_access_observed=False,
        samples=frozen_samples,
        artifact_hash=sha256_json(payload),
    )


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs
    )
    if not isinstance(value, dict):
        raise TypeError("artifact must be a JSON object")
    return value


def _require_keys(value: dict[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match the frozen schema")


def _sample_from_dict(value: object) -> DiverseBeamGeneratedSample:
    if not isinstance(value, dict):
        raise TypeError("generated sample must be an object")
    expected = {
        "algorithm_version",
        "ordinal",
        "sample_id",
        "prompt_family_id",
        "domain",
        "prompt_text_hash",
        "target_length",
        "seed",
        "text",
        "text_hash",
        "continuation_token_ids",
        "continuation_token_hash",
        "text_only_token_ids",
        "text_only_token_hash",
        "generation_config_hash",
        "generation_matching_signature_hash",
        "model_identity_hash",
        "watermark_condition_hash",
        "label",
        "key_split",
        "record_hash",
    }
    _require_keys(value, expected, "generated sample")
    if value["algorithm_version"] != DIVERSE_BEAM_GENERATION_SHARD_VERSION:
        raise ValueError("generated sample version drifted")
    return DiverseBeamGeneratedSample(
        algorithm_version=value["algorithm_version"],
        ordinal=value["ordinal"],
        sample_id=value["sample_id"],
        prompt_family_id=value["prompt_family_id"],
        domain=value["domain"],
        prompt_text_hash=value["prompt_text_hash"],
        target_length=value["target_length"],
        seed=value["seed"],
        text=value["text"],
        text_hash=value["text_hash"],
        continuation_token_ids=tuple(value["continuation_token_ids"]),
        continuation_token_hash=value["continuation_token_hash"],
        text_only_token_ids=tuple(value["text_only_token_ids"]),
        text_only_token_hash=value["text_only_token_hash"],
        generation_config_hash=value["generation_config_hash"],
        generation_matching_signature_hash=value["generation_matching_signature_hash"],
        model_identity_hash=value["model_identity_hash"],
        watermark_condition_hash=value["watermark_condition_hash"],
        label=value["label"],
        key_split=value["key_split"],
        record_hash=value["record_hash"],
    )


def load_diverse_beam_generation_shard(path: Path) -> DiverseBeamGenerationShard:
    value = _read_object(path)
    expected = {
        "algorithm_version",
        "source_code_commit",
        "prompt_profile_hash",
        "shard_index",
        "shard_count",
        "model_identity_hash",
        "watermark_condition_hash",
        "generation_key_access_required",
        "detector_access_observed",
        "samples",
        "artifact_hash",
    }
    _require_keys(value, expected, "generation shard")
    if not isinstance(value["samples"], list):
        raise TypeError("generation shard samples must be a list")
    return DiverseBeamGenerationShard(
        algorithm_version=value["algorithm_version"],
        source_code_commit=value["source_code_commit"],
        prompt_profile_hash=value["prompt_profile_hash"],
        shard_index=value["shard_index"],
        shard_count=value["shard_count"],
        model_identity_hash=value["model_identity_hash"],
        watermark_condition_hash=value["watermark_condition_hash"],
        generation_key_access_required=value["generation_key_access_required"],
        detector_access_observed=value["detector_access_observed"],
        samples=tuple(_sample_from_dict(item) for item in value["samples"]),
        artifact_hash=value["artifact_hash"],
    )


def load_diverse_beam_frozen_corpus(path: Path) -> DiverseBeamFrozenCorpus:
    value = _read_object(path)
    expected = {
        "algorithm_version",
        "source_code_commit",
        "prompt_profile_hash",
        "generation_shard_hashes",
        "model_identity_hash",
        "watermark_condition_hash",
        "generated_sample_count",
        "duplicate_text_only_count",
        "duplicate_token_only_count",
        "duplicate_text_and_token_count",
        "duplicate_excluded_count",
        "surplus_unique_excluded_count",
        "eligible_sample_count",
        "target_lengths",
        "samples_per_target_length",
        "frozen_before_search",
        "detector_score_selection_observed",
        "planner_secret_access_observed",
        "samples",
        "artifact_hash",
    }
    _require_keys(value, expected, "frozen corpus")
    for name in ("generation_shard_hashes", "target_lengths", "samples"):
        if not isinstance(value[name], list):
            raise TypeError(f"{name} must be a list")
    return DiverseBeamFrozenCorpus(
        algorithm_version=value["algorithm_version"],
        source_code_commit=value["source_code_commit"],
        prompt_profile_hash=value["prompt_profile_hash"],
        generation_shard_hashes=tuple(value["generation_shard_hashes"]),
        model_identity_hash=value["model_identity_hash"],
        watermark_condition_hash=value["watermark_condition_hash"],
        generated_sample_count=value["generated_sample_count"],
        duplicate_text_only_count=value["duplicate_text_only_count"],
        duplicate_token_only_count=value["duplicate_token_only_count"],
        duplicate_text_and_token_count=value["duplicate_text_and_token_count"],
        duplicate_excluded_count=value["duplicate_excluded_count"],
        surplus_unique_excluded_count=value["surplus_unique_excluded_count"],
        eligible_sample_count=value["eligible_sample_count"],
        target_lengths=tuple(value["target_lengths"]),
        samples_per_target_length=value["samples_per_target_length"],
        frozen_before_search=value["frozen_before_search"],
        detector_score_selection_observed=value["detector_score_selection_observed"],
        planner_secret_access_observed=value["planner_secret_access_observed"],
        samples=tuple(_sample_from_dict(item) for item in value["samples"]),
        artifact_hash=value["artifact_hash"],
    )
