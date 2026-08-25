from __future__ import annotations

from enum import Enum

from ..hashing import sha256_json


class EvidenceLabel(str, Enum):
    VERIFIED = "VERIFIED"
    SOURCE_BOUND = "SOURCE-BOUND"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    PRODUCT_DISQUALIFIED = "PRODUCT_DISQUALIFIED"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    EXTERNAL_VALIDATION_ONLY = "EXTERNAL-VALIDATION-ONLY"


class ProductGate(str, Enum):
    PASS = "VISIBLE_INVARIANT_PASS"
    FAIL = "VISIBLE_INVARIANT_FAIL"
    DISQUALIFIED = "PRODUCT_DISQUALIFIED"


CYCLE8_SCOREBOARD_VERSION = "cycle8-product-scoreboard-v1"


def product_scoreboard_payload(
    *,
    mechanism_id: str,
    visible_pass_rate: str,
    carrier_type: str,
    inserted_count: int,
    utf8_overhead: int,
    sanitizer: dict[str, object],
    tokenizer: dict[str, object] | None,
    detector: dict[str, object] | None,
    product_gate: ProductGate,
    label: EvidenceLabel,
) -> dict[str, object]:
    payload = {
        "algorithm_version": CYCLE8_SCOREBOARD_VERSION,
        "mechanism_id": mechanism_id,
        "visible_contract": {"projection_pass_rate": visible_pass_rate},
        "carrier": {
            "type": carrier_type,
            "inserted_count": inserted_count,
            "utf8_overhead": utf8_overhead,
        },
        "sanitizer": sanitizer,
        "tokenizer": tokenizer,
        "detector": detector,
        "product_gate": product_gate.value,
        "evidence_label": label.value,
    }
    payload["scoreboard_hash"] = sha256_json(payload)
    return payload
