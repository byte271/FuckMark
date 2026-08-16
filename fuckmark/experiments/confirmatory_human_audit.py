from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms.lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID


CONFIRMATORY_HUMAN_AUDIT_PLAN_ALGORITHM_VERSION = "confirmatory-human-audit-plan-v1"
CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION = "hash-rank-without-replacement-v1"
CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION = "hash-parity-blinding-v1"
MAX_HUMAN_AUDIT_SEED = 2**64 - 1


@dataclass(frozen=True, slots=True)
class ConfirmatoryHumanAuditPlan:
    selection_algorithm_version: str
    blinding_algorithm_version: str
    review_policy_id: str
    target_sample_count: int
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
            "sampling_seed": sampling_seed,
        }
        return cls(
            CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
            CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION,
            review_policy_id,
            target_sample_count,
            sampling_seed,
            sha256_json(payload),
        )
