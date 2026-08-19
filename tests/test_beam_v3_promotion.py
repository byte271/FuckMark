from __future__ import annotations

import pytest

from fuckmark.search.beam_v3_promotion import (
    BEAM_V3_GATE_ARTIFACT_HASH,
    BEAM_V3_GATE_ARTIFACT_ID,
    BEAM_V3_GATE_B4_ROW_COUNT,
    BEAM_V3_GATE_B4_STRICT_GAIN_COUNT,
    BEAM_V3_GATE_B6_ROW_COUNT,
    BEAM_V3_GATE_B6_STRICT_GAIN_COUNT,
    BEAM_V3_GATE_DECISION,
    BEAM_V3_GATE_ROW_COUNT,
    BEAM_V3_GATE_RUN_ID,
    BEAM_V3_PROMOTED,
    CANONICAL_CONTEXT_SURVIVAL_ALGORITHM_VERSION,
    FROZEN_BEAM_V3_PROMOTION_LOCK,
    require_promoted_beam_v3,
)
from fuckmark.scheduling.algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


def test_frozen_k2_lock_preserves_beam_v2_as_canonical() -> None:
    lock = FROZEN_BEAM_V3_PROMOTION_LOCK
    assert lock.gate_decision == BEAM_V3_GATE_DECISION == "K2_V3_SEARCH_HAS_NO_MATCHED_COST_GAIN"
    assert lock.promoted is BEAM_V3_PROMOTED is False
    assert lock.canonical_algorithm_version == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
    assert CANONICAL_CONTEXT_SURVIVAL_ALGORITHM_VERSION == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


def test_frozen_k2_lock_binds_exact_gate_provenance_and_counts() -> None:
    lock = FROZEN_BEAM_V3_PROMOTION_LOCK
    assert lock.gate_artifact_hash == BEAM_V3_GATE_ARTIFACT_HASH == "a0d164669c84528255ed336d6969c5d0f1492ebaab99700172ede287e94dc0f7"
    assert lock.gate_run_id == BEAM_V3_GATE_RUN_ID == 32289266065
    assert lock.gate_artifact_id == BEAM_V3_GATE_ARTIFACT_ID == 9379795114
    assert lock.gate_row_count == BEAM_V3_GATE_ROW_COUNT == 16
    assert (lock.b4_strict_gain_count, lock.b4_row_count) == (
        BEAM_V3_GATE_B4_STRICT_GAIN_COUNT,
        BEAM_V3_GATE_B4_ROW_COUNT,
    ) == (1, 8)
    assert (lock.b6_strict_gain_count, lock.b6_row_count) == (
        BEAM_V3_GATE_B6_STRICT_GAIN_COUNT,
        BEAM_V3_GATE_B6_ROW_COUNT,
    ) == (2, 8)


def test_require_promoted_beam_v3_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="Beam v3 is not promoted"):
        require_promoted_beam_v3()
