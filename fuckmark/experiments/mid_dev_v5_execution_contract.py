from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from ..scheduling.beam_v2 import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from ..search.beam_v3_promotion import FROZEN_BEAM_V3_PROMOTION_LOCK
from ..search.visible_cost_budget import VisibleCostTier
from .mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES
from .mid_dev_plan_v5 import (
    MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION,
    MidDevDevelopmentPlanV5,
    MidDevNormalizedPlanner,
)
from .mid_dev_v5_builder import (
    MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
    MidDevNormalizedTraceArtifact,
)


MID_DEV_V5_EXECUTION_CONTRACT_VERSION = "mid-dev-v5-execution-contract-v1"
MID_DEV_V5_LEGACY_ROW_COUNT = 5688
MID_DEV_V5_SOURCE_GROUP_COUNT = 36
MID_DEV_V5_SAMPLE_COUNT = 72
MID_DEV_V5_NORMALIZED_ROWS_PER_SAMPLE = 2 * (1 + MID_DEV_RANDOM_REPLICATES)
MID_DEV_V5_NORMALIZED_ROW_COUNT = MID_DEV_V5_SAMPLE_COUNT * MID_DEV_V5_NORMALIZED_ROWS_PER_SAMPLE


def expected_normalized_keys(sample_id: str) -> tuple[tuple[str, str, str, int], ...]:
    values: list[tuple[str, str, str, int]] = []
    for tier in (VisibleCostTier.STRICT, VisibleCostTier.RELAXED):
        values.append(
            (
                sample_id,
                MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2.value,
                tier.value,
                0,
            )
        )
        values.extend(
            (
                sample_id,
                MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST.value,
                tier.value,
                replicate,
            )
            for replicate in range(MID_DEV_RANDOM_REPLICATES)
        )
    return tuple(sorted(values))


@dataclass(frozen=True, slots=True)
class MidDevV5ExecutionAttestation:
    development_plan_hash: str
    normalized_trace_artifact_hash: str
    required_cell_registry_hash: str
    legacy_row_count: int
    normalized_row_count: int
    source_group_count: int
    sample_count: int
    candidate_registry_hash: str
    beam_v3_promoted: bool
    detector_access_observed: bool
    secret_access_observed: bool
    attestation_hash: str

    def __post_init__(self) -> None:
        for name in (
            "development_plan_hash",
            "normalized_trace_artifact_hash",
            "required_cell_registry_hash",
            "candidate_registry_hash",
            "attestation_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.required_cell_registry_hash != MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH:
            raise ValueError("required v5 development cell registry drifted")
        for name, expected in (
            ("legacy_row_count", MID_DEV_V5_LEGACY_ROW_COUNT),
            ("normalized_row_count", MID_DEV_V5_NORMALIZED_ROW_COUNT),
            ("source_group_count", MID_DEV_V5_SOURCE_GROUP_COUNT),
            ("sample_count", MID_DEV_V5_SAMPLE_COUNT),
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value != expected:
                raise ValueError(f"{name} does not match frozen v5 execution contract")
        if self.beam_v3_promoted is not False:
            raise ValueError("Beam v3 must remain excluded after frozen K2")
        if type(self.detector_access_observed) is not bool or type(self.secret_access_observed) is not bool:
            raise TypeError("selection access flags must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("v5 planning execution attestation is contaminated")
        if self.attestation_hash != sha256_json(self.payload()):
            raise ValueError("v5 execution attestation hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_EXECUTION_CONTRACT_VERSION,
            "development_plan_hash": self.development_plan_hash,
            "normalized_trace_artifact_hash": self.normalized_trace_artifact_hash,
            "required_cell_registry_hash": self.required_cell_registry_hash,
            "legacy_row_count": self.legacy_row_count,
            "normalized_row_count": self.normalized_row_count,
            "source_group_count": self.source_group_count,
            "sample_count": self.sample_count,
            "candidate_registry_hash": self.candidate_registry_hash,
            "beam_v3_promoted": self.beam_v3_promoted,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def validate_mid_dev_v5_execution_contract(
    plan: MidDevDevelopmentPlanV5,
    traces: MidDevNormalizedTraceArtifact,
) -> MidDevV5ExecutionAttestation:
    if not isinstance(plan, MidDevDevelopmentPlanV5):
        raise TypeError("plan must be MidDevDevelopmentPlanV5")
    if not isinstance(traces, MidDevNormalizedTraceArtifact):
        raise TypeError("traces must be MidDevNormalizedTraceArtifact")
    if len(plan.legacy_plan.rows) != MID_DEV_V5_LEGACY_ROW_COUNT:
        raise ValueError("v5 execution requires the complete 5688-row legacy plan")
    if len(plan.normalized_rows) != MID_DEV_V5_NORMALIZED_ROW_COUNT:
        raise ValueError("v5 execution requires the complete 2448-row normalized plan")
    legacy_samples = {row.sample_id for row in plan.legacy_plan.rows}
    legacy_groups = {row.source_group_id for row in plan.legacy_plan.rows}
    if len(legacy_samples) != MID_DEV_V5_SAMPLE_COUNT or len(legacy_groups) != MID_DEV_V5_SOURCE_GROUP_COUNT:
        raise ValueError("v5 execution source matrix must contain 72 samples in 36 matched groups")
    if traces.development_plan_hash != plan.plan_hash:
        raise ValueError("normalized trace artifact does not bind development plan")
    if traces.required_cell_registry_hash != MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH:
        raise ValueError("normalized trace artifact cell registry drifted")
    row_by_key = {
        (row.sample_id, row.planner.value, row.tier.value, row.replicate): row
        for row in plan.normalized_rows
    }
    if len(row_by_key) != len(plan.normalized_rows):
        raise ValueError("normalized plan row keys are not unique")
    for sample_id in sorted(legacy_samples):
        expected = set(expected_normalized_keys(sample_id))
        actual = {key for key in row_by_key if key[0] == sample_id}
        if actual != expected:
            raise ValueError(f"normalized cell matrix is incomplete for {sample_id}")
    trace_by_key = {
        (trace.sample_id, trace.planner.value, trace.tier.value, trace.replicate): trace
        for trace in traces.traces
    }
    if set(trace_by_key) != set(row_by_key):
        raise ValueError("normalized plan/trace key matrices differ")
    if {trace.trace_hash for trace in traces.traces} != {row.selection_trace_hash for row in plan.normalized_rows}:
        raise ValueError("normalized plan/trace hashes do not bind exactly")
    registry_hashes = {row.candidate_registry_hash for row in plan.normalized_rows}
    if len(registry_hashes) != 1:
        raise ValueError("normalized plan mixed candidate rule registries")
    candidate_registry_hash = next(iter(registry_hashes))
    if {trace.candidate_registry_hash for trace in traces.traces} != {candidate_registry_hash}:
        raise ValueError("normalized traces do not bind the frozen candidate registry")
    for sample_id in sorted(legacy_samples):
        for tier in (VisibleCostTier.STRICT, VisibleCostTier.RELAXED):
            beam_key = (
                sample_id,
                MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2.value,
                tier.value,
                0,
            )
            beam_row = row_by_key[beam_key]
            beam_trace = trace_by_key[beam_key]
            if beam_row.selection_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
                raise ValueError("normalized deterministic row is not Beam v2")
            if beam_trace.reference_state_hash is not None or beam_trace.matched_cost_envelope_hash is not None:
                raise ValueError("Beam v2 trace unexpectedly carries matched-random reference")
            for replicate in range(MID_DEV_RANDOM_REPLICATES):
                random_key = (
                    sample_id,
                    MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST.value,
                    tier.value,
                    replicate,
                )
                random_row = row_by_key[random_key]
                random_trace = trace_by_key[random_key]
                if random_row.selection_algorithm_version != MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION:
                    raise ValueError("normalized random row algorithm version drifted")
                if random_trace.reference_state_hash != beam_row.final_search_state_hash:
                    raise ValueError("matched-cost random trace references the wrong Beam v2 state")
                if random_trace.matched_cost_envelope_hash is None:
                    raise ValueError("matched-cost random trace is missing its realized-cost envelope")
    prohibited = {
        row.selection_algorithm_version
        for row in plan.normalized_rows
        if "beam-v3" in row.selection_algorithm_version.lower()
    }
    if prohibited:
        raise ValueError("Beam v3 appeared in the frozen v5 execution matrix")
    detector_access = any(trace.detector_access_observed for trace in traces.traces)
    secret_access = any(trace.secret_access_observed for trace in traces.traces)
    payload = {
        "algorithm_version": MID_DEV_V5_EXECUTION_CONTRACT_VERSION,
        "development_plan_hash": plan.plan_hash,
        "normalized_trace_artifact_hash": traces.artifact_hash,
        "required_cell_registry_hash": MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
        "legacy_row_count": len(plan.legacy_plan.rows),
        "normalized_row_count": len(plan.normalized_rows),
        "source_group_count": len(legacy_groups),
        "sample_count": len(legacy_samples),
        "candidate_registry_hash": candidate_registry_hash,
        "beam_v3_promoted": FROZEN_BEAM_V3_PROMOTION_LOCK.promoted,
        "detector_access_observed": detector_access,
        "secret_access_observed": secret_access,
    }
    return MidDevV5ExecutionAttestation(
        development_plan_hash=plan.plan_hash,
        normalized_trace_artifact_hash=traces.artifact_hash,
        required_cell_registry_hash=MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
        legacy_row_count=len(plan.legacy_plan.rows),
        normalized_row_count=len(plan.normalized_rows),
        source_group_count=len(legacy_groups),
        sample_count=len(legacy_samples),
        candidate_registry_hash=candidate_registry_hash,
        beam_v3_promoted=FROZEN_BEAM_V3_PROMOTION_LOCK.promoted,
        detector_access_observed=detector_access,
        secret_access_observed=secret_access,
        attestation_hash=sha256_json(payload),
    )
