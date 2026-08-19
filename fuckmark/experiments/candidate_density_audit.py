from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..scheduling.beam_v2 import beam_search_v2
from ..scheduling.state_search import SearchState, SearchTransition
from .mid_dev_quality import protected_span_violation_count, word_edit_rate
from .structural_leverage import character_edit_rate


STRICT_CANDIDATE_DENSITY_AUDIT_VERSION = "strict-candidate-density-audit-v1"
STRICT_CANDIDATE_DENSITY_ROW_VERSION = "strict-candidate-density-row-v1"
STRICT_WORD_EDIT_RATE_MAX = 0.03
STRICT_CHARACTER_EDIT_RATE_MAX = 0.015
STRICT_LENGTH_RATIO_MIN = 0.97
STRICT_LENGTH_RATIO_MAX = 1.03
STRICT_DENSITY_BUDGETS = (4, 6)
STRICT_DENSITY_BEAM_WIDTH = 32
STRICT_SCARCITY_B4 = "STRICT_B4_CANDIDATE_SCARCITY"
STRICT_SCARCITY_B6 = "STRICT_B6_CANDIDATE_SCARCITY"
STRICT_NO_REACHABILITY_SCARCITY = "NO_STRICT_REACHABILITY_SCARCITY"


class CandidateExpander(Protocol):
    @property
    def detector_access_observed(self) -> bool: ...

    @property
    def secret_access_observed(self) -> bool: ...

    def expand(self, state: SearchState) -> Sequence[SearchTransition]: ...


@dataclass(frozen=True, slots=True)
class StrictCandidateAssessment:
    state_hash: str
    word_edit_rate: float
    character_edit_rate: float
    length_ratio: float
    protected_span_violation_count: int
    strict_eligible: bool
    reason_codes: tuple[str, ...]
    assessment_hash: str

    def __post_init__(self) -> None:
        require_sha256("state_hash", self.state_hash)
        for name in ("word_edit_rate", "character_edit_rate", "length_ratio"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if float(value) < 0:
                raise ValueError(f"{name} must be non-negative")
        require_int("protected_span_violation_count", self.protected_span_violation_count)
        if self.protected_span_violation_count < 0:
            raise ValueError("protected_span_violation_count must be non-negative")
        if type(self.strict_eligible) is not bool:
            raise TypeError("strict_eligible must be bool")
        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("reason_codes must be unique and sorted")
        for value in self.reason_codes:
            require_clean_string("reason_code", value)
        if self.strict_eligible != (not self.reason_codes):
            raise ValueError("strict_eligible must match reason codes")
        require_sha256("assessment_hash", self.assessment_hash)
        if self.assessment_hash != sha256_json(self.payload()):
            raise ValueError("assessment_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": "strict-candidate-assessment-v1",
            "state_hash": self.state_hash,
            "word_edit_rate": self.word_edit_rate,
            "character_edit_rate": self.character_edit_rate,
            "length_ratio": self.length_ratio,
            "protected_span_violation_count": self.protected_span_violation_count,
            "strict_eligible": self.strict_eligible,
            "reason_codes": self.reason_codes,
        }


def assess_strict_candidate(root_text: str, state: SearchState) -> StrictCandidateAssessment:
    if not isinstance(root_text, str) or not root_text:
        raise ValueError("root_text must be non-empty")
    if not isinstance(state, SearchState):
        raise TypeError("state must be SearchState")
    word_rate = word_edit_rate(root_text, state.text)
    char_rate = character_edit_rate(root_text, state.text)
    length_ratio = len(state.text) / len(root_text)
    protected_violations = protected_span_violation_count(root_text, state.text)
    reasons: list[str] = []
    if word_rate > STRICT_WORD_EDIT_RATE_MAX:
        reasons.append("STRICT_WORD_EDIT_RATE_EXCEEDED")
    if char_rate > STRICT_CHARACTER_EDIT_RATE_MAX:
        reasons.append("STRICT_CHARACTER_EDIT_RATE_EXCEEDED")
    if not STRICT_LENGTH_RATIO_MIN <= length_ratio <= STRICT_LENGTH_RATIO_MAX:
        reasons.append("STRICT_LENGTH_RATIO_EXCEEDED")
    if protected_violations != 0:
        reasons.append("STRICT_PROTECTED_SPAN_VIOLATION")
    normalized = tuple(sorted(set(reasons)))
    payload = {
        "algorithm_version": "strict-candidate-assessment-v1",
        "state_hash": state.search_state_hash,
        "word_edit_rate": word_rate,
        "character_edit_rate": char_rate,
        "length_ratio": length_ratio,
        "protected_span_violation_count": protected_violations,
        "strict_eligible": not normalized,
        "reason_codes": normalized,
    }
    return StrictCandidateAssessment(**{k: v for k, v in payload.items() if k != "algorithm_version"}, assessment_hash=sha256_json(payload))


class StrictCostExpander:
    def __init__(self, base: CandidateExpander, root_text: str) -> None:
        if not isinstance(root_text, str) or not root_text:
            raise ValueError("root_text must be non-empty")
        self._base = base
        self._root_text = root_text
        self._cache: dict[str, tuple[SearchTransition, ...]] = {}
        self._assessments: dict[str, StrictCandidateAssessment] = {}
        self._raw_transition_hashes: set[str] = set()
        self._strict_transition_hashes: set[str] = set()

    @property
    def detector_access_observed(self) -> bool:
        return bool(getattr(self._base, "detector_access_observed", False))

    @property
    def secret_access_observed(self) -> bool:
        return bool(getattr(self._base, "secret_access_observed", False))

    @property
    def raw_unique_transition_count(self) -> int:
        return len(self._raw_transition_hashes)

    @property
    def strict_unique_transition_count(self) -> int:
        return len(self._strict_transition_hashes)

    @property
    def rejection_reason_counts(self) -> tuple[tuple[str, int], ...]:
        counts: Counter[str] = Counter()
        for assessment in self._assessments.values():
            for reason in assessment.reason_codes:
                counts[reason] += 1
        return tuple(sorted(counts.items()))

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        cached = self._cache.get(state.search_state_hash)
        if cached is not None:
            return cached
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("STRICT candidate-density audit observed prohibited selection access")
        output: list[SearchTransition] = []
        for transition in self._base.expand(state):
            self._raw_transition_hashes.add(transition.transition_hash)
            assessment = self._assessments.get(transition.child.search_state_hash)
            if assessment is None:
                assessment = assess_strict_candidate(self._root_text, transition.child)
                self._assessments[transition.child.search_state_hash] = assessment
            if assessment.strict_eligible:
                self._strict_transition_hashes.add(transition.transition_hash)
                output.append(transition)
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("STRICT candidate-density audit observed prohibited selection access")
        result = tuple(output)
        self._cache[state.search_state_hash] = result
        return result


@dataclass(frozen=True, slots=True)
class StrictCandidateDensityRow:
    source_sample_id: str
    root_enumerated_candidate_count: int
    root_planner_transition_count: int
    root_strict_transition_count: int
    strict_unique_transition_count: int
    raw_unique_transition_count: int
    strict_b4_reachable: bool
    strict_b6_reachable: bool
    strict_b4_final_depth: int
    strict_b6_final_depth: int
    root_family_counts: tuple[tuple[str, int], ...]
    root_strict_family_counts: tuple[tuple[str, int], ...]
    rejection_reason_counts: tuple[tuple[str, int], ...]
    detector_access_observed: bool
    secret_access_observed: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        for name in (
            "root_enumerated_candidate_count",
            "root_planner_transition_count",
            "root_strict_transition_count",
            "strict_unique_transition_count",
            "raw_unique_transition_count",
            "strict_b4_final_depth",
            "strict_b6_final_depth",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in ("strict_b4_reachable", "strict_b6_reachable", "detector_access_observed", "secret_access_observed"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("candidate-density row is contaminated")
        if self.strict_b4_reachable != (self.strict_b4_final_depth >= 4):
            raise ValueError("B4 reachability does not match final depth")
        if self.strict_b6_reachable != (self.strict_b6_final_depth >= 6):
            raise ValueError("B6 reachability does not match final depth")
        if self.root_strict_transition_count > self.root_planner_transition_count:
            raise ValueError("strict root count exceeds planner root count")
        for pairs_name in ("root_family_counts", "root_strict_family_counts", "rejection_reason_counts"):
            pairs = getattr(self, pairs_name)
            if tuple(sorted(pairs)) != pairs:
                raise ValueError(f"{pairs_name} must be sorted")
            for label, count in pairs:
                require_clean_string("label", label)
                require_int("count", count)
                if count < 0:
                    raise ValueError("count must be non-negative")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": STRICT_CANDIDATE_DENSITY_ROW_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"},
        }


@dataclass(frozen=True, slots=True)
class StrictCandidateDensityArtifact:
    source_code_commit: str
    source_corpus_hash: str
    candidate_registry_hash: str
    rows: tuple[StrictCandidateDensityRow, ...]
    decision: str
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_code_commit", self.source_code_commit)
        if len(self.source_code_commit) not in (40, 64) or any(ch not in "0123456789abcdef" for ch in self.source_code_commit):
            raise ValueError("source_code_commit must be a lowercase Git object ID")
        require_sha256("source_corpus_hash", self.source_corpus_hash)
        require_sha256("candidate_registry_hash", self.candidate_registry_hash)
        if not isinstance(self.rows, tuple) or any(not isinstance(row, StrictCandidateDensityRow) for row in self.rows):
            raise TypeError("rows must contain StrictCandidateDensityRow values")
        expected = classify_strict_candidate_density(self.rows)
        if self.decision != expected:
            raise ValueError("candidate-density decision does not reproduce")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": STRICT_CANDIDATE_DENSITY_AUDIT_VERSION,
            "source_code_commit": self.source_code_commit,
            "source_corpus_hash": self.source_corpus_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "strict_policy": {
                "word_edit_rate_max": STRICT_WORD_EDIT_RATE_MAX,
                "character_edit_rate_max": STRICT_CHARACTER_EDIT_RATE_MAX,
                "length_ratio_min": STRICT_LENGTH_RATIO_MIN,
                "length_ratio_max": STRICT_LENGTH_RATIO_MAX,
                "protected_span_violations": 0,
            },
            "budgets": STRICT_DENSITY_BUDGETS,
            "beam_width": STRICT_DENSITY_BEAM_WIDTH,
            "row_hashes": tuple(row.row_hash for row in self.rows),
            "decision": self.decision,
        }


def classify_strict_candidate_density(rows: Sequence[StrictCandidateDensityRow]) -> str:
    materialized = tuple(rows)
    if not materialized:
        raise ValueError("candidate-density audit requires rows")
    if len({row.source_sample_id for row in materialized}) != len(materialized):
        raise ValueError("candidate-density rows require unique source IDs")
    if any(not row.strict_b4_reachable for row in materialized):
        return STRICT_SCARCITY_B4
    if any(not row.strict_b6_reachable for row in materialized):
        return STRICT_SCARCITY_B6
    return STRICT_NO_REACHABILITY_SCARCITY


def _max_depth(result: Any) -> int:
    states = tuple(getattr(result, "states", ())) + tuple(getattr(result, "frontier", ()))
    return max((state.depth for state in states), default=0)


def audit_source_candidate_density(
    *,
    source_sample_id: str,
    source_text: str,
    registry: Any,
    base_expander: CandidateExpander,
    root_state: SearchState,
) -> StrictCandidateDensityRow:
    enumeration = registry.enumerate(source_text)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    root_raw = tuple(base_expander.expand(root_state))
    strict_expander = StrictCostExpander(base_expander, source_text)
    root_strict = tuple(strict_expander.expand(root_state))
    root_families: Counter[str] = Counter()
    root_strict_families: Counter[str] = Counter()
    for transition in root_raw:
        candidate = candidate_by_id.get(transition.candidate_hash)
        if candidate is not None:
            root_families[candidate.family.value] += 1
    for transition in root_strict:
        candidate = candidate_by_id.get(transition.candidate_hash)
        if candidate is not None:
            root_strict_families[candidate.family.value] += 1
    b4 = beam_search_v2(strict_expander, root_state, budget=4, beam_width=STRICT_DENSITY_BEAM_WIDTH)
    b6 = beam_search_v2(strict_expander, root_state, budget=6, beam_width=STRICT_DENSITY_BEAM_WIDTH)
    b4_depth = _max_depth(b4)
    b6_depth = _max_depth(b6)
    payload = {
        "algorithm_version": STRICT_CANDIDATE_DENSITY_ROW_VERSION,
        "source_sample_id": source_sample_id,
        "root_enumerated_candidate_count": len(enumeration.candidates),
        "root_planner_transition_count": len(root_raw),
        "root_strict_transition_count": len(root_strict),
        "strict_unique_transition_count": strict_expander.strict_unique_transition_count,
        "raw_unique_transition_count": strict_expander.raw_unique_transition_count,
        "strict_b4_reachable": b4_depth >= 4,
        "strict_b6_reachable": b6_depth >= 6,
        "strict_b4_final_depth": b4_depth,
        "strict_b6_final_depth": b6_depth,
        "root_family_counts": tuple(sorted(root_families.items())),
        "root_strict_family_counts": tuple(sorted(root_strict_families.items())),
        "rejection_reason_counts": strict_expander.rejection_reason_counts,
        "detector_access_observed": strict_expander.detector_access_observed,
        "secret_access_observed": strict_expander.secret_access_observed,
    }
    return StrictCandidateDensityRow(**{k: v for k, v in payload.items() if k != "algorithm_version"}, row_hash=sha256_json(payload))


def build_strict_candidate_density_artifact(
    *,
    source_code_commit: str,
    source_corpus_hash: str,
    candidate_registry_hash: str,
    rows: Sequence[StrictCandidateDensityRow],
) -> StrictCandidateDensityArtifact:
    row_tuple = tuple(sorted(rows, key=lambda row: row.source_sample_id))
    decision = classify_strict_candidate_density(row_tuple)
    payload = {
        "algorithm_version": STRICT_CANDIDATE_DENSITY_AUDIT_VERSION,
        "source_code_commit": source_code_commit,
        "source_corpus_hash": source_corpus_hash,
        "candidate_registry_hash": candidate_registry_hash,
        "strict_policy": {
            "word_edit_rate_max": STRICT_WORD_EDIT_RATE_MAX,
            "character_edit_rate_max": STRICT_CHARACTER_EDIT_RATE_MAX,
            "length_ratio_min": STRICT_LENGTH_RATIO_MIN,
            "length_ratio_max": STRICT_LENGTH_RATIO_MAX,
            "protected_span_violations": 0,
        },
        "budgets": STRICT_DENSITY_BUDGETS,
        "beam_width": STRICT_DENSITY_BEAM_WIDTH,
        "row_hashes": tuple(row.row_hash for row in row_tuple),
        "decision": decision,
    }
    return StrictCandidateDensityArtifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=source_corpus_hash,
        candidate_registry_hash=candidate_registry_hash,
        rows=row_tuple,
        decision=decision,
        artifact_hash=sha256_json(payload),
    )
