from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

from ._validation import require_sha256
from .config import canonical_json_text
from .hashing import sha256_json, sha256_text
from .transforms import TransformRegistry, development_sentence_boundary_softbreak_rules


SEQUENCE_BOUNDARY_OPPORTUNITY_AUDIT_VERSION = "sequence-boundary-softbreak-opportunity-audit-v1"
FROZEN_CORPUS_VERSION = "diverse-beam-frozen-corpus-v1"
FROZEN_CORPUS_ARTIFACT_HASH = "354097a63d58a963b67b12a64928d0a0f11dd46b29012d667ca4702a913f395e"
AUDIT_BUDGETS = (2, 4, 6)
MAX_CORPUS_BYTES = 64 * 1024 * 1024

PRIMARY_TOKENIZERS = (
    ("openai-community/gpt2", "607a30d783dfa663caf39e06633721c8d4cfcd7e", "GPT2TokenizerFast byte-level BPE"),
    ("Qwen/Qwen2.5-0.5B", "060db6499f32faf8b98477b0a26969ef7d8b9987", "Qwen2TokenizerFast byte-level BPE"),
    ("mistralai/Mistral-7B-v0.1", "27d67f1b5f57dc0953326b2601d68371d40ea8da", "LlamaTokenizerFast SentencePiece"),
)
NEGATIVE_CONTROL_TOKENIZER = (
    "google-t5/t5-small",
    "df1b051c49625cf57a3d0d8d3863ed4d13564fe4",
    "T5TokenizerFast SentencePiece whitespace-normalizing control",
)

_TRAILING_HORIZONTAL_RE = re.compile(r"[ \t]+(?=\n|$)")
_HORIZONTAL_RUN_RE = re.compile(r"[ \t]+")


def _copy_paste_normalize(text: str) -> str:
    output = text.replace("\r\n", "\n").replace("\r", "\n")
    output = _TRAILING_HORIZONTAL_RE.sub("", output)
    return _HORIZONTAL_RUN_RE.sub(" ", output)


def _load_frozen_sources(path: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    size = path.stat().st_size
    if size <= 0 or size > MAX_CORPUS_BYTES:
        raise ValueError("frozen corpus size is invalid")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("algorithm_version") != FROZEN_CORPUS_VERSION:
        raise ValueError("unsupported frozen corpus")
    artifact_hash = data.get("artifact_hash")
    require_sha256("artifact_hash", artifact_hash)
    payload = {key: value for key, value in data.items() if key != "artifact_hash"}
    if sha256_json(payload) != artifact_hash:
        raise ValueError("frozen corpus artifact hash mismatch")
    if artifact_hash != FROZEN_CORPUS_ARTIFACT_HASH:
        raise ValueError("unexpected frozen corpus identity")
    samples = data.get("samples")
    if not isinstance(samples, list) or len(samples) != 500:
        raise ValueError("frozen corpus must contain 500 sources")
    sources = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise TypeError("frozen corpus samples must be objects")
        sample_id = sample.get("sample_id")
        text = sample.get("text")
        text_hash = sample.get("text_hash")
        if not isinstance(sample_id, str) or not sample_id or not isinstance(text, str) or not text:
            raise ValueError("frozen corpus sample identity or text is invalid")
        require_sha256("text_hash", text_hash)
        if sha256_text(text) != text_hash:
            raise ValueError("frozen corpus sample text hash mismatch")
        sources.append((sample_id, text))
    values = tuple(sources)
    if len({sample_id for sample_id, _ in values}) != len(values):
        raise ValueError("frozen corpus sample IDs must be unique")
    return artifact_hash, values


def _encode(tokenizer: object, text: str) -> tuple[int, ...]:
    encode = getattr(tokenizer, "encode", None)
    if not callable(encode):
        raise TypeError("tokenizer must expose encode")
    values = encode(text, add_special_tokens=False)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise TypeError("tokenizer output must be a sequence")
    output = tuple(values)
    if not output or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in output):
        raise ValueError("tokenizer output must contain non-negative integer token IDs")
    return output


def audit_sequence_boundary_opportunity(
    *,
    source_corpus_artifact_hash: str,
    sources: Sequence[tuple[str, str]],
    primary_tokenizers: Mapping[tuple[str, str, str], object],
    negative_control: tuple[tuple[str, str, str], object],
) -> dict[str, object]:
    require_sha256("source_corpus_artifact_hash", source_corpus_artifact_hash)
    if source_corpus_artifact_hash != FROZEN_CORPUS_ARTIFACT_HASH:
        raise ValueError("unexpected frozen corpus identity")
    materialized_sources = tuple(sources)
    if len(materialized_sources) != 500:
        raise ValueError("opportunity audit requires exactly 500 sources")
    if len(set(materialized_sources)) != len(materialized_sources):
        raise ValueError("opportunity audit sources must be unique")
    expected_primary = tuple(PRIMARY_TOKENIZERS)
    if tuple(primary_tokenizers) != expected_primary:
        raise ValueError("primary tokenizer bindings drifted")
    negative_identity, negative_tokenizer = negative_control
    if negative_identity != NEGATIVE_CONTROL_TOKENIZER:
        raise ValueError("negative-control tokenizer binding drifted")

    registry = TransformRegistry(development_sentence_boundary_softbreak_rules())
    source_with_candidate_count = 0
    candidate_count = 0
    invariant_pass_count = 0
    nfc_pass_count = 0
    n4_survival_count = 0
    budget_counts = {budget: 0 for budget in AUDIT_BUDGETS}
    primary_changes = {identity: 0 for identity in expected_primary}
    negative_changes = 0
    universal_primary_changes = 0

    for sample_id, source_text in materialized_sources:
        if not isinstance(sample_id, str) or not sample_id or not isinstance(source_text, str) or not source_text:
            raise ValueError("opportunity audit source is invalid")
        enumeration = registry.enumerate(source_text)
        candidates = enumeration.candidates
        candidate_count += len(candidates)
        source_with_candidate_count += bool(candidates)
        base_primary = {
            identity: _encode(tokenizer, source_text)
            for identity, tokenizer in primary_tokenizers.items()
        }
        base_negative = _encode(negative_tokenizer, source_text)
        for candidate in candidates:
            result = registry.apply(enumeration, (candidate.candidate_id,), seed=0)
            invariant_pass_count += result.trace.invariant_report.status.value == "pass"
            nfc_pass_count += result.output_text == unicodedata.normalize("NFC", result.output_text)
            n4_survival_count += _copy_paste_normalize(source_text) != _copy_paste_normalize(result.output_text)
            flags = {
                identity: _encode(tokenizer, result.output_text) != base_primary[identity]
                for identity, tokenizer in primary_tokenizers.items()
            }
            for identity, changed in flags.items():
                primary_changes[identity] += changed
            universal_primary_changes += all(flags.values())
            negative_changes += _encode(negative_tokenizer, result.output_text) != base_negative
        for budget in AUDIT_BUDGETS:
            if len(candidates) < budget:
                continue
            result = registry.apply(
                enumeration,
                tuple(candidate.candidate_id for candidate in candidates[:budget]),
                seed=0,
            )
            if (
                result.trace.invariant_report.status.value == "pass"
                and _copy_paste_normalize(source_text) != _copy_paste_normalize(result.output_text)
            ):
                budget_counts[budget] += 1

    primary_rows = tuple(
        {
            "model_id": identity[0],
            "revision": identity[1],
            "family": identity[2],
            "individual_change_count": primary_changes[identity],
        }
        for identity in expected_primary
    )
    negative_row = {
        "model_id": negative_identity[0],
        "revision": negative_identity[1],
        "family": negative_identity[2],
        "individual_change_count": negative_changes,
    }
    payload = {
        "algorithm_version": SEQUENCE_BOUNDARY_OPPORTUNITY_AUDIT_VERSION,
        "source_corpus_artifact_hash": source_corpus_artifact_hash,
        "ruleset_hash": registry.ruleset_hash,
        "source_count": len(materialized_sources),
        "protected_span_safe_candidate_count": candidate_count,
        "source_with_candidate_count": source_with_candidate_count,
        "budget_2_reachable_count": budget_counts[2],
        "budget_4_reachable_count": budget_counts[4],
        "budget_6_reachable_count": budget_counts[6],
        "individual_invariant_pass_count": invariant_pass_count,
        "individual_nfc_pass_count": nfc_pass_count,
        "individual_n4_survival_count": n4_survival_count,
        "primary_tokenizers": primary_rows,
        "universal_primary_tokenizer_change_count": universal_primary_changes,
        "negative_control": negative_row,
        "detector_query_count": 0,
        "secret_query_count": 0,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _write_fsynced(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_text(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-sequence-boundary-opportunity-audit")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned tokenizer dependencies first") from error
    corpus_hash, sources = _load_frozen_sources(args.corpus_json)
    primary = {
        identity: AutoTokenizer.from_pretrained(identity[0], revision=identity[1], use_fast=True)
        for identity in PRIMARY_TOKENIZERS
    }
    negative = (
        NEGATIVE_CONTROL_TOKENIZER,
        AutoTokenizer.from_pretrained(
            NEGATIVE_CONTROL_TOKENIZER[0],
            revision=NEGATIVE_CONTROL_TOKENIZER[1],
            use_fast=True,
        ),
    )
    artifact = audit_sequence_boundary_opportunity(
        source_corpus_artifact_hash=corpus_hash,
        sources=sources,
        primary_tokenizers=primary,
        negative_control=negative,
    )
    _write_fsynced(args.json, artifact)
    print(f"artifact_hash={artifact['artifact_hash']}")
    print(f"candidate_count={artifact['protected_span_safe_candidate_count']}")
    print(f"budget_2_reachable_count={artifact['budget_2_reachable_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
