from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..scheduling.algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from .beam_v3 import CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION


BEAM_V3_PROMOTION_LOCK_VERSION = "beam-v3-promotion-lock-v1"
BEAM_V3_GATE_DECISION = "K2_V3_SEARCH_HAS_NO_MATCHED_COST_GAIN"
BEAM_V3_GATE_ARTIFACT_HASH = "a0d164669c84528255ed336d6969c5d0f1492ebaab99700172ede287e94dc0f7"
BEAM_V3_GATE_ARTIFACT_ZIP_SHA256 = "e74412d9b4497a7b4e3473c368cdc9f960f1422c2221ca8225e40c2912dceb38"
BEAM_V3_GATE_RUN_ID = 32289266065
BEAM_V3_GATE_ARTIFACT_ID = 9379795114
BEAM_V3_GATE_ROW_COUNT = 16
BEAM_V3_GATE_B4_STRICT_GAIN_COUNT = 1
BEAM_V3_GATE_B6_STRICT_GAIN_COUNT = 2
BEAM_V3_GATE_B4_ROW_COUNT = 8
BEAM_V3_GATE_B6_ROW_COUNT = 8
BEAM_V3_EVALUATED_MAIN_COMMIT = "1740cbca1d5e633d8a6ea40b509ce900cb89f127"
BEAM_V3_VALIDATION_MERGE_COMMIT = "cefc08624bec1dcb8bd51706ecc9e4d5b5e40bfb"
BEAM_V3_PROMOTED = False
CANONICAL_CONTEXT_SURVIVAL_ALGORITHM_VERSION = CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


@dataclass(frozen=True, slots=True)
class BeamV3PromotionLock:
    lock_version: str
    v3_algorithm_version: str
    gate_decision: str
    gate_artifact_hash: str
    gate_artifact_zip_sha256: str
    gate_run_id: int
    gate_artifact_id: int
    gate_row_count: int
    b4_strict_gain_count: int
    b4_row_count: int
    b6_strict_gain_count: int
    b6_row_count: int
    evaluated_main_commit: str
    validation_merge_commit: str
    promoted: bool
    canonical_algorithm_version: str
    lock_hash: str

    def __post_init__(self) -> None:
        if self.lock_version != BEAM_V3_PROMOTION_LOCK_VERSION:
            raise ValueError("unsupported Beam v3 promotion lock version")
        if self.v3_algorithm_version != CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION:
            raise ValueError("Beam v3 algorithm identity drifted")
        require_clean_string("gate_decision", self.gate_decision)
        if self.gate_decision != BEAM_V3_GATE_DECISION:
            raise ValueError("Beam v3 gate decision drifted")
        require_sha256("gate_artifact_hash", self.gate_artifact_hash)
        require_sha256("gate_artifact_zip_sha256", self.gate_artifact_zip_sha256)
        for name in (
            "gate_run_id",
            "gate_artifact_id",
            "gate_row_count",
            "b4_strict_gain_count",
            "b4_row_count",
            "b6_strict_gain_count",
            "b6_row_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.gate_row_count != self.b4_row_count + self.b6_row_count:
            raise ValueError("gate row accounting is inconsistent")
        if self.b4_strict_gain_count > self.b4_row_count:
            raise ValueError("B4 strict gain count exceeds B4 rows")
        if self.b6_strict_gain_count > self.b6_row_count:
            raise ValueError("B6 strict gain count exceeds B6 rows")
        for name in ("evaluated_main_commit", "validation_merge_commit"):
            value = getattr(self, name)
            require_clean_string(name, value)
            if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{name} must be a lowercase 40-hex Git SHA")
        if type(self.promoted) is not bool:
            raise TypeError("promoted must be bool")
        if self.promoted:
            raise ValueError("Beam v3 cannot be promoted under the frozen K2 result")
        if self.canonical_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
            raise ValueError("Beam v2 must remain canonical after K2")
        require_sha256("lock_hash", self.lock_hash)
        if self.lock_hash != sha256_json(self.payload()):
            raise ValueError("Beam v3 promotion lock hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "lock_version": self.lock_version,
            "v3_algorithm_version": self.v3_algorithm_version,
            "gate_decision": self.gate_decision,
            "gate_artifact_hash": self.gate_artifact_hash,
            "gate_artifact_zip_sha256": self.gate_artifact_zip_sha256,
            "gate_run_id": self.gate_run_id,
            "gate_artifact_id": self.gate_artifact_id,
            "gate_row_count": self.gate_row_count,
            "b4_strict_gain_count": self.b4_strict_gain_count,
            "b4_row_count": self.b4_row_count,
            "b6_strict_gain_count": self.b6_strict_gain_count,
            "b6_row_count": self.b6_row_count,
            "evaluated_main_commit": self.evaluated_main_commit,
            "validation_merge_commit": self.validation_merge_commit,
            "promoted": self.promoted,
            "canonical_algorithm_version": self.canonical_algorithm_version,
        }

    @classmethod
    def frozen_k2(cls) -> BeamV3PromotionLock:
        payload = {
            "lock_version": BEAM_V3_PROMOTION_LOCK_VERSION,
            "v3_algorithm_version": CONTEXT_SURVIVAL_BEAM_V3_ALGORITHM_VERSION,
            "gate_decision": BEAM_V3_GATE_DECISION,
            "gate_artifact_hash": BEAM_V3_GATE_ARTIFACT_HASH,
            "gate_artifact_zip_sha256": BEAM_V3_GATE_ARTIFACT_ZIP_SHA256,
            "gate_run_id": BEAM_V3_GATE_RUN_ID,
            "gate_artifact_id": BEAM_V3_GATE_ARTIFACT_ID,
            "gate_row_count": BEAM_V3_GATE_ROW_COUNT,
            "b4_strict_gain_count": BEAM_V3_GATE_B4_STRICT_GAIN_COUNT,
            "b4_row_count": BEAM_V3_GATE_B4_ROW_COUNT,
            "b6_strict_gain_count": BEAM_V3_GATE_B6_STRICT_GAIN_COUNT,
            "b6_row_count": BEAM_V3_GATE_B6_ROW_COUNT,
            "evaluated_main_commit": BEAM_V3_EVALUATED_MAIN_COMMIT,
            "validation_merge_commit": BEAM_V3_VALIDATION_MERGE_COMMIT,
            "promoted": BEAM_V3_PROMOTED,
            "canonical_algorithm_version": CANONICAL_CONTEXT_SURVIVAL_ALGORITHM_VERSION,
        }
        return cls(**payload, lock_hash=sha256_json(payload))


FROZEN_BEAM_V3_PROMOTION_LOCK = BeamV3PromotionLock.frozen_k2()


def require_promoted_beam_v3() -> None:
    raise RuntimeError(
        "Beam v3 is not promoted: frozen geometry gate decision is "
        f"{FROZEN_BEAM_V3_PROMOTION_LOCK.gate_decision}; "
        f"canonical algorithm remains {CANONICAL_CONTEXT_SURVIVAL_ALGORITHM_VERSION}."
    )
