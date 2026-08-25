from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .._validation import require_sha256
from ..hashing import sha256_json, sha256_text
from ..transforms.schema import InvariantStatus
from .visible_projection import (
    VISIBLE_PROJECTION_ALGORITHM_VERSION,
    is_carrier_insertion_v1,
    normalize_approved_carriers,
    product_approved_carriers_v1,
    project_visible_v1,
)


USER_VISIBLE_INVARIANT_ALGORITHM_VERSION = "user-visible-invariant-v1"


class UserVisibleInvariantReason(str, Enum):
    USER_VISIBLE_TEXT_CHANGED = "user_visible_text_changed"


@dataclass(frozen=True, slots=True)
class UserVisibleInvariantReport:
    status: InvariantStatus
    original_hash: str
    transformed_hash: str
    original_projection_hash: str
    transformed_projection_hash: str
    approved_carriers: tuple[int, ...]
    reasons: tuple[UserVisibleInvariantReason, ...]
    report_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, InvariantStatus):
            raise TypeError("status must be an InvariantStatus")
        require_sha256("original_hash", self.original_hash)
        require_sha256("transformed_hash", self.transformed_hash)
        require_sha256("original_projection_hash", self.original_projection_hash)
        require_sha256("transformed_projection_hash", self.transformed_projection_hash)
        carriers = tuple(self.approved_carriers)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in carriers):
            raise TypeError("approved_carriers must contain integers")
        if carriers != tuple(sorted(set(carriers))):
            raise ValueError("approved_carriers must be unique and sorted")
        object.__setattr__(self, "approved_carriers", carriers)
        reasons = tuple(self.reasons)
        if any(not isinstance(value, UserVisibleInvariantReason) for value in reasons):
            raise TypeError("reasons must contain UserVisibleInvariantReason values")
        if reasons != tuple(sorted(set(reasons), key=lambda value: value.value)):
            raise ValueError("reasons must be unique and sorted")
        object.__setattr__(self, "reasons", reasons)
        expected_status = InvariantStatus.PASS if not reasons else InvariantStatus.FAIL
        if self.status is not expected_status:
            raise ValueError("user-visible invariant status does not match reasons")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match user-visible invariant report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": USER_VISIBLE_INVARIANT_ALGORITHM_VERSION,
            "projection_algorithm_version": VISIBLE_PROJECTION_ALGORITHM_VERSION,
            "status": self.status.value,
            "original_hash": self.original_hash,
            "transformed_hash": self.transformed_hash,
            "original_projection_hash": self.original_projection_hash,
            "transformed_projection_hash": self.transformed_projection_hash,
            "approved_carriers": self.approved_carriers,
            "reasons": tuple(value.value for value in self.reasons),
        }


def validate_user_visible_invariants(
    original: str,
    transformed: str,
    approved_carriers: Iterable[int] | None = None,
) -> UserVisibleInvariantReport:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    approved = normalize_approved_carriers(
        product_approved_carriers_v1() if approved_carriers is None else approved_carriers
    )
    ordered = tuple(sorted(approved))
    original_projection = project_visible_v1(original, approved)
    transformed_projection = project_visible_v1(transformed, approved)
    reasons: list[UserVisibleInvariantReason] = []
    if not is_carrier_insertion_v1(original, transformed, approved):
        reasons.append(UserVisibleInvariantReason.USER_VISIBLE_TEXT_CHANGED)
    elif original_projection != transformed_projection:
        reasons.append(UserVisibleInvariantReason.USER_VISIBLE_TEXT_CHANGED)
    normalized_reasons = tuple(sorted(set(reasons), key=lambda value: value.value))
    status = InvariantStatus.PASS if not normalized_reasons else InvariantStatus.FAIL
    original_hash = sha256_text(original)
    transformed_hash = sha256_text(transformed)
    original_projection_hash = sha256_text(original_projection)
    transformed_projection_hash = sha256_text(transformed_projection)
    payload = {
        "algorithm_version": USER_VISIBLE_INVARIANT_ALGORITHM_VERSION,
        "projection_algorithm_version": VISIBLE_PROJECTION_ALGORITHM_VERSION,
        "status": status.value,
        "original_hash": original_hash,
        "transformed_hash": transformed_hash,
        "original_projection_hash": original_projection_hash,
        "transformed_projection_hash": transformed_projection_hash,
        "approved_carriers": ordered,
        "reasons": tuple(value.value for value in normalized_reasons),
    }
    return UserVisibleInvariantReport(
        status,
        original_hash,
        transformed_hash,
        original_projection_hash,
        transformed_projection_hash,
        ordered,
        normalized_reasons,
        sha256_json(payload),
    )
