from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..config import canonical_json_text
from .generation import GenerationParameters, WatermarkCondition
from .identity import ModelTokenizerIdentity, PaddingSide
from .manifest import CorpusManifest
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import (
    CorpusDomain,
    CorpusSplit,
    DeduplicationPolicy,
    KeySplit,
    PromptBoundaryMode,
    WatermarkLabel,
)
from .tiny_dev import TinyDevCorpusArtifact, TinyDevCorpusCell
from .tokenization import GenerationTokenRecord, TextOnlyTokenRecord


TINY_DEV_JSON_MAX_BYTES = 64 * 1024 * 1024


class TinyDevCorpusJsonError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise TinyDevCorpusJsonError(f"non-finite JSON number is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise TinyDevCorpusJsonError(f"duplicate JSON object key: {key}")
        output[key] = value
    return output


def _mapping(name: str, value: object, fields: tuple[str, ...]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TinyDevCorpusJsonError(f"{name} must be a JSON object")
    actual = set(value)
    expected = set(fields)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise TinyDevCorpusJsonError(f"{name} fields do not match schema: missing={missing} extra={extra}")
    return value


def _array(name: str, value: object) -> list[Any]:
    if not isinstance(value, list):
        raise TinyDevCorpusJsonError(f"{name} must be a JSON array")
    return value


def _model(value: object) -> ModelTokenizerIdentity:
    data = _mapping(
        "model",
        value,
        (
            "model_id",
            "model_revision",
            "tokenizer_id",
            "tokenizer_revision",
            "chat_template_present",
            "chat_template_hash",
            "special_token_map_hash",
            "padding_side",
            "bos_token_id",
            "eos_token_id",
            "pad_token_id",
            "add_bos_token",
            "add_eos_token",
            "identity_hash",
        ),
    )
    return ModelTokenizerIdentity(
        model_id=data["model_id"],
        model_revision=data["model_revision"],
        tokenizer_id=data["tokenizer_id"],
        tokenizer_revision=data["tokenizer_revision"],
        chat_template_present=data["chat_template_present"],
        chat_template_hash=data["chat_template_hash"],
        special_token_map_hash=data["special_token_map_hash"],
        padding_side=PaddingSide(data["padding_side"]),
        bos_token_id=data["bos_token_id"],
        eos_token_id=data["eos_token_id"],
        pad_token_id=data["pad_token_id"],
        add_bos_token=data["add_bos_token"],
        add_eos_token=data["add_eos_token"],
        identity_hash=data["identity_hash"],
    )


def _generation(value: object) -> GenerationParameters:
    data = _mapping(
        "generation",
        value,
        (
            "seed",
            "seed_policy_id",
            "temperature",
            "top_k",
            "top_p",
            "max_new_tokens",
            "do_sample",
            "dtype",
            "device",
            "backend_id",
            "backend_version",
            "config_hash",
            "matching_signature_hash",
        ),
    )
    return GenerationParameters(
        seed=data["seed"],
        seed_policy_id=data["seed_policy_id"],
        temperature=data["temperature"],
        top_k=data["top_k"],
        top_p=data["top_p"],
        max_new_tokens=data["max_new_tokens"],
        do_sample=data["do_sample"],
        dtype=data["dtype"],
        device=data["device"],
        backend_id=data["backend_id"],
        backend_version=data["backend_version"],
        config_hash=data["config_hash"],
        matching_signature_hash=data["matching_signature_hash"],
    )


def _watermark(value: object) -> WatermarkCondition:
    data = _mapping(
        "watermark",
        value,
        ("watermark_config_hash", "key_split", "key_id", "condition_hash"),
    )
    return WatermarkCondition(
        watermark_config_hash=data["watermark_config_hash"],
        key_split=KeySplit(data["key_split"]),
        key_id=data["key_id"],
        condition_hash=data["condition_hash"],
    )


def _generation_tokens(value: object) -> GenerationTokenRecord:
    data = _mapping(
        "generation_tokens",
        value,
        (
            "model_tokenizer_identity_hash",
            "input_token_ids",
            "attention_mask",
            "generated_sequence_ids",
            "continuation_start_index",
            "continuation_token_ids",
            "prompt_length_after_templating",
            "input_token_hash",
            "generated_sequence_hash",
            "continuation_token_hash",
            "record_hash",
        ),
    )
    return GenerationTokenRecord(
        model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
        input_token_ids=tuple(_array("generation_tokens.input_token_ids", data["input_token_ids"])),
        attention_mask=tuple(_array("generation_tokens.attention_mask", data["attention_mask"])),
        generated_sequence_ids=tuple(
            _array("generation_tokens.generated_sequence_ids", data["generated_sequence_ids"])
        ),
        continuation_start_index=data["continuation_start_index"],
        continuation_token_ids=tuple(
            _array("generation_tokens.continuation_token_ids", data["continuation_token_ids"])
        ),
        prompt_length_after_templating=data["prompt_length_after_templating"],
        input_token_hash=data["input_token_hash"],
        generated_sequence_hash=data["generated_sequence_hash"],
        continuation_token_hash=data["continuation_token_hash"],
        record_hash=data["record_hash"],
    )


def _text_only_tokens(value: object) -> TextOnlyTokenRecord | None:
    if value is None:
        return None
    data = _mapping(
        "text_only_tokens",
        value,
        (
            "model_tokenizer_identity_hash",
            "source_text_sha256",
            "token_ids",
            "token_hash",
            "record_hash",
        ),
    )
    return TextOnlyTokenRecord(
        model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
        source_text_sha256=data["source_text_sha256"],
        token_ids=tuple(_array("text_only_tokens.token_ids", data["token_ids"])),
        token_hash=data["token_hash"],
        record_hash=data["record_hash"],
    )


def _prompt(value: object) -> PromptRecord:
    data = _mapping(
        "prompt",
        value,
        (
            "prompt_id",
            "prompt_family_id",
            "domain",
            "split",
            "language",
            "source_id",
            "source_hash",
            "license_id",
            "provenance",
            "text",
            "text_sha256",
            "record_hash",
        ),
    )
    return PromptRecord(
        prompt_id=data["prompt_id"],
        prompt_family_id=data["prompt_family_id"],
        domain=CorpusDomain(data["domain"]),
        split=CorpusSplit(data["split"]),
        language=data["language"],
        source_id=data["source_id"],
        source_hash=data["source_hash"],
        license_id=data["license_id"],
        provenance=data["provenance"],
        text=data["text"],
        text_sha256=data["text_sha256"],
        record_hash=data["record_hash"],
    )


def _sample(value: object) -> CorpusSample:
    data = _mapping(
        "sample",
        value,
        (
            "sample_id",
            "match_id",
            "prompt_id",
            "prompt_family_id",
            "domain",
            "split",
            "language",
            "label",
            "text",
            "text_sha256",
            "model",
            "generation",
            "watermark",
            "target_length",
            "prompt_boundary_mode",
            "generation_tokens",
            "text_only_tokens",
            "generation_realized_length",
            "record_hash",
        ),
    )
    return CorpusSample(
        sample_id=data["sample_id"],
        match_id=data["match_id"],
        prompt_id=data["prompt_id"],
        prompt_family_id=data["prompt_family_id"],
        domain=CorpusDomain(data["domain"]),
        split=CorpusSplit(data["split"]),
        language=data["language"],
        label=WatermarkLabel(data["label"]),
        text=data["text"],
        text_sha256=data["text_sha256"],
        model=_model(data["model"]),
        generation=_generation(data["generation"]),
        watermark=_watermark(data["watermark"]),
        target_length=data["target_length"],
        prompt_boundary_mode=PromptBoundaryMode(data["prompt_boundary_mode"]),
        generation_tokens=_generation_tokens(data["generation_tokens"]),
        text_only_tokens=_text_only_tokens(data["text_only_tokens"]),
        generation_realized_length=data["generation_realized_length"],
        record_hash=data["record_hash"],
    )


def _manifest(value: object) -> CorpusManifest:
    data = _mapping(
        "manifest",
        value,
        (
            "corpus_id",
            "language",
            "deduplication_policy",
            "prompts",
            "samples",
            "prompt_manifest_hash",
            "sample_manifest_hash",
            "manifest_hash",
            "algorithm_version",
        ),
    )
    return CorpusManifest(
        corpus_id=data["corpus_id"],
        language=data["language"],
        deduplication_policy=DeduplicationPolicy(data["deduplication_policy"]),
        prompts=tuple(_prompt(item) for item in _array("manifest.prompts", data["prompts"])),
        samples=tuple(_sample(item) for item in _array("manifest.samples", data["samples"])),
        prompt_manifest_hash=data["prompt_manifest_hash"],
        sample_manifest_hash=data["sample_manifest_hash"],
        manifest_hash=data["manifest_hash"],
        algorithm_version=data["algorithm_version"],
    )


def _cell(value: object) -> TinyDevCorpusCell:
    data = _mapping("cell", value, ("split", "domain", "pair_count"))
    return TinyDevCorpusCell(
        split=CorpusSplit(data["split"]),
        domain=CorpusDomain(data["domain"]),
        pair_count=data["pair_count"],
    )


def _artifact(value: object) -> TinyDevCorpusArtifact:
    data = _mapping(
        "artifact",
        value,
        (
            "algorithm_version",
            "manifest",
            "target_length",
            "calibration_pairs_per_domain",
            "attack_pairs_per_domain",
            "required_splits",
            "required_domains",
            "model_identity_hash",
            "generation_matching_signature_hash",
            "watermark_condition_hash",
            "cells",
            "artifact_hash",
        ),
    )
    return TinyDevCorpusArtifact(
        algorithm_version=data["algorithm_version"],
        manifest=_manifest(data["manifest"]),
        target_length=data["target_length"],
        calibration_pairs_per_domain=data["calibration_pairs_per_domain"],
        attack_pairs_per_domain=data["attack_pairs_per_domain"],
        required_splits=tuple(
            CorpusSplit(item) for item in _array("artifact.required_splits", data["required_splits"])
        ),
        required_domains=tuple(
            CorpusDomain(item) for item in _array("artifact.required_domains", data["required_domains"])
        ),
        model_identity_hash=data["model_identity_hash"],
        generation_matching_signature_hash=data["generation_matching_signature_hash"],
        watermark_condition_hash=data["watermark_condition_hash"],
        cells=tuple(_cell(item) for item in _array("artifact.cells", data["cells"])),
        artifact_hash=data["artifact_hash"],
    )


def parse_tiny_dev_corpus_json(text: str, *, require_canonical: bool = True) -> TinyDevCorpusArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > TINY_DEV_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("tiny-dev JSON exceeds the size limit")
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except TinyDevCorpusJsonError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise TinyDevCorpusJsonError("tiny-dev JSON is not valid JSON") from error
    try:
        artifact = _artifact(decoded)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("tiny-dev JSON failed artifact validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("tiny-dev JSON is not in canonical serialized form")
    return artifact


def load_tiny_dev_corpus_json(path: str | Path, *, require_canonical: bool = True) -> TinyDevCorpusArtifact:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > TINY_DEV_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("tiny-dev JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TinyDevCorpusJsonError("tiny-dev JSON must be UTF-8") from error
    return parse_tiny_dev_corpus_json(text, require_canonical=require_canonical)
