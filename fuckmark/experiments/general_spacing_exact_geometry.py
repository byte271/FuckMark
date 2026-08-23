from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..coverage import union_size
from ..geometry import CounterfactualGeometryEngine, GeometryConfig
from ..hashing import sha256_json, sha256_text
from ..transforms.candidate_artifacts import CandidateEnumeration
from ..transforms.registry import TransformRegistry
from ..transforms.tokenizer_geometry import build_candidate_tokenizer_geometry


GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION = "general-spacing-exact-geometry-diagnostic-v1"
GENERAL_SPACING_EXACT_GEOMETRY_POLICY_ID = "all-eligible-v1"


@dataclass(frozen=True, slots=True)
class GeneralSpacingExactGeometryDiagnostic:
    algorithm_version: str
    source_sample_id: str
    source_text_hash: str
    enumeration_hash: str
    ruleset_hash: str
    tokenizer_identity_hash: str
    ngram_len: int
    selected_candidate_ids: tuple[str, ...]
    selected_rule_ids: tuple[str, ...]
    selected_candidate_count: int
    root_observation_count: int
    proxy_covered_observation_count: int
    exact_destroyed_observation_count: int
    exact_surviving_observation_count: int
    proxy_coverage_ratio: float
    exact_destruction_ratio: float
    exact_minus_proxy_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    diagnostic_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION:
            raise ValueError("unsupported exact spacing geometry diagnostic version")
        require_clean_string("source_sample_id", self.source_sample_id)
        for name in (
            "source_text_hash",
            "enumeration_hash",
            "ruleset_hash",
            "tokenizer_identity_hash",
            "diagnostic_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "ngram_len",
            "selected_candidate_count",
            "root_observation_count",
            "proxy_covered_observation_count",
            "exact_destroyed_observation_count",
            "exact_surviving_observation_count",
            "exact_minus_proxy_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        if self.selected_candidate_count <= 0:
            raise ValueError("selected_candidate_count must be positive")
        if self.selected_candidate_count != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_count does not match selected_candidate_ids")
        if len(self.selected_rule_ids) != self.selected_candidate_count:
            raise ValueError("selected_rule_ids does not match selected candidates")
        if len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_ids must be unique")
        for candidate_id in self.selected_candidate_ids:
            require_sha256("selected_candidate_id", candidate_id)
        for rule_id in self.selected_rule_ids:
            require_clean_string("selected_rule_id", rule_id)
        if self.root_observation_count < 0:
            raise ValueError("root_observation_count must be non-negative")
        if not 0 <= self.proxy_covered_observation_count <= self.root_observation_count:
            raise ValueError("proxy covered observation count is outside the root denominator")
        if not 0 <= self.exact_destroyed_observation_count <= self.root_observation_count:
            raise ValueError("exact destroyed observation count is outside the root denominator")
        if not 0 <= self.exact_surviving_observation_count <= self.root_observation_count:
            raise ValueError("exact surviving observation count is outside the root denominator")
        if self.exact_destroyed_observation_count + self.exact_surviving_observation_count != self.root_observation_count:
            raise ValueError("exact survival counts do not partition the root observations")
        if self.exact_minus_proxy_count != self.exact_destroyed_observation_count - self.proxy_covered_observation_count:
            raise ValueError("exact_minus_proxy_count does not match exact minus proxy")
        expected_proxy_ratio = (
            self.proxy_covered_observation_count / self.root_observation_count
            if self.root_observation_count
            else 0.0
        )
        expected_exact_ratio = (
            self.exact_destroyed_observation_count / self.root_observation_count
            if self.root_observation_count
            else 0.0
        )
        if self.proxy_coverage_ratio != expected_proxy_ratio:
            raise ValueError("proxy_coverage_ratio does not match structural counts")
        if self.exact_destruction_ratio != expected_exact_ratio:
            raise ValueError("exact_destruction_ratio does not match structural counts")
        if self.detector_access_observed is not False or self.secret_access_observed is not False:
            raise ValueError("exact spacing geometry diagnostics must remain detector-blind and key-blind")
        if self.diagnostic_hash != sha256_json(self.payload()):
            raise ValueError("diagnostic_hash does not match exact spacing geometry diagnostic")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "enumeration_hash": self.enumeration_hash,
            "ruleset_hash": self.ruleset_hash,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "ngram_len": self.ngram_len,
            "selected_candidate_ids": self.selected_candidate_ids,
            "selected_rule_ids": self.selected_rule_ids,
            "selected_candidate_count": self.selected_candidate_count,
            "root_observation_count": self.root_observation_count,
            "proxy_covered_observation_count": self.proxy_covered_observation_count,
            "exact_destroyed_observation_count": self.exact_destroyed_observation_count,
            "exact_surviving_observation_count": self.exact_surviving_observation_count,
            "proxy_coverage_ratio": self.proxy_coverage_ratio,
            "exact_destruction_ratio": self.exact_destruction_ratio,
            "exact_minus_proxy_count": self.exact_minus_proxy_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _encode_with_offsets(tokenizer: Any, text: str) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable for offset-aware source tokenization")
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    if not isinstance(encoded, Mapping):
        raise TypeError("tokenizer must return a mapping for offset-aware source tokenization")
    if "input_ids" not in encoded or "offset_mapping" not in encoded:
        raise TypeError("tokenizer output must contain input_ids and offset_mapping")
    token_ids = tuple(int(value) for value in encoded["input_ids"])
    offsets = tuple((int(start), int(end)) for start, end in encoded["offset_mapping"])
    return token_ids, offsets


def diagnose_selected_candidate_geometry(
    *,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    selected_candidate_ids: Sequence[str],
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> GeneralSpacingExactGeometryDiagnostic:
    require_clean_string("source_sample_id", source_sample_id)
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    if not isinstance(enumeration, CandidateEnumeration):
        raise TypeError("enumeration must be a CandidateEnumeration")
    if enumeration.input_text != source_text or enumeration.input_hash != sha256_text(source_text):
        raise ValueError("candidate enumeration does not bind the supplied source text")
    if enumeration.ruleset_hash != registry.ruleset_hash:
        raise ValueError("candidate enumeration ruleset does not match registry")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if not isinstance(selected_candidate_ids, Sequence) or isinstance(
        selected_candidate_ids, (str, bytes, bytearray)
    ):
        raise TypeError("selected_candidate_ids must be a sequence")
    selected_ids = tuple(selected_candidate_ids)
    if not selected_ids:
        raise ValueError("selected_candidate_ids must not be empty")
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("selected_candidate_ids must be unique")
    for candidate_id in selected_ids:
        require_sha256("selected_candidate_id", candidate_id)

    candidates_by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    unknown = tuple(candidate_id for candidate_id in selected_ids if candidate_id not in candidates_by_id)
    if unknown:
        raise KeyError("selected_candidate_ids contains an unknown or rejected candidate")

    token_ids, offsets = _encode_with_offsets(tokenizer, source_text)
    proxy_geometry = build_candidate_tokenizer_geometry(
        source_text,
        enumeration,
        token_ids,
        offsets,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
    )
    coverage_mapping = proxy_geometry.coverage_mapping()
    proxy_covered = union_size(
        interval
        for candidate_id in selected_ids
        for interval in coverage_mapping[candidate_id]
    )

    transformed = registry.apply(enumeration, selected_ids)
    config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=GENERAL_SPACING_EXACT_GEOMETRY_POLICY_ID,
    )
    engine = CounterfactualGeometryEngine(tokenizer=tokenizer, config=config)
    root = engine.build_root(source_sample_id=source_sample_id, source_text=source_text)
    selection_hash = sha256_json(
        {
            "algorithm_version": GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION,
            "source_text_hash": enumeration.input_hash,
            "selected_candidate_ids": selected_ids,
        }
    )
    exact = engine.evaluate_output(
        root=root,
        current_text=source_text,
        output_text=transformed.output_text,
        candidate_id=selection_hash,
        rule_hash=registry.ruleset_hash,
        visible_cost_class=0,
        family="exact-geometry-diagnostic",
        tier=0,
    )
    if exact.root_observation_count != max(0, len(token_ids) - ngram_len + 1):
        raise ValueError("exact root observation denominator does not match public source tokenization")

    selected_rule_ids = tuple(candidates_by_id[candidate_id].rule_id for candidate_id in selected_ids)
    root_count = exact.root_observation_count
    proxy_ratio = proxy_covered / root_count if root_count else 0.0
    exact_ratio = exact.destroyed_count / root_count if root_count else 0.0
    payload = {
        "algorithm_version": GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION,
        "source_sample_id": source_sample_id,
        "source_text_hash": enumeration.input_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "ruleset_hash": registry.ruleset_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "selected_candidate_ids": selected_ids,
        "selected_rule_ids": selected_rule_ids,
        "selected_candidate_count": len(selected_ids),
        "root_observation_count": root_count,
        "proxy_covered_observation_count": proxy_covered,
        "exact_destroyed_observation_count": exact.destroyed_count,
        "exact_surviving_observation_count": exact.surviving_count,
        "proxy_coverage_ratio": proxy_ratio,
        "exact_destruction_ratio": exact_ratio,
        "exact_minus_proxy_count": exact.destroyed_count - proxy_covered,
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return GeneralSpacingExactGeometryDiagnostic(
        **payload,
        diagnostic_hash=sha256_json(payload),
    )
