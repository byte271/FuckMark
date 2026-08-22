from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .._validation import normalize_token_sequence, require_bool, require_clean_string, require_int, require_sha256
from ..alignment import AlignmentOp, align_tokens
from ..corpus import ModelTokenizerIdentity
from ..hashing import sha256_json, sha256_text
from ..transforms import TransformResult


REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION = "representation-differential-audit-v1"
REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS = "DESCRIPTIVE_REPRESENTATION_EVIDENCE_ONLY"
REPRESENTATION_DIFFERENTIAL_MINIMUM_TOKENIZERS = 2
_SENSITIVE_UNICODE_CATEGORIES = frozenset({"Cf", "Cs", "Co", "Mn", "Me"})


class RepresentationDifferentialInputError(ValueError):
    pass


def _finite_ratio(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


def _sensitive_unicode_sequence(text: str) -> tuple[str, ...]:
    return tuple(
        character
        for character in text
        if unicodedata.category(character) in _SENSITIVE_UNICODE_CATEGORIES
    )


def _validate_text_pair(source_text: str, transformed_text: str) -> None:
    if not isinstance(source_text, str) or not source_text:
        raise ValueError("source_text must be a non-empty string")
    if not isinstance(transformed_text, str) or not transformed_text:
        raise ValueError("transformed_text must be a non-empty string")
    if source_text == transformed_text:
        raise RepresentationDifferentialInputError("representation evidence requires a realized text transformation")
    if unicodedata.normalize("NFC", source_text) != source_text:
        raise RepresentationDifferentialInputError("source text must already be Unicode NFC")
    if unicodedata.normalize("NFC", transformed_text) != transformed_text:
        raise RepresentationDifferentialInputError("transformed text must remain Unicode NFC")
    if _sensitive_unicode_sequence(source_text) != _sensitive_unicode_sequence(transformed_text):
        raise RepresentationDifferentialInputError(
            "transformation must not add, remove, or reorder invisible or representation-sensitive Unicode code points"
        )


def _direction(value: int) -> int:
    return (value > 0) - (value < 0)


@dataclass(frozen=True, slots=True)
class TokenizerRepresentationRow:
    model_tokenizer_identity_hash: str
    source_token_ids: tuple[int, ...]
    transformed_token_ids: tuple[int, ...]
    source_token_hash: str
    transformed_token_hash: str
    source_token_count: int
    transformed_token_count: int
    token_count_delta: int
    token_edit_distance: int
    normalized_edit_distance: float
    matched_token_count: int
    tokenization_changed: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        source_tokens = normalize_token_sequence("source_token_ids", self.source_token_ids)
        transformed_tokens = normalize_token_sequence("transformed_token_ids", self.transformed_token_ids)
        if source_tokens != self.source_token_ids or transformed_tokens != self.transformed_token_ids:
            raise ValueError("representation token sequences must be canonical tuples")
        if not source_tokens or not transformed_tokens:
            raise ValueError("representation token sequences must not be empty")
        require_sha256("source_token_hash", self.source_token_hash)
        require_sha256("transformed_token_hash", self.transformed_token_hash)
        if self.source_token_hash != sha256_json(source_tokens):
            raise ValueError("source_token_hash does not match source_token_ids")
        if self.transformed_token_hash != sha256_json(transformed_tokens):
            raise ValueError("transformed_token_hash does not match transformed_token_ids")
        for name, value in (
            ("source_token_count", self.source_token_count),
            ("transformed_token_count", self.transformed_token_count),
            ("token_count_delta", self.token_count_delta),
            ("token_edit_distance", self.token_edit_distance),
            ("matched_token_count", self.matched_token_count),
        ):
            require_int(name, value)
        if self.source_token_count != len(source_tokens):
            raise ValueError("source_token_count does not match source_token_ids")
        if self.transformed_token_count != len(transformed_tokens):
            raise ValueError("transformed_token_count does not match transformed_token_ids")
        if self.token_count_delta != self.transformed_token_count - self.source_token_count:
            raise ValueError("token_count_delta does not match token counts")
        alignment = align_tokens(source_tokens, transformed_tokens)
        if self.token_edit_distance != alignment.distance:
            raise ValueError("token_edit_distance does not match canonical token alignment")
        expected_normalized = alignment.distance / max(len(source_tokens), len(transformed_tokens))
        normalized = _finite_ratio("normalized_edit_distance", self.normalized_edit_distance)
        object.__setattr__(self, "normalized_edit_distance", normalized)
        if not math.isclose(normalized, expected_normalized, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("normalized_edit_distance does not match canonical token alignment")
        expected_matches = sum(step.op is AlignmentOp.MATCH for step in alignment.steps)
        if self.matched_token_count != expected_matches:
            raise ValueError("matched_token_count does not match canonical token alignment")
        require_bool("tokenization_changed", self.tokenization_changed)
        if self.tokenization_changed != (source_tokens != transformed_tokens):
            raise ValueError("tokenization_changed does not match token sequences")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match tokenizer representation row")

    def _payload(self) -> dict[str, object]:
        return {
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "source_token_ids": self.source_token_ids,
            "transformed_token_ids": self.transformed_token_ids,
            "source_token_hash": self.source_token_hash,
            "transformed_token_hash": self.transformed_token_hash,
            "source_token_count": self.source_token_count,
            "transformed_token_count": self.transformed_token_count,
            "token_count_delta": self.token_count_delta,
            "token_edit_distance": self.token_edit_distance,
            "normalized_edit_distance": self.normalized_edit_distance,
            "matched_token_count": self.matched_token_count,
            "tokenization_changed": self.tokenization_changed,
        }


def _build_row(
    identity: ModelTokenizerIdentity,
    source_tokens: tuple[int, ...],
    transformed_tokens: tuple[int, ...],
) -> TokenizerRepresentationRow:
    alignment = align_tokens(source_tokens, transformed_tokens)
    payload = {
        "model_tokenizer_identity_hash": identity.identity_hash,
        "source_token_ids": source_tokens,
        "transformed_token_ids": transformed_tokens,
        "source_token_hash": sha256_json(source_tokens),
        "transformed_token_hash": sha256_json(transformed_tokens),
        "source_token_count": len(source_tokens),
        "transformed_token_count": len(transformed_tokens),
        "token_count_delta": len(transformed_tokens) - len(source_tokens),
        "token_edit_distance": alignment.distance,
        "normalized_edit_distance": alignment.distance / max(len(source_tokens), len(transformed_tokens)),
        "matched_token_count": sum(step.op is AlignmentOp.MATCH for step in alignment.steps),
        "tokenization_changed": source_tokens != transformed_tokens,
    }
    return TokenizerRepresentationRow(
        identity.identity_hash,
        source_tokens,
        transformed_tokens,
        payload["source_token_hash"],
        payload["transformed_token_hash"],
        len(source_tokens),
        len(transformed_tokens),
        payload["token_count_delta"],
        alignment.distance,
        payload["normalized_edit_distance"],
        payload["matched_token_count"],
        payload["tokenization_changed"],
        sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class RepresentationPairEvidence:
    algorithm_version: str
    source_sample_id: str
    prompt_family_id: str
    source_text_hash: str
    transformed_text_hash: str
    transform_result_hash: str
    transform_trace_hash: str
    ruleset_hash: str
    model_tokenizer_identities: tuple[ModelTokenizerIdentity, ...]
    rows: tuple[TokenizerRepresentationRow, ...]
    changed_tokenizer_count: int
    universal_tokenization_change: bool
    metric_disagreement: bool
    token_count_direction_disagreement: bool
    detector_query_count: int
    secret_query_count: int
    pair_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION:
            raise ValueError("unsupported representation differential algorithm version")
        require_clean_string("source_sample_id", self.source_sample_id)
        require_clean_string("prompt_family_id", self.prompt_family_id)
        for name, value in (
            ("source_text_hash", self.source_text_hash),
            ("transformed_text_hash", self.transformed_text_hash),
            ("transform_result_hash", self.transform_result_hash),
            ("transform_trace_hash", self.transform_trace_hash),
            ("ruleset_hash", self.ruleset_hash),
            ("pair_hash", self.pair_hash),
        ):
            require_sha256(name, value)
        if self.source_text_hash == self.transformed_text_hash:
            raise ValueError("representation pair must bind distinct source and transformed text")
        if not isinstance(self.model_tokenizer_identities, tuple):
            raise TypeError("model_tokenizer_identities must be a tuple")
        if len(self.model_tokenizer_identities) < REPRESENTATION_DIFFERENTIAL_MINIMUM_TOKENIZERS:
            raise ValueError("representation pair requires at least two model/tokenizer identities")
        if any(not isinstance(value, ModelTokenizerIdentity) for value in self.model_tokenizer_identities):
            raise TypeError("model_tokenizer_identities must contain ModelTokenizerIdentity values")
        expected_identities = tuple(sorted(self.model_tokenizer_identities, key=lambda value: value.identity_hash))
        if self.model_tokenizer_identities != expected_identities:
            raise ValueError("model/tokenizer identities must be canonically ordered")
        identity_hashes = tuple(value.identity_hash for value in self.model_tokenizer_identities)
        if len(set(identity_hashes)) != len(identity_hashes):
            raise ValueError("model/tokenizer identities must be unique")
        if not isinstance(self.rows, tuple) or any(not isinstance(value, TokenizerRepresentationRow) for value in self.rows):
            raise TypeError("rows must be a tuple of TokenizerRepresentationRow values")
        expected_rows = tuple(sorted(self.rows, key=lambda value: value.model_tokenizer_identity_hash))
        if self.rows != expected_rows:
            raise ValueError("representation rows must be canonically ordered")
        if tuple(value.model_tokenizer_identity_hash for value in self.rows) != identity_hashes:
            raise ValueError("representation rows must exactly cover the bound model/tokenizer identities")
        require_int("changed_tokenizer_count", self.changed_tokenizer_count)
        expected_changed = sum(value.tokenization_changed for value in self.rows)
        if self.changed_tokenizer_count != expected_changed:
            raise ValueError("changed_tokenizer_count does not match representation rows")
        for name, value in (
            ("universal_tokenization_change", self.universal_tokenization_change),
            ("metric_disagreement", self.metric_disagreement),
            ("token_count_direction_disagreement", self.token_count_direction_disagreement),
        ):
            require_bool(name, value)
        if self.universal_tokenization_change != (expected_changed == len(self.rows)):
            raise ValueError("universal_tokenization_change does not match representation rows")
        metrics = {
            (
                value.source_token_count,
                value.transformed_token_count,
                value.token_edit_distance,
                value.matched_token_count,
            )
            for value in self.rows
        }
        if self.metric_disagreement != (len(metrics) > 1):
            raise ValueError("metric_disagreement does not match representation rows")
        directions = {_direction(value.token_count_delta) for value in self.rows}
        if self.token_count_direction_disagreement != (len(directions) > 1):
            raise ValueError("token_count_direction_disagreement does not match representation rows")
        for name, value in (
            ("detector_query_count", self.detector_query_count),
            ("secret_query_count", self.secret_query_count),
        ):
            require_int(name, value)
            if value != 0:
                raise ValueError(f"{name} must remain zero")
        if self.pair_hash != sha256_json(self._payload()):
            raise ValueError("pair_hash does not match representation pair evidence")

    @property
    def tokenizer_identity_hashes(self) -> tuple[str, ...]:
        return tuple(value.identity_hash for value in self.model_tokenizer_identities)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "prompt_family_id": self.prompt_family_id,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "transform_result_hash": self.transform_result_hash,
            "transform_trace_hash": self.transform_trace_hash,
            "ruleset_hash": self.ruleset_hash,
            "model_tokenizer_identities": self.model_tokenizer_identities,
            "rows": self.rows,
            "changed_tokenizer_count": self.changed_tokenizer_count,
            "universal_tokenization_change": self.universal_tokenization_change,
            "metric_disagreement": self.metric_disagreement,
            "token_count_direction_disagreement": self.token_count_direction_disagreement,
            "detector_query_count": self.detector_query_count,
            "secret_query_count": self.secret_query_count,
        }


def _bindings(
    tokenizer_bindings: Sequence[tuple[ModelTokenizerIdentity, Callable[[str], Sequence[int]]]],
) -> tuple[tuple[ModelTokenizerIdentity, Callable[[str], Sequence[int]]], ...]:
    if not isinstance(tokenizer_bindings, Sequence) or isinstance(tokenizer_bindings, (str, bytes, bytearray)):
        raise TypeError("tokenizer_bindings must be a sequence")
    values = tuple(tokenizer_bindings)
    if len(values) < REPRESENTATION_DIFFERENTIAL_MINIMUM_TOKENIZERS:
        raise RepresentationDifferentialInputError("representation capture requires at least two tokenizer bindings")
    normalized = []
    for value in values:
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError("tokenizer bindings must be two-item tuples")
        identity, tokenizer = value
        if not isinstance(identity, ModelTokenizerIdentity):
            raise TypeError("tokenizer binding identity must be a ModelTokenizerIdentity")
        if not callable(tokenizer):
            raise TypeError("tokenizer binding tokenizer must be callable")
        normalized.append((identity, tokenizer))
    ordered = tuple(sorted(normalized, key=lambda value: value[0].identity_hash))
    if len({value[0].identity_hash for value in ordered}) != len(ordered):
        raise RepresentationDifferentialInputError("tokenizer binding identities must be unique")
    return ordered


def capture_representation_pair(
    source_sample_id: str,
    prompt_family_id: str,
    source_text: str,
    transform_result: TransformResult,
    tokenizer_bindings: Sequence[tuple[ModelTokenizerIdentity, Callable[[str], Sequence[int]]]],
) -> RepresentationPairEvidence:
    require_clean_string("source_sample_id", source_sample_id)
    require_clean_string("prompt_family_id", prompt_family_id)
    if not isinstance(transform_result, TransformResult):
        raise TypeError("transform_result must be a TransformResult")
    if transform_result.trace.input_hash != sha256_text(source_text):
        raise RepresentationDifferentialInputError("transform result does not bind the supplied source text")
    if not transform_result.trace.operations:
        raise RepresentationDifferentialInputError("representation capture requires at least one selected transform")
    _validate_text_pair(source_text, transform_result.output_text)
    if any(
        _sensitive_unicode_sequence(operation.before_text)
        != _sensitive_unicode_sequence(operation.after_text)
        for operation in transform_result.trace.operations
    ):
        raise RepresentationDifferentialInputError(
            "individual transform operations must not mutate invisible or representation-sensitive Unicode code points"
        )
    bindings = _bindings(tokenizer_bindings)
    identities = tuple(value[0] for value in bindings)
    rows = tuple(
        _build_row(
            identity,
            normalize_token_sequence("source tokenizer output", tokenizer(source_text)),
            normalize_token_sequence("transformed tokenizer output", tokenizer(transform_result.output_text)),
        )
        for identity, tokenizer in bindings
    )
    changed_count = sum(value.tokenization_changed for value in rows)
    metrics = {
        (
            value.source_token_count,
            value.transformed_token_count,
            value.token_edit_distance,
            value.matched_token_count,
        )
        for value in rows
    }
    directions = {_direction(value.token_count_delta) for value in rows}
    payload = {
        "algorithm_version": REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION,
        "source_sample_id": source_sample_id,
        "prompt_family_id": prompt_family_id,
        "source_text_hash": sha256_text(source_text),
        "transformed_text_hash": sha256_text(transform_result.output_text),
        "transform_result_hash": transform_result.result_hash,
        "transform_trace_hash": transform_result.trace.trace_hash,
        "ruleset_hash": transform_result.trace.ruleset_hash,
        "model_tokenizer_identities": identities,
        "rows": rows,
        "changed_tokenizer_count": changed_count,
        "universal_tokenization_change": changed_count == len(rows),
        "metric_disagreement": len(metrics) > 1,
        "token_count_direction_disagreement": len(directions) > 1,
        "detector_query_count": 0,
        "secret_query_count": 0,
    }
    return RepresentationPairEvidence(
        REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION,
        source_sample_id,
        prompt_family_id,
        payload["source_text_hash"],
        payload["transformed_text_hash"],
        transform_result.result_hash,
        transform_result.trace.trace_hash,
        transform_result.trace.ruleset_hash,
        identities,
        rows,
        changed_count,
        payload["universal_tokenization_change"],
        payload["metric_disagreement"],
        payload["token_count_direction_disagreement"],
        0,
        0,
        sha256_json(payload),
    )


def verify_representation_pair(
    evidence: RepresentationPairEvidence,
    source_text: str,
    transform_result: TransformResult,
    tokenizer_bindings: Sequence[tuple[ModelTokenizerIdentity, Callable[[str], Sequence[int]]]],
) -> None:
    if not isinstance(evidence, RepresentationPairEvidence):
        raise TypeError("evidence must be RepresentationPairEvidence")
    expected = capture_representation_pair(
        evidence.source_sample_id,
        evidence.prompt_family_id,
        source_text,
        transform_result,
        tokenizer_bindings,
    )
    if evidence != expected:
        raise RepresentationDifferentialInputError(
            "representation pair does not replay exactly from the supplied transform and tokenizers"
        )


@dataclass(frozen=True, slots=True)
class RepresentationDifferentialAudit:
    algorithm_version: str
    pairs: tuple[RepresentationPairEvidence, ...]
    tokenizer_identity_hashes: tuple[str, ...]
    independent_source_count: int
    representation_cell_count: int
    changed_cell_count: int
    universal_change_source_count: int
    metric_disagreement_source_count: int
    token_count_direction_disagreement_source_count: int
    detector_query_count: int
    secret_query_count: int
    claim_status: str
    audit_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION:
            raise ValueError("unsupported representation differential audit version")
        if not isinstance(self.pairs, tuple) or len(self.pairs) < 2:
            raise ValueError("representation differential audit requires at least two independent source pairs")
        if any(not isinstance(value, RepresentationPairEvidence) for value in self.pairs):
            raise TypeError("pairs must contain RepresentationPairEvidence values")
        expected_pairs = tuple(sorted(self.pairs, key=lambda value: (value.source_sample_id, value.pair_hash)))
        if self.pairs != expected_pairs:
            raise ValueError("representation pairs must be canonically ordered")
        if len({value.source_sample_id for value in self.pairs}) != len(self.pairs):
            raise ValueError("representation audit permits only one transformed pair per independent source")
        if len({value.source_text_hash for value in self.pairs}) != len(self.pairs):
            raise ValueError("representation audit rejects duplicate source text across independent source IDs")
        expected_tokenizers = self.pairs[0].tokenizer_identity_hashes
        if any(value.tokenizer_identity_hashes != expected_tokenizers for value in self.pairs):
            raise ValueError("every representation pair must use the same tokenizer identity set")
        if self.tokenizer_identity_hashes != expected_tokenizers:
            raise ValueError("tokenizer_identity_hashes do not match representation pairs")
        for value in self.tokenizer_identity_hashes:
            require_sha256("tokenizer identity hash", value)
        expected_counts = (
            len(self.pairs),
            sum(len(value.rows) for value in self.pairs),
            sum(value.changed_tokenizer_count for value in self.pairs),
            sum(value.universal_tokenization_change for value in self.pairs),
            sum(value.metric_disagreement for value in self.pairs),
            sum(value.token_count_direction_disagreement for value in self.pairs),
        )
        actual_counts = (
            self.independent_source_count,
            self.representation_cell_count,
            self.changed_cell_count,
            self.universal_change_source_count,
            self.metric_disagreement_source_count,
            self.token_count_direction_disagreement_source_count,
        )
        for name, value in zip(
            (
                "independent_source_count",
                "representation_cell_count",
                "changed_cell_count",
                "universal_change_source_count",
                "metric_disagreement_source_count",
                "token_count_direction_disagreement_source_count",
            ),
            actual_counts,
        ):
            require_int(name, value)
        if actual_counts != expected_counts:
            raise ValueError("representation audit counts do not close over source pairs")
        for name, value in (
            ("detector_query_count", self.detector_query_count),
            ("secret_query_count", self.secret_query_count),
        ):
            require_int(name, value)
            if value != 0:
                raise ValueError(f"{name} must remain zero")
        require_clean_string("claim_status", self.claim_status)
        if self.claim_status != REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS:
            raise ValueError("representation audit must remain descriptive development evidence")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self._payload()):
            raise ValueError("audit_hash does not match representation differential audit")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "pairs": self.pairs,
            "tokenizer_identity_hashes": self.tokenizer_identity_hashes,
            "independent_source_count": self.independent_source_count,
            "representation_cell_count": self.representation_cell_count,
            "changed_cell_count": self.changed_cell_count,
            "universal_change_source_count": self.universal_change_source_count,
            "metric_disagreement_source_count": self.metric_disagreement_source_count,
            "token_count_direction_disagreement_source_count": self.token_count_direction_disagreement_source_count,
            "detector_query_count": self.detector_query_count,
            "secret_query_count": self.secret_query_count,
            "claim_status": self.claim_status,
        }


def build_representation_differential_audit(
    pairs: Sequence[RepresentationPairEvidence],
) -> RepresentationDifferentialAudit:
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes, bytearray)):
        raise TypeError("pairs must be a sequence")
    values = tuple(pairs)
    if any(not isinstance(value, RepresentationPairEvidence) for value in values):
        raise TypeError("pairs must contain RepresentationPairEvidence values")
    ordered = tuple(sorted(values, key=lambda value: (value.source_sample_id, value.pair_hash)))
    if len(ordered) < 2:
        raise RepresentationDifferentialInputError(
            "representation differential audit requires at least two independent source pairs"
        )
    tokenizer_hashes = ordered[0].tokenizer_identity_hashes
    payload = {
        "algorithm_version": REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION,
        "pairs": ordered,
        "tokenizer_identity_hashes": tokenizer_hashes,
        "independent_source_count": len(ordered),
        "representation_cell_count": sum(len(value.rows) for value in ordered),
        "changed_cell_count": sum(value.changed_tokenizer_count for value in ordered),
        "universal_change_source_count": sum(value.universal_tokenization_change for value in ordered),
        "metric_disagreement_source_count": sum(value.metric_disagreement for value in ordered),
        "token_count_direction_disagreement_source_count": sum(
            value.token_count_direction_disagreement for value in ordered
        ),
        "detector_query_count": 0,
        "secret_query_count": 0,
        "claim_status": REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS,
    }
    return RepresentationDifferentialAudit(
        REPRESENTATION_DIFFERENTIAL_ALGORITHM_VERSION,
        ordered,
        tokenizer_hashes,
        payload["independent_source_count"],
        payload["representation_cell_count"],
        payload["changed_cell_count"],
        payload["universal_change_source_count"],
        payload["metric_disagreement_source_count"],
        payload["token_count_direction_disagreement_source_count"],
        0,
        0,
        REPRESENTATION_DIFFERENTIAL_CLAIM_STATUS,
        sha256_json(payload),
    )


def verify_representation_differential_audit(
    audit: RepresentationDifferentialAudit,
    pairs: Sequence[RepresentationPairEvidence],
) -> None:
    if not isinstance(audit, RepresentationDifferentialAudit):
        raise TypeError("audit must be a RepresentationDifferentialAudit")
    expected = build_representation_differential_audit(pairs)
    if audit != expected:
        raise RepresentationDifferentialInputError(
            "representation differential audit does not replay exactly from source pairs"
        )
