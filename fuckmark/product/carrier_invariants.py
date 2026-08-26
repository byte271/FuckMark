from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..hashing import sha256_json, sha256_text
from ..transforms.hard_invariants import HARD_INVARIANT_ALGORITHM_VERSION, HardInvariantReport, hard_invariant_signature
from ..transforms.invariants import validate_protected_invariants
from ..transforms.protected_artifacts import UserProtectedRange
from ..transforms.schema import HardInvariantReason, InvariantStatus
from .visible_projection import normalize_approved_carriers, project_visible_v1


PRODUCT_CARRIER_INVARIANT_ALGORITHM_VERSION = "product-carrier-invariant-v1"
WORD_SIGNATURE_SOURCE_RAW = "raw"
WORD_SIGNATURE_SOURCE_VISIBLE = "visible"
WORD_SIGNATURE_SOURCES = frozenset({WORD_SIGNATURE_SOURCE_RAW, WORD_SIGNATURE_SOURCE_VISIBLE})


def validate_product_carrier_invariants(
    original: str,
    transformed: str,
    identifiers: Sequence[str] = (),
    user_ranges: Sequence[UserProtectedRange] = (),
    *,
    include_quotations: bool = True,
    approved_carriers: Iterable[int] = (),
) -> HardInvariantReport:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    approved = normalize_approved_carriers(approved_carriers)
    protected_report = validate_protected_invariants(
        original,
        transformed,
        identifiers,
        user_ranges,
        include_quotations=include_quotations,
    )
    original_signature = hard_invariant_signature(project_visible_v1(original, approved))
    transformed_signature = hard_invariant_signature(project_visible_v1(transformed, approved))
    reasons = []
    if protected_report.status is InvariantStatus.FAIL:
        reasons.append(HardInvariantReason.PROTECTED_CONTENT_CHANGED)
    if original_signature.negations != transformed_signature.negations:
        reasons.append(HardInvariantReason.NEGATION_CHANGED)
    if original_signature.modalities != transformed_signature.modalities:
        reasons.append(HardInvariantReason.MODALITY_CHANGED)
    normalized_reasons = tuple(sorted(reasons, key=lambda value: value.value))
    status = InvariantStatus.PASS if not normalized_reasons else InvariantStatus.FAIL
    original_hash = sha256_text(original)
    transformed_hash = sha256_text(transformed)
    payload = {
        "algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION,
        "status": status.value,
        "original_hash": original_hash,
        "transformed_hash": transformed_hash,
        "protected_report": protected_report,
        "original_signature": original_signature,
        "transformed_signature": transformed_signature,
        "reasons": tuple(value.value for value in normalized_reasons),
    }
    return HardInvariantReport(
        status,
        original_hash,
        transformed_hash,
        protected_report,
        original_signature,
        transformed_signature,
        normalized_reasons,
        sha256_json(payload),
    )
