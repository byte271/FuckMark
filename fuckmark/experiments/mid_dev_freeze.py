from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev_context_survival import (
    MID_DEV_PLAN_ALGORITHM_VERSION,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
)


MID_DEV_DETERMINISTIC_COMPUTE_VERSION = "mid-dev-deterministic-compute-v1"
MID_DEV_DETERMINISTIC_PLAN_VERSION = "mid-dev-context-survival-plan-v3"
MID_DEV_RUNTIME_TIMING_VERSION = "mid-dev-runtime-timing-v1"


@dataclass(frozen=True, slots=True)
class MidDevDeterministicComputeRow:
    plan_row_hash: str
    expanded_state_count: int
    pruned_state_count: int
    candidate_evaluation_count: int
    expansion_cache_hit_count: int
    expansion_cache_miss_count: int
    geometry_cache_hit_count: int
    selection_detector_query_count: int
    selection_secret_query_count: int
    compute_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_row_hash", self.plan_row_hash)
        for name in (
            "expanded_state_count",
            "pruned_state_count",
            "candidate_evaluation_count",
            "expansion_cache_hit_count",
            "expansion_cache_miss_count",
            "geometry_cache_hit_count",
            "selection_detector_query_count",
            "selection_secret_query_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.selection_detector_query_count or self.selection_secret_query_count:
            raise ValueError("frozen MidDev compute row recorded detector or secret queries")
        require_sha256("compute_hash", self.compute_hash)
        if self.compute_hash != sha256_json(self.payload()):
            raise ValueError("compute_hash does not match deterministic compute payload")

    @classmethod
    def create(
        cls,
        *,
        plan_row_hash: str,
        expanded_state_count: int,
        pruned_state_count: int,
        candidate_evaluation_count: int,
        expansion_cache_hit_count: int,
        expansion_cache_miss_count: int,
        geometry_cache_hit_count: int,
        selection_detector_query_count: int = 0,
        selection_secret_query_count: int = 0,
    ) -> "MidDevDeterministicComputeRow":
        payload = {
            "algorithm_version": MID_DEV_DETERMINISTIC_COMPUTE_VERSION,
            "plan_row_hash": plan_row_hash,
            "expanded_state_count": expanded_state_count,
            "pruned_state_count": pruned_state_count,
            "candidate_evaluation_count": candidate_evaluation_count,
            "expansion_cache_hit_count": expansion_cache_hit_count,
            "expansion_cache_miss_count": expansion_cache_miss_count,
            "geometry_cache_hit_count": geometry_cache_hit_count,
            "selection_detector_query_count": selection_detector_query_count,
            "selection_secret_query_count": selection_secret_query_count,
        }
        return cls(
            plan_row_hash,
            expanded_state_count,
            pruned_state_count,
            candidate_evaluation_count,
            expansion_cache_hit_count,
            expansion_cache_miss_count,
            geometry_cache_hit_count,
            selection_detector_query_count,
            selection_secret_query_count,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_DETERMINISTIC_COMPUTE_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "candidate_evaluation_count": self.candidate_evaluation_count,
            "expansion_cache_hit_count": self.expansion_cache_hit_count,
            "expansion_cache_miss_count": self.expansion_cache_miss_count,
            "geometry_cache_hit_count": self.geometry_cache_hit_count,
            "selection_detector_query_count": self.selection_detector_query_count,
            "selection_secret_query_count": self.selection_secret_query_count,
        }


@dataclass(frozen=True, slots=True)
class MidDevRuntimeTimingRow:
    plan_row_hash: str
    planning_wall_time_ms: float
    timing_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_row_hash", self.plan_row_hash)
        if isinstance(self.planning_wall_time_ms, bool) or not isinstance(
            self.planning_wall_time_ms, (int, float)
        ):
            raise ValueError("planning_wall_time_ms must be numeric")
        if not math.isfinite(float(self.planning_wall_time_ms)) or self.planning_wall_time_ms < 0:
            raise ValueError("planning_wall_time_ms must be finite and non-negative")
        require_sha256("timing_hash", self.timing_hash)
        if self.timing_hash != sha256_json(self.payload()):
            raise ValueError("timing_hash does not match runtime timing payload")

    @classmethod
    def create(
        cls,
        *,
        plan_row_hash: str,
        planning_wall_time_ms: float,
    ) -> "MidDevRuntimeTimingRow":
        payload = {
            "algorithm_version": MID_DEV_RUNTIME_TIMING_VERSION,
            "plan_row_hash": plan_row_hash,
            "planning_wall_time_ms": float(planning_wall_time_ms),
        }
        return cls(
            plan_row_hash,
            float(planning_wall_time_ms),
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_RUNTIME_TIMING_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "planning_wall_time_ms": self.planning_wall_time_ms,
        }


@dataclass(frozen=True, slots=True)
class MidDevDeterministicFrozenPlan:
    algorithm_version: str
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    source_code_commit: str
    selection_config: MidDevSelectionConfig
    selection_attestation: MidDevSelectionAttestation
    rows: tuple[MidDevPlanRow, ...]
    quality_rows: tuple[MidDevQualityRow, ...]
    compute_rows: tuple[MidDevDeterministicComputeRow, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_DETERMINISTIC_PLAN_VERSION:
            raise ValueError("unsupported deterministic MidDev plan version")
        for name in (
            "corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "plan_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.source_code_commit, str) or not self.source_code_commit:
            raise ValueError("source_code_commit must be non-empty")
        if not isinstance(self.selection_config, MidDevSelectionConfig):
            raise TypeError("selection_config must be MidDevSelectionConfig")
        if not isinstance(self.selection_attestation, MidDevSelectionAttestation):
            raise TypeError("selection_attestation must be MidDevSelectionAttestation")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("rows must be a non-empty tuple")
        if any(not isinstance(value, MidDevPlanRow) for value in self.rows):
            raise TypeError("rows must contain MidDevPlanRow values")
        if any(not isinstance(value, MidDevQualityRow) for value in self.quality_rows):
            raise TypeError("quality_rows must contain MidDevQualityRow values")
        if any(not isinstance(value, MidDevDeterministicComputeRow) for value in self.compute_rows):
            raise TypeError("compute_rows must contain deterministic compute rows")
        row_hashes = tuple(value.plan_row_hash for value in self.rows)
        if len(set(row_hashes)) != len(row_hashes):
            raise ValueError("deterministic MidDev plan rows must be unique")
        if {value.plan_row_hash for value in self.quality_rows} != set(row_hashes):
            raise ValueError("quality rows must bind the complete frozen row set")
        if {value.plan_row_hash for value in self.compute_rows} != set(row_hashes):
            raise ValueError("compute rows must bind the complete frozen row set")
        if len(self.quality_rows) != len(self.rows) or len(self.compute_rows) != len(self.rows):
            raise ValueError("frozen sidecars must bind each row exactly once")
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match deterministic MidDev plan payload")

    @classmethod
    def create(
        cls,
        *,
        corpus_artifact_hash: str,
        source_profile_hash: str,
        analysis_split_hash: str,
        source_code_commit: str,
        selection_config: MidDevSelectionConfig,
        selection_attestation: MidDevSelectionAttestation,
        rows: Sequence[MidDevPlanRow],
        quality_rows: Sequence[MidDevQualityRow],
        compute_rows: Sequence[MidDevDeterministicComputeRow],
    ) -> "MidDevDeterministicFrozenPlan":
        materialized = tuple(
            sorted(
                rows,
                key=lambda value: (
                    value.source_group_id,
                    value.sample_id,
                    value.condition.value,
                    value.budget,
                    value.replicate,
                ),
            )
        )
        quality = tuple(sorted(quality_rows, key=lambda value: value.plan_row_hash))
        compute = tuple(sorted(compute_rows, key=lambda value: value.plan_row_hash))
        payload = {
            "algorithm_version": MID_DEV_DETERMINISTIC_PLAN_VERSION,
            "legacy_foundation_version": MID_DEV_PLAN_ALGORITHM_VERSION,
            "corpus_artifact_hash": corpus_artifact_hash,
            "source_profile_hash": source_profile_hash,
            "analysis_split_hash": analysis_split_hash,
            "source_code_commit": source_code_commit,
            "selection_config_hash": selection_config.config_hash,
            "selection_attestation_hash": selection_attestation.attestation_hash,
            "row_hashes": tuple(value.plan_row_hash for value in materialized),
            "quality_hashes": tuple(value.quality_hash for value in quality),
            "compute_hashes": tuple(value.compute_hash for value in compute),
        }
        return cls(
            MID_DEV_DETERMINISTIC_PLAN_VERSION,
            corpus_artifact_hash,
            source_profile_hash,
            analysis_split_hash,
            source_code_commit,
            selection_config,
            selection_attestation,
            materialized,
            quality,
            compute,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "legacy_foundation_version": MID_DEV_PLAN_ALGORITHM_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "source_code_commit": self.source_code_commit,
            "selection_config_hash": self.selection_config.config_hash,
            "selection_attestation_hash": self.selection_attestation.attestation_hash,
            "row_hashes": tuple(value.plan_row_hash for value in self.rows),
            "quality_hashes": tuple(value.quality_hash for value in self.quality_rows),
            "compute_hashes": tuple(value.compute_hash for value in self.compute_rows),
        }
