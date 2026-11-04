"""Public API, resolved on demand without importing unrelated research modules.

The export order and targets preserve the pre-refactor API. Implementations
remain in their original modules; this is an import-boundary change only.
"""

from importlib import import_module as _import_module


# None denotes metadata defined in this module, not a deferred import.
_EXPORTS: dict[str, str | None] = {
    "InvisibleCarrierAfterAsciiLetterRule": ".carriers",
    "InvisibleCarrierAfterWordFinalAsciiLetterRule": ".carriers",
    "FROZEN_PRODUCT_CONTRACT_HASH": ".contract",
    "PRODUCT_CARRIER_INVARIANT_ALGORITHM_VERSION": ".carrier_invariants",
    "PRODUCT_CONTRACT_ID": ".visible_projection",
    "PRODUCT_CONTRACT_PATH": ".contract",
    "PRODUCT_DOMAIN_ID": ".domain",
    "PRODUCT_ENCODING_POLICY_VERSION": ".encodings",
    "PRODUCT_REGISTRY_ALGORITHM_VERSION": ".registry",
    "PRODUCT_SEARCH_ALGORITHM_VERSION": ".search",
    "PRODUCT_TEXT_ENCODING": ".encodings",
    "SCAN_ALGORITHM_VERSION": ".scan",
    "SCAN_CATEGORIES": ".scan",
    "SECURITY_SCAN_CATEGORIES": ".scan",
    "TROJAN_SOURCE_CATEGORIES": ".scan",
    "NORMALIZE_ALGORITHM_VERSION": ".normalize",
    "NormalizeReceipt": ".normalize",
    "normalize_payload": ".normalize",
    "normalize_receipt_dict": ".normalize",
    "normalize_text": ".normalize",
    "skeleton_fold": ".normalize",
    "CONTEXT_COMMENT": ".severity",
    "CONTEXT_EMOJI": ".severity",
    "CONTEXT_IDENTIFIER": ".severity",
    "CONTEXT_PROSE": ".severity",
    "CONTEXT_STRING": ".severity",
    "SEVERITY_CRITICAL": ".severity",
    "SEVERITY_HIGH": ".severity",
    "SEVERITY_INFO": ".severity",
    "SEVERITY_MEDIUM": ".severity",
    "annotate_finding": ".severity",
    "classify_context": ".severity",
    "language_from_path": ".severity",
    "normalize_language": ".severity",
    "score_severity": ".severity",
    "source_roles": ".severity",
    "autofix_trojan_source": ".scan",
    "HiddenFinding": ".scan",
    "ScanResult": ".scan",
    "classify_hidden_codepoint": ".scan",
    "clean_hidden_characters": ".scan",
    "extract_tag_payload": ".scan",
    "scan_dict": ".scan",
    "scan_hidden_characters": ".scan",
    "scan_human_report": ".scan",
    "scan_machine_line": ".scan",
    "ProductTransformRegistry": ".registry",
    "UNSUPPORTED_PRODUCT_ENCODINGS": ".encodings",
    "USER_VISIBLE_INVARIANT_ALGORITHM_VERSION": ".invariants",
    "UserVisibleInvariantReason": ".invariants",
    "UserVisibleInvariantReport": ".invariants",
    "VISIBLE_PROJECTION_ALGORITHM_VERSION": ".visible_projection",
    "canonical_product_encoding_name": ".encodings",
    "codepoint_label": ".carriers",
    "encoding_roundtrip_survives": ".encodings",
    "is_carrier_insertion_v1": ".visible_projection",
    "is_supported_product_domain_v1": ".domain",
    "is_supported_product_encoding": ".encodings",
    "load_product_contract": ".contract",
    "normalize_approved_carriers": ".visible_projection",
    "product_approved_carriers_v1": ".visible_projection",
    "product_contract_hash": ".contract",
    "product_contract_payload": ".contract",
    "product_transform_registry": ".registry",
    "project_visible_v1": ".visible_projection",
    "raw_codepoint_contains": ".search",
    "require_supported_product_encoding": ".encodings",
    "rule_preserves_visible_projection": ".carriers",
    "space_carrier_rule": ".carriers",
    "validate_product_carrier_invariants": ".carrier_invariants",
    "validate_user_visible_invariants": ".invariants",
    "visible_contains": ".search",
    "WORD_SIGNATURE_SOURCE_RAW": ".carrier_invariants",
    "WORD_SIGNATURE_SOURCE_VISIBLE": ".carrier_invariants",
}

__all__ = list(_EXPORTS)

# A reload must not retain objects cached by a previous module execution.
for _export_name in _EXPORTS:
    globals().pop(_export_name, None)
del _export_name



def __getattr__(name: str) -> object:
    source = _EXPORTS.get(name)
    if source is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_import_module(source, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
