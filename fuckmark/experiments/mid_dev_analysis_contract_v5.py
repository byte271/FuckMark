from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev_analysis import MID_DEV_FROZEN_PRIMARY_CELLS, MID_DEV_FROZEN_PRIMARY_CELLS_HASH
from .mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES
from .mid_dev_pre_run_lock import (
    PRE_RUN_BOOTSTRAP_REPLICATES,
    PRE_RUN_BOOTSTRAP_SEED_BASE,
    PRE_RUN_MULTIPLICITY_RULE,
    PRE_RUN_NORMALIZED_PRIMARY_CELLS,
)


MID_DEV_V5_ANALYSIS_CONTRACT_VERSION = "mid-dev-v5-analysis-contract-v1"
MID_DEV_V5_INDEPENDENT_UNIT = "SOURCE_GROUP"
MID_DEV_V5_PLANNED_SOURCE_GROUP_COUNT = 36
MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS = 32
MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES = 8
MID_DEV_V5_ALLOW_CONFIRMATORY_P_VALUES = False
MID_DEV_V5_MATCHED_COMPARISONS = (
    "MATCHED_BEAM_V2_STRICT_VS_RANDOM_SAFE",
    "MATCHED_BEAM_V2_RELAXED_VS_RANDOM_SAFE",
)


def legacy_primary_cell_ids() -> tuple[str, ...]:
    return tuple(
        f"{condition.value}_B{budget}"
        for condition, budget in MID_DEV_FROZEN_PRIMARY_CELLS
    )


def validate_usable_random_replicates(count: int) -> None:
    require_int("usable_random_replicate_count", count)
    if count < MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES:
        raise ValueError("source-level matched comparison requires at least eight usable random replicates")
    if count > MID_DEV_RANDOM_REPLICATES:
        raise ValueError("usable random replicate count exceeds the frozen 16-replicate design")


def source_level_bootstrap_mean(
    source_group_values: Sequence[float],
    *,
    seed: int,
    replicates: int = PRE_RUN_BOOTSTRAP_REPLICATES,
) -> tuple[float, float, float]:
    require_int("seed", seed)
    require_int("replicates", replicates)
    if seed < 0 or replicates != PRE_RUN_BOOTSTRAP_REPLICATES:
        raise ValueError("source-level bootstrap must use the frozen seed domain and 10,000 replicates")
    values = tuple(float(value) for value in source_group_values)
    if len(values) < MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS:
        raise ValueError("source-level bootstrap requires at least 32 eligible source groups")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("source-level bootstrap values must be finite")
    rng = random.Random(seed)
    count = len(values)
    draws = []
    for _ in range(replicates):
        draws.append(sum(values[rng.randrange(count)] for _ in range(count)) / count)
    draws.sort()
    lower_index = max(0, math.floor(0.025 * (replicates - 1)))
    upper_index = min(replicates - 1, math.ceil(0.975 * (replicates - 1)))
    return sum(values) / count, draws[lower_index], draws[upper_index]


@dataclass(frozen=True, slots=True)
class MidDevV5AnalysisContract:
    independent_unit: str
    planned_source_group_count: int
    minimum_eligible_source_groups: int
    random_replicates_per_source: int
    minimum_usable_random_replicates: int
    bootstrap_replicates: int
    bootstrap_seed_base: int
    legacy_primary_cells_hash: str
    legacy_primary_cell_ids: tuple[str, ...]
    normalized_primary_cell_ids: tuple[str, ...]
    matched_comparison_ids: tuple[str, ...]
    multiplicity_rule: str
    allow_confirmatory_p_values: bool
    contract_hash: str

    def __post_init__(self) -> None:
        if self.independent_unit != MID_DEV_V5_INDEPENDENT_UNIT:
            raise ValueError("MidDev v5 independent unit must remain SOURCE_GROUP")
        for name, expected in (
            ("planned_source_group_count", MID_DEV_V5_PLANNED_SOURCE_GROUP_COUNT),
            ("minimum_eligible_source_groups", MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS),
            ("random_replicates_per_source", MID_DEV_RANDOM_REPLICATES),
            ("minimum_usable_random_replicates", MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES),
            ("bootstrap_replicates", PRE_RUN_BOOTSTRAP_REPLICATES),
            ("bootstrap_seed_base", PRE_RUN_BOOTSTRAP_SEED_BASE),
        ):
            require_int(name, getattr(self, name))
            if getattr(self, name) != expected:
                raise ValueError(f"{name} drifted from preregistration")
        require_sha256("legacy_primary_cells_hash", self.legacy_primary_cells_hash)
        if self.legacy_primary_cells_hash != MID_DEV_FROZEN_PRIMARY_CELLS_HASH:
            raise ValueError("legacy primary-cell registry drifted")
        if self.legacy_primary_cell_ids != legacy_primary_cell_ids():
            raise ValueError("all six legacy primary cells must always be reported")
        if self.normalized_primary_cell_ids != PRE_RUN_NORMALIZED_PRIMARY_CELLS:
            raise ValueError("all four normalized primary cells must always be reported")
        if self.matched_comparison_ids != MID_DEV_V5_MATCHED_COMPARISONS:
            raise ValueError("matched comparison registry drifted")
        if self.multiplicity_rule != PRE_RUN_MULTIPLICITY_RULE:
            raise ValueError("development multiplicity rule drifted")
        if self.allow_confirmatory_p_values is not MID_DEV_V5_ALLOW_CONFIRMATORY_P_VALUES:
            raise ValueError("development analysis cannot enable confirmatory p-values")
        require_sha256("contract_hash", self.contract_hash)
        if self.contract_hash != sha256_json(self.payload()):
            raise ValueError("analysis contract hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_ANALYSIS_CONTRACT_VERSION,
            "independent_unit": self.independent_unit,
            "planned_source_group_count": self.planned_source_group_count,
            "minimum_eligible_source_groups": self.minimum_eligible_source_groups,
            "random_replicates_per_source": self.random_replicates_per_source,
            "minimum_usable_random_replicates": self.minimum_usable_random_replicates,
            "bootstrap_replicates": self.bootstrap_replicates,
            "bootstrap_seed_base": self.bootstrap_seed_base,
            "legacy_primary_cells_hash": self.legacy_primary_cells_hash,
            "legacy_primary_cell_ids": self.legacy_primary_cell_ids,
            "normalized_primary_cell_ids": self.normalized_primary_cell_ids,
            "matched_comparison_ids": self.matched_comparison_ids,
            "multiplicity_rule": self.multiplicity_rule,
            "allow_confirmatory_p_values": self.allow_confirmatory_p_values,
        }


def create_mid_dev_v5_analysis_contract() -> MidDevV5AnalysisContract:
    values = {
        "independent_unit": MID_DEV_V5_INDEPENDENT_UNIT,
        "planned_source_group_count": MID_DEV_V5_PLANNED_SOURCE_GROUP_COUNT,
        "minimum_eligible_source_groups": MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS,
        "random_replicates_per_source": MID_DEV_RANDOM_REPLICATES,
        "minimum_usable_random_replicates": MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES,
        "bootstrap_replicates": PRE_RUN_BOOTSTRAP_REPLICATES,
        "bootstrap_seed_base": PRE_RUN_BOOTSTRAP_SEED_BASE,
        "legacy_primary_cells_hash": MID_DEV_FROZEN_PRIMARY_CELLS_HASH,
        "legacy_primary_cell_ids": legacy_primary_cell_ids(),
        "normalized_primary_cell_ids": PRE_RUN_NORMALIZED_PRIMARY_CELLS,
        "matched_comparison_ids": MID_DEV_V5_MATCHED_COMPARISONS,
        "multiplicity_rule": PRE_RUN_MULTIPLICITY_RULE,
        "allow_confirmatory_p_values": MID_DEV_V5_ALLOW_CONFIRMATORY_P_VALUES,
    }
    payload = {"algorithm_version": MID_DEV_V5_ANALYSIS_CONTRACT_VERSION, **values}
    return MidDevV5AnalysisContract(**values, contract_hash=sha256_json(payload))


FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT = create_mid_dev_v5_analysis_contract()
