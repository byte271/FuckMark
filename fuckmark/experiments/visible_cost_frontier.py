from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from ..search.visible_cost_budget import (
    RELAXED_VISIBLE_COST_POLICY,
    STRICT_VISIBLE_COST_POLICY,
    VisibleCostAssessment,
    VisibleCostSearchResult,
)


VISIBLE_COST_FRONTIER_ARTIFACT_VERSION = "tiny-dev-visible-cost-frontier-v1"
VISIBLE_COST_FRONTIER_ROW_VERSION = "tiny-dev-visible-cost-frontier-row-v1"


@dataclass(frozen=True, slots=True)
class VisibleCostFrontierRow:
    source_sample_id: str
    source_character_count: int
    root_surviving_observations: int
    strict_result_hash: str
    strict_reached_depth: int
    strict_state_hash: str
    strict_surviving_observations: int
    strict_assessment_hash: str
    strict_word_edit_rate: float
    strict_character_edit_rate: float
    relaxed_result_hash: str
    relaxed_reached_depth: int
    relaxed_state_hash: str
    relaxed_surviving_observations: int
    relaxed_assessment_hash: str
    relaxed_word_edit_rate: float
    relaxed_character_edit_rate: float
    row_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_sample_id, str) or not self.source_sample_id:
            raise ValueError("source_sample_id must be non-empty")
        for name in (
            "source_character_count",
            "root_surviving_observations",
            "strict_reached_depth",
            "strict_surviving_observations",
            "relaxed_reached_depth",
            "relaxed_surviving_observations",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.source_character_count <= 0:
            raise ValueError("source_character_count must be positive")
        for name in (
            "strict_result_hash",
            "strict_state_hash",
            "strict_assessment_hash",
            "relaxed_result_hash",
            "relaxed_state_hash",
            "relaxed_assessment_hash",
            "row_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "strict_word_edit_rate",
            "strict_character_edit_rate",
            "relaxed_word_edit_rate",
            "relaxed_character_edit_rate",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.strict_word_edit_rate > STRICT_VISIBLE_COST_POLICY.word_edit_rate_max:
            raise ValueError("STRICT word edit rate exceeded")
        if self.strict_character_edit_rate > STRICT_VISIBLE_COST_POLICY.character_edit_rate_max:
            raise ValueError("STRICT character edit rate exceeded")
        if self.relaxed_word_edit_rate > RELAXED_VISIBLE_COST_POLICY.word_edit_rate_max:
            raise ValueError("RELAXED word edit rate exceeded")
        if self.relaxed_character_edit_rate > RELAXED_VISIBLE_COST_POLICY.character_edit_rate_max:
            raise ValueError("RELAXED character edit rate exceeded")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        source_sample_id: str,
        source_character_count: int,
        root_surviving_observations: int,
        strict_result: VisibleCostSearchResult,
        strict_assessment: VisibleCostAssessment,
        relaxed_result: VisibleCostSearchResult,
        relaxed_assessment: VisibleCostAssessment,
    ) -> "VisibleCostFrontierRow":
        strict_state = strict_result.states[0]
        relaxed_state = relaxed_result.states[0]
        if strict_assessment.state_hash != strict_state.search_state_hash or not strict_assessment.eligible:
            raise ValueError("STRICT assessment does not bind eligible terminal state")
        if relaxed_assessment.state_hash != relaxed_state.search_state_hash or not relaxed_assessment.eligible:
            raise ValueError("RELAXED assessment does not bind eligible terminal state")
        payload = {
            "algorithm_version": VISIBLE_COST_FRONTIER_ROW_VERSION,
            "source_sample_id": source_sample_id,
            "source_character_count": source_character_count,
            "root_surviving_observations": root_surviving_observations,
            "strict_result_hash": strict_result.result_hash,
            "strict_reached_depth": strict_result.reached_depth,
            "strict_state_hash": strict_state.search_state_hash,
            "strict_surviving_observations": strict_state.surviving_root_observations,
            "strict_assessment_hash": strict_assessment.assessment_hash,
            "strict_word_edit_rate": strict_assessment.word_edit_rate,
            "strict_character_edit_rate": strict_assessment.character_edit_rate,
            "relaxed_result_hash": relaxed_result.result_hash,
            "relaxed_reached_depth": relaxed_result.reached_depth,
            "relaxed_state_hash": relaxed_state.search_state_hash,
            "relaxed_surviving_observations": relaxed_state.surviving_root_observations,
            "relaxed_assessment_hash": relaxed_assessment.assessment_hash,
            "relaxed_word_edit_rate": relaxed_assessment.word_edit_rate,
            "relaxed_character_edit_rate": relaxed_assessment.character_edit_rate,
        }
        return cls(
            **{key: value for key, value in payload.items() if key != "algorithm_version"},
            row_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": VISIBLE_COST_FRONTIER_ROW_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"},
        }


@dataclass(frozen=True, slots=True)
class VisibleCostFrontierArtifact:
    source_code_commit: str
    source_corpus_hash: str
    candidate_registry_hash: str
    scarcity_diagnosis_artifact_hash: str
    rows: tuple[VisibleCostFrontierRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_code_commit, str)
            or len(self.source_code_commit) not in (40, 64)
            or any(ch not in "0123456789abcdef" for ch in self.source_code_commit)
        ):
            raise ValueError("source_code_commit must be a lowercase Git object ID")
        for name in (
            "source_corpus_hash",
            "candidate_registry_hash",
            "scarcity_diagnosis_artifact_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.rows, tuple) or any(not isinstance(row, VisibleCostFrontierRow) for row in self.rows):
            raise TypeError("rows must contain VisibleCostFrontierRow values")
        if not self.rows:
            raise ValueError("visible-cost frontier requires rows")
        if len({row.source_sample_id for row in self.rows}) != len(self.rows):
            raise ValueError("visible-cost frontier source IDs must be unique")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": VISIBLE_COST_FRONTIER_ARTIFACT_VERSION,
            "source_code_commit": self.source_code_commit,
            "source_corpus_hash": self.source_corpus_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "scarcity_diagnosis_artifact_hash": self.scarcity_diagnosis_artifact_hash,
            "strict_policy_hash": STRICT_VISIBLE_COST_POLICY.policy_hash,
            "relaxed_policy_hash": RELAXED_VISIBLE_COST_POLICY.policy_hash,
            "row_hashes": tuple(row.row_hash for row in self.rows),
        }


def build_visible_cost_frontier_artifact(
    *,
    source_code_commit: str,
    source_corpus_hash: str,
    candidate_registry_hash: str,
    scarcity_diagnosis_artifact_hash: str,
    rows: Sequence[VisibleCostFrontierRow],
) -> VisibleCostFrontierArtifact:
    normalized = tuple(sorted(rows, key=lambda row: row.source_sample_id))
    payload = {
        "algorithm_version": VISIBLE_COST_FRONTIER_ARTIFACT_VERSION,
        "source_code_commit": source_code_commit,
        "source_corpus_hash": source_corpus_hash,
        "candidate_registry_hash": candidate_registry_hash,
        "scarcity_diagnosis_artifact_hash": scarcity_diagnosis_artifact_hash,
        "strict_policy_hash": STRICT_VISIBLE_COST_POLICY.policy_hash,
        "relaxed_policy_hash": RELAXED_VISIBLE_COST_POLICY.policy_hash,
        "row_hashes": tuple(row.row_hash for row in normalized),
    }
    return VisibleCostFrontierArtifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=source_corpus_hash,
        candidate_registry_hash=candidate_registry_hash,
        scarcity_diagnosis_artifact_hash=scarcity_diagnosis_artifact_hash,
        rows=normalized,
        artifact_hash=sha256_json(payload),
    )
