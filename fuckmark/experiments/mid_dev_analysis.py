from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus.mid_dev import MidDevAttackArtifact
from ..hashing import sha256_json
from .mid_dev_ecs1_safe import MidDevECS1RawArtifact, build_ecs1_raw_artifact
from .mid_dev_primary_inference_safe import (
    MidDevPrimaryInferenceResult,
    _source_contrast,
    primary_realized_cost_inference,
)
from .mid_dev_scored_schema import MidDevScoringArtifact
from .mid_dev_scoring_contracts import MidDevCondition, MidDevFrozenPlanView


MID_DEV_ANALYSIS_VERSION = "mid-dev-analysis-v2"
MID_DEV_PRIMARY_INELIGIBLE_VERSION = "mid-dev-primary-ineligible-v1"
MID_DEV_FROZEN_PRIMARY_CELLS = (
    (MidDevCondition.CONTEXT_SURVIVAL_GREEDY, 1),
    (MidDevCondition.CONTEXT_SURVIVAL_GREEDY, 2),
    (MidDevCondition.CONTEXT_SURVIVAL_GREEDY, 4),
    (MidDevCondition.CONTEXT_SURVIVAL_GREEDY, 6),
    (MidDevCondition.CONTEXT_SURVIVAL_BEAM, 4),
    (MidDevCondition.CONTEXT_SURVIVAL_BEAM, 6),
)
MID_DEV_FROZEN_PRIMARY_CELLS_HASH = sha256_json(
    tuple((condition.value, budget) for condition, budget in MID_DEV_FROZEN_PRIMARY_CELLS)
)


@dataclass(frozen=True, slots=True)
class MidDevPrimaryIneligibleCell:
    deterministic_condition: MidDevCondition
    budget: int
    planned_source_group_count: int
    eligible_source_group_count: int
    excluded_source_group_ids: tuple[str, ...]
    reason_code: str
    cell_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.deterministic_condition, MidDevCondition):
            raise TypeError("deterministic_condition must be MidDevCondition")
        require_int("budget", self.budget)
        require_int("planned_source_group_count", self.planned_source_group_count)
        require_int("eligible_source_group_count", self.eligible_source_group_count)
        if self.planned_source_group_count != 36:
            raise ValueError("MidDev ineligible cell must start from 36 planned source groups")
        if not 0 <= self.eligible_source_group_count < 32:
            raise ValueError("MidDev ineligible cell must contain fewer than 32 eligible source groups")
        if len(self.excluded_source_group_ids) != 36 - self.eligible_source_group_count:
            raise ValueError("MidDev ineligible cell source partition is inconsistent")
        if len(set(self.excluded_source_group_ids)) != len(self.excluded_source_group_ids):
            raise ValueError("MidDev ineligible cell excluded source IDs must be unique")
        if self.reason_code != "INSUFFICIENT_REALIZED_COST_MATCHED_SOURCES":
            raise ValueError("unsupported MidDev primary ineligible reason")
        require_sha256("cell_hash", self.cell_hash)
        if self.cell_hash != sha256_json(self.payload()):
            raise ValueError("cell_hash does not match MidDev ineligible cell")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_PRIMARY_INELIGIBLE_VERSION,
            "deterministic_condition": self.deterministic_condition.value,
            "budget": self.budget,
            "planned_source_group_count": self.planned_source_group_count,
            "eligible_source_group_count": self.eligible_source_group_count,
            "excluded_source_group_ids": self.excluded_source_group_ids,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class MidDevAnalysisArtifact:
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    plan_hash: str
    scoring_artifact_hash: str
    detector_identity_hash: str
    length_calibration_registry_hash: str
    frozen_primary_cells_hash: str
    primary_results: tuple[MidDevPrimaryInferenceResult, ...]
    ineligible_primary_cells: tuple[MidDevPrimaryIneligibleCell, ...]
    ecs1_raw_artifact_hash: str
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "plan_hash",
            "scoring_artifact_hash",
            "detector_identity_hash",
            "length_calibration_registry_hash",
            "frozen_primary_cells_hash",
            "ecs1_raw_artifact_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.frozen_primary_cells_hash != MID_DEV_FROZEN_PRIMARY_CELLS_HASH:
            raise ValueError("MidDev frozen primary cell registry drifted")
        cells = {
            (value.deterministic_condition, value.budget)
            for value in self.primary_results
        } | {
            (value.deterministic_condition, value.budget)
            for value in self.ineligible_primary_cells
        }
        if cells != set(MID_DEV_FROZEN_PRIMARY_CELLS):
            raise ValueError("MidDev analysis must report every frozen primary cell exactly once")
        if len(self.primary_results) + len(self.ineligible_primary_cells) != len(MID_DEV_FROZEN_PRIMARY_CELLS):
            raise ValueError("MidDev analysis primary cell outputs contain duplicates")
        if any(value.detector_identity_hash != self.detector_identity_hash for value in self.primary_results):
            raise ValueError("MidDev primary results mixed detector identities")
        if any(value.threshold_registry_hash != self.length_calibration_registry_hash for value in self.primary_results):
            raise ValueError("MidDev primary results do not bind the scoring length calibration registry")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match MidDev analysis artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_ANALYSIS_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "plan_hash": self.plan_hash,
            "scoring_artifact_hash": self.scoring_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "length_calibration_registry_hash": self.length_calibration_registry_hash,
            "frozen_primary_cells_hash": self.frozen_primary_cells_hash,
            "primary_result_hashes": tuple(value.result_hash for value in self.primary_results),
            "ineligible_primary_cell_hashes": tuple(
                value.cell_hash for value in self.ineligible_primary_cells
            ),
            "ecs1_raw_artifact_hash": self.ecs1_raw_artifact_hash,
        }


def _cell_contrasts(scoring: MidDevScoringArtifact, condition: MidDevCondition, budget: int):
    relevant = tuple(
        row
        for row in scoring.rows
        if row.budget == budget
        and row.condition in {condition, MidDevCondition.RANDOM_SAFE}
    )
    grouped: dict[str, list] = {}
    for row in relevant:
        grouped.setdefault(row.source_group_id, []).append(row)
    if len(grouped) != 36:
        raise ValueError("MidDev analysis requires all 36 source groups in every frozen primary cell")
    contrasts = []
    excluded = []
    for source_group_id in sorted(grouped):
        contrast = _source_contrast(
            source_group_id,
            grouped[source_group_id],
            deterministic_condition=condition,
            budget=budget,
        )
        if contrast is None:
            excluded.append(source_group_id)
        else:
            contrasts.append(contrast)
    return tuple(contrasts), tuple(excluded)


def build_mid_dev_analysis_artifact(
    corpus: MidDevAttackArtifact,
    plan: MidDevFrozenPlanView,
    scoring: MidDevScoringArtifact,
    *,
    bootstrap_replicates: int = 10_000,
    bootstrap_seed_base: int = 0x4D494444455641,
) -> tuple[MidDevAnalysisArtifact, MidDevECS1RawArtifact]:
    require_int("bootstrap_replicates", bootstrap_replicates)
    require_int("bootstrap_seed_base", bootstrap_seed_base)
    if bootstrap_replicates <= 0 or bootstrap_seed_base < 0:
        raise ValueError("invalid MidDev analysis bootstrap configuration")
    if plan.corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("MidDev analysis plan does not bind the supplied corpus")
    if scoring.mid_dev_corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("MidDev analysis scoring artifact does not bind the supplied corpus")
    if scoring.plan_hash != plan.plan_hash:
        raise ValueError("MidDev analysis scoring artifact does not bind the supplied plan")
    ecs1 = build_ecs1_raw_artifact(corpus, plan, scoring)
    results = []
    ineligible = []
    for cell_index, (condition, budget) in enumerate(MID_DEV_FROZEN_PRIMARY_CELLS):
        contrasts, excluded = _cell_contrasts(scoring, condition, budget)
        if len(contrasts) >= 32:
            results.append(
                primary_realized_cost_inference(
                    scoring.rows,
                    deterministic_condition=condition,
                    budget=budget,
                    bootstrap_replicates=bootstrap_replicates,
                    bootstrap_seed=bootstrap_seed_base + cell_index,
                )
            )
        else:
            payload = {
                "algorithm_version": MID_DEV_PRIMARY_INELIGIBLE_VERSION,
                "deterministic_condition": condition.value,
                "budget": budget,
                "planned_source_group_count": 36,
                "eligible_source_group_count": len(contrasts),
                "excluded_source_group_ids": excluded,
                "reason_code": "INSUFFICIENT_REALIZED_COST_MATCHED_SOURCES",
            }
            ineligible.append(
                MidDevPrimaryIneligibleCell(
                    condition,
                    budget,
                    36,
                    len(contrasts),
                    excluded,
                    "INSUFFICIENT_REALIZED_COST_MATCHED_SOURCES",
                    sha256_json(payload),
                )
            )
    result_tuple = tuple(results)
    ineligible_tuple = tuple(ineligible)
    payload = {
        "algorithm_version": MID_DEV_ANALYSIS_VERSION,
        "corpus_artifact_hash": corpus.artifact_hash,
        "source_profile_hash": corpus.source_profile_hash,
        "analysis_split_hash": corpus.analysis_split_hash,
        "plan_hash": plan.plan_hash,
        "scoring_artifact_hash": scoring.artifact_hash,
        "detector_identity_hash": scoring.detector_identity_hash,
        "length_calibration_registry_hash": scoring.length_calibration_registry_hash,
        "frozen_primary_cells_hash": MID_DEV_FROZEN_PRIMARY_CELLS_HASH,
        "primary_result_hashes": tuple(value.result_hash for value in result_tuple),
        "ineligible_primary_cell_hashes": tuple(value.cell_hash for value in ineligible_tuple),
        "ecs1_raw_artifact_hash": ecs1.artifact_hash,
    }
    return (
        MidDevAnalysisArtifact(
            corpus.artifact_hash,
            corpus.source_profile_hash,
            corpus.analysis_split_hash,
            plan.plan_hash,
            scoring.artifact_hash,
            scoring.detector_identity_hash,
            scoring.length_calibration_registry_hash,
            MID_DEV_FROZEN_PRIMARY_CELLS_HASH,
            result_tuple,
            ineligible_tuple,
            ecs1.artifact_hash,
            sha256_json(payload),
        ),
        ecs1,
    )
