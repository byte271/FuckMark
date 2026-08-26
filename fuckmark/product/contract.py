from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from ..hashing import sha256_json
from .visible_projection import PRODUCT_CONTRACT_ID, VISIBLE_PROJECTION_ALGORITHM_VERSION


PRODUCT_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "specs" / "fuckmark-user-visible-invariance-v1.contract.json"
FROZEN_PRODUCT_CONTRACT_HASH = "5afd79586f82e31d0d673acbebebf0ac00804cff74b9f644f000bddfd3dc07d1"


def product_contract_payload() -> dict[str, object]:
    return {
        "contract_id": PRODUCT_CONTRACT_ID,
        "contract_version": "v1",
        "status": "active_product_constraint",
        "priority": {
            "rank": 0,
            "name": "exact_user_visible_text_preservation",
            "outranks": [
                "detector_score",
                "detection_rate",
                "evasion_rate",
                "candidate_density",
                "root_window_destruction",
                "tokenizer_disruption",
                "scheduler_quality",
                "sanitizer_robustness",
                "semantic_equivalence",
                "human_fidelity",
            ],
        },
        "scope": {
            "applies_to": [
                "release_transform_registry",
                "public_cli",
                "product_transform_registry",
                "cycle8_product_research_intended_for_eventual_release",
            ],
            "does_not_rewrite": [
                "frozen_historical_contracts",
                "cycle4_formal_evidence",
                "cycle6_formal_nonzero_residual",
                "cycle7_visible_edit_research_artifacts",
            ],
        },
        "supported_input_domain": {
            "id": "ordinary-english-ascii-v1",
            "allowed_code_points": ["U+0009", "U+000A", "U+000D", "U+0020..U+007E"],
            "outside_domain": "fail_closed_leave_text_unchanged",
        },
        "visible_projection": {
            "algorithm_version": VISIBLE_PROJECTION_ALGORITHM_VERSION,
            "rule": "transformed must equal original with only insertions of approved non-rendering carriers",
            "original_visible_code_points": "intact_same_order",
            "substitutions": "forbidden",
            "deletions": "forbidden",
            "reordering": "forbidden",
            "visible_ascii_spaces": "immutable",
            "newlines": "immutable",
            "tabs": "immutable",
            "punctuation": "immutable",
            "letters_words_digits": "immutable",
        },
        "allowed_hidden_modifications": {
            "product_authorized_carriers_v1": [],
            "research_carriers": "must be individually evidenced before product authorization",
        },
        "forbidden_visible_modifications": [
            "letter_or_word_rewrites",
            "contraction_or_expansion",
            "hyphenation_changes",
            "apostrophe_or_quote_substitution",
            "punctuation_insertion_or_deletion",
            "visible_whitespace_changes",
            "newline_or_layout_changes",
            "homoglyphs",
            "compatibility_or_fullwidth_variants",
            "lookalike_punctuation",
        ],
        "renderer_assumptions": {
            "output": "ordinary_unicode_plain_text",
            "no_special_renderer": True,
            "required_environments": ["terminal", "text_editor", "browser_text_box", "clipboard", "file"],
            "cross_platform_rendering": "unknown_unless_measured",
        },
        "plain_text_requirement": {
            "html_overlays": "forbidden",
            "css_or_font_tricks": "forbidden",
            "images_or_canvas": "forbidden",
            "metadata_outside_payload": "forbidden",
            "viewer_plugins": "forbidden",
        },
        "clipboard_requirement": {
            "payload": "the_unicode_string_itself",
            "roundtrip": "utf8_file_and_stdin_stdout_must_preserve_code_points",
        },
        "sanitizer_assumptions": {
            "frozen_cycle6_variants": ["raw", "nfkc", "cf_strip", "nfkc_cf_strip"],
            "frozen_cycle7_additions": ["ws_collapse", "ws_collapse_nfkc_cf_strip"],
            "stress_only_not_frozen": ["default_ignorable_removal", "nonspacing_mark_removal"],
        },
        "release_gating": {
            "product_authorized_carriers_required": True,
            "semantic_fidelity_insufficient": True,
            "visible_edit_fallback": "forbidden",
            "empty_authorized_set": "fail_closed_return_original",
        },
        "carrier_promotion_evidence": [
            "unicode_properties",
            "normalization_nfc_nfd_nfkc_nfkd",
            "cf_strip_survival",
            "whitespace_collapse_survival",
            "combined_sanitizer_survival",
            "gpt2_tokenization_effect",
            "rendering_evidence_or_unknown",
            "copy_paste_survival_or_unknown",
            "protected_machine_span_safety",
            "fresh_detector_reduction_is_not_a_substitute_for_visibility",
        ],
        "failure_behavior": {
            "visible_invariant_fail": "reject_candidate_or_return_original",
            "unsupported_domain": "return_original",
            "uncertain_carrier_safety": "return_original",
            "protected_machine_content": "do_not_insert_carriers_inside_span",
        },
        "versioning_rules": {
            "this_contract": "immutable_once_used_for_formal_product_evidence",
            "successors": "new_filename_and_new_contract_id",
            "historical_visible_edit_research": "may_replay_but_cannot_enter_release",
        },
        "historical_reclassification": {
            "cycle6_formal": {
                "detector_result": "NONZERO_RESIDUAL_7_of_192",
                "product_status": "PRODUCT_DISQUALIFIED",
                "reason": "visible_ascii_space_insertion",
            },
            "cycle7_durable_visible_edits": {
                "scientific_status": "INSUFFICIENT_EVIDENCE",
                "product_status": "PRODUCT_DISQUALIFIED",
                "reason": "visible_word_punctuation_or_layout_edits",
            },
            "u200c_visible_projection": {
                "visibility": "conceptually_product_aligned",
                "durability": "REJECTED_as_final_durable_mechanism",
                "reason": "removed_by_cf_strip",
            },
        },
    }


def product_contract_hash() -> str:
    return sha256_json(product_contract_payload())


def load_product_contract() -> dict[str, object]:
    payload = product_contract_payload()
    digest = sha256_json(payload)
    if digest != FROZEN_PRODUCT_CONTRACT_HASH:
        raise ValueError("embedded product contract hash does not match frozen v1 digest")
    contract = {**payload, "contract_hash": digest}
    if PRODUCT_CONTRACT_PATH.is_file():
        disk = json.loads(PRODUCT_CONTRACT_PATH.read_text(encoding="utf-8"))
        if disk != contract:
            raise ValueError("product contract file does not match embedded v1 payload")
    return contract
