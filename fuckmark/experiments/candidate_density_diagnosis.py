from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json


STRICT_SCARCITY_DIAGNOSIS_VERSION = "strict-scarcity-diagnosis-v1"
STRICT_SCARCITY_DIAGNOSIS_ROW_VERSION = "strict-scarcity-diagnosis-row-v1"
STRICT_CHARACTER_EDIT_RATE_MAX = 0.015
MINIMUM_VISIBLE_CHARACTER_EDITS_PER_OPERATION = 1
GENUINE_STRICT_B4_CANDIDATE_SCARCITY = "GENUINE_STRICT_B4_CANDIDATE_SCARCITY"
GENUINE_STRICT_B6_CANDIDATE_SCARCITY = "GENUINE_STRICT_B6_CANDIDATE_SCARCITY"
STRICT_VISIBLE_COST_CEILING_DOMINATES = "STRICT_VISIBLE_COST_CEILING_DOMINATES"
NO_STRICT_REACHABILITY_SCARCITY = "NO_STRICT_REACHABILITY_SCARCITY"


def strict_character_edit_budget(source_character_count: int) -> int:
    require_int("source_character_count", source_character_count)
    if source_character_count <= 0:
        raise ValueError("source_character_count must be positive")
    return int(math.floor(STRICT_CHARACTER_EDIT_RATE_MAX * source_character_count + 1e-12))


@dataclass(frozen=True, slots=True)
class StrictScarcityDiagnosisRow:
    source_sample_id: str
    source_character_count: int
    maximum_minimum_cost_operations: int
    observed_b4_reachable: bool
    observed_b6_reachable: bool
    b4_theoretically_reachable: bool
    b6_theoretically_reachable: bool
    b4_candidate_limited: bool
    b6_candidate_limited: bool
    b4_cost_ceiling_limited: bool
    b6_cost_ceiling_limited: bool
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        for name in ("source_character_count", "maximum_minimum_cost_operations"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.source_character_count <= 0:
            raise ValueError("source_character_count must be positive")
        maximum = strict_character_edit_budget(self.source_character_count)
        if self.maximum_minimum_cost_operations != maximum:
            raise ValueError("maximum_minimum_cost_operations does not match frozen STRICT character cap")
        for name in (
            "observed_b4_reachable",
            "observed_b6_reachable",
            "b4_theoretically_reachable",
            "b6_theoretically_reachable",
            "b4_candidate_limited",
            "b6_candidate_limited",
            "b4_cost_ceiling_limited",
            "b6_cost_ceiling_limited",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        b4 = maximum >= 4
        b6 = maximum >= 6
        expected = (
            b4,
            b6,
            not self.observed_b4_reachable and b4,
            not self.observed_b6_reachable and b6,
            not self.observed_b4_reachable and not b4,
            not self.observed_b6_reachable and not b6,
        )
        actual = (
            self.b4_theoretically_reachable,
            self.b6_theoretically_reachable,
            self.b4_candidate_limited,
            self.b6_candidate_limited,
            self.b4_cost_ceiling_limited,
            self.b6_cost_ceiling_limited,
        )
        if actual != expected:
            raise ValueError("strict scarcity diagnosis flags do not reproduce")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        source_sample_id: str,
        source_character_count: int,
        observed_b4_reachable: bool,
        observed_b6_reachable: bool,
    ) -> "StrictScarcityDiagnosisRow":
        maximum = strict_character_edit_budget(source_character_count)
        b4 = maximum >= 4
        b6 = maximum >= 6
        payload = {
            "algorithm_version": STRICT_SCARCITY_DIAGNOSIS_ROW_VERSION,
            "source_sample_id": source_sample_id,
            "source_character_count": source_character_count,
            "maximum_minimum_cost_operations": maximum,
            "observed_b4_reachable": observed_b4_reachable,
            "observed_b6_reachable": observed_b6_reachable,
            "b4_theoretically_reachable": b4,
            "b6_theoretically_reachable": b6,
            "b4_candidate_limited": not observed_b4_reachable and b4,
            "b6_candidate_limited": not observed_b6_reachable and b6,
            "b4_cost_ceiling_limited": not observed_b4_reachable and not b4,
            "b6_cost_ceiling_limited": not observed_b6_reachable and not b6,
        }
        return cls(
            **{key: value for key, value in payload.items() if key != "algorithm_version"},
            row_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": STRICT_SCARCITY_DIAGNOSIS_ROW_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"},
        }


def classify_strict_scarcity(rows: Sequence[StrictScarcityDiagnosisRow]) -> str:
    materialized = tuple(rows)
    if not materialized:
        raise ValueError("strict scarcity diagnosis requires rows")
    if len({row.source_sample_id for row in materialized}) != len(materialized):
        raise ValueError("strict scarcity diagnosis requires unique source IDs")
    if any(row.b4_candidate_limited for row in materialized):
        return GENUINE_STRICT_B4_CANDIDATE_SCARCITY
    if any(row.b6_candidate_limited for row in materialized):
        return GENUINE_STRICT_B6_CANDIDATE_SCARCITY
    if any(row.b4_cost_ceiling_limited or row.b6_cost_ceiling_limited for row in materialized):
        return STRICT_VISIBLE_COST_CEILING_DOMINATES
    return NO_STRICT_REACHABILITY_SCARCITY


@dataclass(frozen=True, slots=True)
class StrictScarcityDiagnosisArtifact:
    source_corpus_hash: str
    source_candidate_density_artifact_hash: str
    rows: tuple[StrictScarcityDiagnosisRow, ...]
    decision: str
    family_expansion_permitted: bool
    artifact_hash: str

    def __post_init__(self) -> None:
        require_sha256("source_corpus_hash", self.source_corpus_hash)
        require_sha256("source_candidate_density_artifact_hash", self.source_candidate_density_artifact_hash)
        if not isinstance(self.rows, tuple) or any(not isinstance(row, StrictScarcityDiagnosisRow) for row in self.rows):
            raise TypeError("rows must contain StrictScarcityDiagnosisRow values")
        decision = classify_strict_scarcity(self.rows)
        if self.decision != decision:
            raise ValueError("strict scarcity decision does not reproduce")
        permitted = decision in {
            GENUINE_STRICT_B4_CANDIDATE_SCARCITY,
            GENUINE_STRICT_B6_CANDIDATE_SCARCITY,
        }
        if type(self.family_expansion_permitted) is not bool or self.family_expansion_permitted != permitted:
            raise ValueError("family_expansion_permitted does not match diagnosis")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": STRICT_SCARCITY_DIAGNOSIS_VERSION,
            "source_corpus_hash": self.source_corpus_hash,
            "source_candidate_density_artifact_hash": self.source_candidate_density_artifact_hash,
            "strict_character_edit_rate_max": STRICT_CHARACTER_EDIT_RATE_MAX,
            "minimum_visible_character_edits_per_operation": MINIMUM_VISIBLE_CHARACTER_EDITS_PER_OPERATION,
            "row_hashes": tuple(row.row_hash for row in self.rows),
            "decision": self.decision,
            "family_expansion_permitted": self.family_expansion_permitted,
        }


def build_strict_scarcity_diagnosis(
    *,
    source_corpus_hash: str,
    candidate_density_artifact: Mapping[str, Any],
    source_character_counts: Mapping[str, int],
) -> StrictScarcityDiagnosisArtifact:
    if not isinstance(candidate_density_artifact, Mapping):
        raise TypeError("candidate_density_artifact must be a mapping")
    require_sha256("source_corpus_hash", source_corpus_hash)
    candidate_hash = candidate_density_artifact.get("artifact_hash")
    if not isinstance(candidate_hash, str):
        raise ValueError("candidate-density artifact is missing artifact_hash")
    require_sha256("candidate_density_artifact_hash", candidate_hash)
    raw_rows = candidate_density_artifact.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("candidate-density artifact rows must be a list")
    rows: list[StrictScarcityDiagnosisRow] = []
    seen: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("candidate-density rows must be mappings")
        sample_id = raw.get("source_sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError("candidate-density row is missing source_sample_id")
        if sample_id in seen:
            raise ValueError("candidate-density source IDs must be unique")
        seen.add(sample_id)
        if sample_id not in source_character_counts:
            raise ValueError(f"missing source character count for {sample_id}")
        b4 = raw.get("strict_b4_reachable")
        b6 = raw.get("strict_b6_reachable")
        if type(b4) is not bool or type(b6) is not bool:
            raise ValueError("candidate-density reachability values must be bool")
        rows.append(
            StrictScarcityDiagnosisRow.create(
                source_sample_id=sample_id,
                source_character_count=source_character_counts[sample_id],
                observed_b4_reachable=b4,
                observed_b6_reachable=b6,
            )
        )
    if set(source_character_counts) != seen:
        raise ValueError("source character-count IDs must exactly match candidate-density rows")
    normalized = tuple(sorted(rows, key=lambda row: row.source_sample_id))
    decision = classify_strict_scarcity(normalized)
    permitted = decision in {
        GENUINE_STRICT_B4_CANDIDATE_SCARCITY,
        GENUINE_STRICT_B6_CANDIDATE_SCARCITY,
    }
    payload = {
        "algorithm_version": STRICT_SCARCITY_DIAGNOSIS_VERSION,
        "source_corpus_hash": source_corpus_hash,
        "source_candidate_density_artifact_hash": candidate_hash,
        "strict_character_edit_rate_max": STRICT_CHARACTER_EDIT_RATE_MAX,
        "minimum_visible_character_edits_per_operation": MINIMUM_VISIBLE_CHARACTER_EDITS_PER_OPERATION,
        "row_hashes": tuple(row.row_hash for row in normalized),
        "decision": decision,
        "family_expansion_permitted": permitted,
    }
    return StrictScarcityDiagnosisArtifact(
        source_corpus_hash=source_corpus_hash,
        source_candidate_density_artifact_hash=candidate_hash,
        rows=normalized,
        decision=decision,
        family_expansion_permitted=permitted,
        artifact_hash=sha256_json(payload),
    )
