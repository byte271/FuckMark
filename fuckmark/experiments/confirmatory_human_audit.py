from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms.lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID


CONFIRMATORY_HUMAN_AUDIT_PLAN_ALGORITHM_VERSION = "confirmatory-human-audit-plan-v2"
CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION = "cell-quartile-hash-rank-v1"
CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION = "hash-parity-blinding-v1"
CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT = 4
CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR = 0.01
MAX_HUMAN_AUDIT_SEED = 2**64 - 1


@dataclass(frozen=True, slots=True)
class ConfirmatoryHumanAuditPlan:
    selection_algorithm_version: str
    blinding_algorithm_version: str
    review_policy_id: str
    target_sample_count: int
    quartile_count: int
    degradation_target_fpr: float
    sampling_seed: int
    plan_hash: str

    def __post_init__(self) -> None:
        if self.selection_algorithm_version != CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory human-audit selection algorithm version")
        if self.blinding_algorithm_version != CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory human-audit blinding algorithm version")
        require_clean_string("review_policy_id", self.review_policy_id)
        if self.review_policy_id != BLIND_HUMAN_REVIEW_POLICY_ID:
            raise ValueError("confirmatory human audit must use the frozen blind-review policy")
        require_int("target_sample_count", self.target_sample_count)
        if self.target_sample_count <= 0:
            raise ValueError("target_sample_count must be positive")
        if self.target_sample_count < 50:
            raise ValueError("confirmatory human audit requires at least 50 selected outputs per feasible cell")
        require_int("quartile_count", self.quartile_count)
        if self.quartile_count != CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT:
            raise ValueError("confirmatory human audit must use four detector-degradation quartiles")
        if isinstance(self.degradation_target_fpr, bool) or not isinstance(self.degradation_target_fpr, (int, float)):
            raise TypeError("degradation_target_fpr must be a real number")
        target_fpr = float(self.degradation_target_fpr)
        if not math.isclose(target_fpr, CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("confirmatory human audit degradation strata must use the primary 1% FPR operating point")
        object.__setattr__(self, "degradation_target_fpr", target_fpr)
        require_int("sampling_seed", self.sampling_seed)
        if self.sampling_seed < 0 or self.sampling_seed > MAX_HUMAN_AUDIT_SEED:
            raise ValueError("sampling_seed must be between 0 and 2^64-1")
        require_sha256("plan_hash", self.plan_hash)
        if self.plan_hash != sha256_json(self._payload()):
            raise ValueError("plan_hash does not match confirmatory human-audit plan")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": CONFIRMATORY_HUMAN_AUDIT_PLAN_ALGORITHM_VERSION,
            "selection_algorithm_version": self.selection_algorithm_version,
            "blinding_algorithm_version": self.blinding_algorithm_version,
            "review_policy_id": self.review_policy_id,
            "target_sample_count": self.target_sample_count,
            "quartile_count": self.quartile_count,
            "degradation_target_fpr": self.degradation_target_fpr,
            "sampling_seed": self.sampling_seed,
        }

    @classmethod
    def create(
        cls,
        target_sample_count: int,
        sampling_seed: int,
        review_policy_id: str = BLIND_HUMAN_REVIEW_POLICY_ID,
    ) -> ConfirmatoryHumanAuditPlan:
        payload = {
            "algorithm_version": CONFIRMATORY_HUMAN_AUDIT_PLAN_ALGORITHM_VERSION,
            "selection_algorithm_version": CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            "blinding_algorithm_version": CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION,
            "review_policy_id": review_policy_id,
            "target_sample_count": target_sample_count,
            "quartile_count": CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT,
            "degradation_target_fpr": CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR,
            "sampling_seed": sampling_seed,
        }
        return cls(
            CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION,
            review_policy_id,
            target_sample_count,
            CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT,
            CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR,
            sampling_seed,
            sha256_json(payload),
        )
