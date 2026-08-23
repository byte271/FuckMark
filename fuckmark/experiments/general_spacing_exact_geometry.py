from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..coverage import Interval, union_size
from ..geometry import CounterfactualGeometryEngine, GeometryConfig
from ..hashing import sha256_json, sha256_text
from ..transforms.candidate_artifacts import CandidateEnumeration, TransformCandidate
from ..transforms.registry import TransformRegistry
from ..transforms.tokenizer_geometry import CandidateTokenizerGeometry, build_candidate_tokenizer_geometry


GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION = "general-spacing-exact-geometry-diagnostic-v1"
GENERAL_SPACING_EXACT_MARGINAL_DIAGNOSTIC_VERSION = "general-spacing-exact-marginal-diagnostic-v1"
GENERAL_SPACING_EXACT_GEOMETRY_POLICY_ID = "all-eligible-v1"


@dataclass(frozen=True, slots=True)
class GeneralSpacingExactGeometryDiagnostic:
    algorithm_version: str
    source_sample_id: str
    source_text_hash: str
    enumeration_hash: str
    ruleset_hash: str
    tokenizer_identity_hash: str
    proxy_geometry_hash: str
    ngram_len: int
    selected_candidate_ids: tuple[str, ...]
    selected_rule_ids: tuple[str, ...]
    selected_candidate_count: int
    selection_hash: str
    transformed_text_hash: str
    transform_trace_hash: str
    exact_geometry_hash: str
    exact_survival_report_hash: str
    exact_token_edit_distance: int
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
            "proxy_geometry_hash",
            "selection_hash",
            "transformed_text_hash",
            "transform_trace_hash",
            "exact_geometry_hash",
            "exact_survival_report_hash",
            "diagnostic_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "ngram_len",
            "selected_candidate_count",
            "exact_token_edit_distance",
            "root_observation_count",
            "proxy_covered_observation_count",
            "exact_destroyed_observation_count",
            "exact_surviving_observation_count",
            "exact_minus_proxy_count",
        ):
            require_int(name, getattr(self, name))
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        if self.selected_candidate_count <= 0:
            raise ValueError("selected_candidate_count must be positive")
        if self.exact_token_edit_distance < 0:
            raise ValueError("exact_token_edit_distance must be non-negative")
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
            "proxy_geometry_hash": self.proxy_geometry_hash,
            "ngram_len": self.ngram_len,
            "selected_candidate_ids": self.selected_candidate_ids,
            "selected_rule_ids": self.selected_rule_ids,
            "selected_candidate_count": self.selected_candidate_count,
            "selection_hash": self.selection_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "transform_trace_hash": self.transform_trace_hash,
            "exact_geometry_hash": self.exact_geometry_hash,
            "exact_survival_report_hash": self.exact_survival_report_hash,
            "exact_token_edit_distance": self.exact_token_edit_distance,
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


@dataclass(frozen=True, slots=True)
class ExactMarginalCandidateRow:
    candidate_id: str
    rule_id: str
    source_start: int
    source_end: int
    proxy_marginal_gain: int
    exact_marginal_gain: int
    exact_destroyed_after: int
    transformed_text_hash: str
    exact_geometry_hash: str
    hidden_exact_gain: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("candidate_id", self.candidate_id)
        require_clean_string("rule_id", self.rule_id)
        for name in (
            "source_start",
            "source_end",
            "proxy_marginal_gain",
            "exact_marginal_gain",
            "exact_destroyed_after",
        ):
            require_int(name, getattr(self, name))
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("candidate source span must be non-empty and ordered")
        if self.proxy_marginal_gain < 0:
            raise ValueError("proxy_marginal_gain must be non-negative")
        if self.exact_destroyed_after < 0:
            raise ValueError("exact_destroyed_after must be non-negative")
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        require_sha256("exact_geometry_hash", self.exact_geometry_hash)
        if type(self.hidden_exact_gain) is not bool:
            raise TypeError("hidden_exact_gain must be boolean")
        if self.hidden_exact_gain != (self.proxy_marginal_gain == 0 and self.exact_marginal_gain > 0):
            raise ValueError("hidden_exact_gain does not match marginal gains")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match exact marginal candidate row")

    def payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "rule_id": self.rule_id,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "proxy_marginal_gain": self.proxy_marginal_gain,
            "exact_marginal_gain": self.exact_marginal_gain,
            "exact_destroyed_after": self.exact_destroyed_after,
            "transformed_text_hash": self.transformed_text_hash,
            "exact_geometry_hash": self.exact_geometry_hash,
            "hidden_exact_gain": self.hidden_exact_gain,
        }


@dataclass(frozen=True, slots=True)
class GeneralSpacingExactMarginalDiagnostic:
    algorithm_version: str
    source_sample_id: str
    source_text_hash: str
    enumeration_hash: str
    ruleset_hash: str
    tokenizer_identity_hash: str
    ngram_len: int
    baseline_diagnostic_hash: str
    selected_candidate_ids: tuple[str, ...]
    evaluated_candidate_count: int
    conflict_excluded_candidate_count: int
    baseline_proxy_covered_observation_count: int
    baseline_exact_destroyed_observation_count: int
    hidden_exact_gain_count: int
    maximum_hidden_exact_gain: int
    rows: tuple[ExactMarginalCandidateRow, ...]
    detector_access_observed: bool
    secret_access_observed: bool
    diagnostic_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != GENERAL_SPACING_EXACT_MARGINAL_DIAGNOSTIC_VERSION:
            raise ValueError("unsupported exact spacing marginal diagnostic version")
        require_clean_string("source_sample_id", self.source_sample_id)
        for name in (
            "source_text_hash",
            "enumeration_hash",
            "ruleset_hash",
            "tokenizer_identity_hash",
            "baseline_diagnostic_hash",
            "diagnostic_hash",
        ):
            require_sha256(name, getattr(self, name))
        for candidate_id in self.selected_candidate_ids:
            require_sha256("selected_candidate_id", candidate_id)
        if len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_ids must be unique")
        for name in (
            "ngram_len",
            "evaluated_candidate_count",
            "conflict_excluded_candidate_count",
            "baseline_proxy_covered_observation_count",
            "baseline_exact_destroyed_observation_count",
            "hidden_exact_gain_count",
            "maximum_hidden_exact_gain",
        ):
            require_int(name, getattr(self, name))
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        if any(
            value < 0
            for value in (
                self.evaluated_candidate_count,
                self.conflict_excluded_candidate_count,
                self.baseline_proxy_covered_observation_count,
                self.baseline_exact_destroyed_observation_count,
                self.hidden_exact_gain_count,
                self.maximum_hidden_exact_gain,
            )
        ):
            raise ValueError("marginal diagnostic counts must be non-negative")
        if not isinstance(self.rows, tuple) or any(not isinstance(row, ExactMarginalCandidateRow) for row in self.rows):
            raise TypeError("rows must contain ExactMarginalCandidateRow values")
        if self.rows != tuple(sorted(self.rows, key=lambda row: row.candidate_id)):
            raise ValueError("marginal diagnostic rows must be sorted by candidate_id")
        if self.evaluated_candidate_count != len(self.rows):
            raise ValueError("evaluated_candidate_count does not match rows")
        expected_hidden = tuple(row for row in self.rows if row.hidden_exact_gain)
        if self.hidden_exact_gain_count != len(expected_hidden):
            raise ValueError("hidden_exact_gain_count does not match rows")
        expected_maximum = max((row.exact_marginal_gain for row in expected_hidden), default=0)
        if self.maximum_hidden_exact_gain != expected_maximum:
            raise ValueError("maximum_hidden_exact_gain does not match rows")
        if self.detector_access_observed is not False or self.secret_access_observed is not False:
            raise ValueError("exact spacing marginal diagnostics must remain detector-blind and key-blind")
        if self.diagnostic_hash != sha256_json(self.payload()):
            raise ValueError("diagnostic_hash does not match exact spacing marginal diagnostic")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "enumeration_hash": self.enumeration_hash,
            "ruleset_hash": self.ruleset_hash,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "ngram_len": self.ngram_len,
            "baseline_diagnostic_hash": self.baseline_diagnostic_hash,
            "selected_candidate_ids": self.selected_candidate_ids,
            "evaluated_candidate_count": self.evaluated_candidate_count,
            "conflict_excluded_candidate_count": self.conflict_excluded_candidate_count,
            "baseline_proxy_covered_observation_count": self.baseline_proxy_covered_observation_count,
            "baseline_exact_destroyed_observation_count": self.baseline_exact_destroyed_observation_count,
            "hidden_exact_gain_count": self.hidden_exact_gain_count,
            "maximum_hidden_exact_gain": self.maximum_hidden_exact_gain,
            "row_hashes": tuple(row.row_hash for row in self.rows),
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


def _validate_selected_ids(
    enumeration: CandidateEnumeration,
    selected_candidate_ids: Sequence[str],
) -> tuple[tuple[str, ...], dict[str, TransformCandidate]]:
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
    return selected_ids, candidates_by_id


def _prepare_geometry(
    *,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> tuple[
    tuple[int, ...],
    CandidateTokenizerGeometry,
    CounterfactualGeometryEngine,
    Any,
]:
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
    token_ids, offsets = _encode_with_offsets(tokenizer, source_text)
    proxy_geometry = build_candidate_tokenizer_geometry(
        source_text,
        enumeration,
        token_ids,
        offsets,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
    )
    config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=GENERAL_SPACING_EXACT_GEOMETRY_POLICY_ID,
    )
    engine = CounterfactualGeometryEngine(tokenizer=tokenizer, config=config)
    root = engine.build_root(source_sample_id=source_sample_id, source_text=source_text)
    if root.observations.eligible_count != root.observations.token_count - ngram_len + 1:
        if root.observations.eligible_count != max(0, root.observations.token_count - ngram_len + 1):
            raise ValueError("exact root observation denominator does not match all-eligible geometry")
    if root.observations.token_count != len(token_ids):
        raise ValueError("exact root token count does not match offset-aware source tokenization")
    return token_ids, proxy_geometry, engine, root


def _selection_hash(source_text_hash: str, selected_ids: tuple[str, ...]) -> str:
    return sha256_json(
        {
            "algorithm_version": GENERAL_SPACING_EXACT_GEOMETRY_DIAGNOSTIC_VERSION,
            "source_text_hash": source_text_hash,
            "selected_candidate_ids": selected_ids,
        }
    )


def _evaluate_selection(
    *,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    selected_ids: tuple[str, ...],
    source_text: str,
    engine: CounterfactualGeometryEngine,
    root: Any,
):
    transformed = registry.apply(enumeration, selected_ids)
    selection_hash = _selection_hash(enumeration.input_hash, selected_ids)
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
    return transformed, exact, selection_hash


def _selected_proxy_intervals(
    geometry: CandidateTokenizerGeometry,
    selected_ids: tuple[str, ...],
) -> tuple[Interval, ...]:
    mapping = geometry.coverage_mapping()
    return tuple(
        interval
        for candidate_id in selected_ids
        for interval in mapping[candidate_id]
    )


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
    selected_ids, candidates_by_id = _validate_selected_ids(enumeration, selected_candidate_ids)
    token_ids, proxy_geometry, engine, root = _prepare_geometry(
        source_sample_id=source_sample_id,
        source_text=source_text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=tokenizer,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
    )
    proxy_covered = union_size(_selected_proxy_intervals(proxy_geometry, selected_ids))
    transformed, exact, selection_hash = _evaluate_selection(
        registry=registry,
        enumeration=enumeration,
        selected_ids=selected_ids,
        source_text=source_text,
        engine=engine,
        root=root,
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
        "proxy_geometry_hash": proxy_geometry.geometry_hash,
        "ngram_len": ngram_len,
        "selected_candidate_ids": selected_ids,
        "selected_rule_ids": selected_rule_ids,
        "selected_candidate_count": len(selected_ids),
        "selection_hash": selection_hash,
        "transformed_text_hash": sha256_text(transformed.output_text),
        "transform_trace_hash": transformed.trace.trace_hash,
        "exact_geometry_hash": exact.geometry_hash,
        "exact_survival_report_hash": exact.survival_report.report_hash,
        "exact_token_edit_distance": exact.token_edit_distance,
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


def diagnose_unselected_exact_marginals(
    *,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    selected_candidate_ids: Sequence[str],
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> GeneralSpacingExactMarginalDiagnostic:
    selected_ids, candidates_by_id = _validate_selected_ids(enumeration, selected_candidate_ids)
    baseline = diagnose_selected_candidate_geometry(
        source_sample_id=source_sample_id,
        source_text=source_text,
        registry=registry,
        enumeration=enumeration,
        selected_candidate_ids=selected_ids,
        tokenizer=tokenizer,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
    )
    _, proxy_geometry, engine, root = _prepare_geometry(
        source_sample_id=source_sample_id,
        source_text=source_text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=tokenizer,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
    )
    selected_set = set(selected_ids)
    conflict_pairs = {
        frozenset((conflict.first_candidate_id, conflict.second_candidate_id))
        for conflict in enumeration.conflicts
    }
    baseline_intervals = _selected_proxy_intervals(proxy_geometry, selected_ids)
    baseline_proxy = union_size(baseline_intervals)
    coverage_mapping = proxy_geometry.coverage_mapping()
    rows: list[ExactMarginalCandidateRow] = []
    conflict_excluded = 0
    for candidate in enumeration.candidates:
        if candidate.candidate_id in selected_set:
            continue
        if any(
            frozenset((candidate.candidate_id, selected_id)) in conflict_pairs
            for selected_id in selected_ids
        ):
            conflict_excluded += 1
            continue
        proxy_gain = union_size((*baseline_intervals, *coverage_mapping[candidate.candidate_id])) - baseline_proxy
        augmented_ids = (*selected_ids, candidate.candidate_id)
        transformed, exact, _ = _evaluate_selection(
            registry=registry,
            enumeration=enumeration,
            selected_ids=augmented_ids,
            source_text=source_text,
            engine=engine,
            root=root,
        )
        exact_gain = exact.destroyed_count - baseline.exact_destroyed_observation_count
        row_payload = {
            "candidate_id": candidate.candidate_id,
            "rule_id": candidate.rule_id,
            "source_start": candidate.start,
            "source_end": candidate.end,
            "proxy_marginal_gain": proxy_gain,
            "exact_marginal_gain": exact_gain,
            "exact_destroyed_after": exact.destroyed_count,
            "transformed_text_hash": sha256_text(transformed.output_text),
            "exact_geometry_hash": exact.geometry_hash,
            "hidden_exact_gain": proxy_gain == 0 and exact_gain > 0,
        }
        rows.append(ExactMarginalCandidateRow(**row_payload, row_hash=sha256_json(row_payload)))
    ordered_rows = tuple(sorted(rows, key=lambda row: row.candidate_id))
    hidden_rows = tuple(row for row in ordered_rows if row.hidden_exact_gain)
    payload = {
        "algorithm_version": GENERAL_SPACING_EXACT_MARGINAL_DIAGNOSTIC_VERSION,
        "source_sample_id": source_sample_id,
        "source_text_hash": enumeration.input_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "ruleset_hash": registry.ruleset_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "baseline_diagnostic_hash": baseline.diagnostic_hash,
        "selected_candidate_ids": selected_ids,
        "evaluated_candidate_count": len(ordered_rows),
        "conflict_excluded_candidate_count": conflict_excluded,
        "baseline_proxy_covered_observation_count": baseline.proxy_covered_observation_count,
        "baseline_exact_destroyed_observation_count": baseline.exact_destroyed_observation_count,
        "hidden_exact_gain_count": len(hidden_rows),
        "maximum_hidden_exact_gain": max((row.exact_marginal_gain for row in hidden_rows), default=0),
        "row_hashes": tuple(row.row_hash for row in ordered_rows),
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    return GeneralSpacingExactMarginalDiagnostic(
        algorithm_version=GENERAL_SPACING_EXACT_MARGINAL_DIAGNOSTIC_VERSION,
        source_sample_id=source_sample_id,
        source_text_hash=enumeration.input_hash,
        enumeration_hash=enumeration.enumeration_hash,
        ruleset_hash=registry.ruleset_hash,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        baseline_diagnostic_hash=baseline.diagnostic_hash,
        selected_candidate_ids=selected_ids,
        evaluated_candidate_count=len(ordered_rows),
        conflict_excluded_candidate_count=conflict_excluded,
        baseline_proxy_covered_observation_count=baseline.proxy_covered_observation_count,
        baseline_exact_destroyed_observation_count=baseline.exact_destroyed_observation_count,
        hidden_exact_gain_count=len(hidden_rows),
        maximum_hidden_exact_gain=max((row.exact_marginal_gain for row in hidden_rows), default=0),
        rows=ordered_rows,
        detector_access_observed=False,
        secret_access_observed=False,
        diagnostic_hash=sha256_json(payload),
    )
