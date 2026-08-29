from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.contract import FROZEN_PRODUCT_CONTRACT_HASH, product_contract_payload
from ..sanitizer_robustness import strip_unicode_format_characters
from .benchmark import strip_default_ignorable, strip_nonspacing_marks
from .control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from .letter_mix import HISTORICAL_MARK_MIX_CARRIERS, apply_historical_mark_letter_mix
from .post_sanitizer_sequences import CYCLE8_POST_SANITIZER_SEQUENCES_HASH
from .publishability import (
    CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH,
    build_mix_confirmation_scorecard,
    measure_mix_fixtures,
)

CYCLE8_THREAT_MODEL_AUDIT_VERSION = "cycle8-threat-model-audit-v1"
CYCLE8_THREAT_MODEL_AUDIT_PATH = "specs/cycle8/fuckmark-cycle8-threat-model-audit-v1.json"
CYCLE8_THREAT_MODEL_AUDIT_HASH = "bcd3026a514e1dc80338f57345d65aa1ec51a816e0135ab14843d850ed9aa680"

AUDIT_SOURCE = "I do not agree."
H16_RESEARCH_EXTRA_INSTALL = 'pip install -e ".[research]"'
CHROMIUM_PRE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SHAPING_FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
SHAPING_LEFT = "A"
SHAPING_RIGHT = "B"
LM_WATERMARKING_UNICODE_SANITIZER_SOURCE = (
    "jwkirchenbauer/lm-watermarking normalizers.py UnicodeSanitizer, ruleset='whitespaces', "
    "the shipped default of WatermarkDetector(normalizers=['unicode'])"
)
LM_WATERMARKING_UNICODE_SANITIZER_PATTERN = re.compile(
    "[\u00a0\u1680\u180e\u2000-\u200b\u200c\u200d\u200e\u200f\u2060\u2063\u202f\u205f\u3000"
    "\ufeff\uffa0\ufff9\ufffa\ufffb\ufe00\ufe01\ufe02\ufe03\ufe04\ufe05\ufe06\ufe07\ufe08\ufe09"
    "\ufe0a\ufe0b\ufe0c\ufe0d\ufe0e\ufe0f\u3164\u202a\u202b\u202c\u202d\u202e\u202f]"
)
REAL_SANITIZER_SOURCE = "I do not agree with that."
SHAPING_CONTEXTS: tuple[tuple[str, str, str], ...] = (
    ("latin", "A", "B"),
    ("latin_lower", "n", "o"),
    ("digit", "4", "7"),
    ("space_left", " ", "a"),
    ("space_right", "a", " "),
    ("start", "", "Ab"),
    ("end", "Ab", ""),
    ("arabic", "\u0645", "\u0646"),
    ("devanagari", "\u0915", "\u0916"),
    ("cjk", "\u4e2d", "\u6587"),
    ("hangul", "\uac00", "\ub098"),
    ("punct", ".", ","),
)
PRODUCT_SHAPING_CONTEXT_IDS = ("latin", "latin_lower", "digit", "space_left", "space_right", "start", "end", "punct")
ORIGINAL_H16_SCAN_CONTEXT_IDS = ("latin",)
TWELVE_CONTEXT_RESCAN_STATUS = "recorded"
TWELVE_CONTEXT_INVISIBLE_COUNT = 396
TWELVE_CONTEXT_PRODUCT_INVISIBLE_COUNT = 396
TWELVE_CONTEXT_INTERSECTION_COUNT = 0
TWELVE_CONTEXT_PER_CONTEXT = {
    "arabic": 390,
    "cjk": 396,
    "devanagari": 396,
    "digit": 395,
    "end": 396,
    "hangul": 396,
    "latin": 396,
    "latin_lower": 396,
    "punct": 395,
    "space_left": 396,
    "space_right": 396,
    "start": 395,
}
TWELVE_CONTEXT_ARTIFACT = "evidence/h16-local/shaping-closure-12context.json"

SHAPING_INVISIBLE_RANGES: tuple[tuple[int, int], ...] = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x17B4, 0x17B5),
    (0x180B, 0x180E),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x2064),
    (0x2066, 0x206F),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0x1D173, 0x1D17A),
    (0xE0001, 0xE0001),
    (0xE0020, 0xE007F),
    (0xE0100, 0xE01EF),
)
ASSIGNED_CODEPOINTS_SCANNED = 286719
REQUIRED_SANITIZER_FIXED_POINT_COUNT = 267550
SHAPING_CONTEXTS_ADVERTISED = 12
SHAPING_CONTEXTS_SCANNED = 1
ORACLE_VALIDATION_SAMPLE = 23
ORACLE_VALIDATION_AGREEMENT = 20
ORACLE_VALIDATION_DISAGREEMENTS = ("cf_zwnj", "cc_del", "cc_c1_pad")

DEPLOYABILITY_CORPUS: tuple[tuple[str, str], ...] = (
    ("devanagari", "\u092e\u0948\u0902 \u0907\u0938\u0938\u0947 \u0938\u0939\u092e\u0924 \u0928\u0939\u0940\u0902 \u0939\u0942\u0901\u0964"),
    ("hebrew_niqqud", "\u05d0\u05b2\u05e0\u05b4\u05d9 \u05dc\u05b9\u05d0 \u05de\u05b7\u05e1\u05b0\u05db\u05bc\u05b4\u05d9\u05dd."),
    ("thai", "\u0e09\u0e31\u0e19\u0e44\u0e21\u0e48\u0e40\u0e2b\u0e47\u0e19\u0e14\u0e49\u0e27\u0e22"),
    ("persian_zwnj", "\u0645\u0646 \u0645\u0648\u0627\u0641\u0642 \u0646\u06cc\u0633\u062a\u0645\u200c\u0647\u0627."),
    ("emoji_zwj_family", "Our family \U0001f468\u200d\U0001f469\u200d\U0001f467 disagrees."),
    ("emoji_vs16", "I disagree \u2764\ufe0f strongly."),
    ("devanagari_zwj_conjunct", "\u0915\u094d\u200d\u0937 \u0938\u0939\u0940 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964"),
)

REAL_SANITIZER_DETECTOR_ROLE = "exploratory_only_not_confirmation"
REAL_SANITIZER_DETECTOR_SEED_BASE = 890000
REAL_SANITIZER_DETECTOR_MODEL = "openai-community/gpt2"
REAL_SANITIZER_DETECTOR_WATERMARKED_ROWS = 48
REAL_SANITIZER_DETECTOR_PRISTINE_DETECTED = 47
REAL_SANITIZER_DETECTOR_OBSERVATIONS: tuple[dict[str, object], ...] = (
    {"variant": "raw", "watermarked_detected": 0, "carrier_free_detected": 47, "restores_source": 0},
    {"variant": "nfkc", "watermarked_detected": 0, "carrier_free_detected": 47, "restores_source": 0},
    {"variant": "cf_strip", "watermarked_detected": 0, "carrier_free_detected": 47, "restores_source": 0},
    {
        "variant": "lm_watermarking_unicode_sanitizer",
        "watermarked_detected": 0,
        "carrier_free_detected": 46,
        "restores_source": 0,
    },
    {"variant": "required_bundle", "watermarked_detected": 47, "carrier_free_detected": 47, "restores_source": 96},
)
TOKENIZER_OBSERVATIONS: tuple[dict[str, object], ...] = (
    {"model": "gemma-2-2b-it", "normalizer": "Replace", "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "gemma-3-1b-it", "normalizer": "Replace", "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "gpt2", "normalizer": None, "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "llama-2-7b", "normalizer": "Sequence[Prepend,Replace]", "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "llama-3-8b", "normalizer": None, "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "mistral-7b-v0.2", "normalizer": None, "carriers_reaching_token_stream": 9, "carriers_probed": 9},
    {"model": "xlm-roberta-base", "normalizer": "Precompiled", "carriers_reaching_token_stream": 8, "carriers_probed": 9},
    {"model": "t5-small", "normalizer": "Precompiled", "carriers_reaching_token_stream": 8, "carriers_probed": 9},
)


def iter_shaping_invisible_codepoints():
    for start, end in SHAPING_INVISIBLE_RANGES:
        yield from range(start, end + 1)


def shaping_invisible_codepoint_count() -> int:
    return sum(end - start + 1 for start, end in SHAPING_INVISIBLE_RANGES)


def shaping_invisible_categories() -> dict[str, int]:
    counts: dict[str, int] = {}
    for codepoint in iter_shaping_invisible_codepoints():
        category = unicodedata.category(chr(codepoint))
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def shaping_invisible_all_stripped_by_required_bundle() -> bool:
    return all(
        not required_sanitizers_keep(f"I{chr(codepoint)} do not agree.")
        for codepoint in iter_shaping_invisible_codepoints()
    )


def control_required_sanitizer_fixed_points() -> tuple[int, ...]:
    return tuple(
        codepoint
        for codepoint in range(0x110000)
        if unicodedata.category(chr(codepoint)) == "Cc"
        and required_sanitizers_keep(f"I{chr(codepoint)} do not agree.")
    )


def ascii_domain_is_normalization_fixed_point() -> bool:
    domain = "".join(chr(c) for c in [0x09, 0x0A, 0x0D, *range(0x20, 0x7F)])
    return all(
        unicodedata.normalize(form, domain) == domain
        for form in ("NFC", "NFD", "NFKC", "NFKD")
    )


def render_identical_ascii_substitutes() -> tuple[int, ...]:
    return (
        0x00A0, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
        0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F,
    )


def substitution_class_survivors() -> tuple[int, ...]:
    return tuple(
        codepoint
        for codepoint in render_identical_ascii_substitutes()
        if required_sanitizers_keep(f"I{chr(codepoint)} do not agree.")
    )


def sanitizer_deployability_damage() -> dict[str, dict[str, object]]:
    sanitizers = (
        ("nfc", lambda t: unicodedata.normalize("NFC", t), "frozen"),
        ("nfkc", lambda t: unicodedata.normalize("NFKC", t), "frozen"),
        ("cf_strip", strip_unicode_format_characters, "frozen"),
        ("mn_strip", strip_nonspacing_marks, "stress_only_not_frozen"),
        ("default_ignorable_strip", strip_default_ignorable, "stress_only_not_frozen"),
    )
    report: dict[str, dict[str, object]] = {}
    for name, function, category in sanitizers:
        corrupted = [
            sample_id for sample_id, text in DEPLOYABILITY_CORPUS if function(text) != text
        ]
        report[name] = {
            "contract_category": category,
            "corrupted_sample_ids": corrupted,
            "corrupted": len(corrupted),
            "of": len(DEPLOYABILITY_CORPUS),
        }
    return report


def lm_watermarking_unicode_sanitizer(text: str) -> str:
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = LM_WATERMARKING_UNICODE_SANITIZER_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(" +", " ", cleaned)
    return "".join(character for character in cleaned if unicodedata.category(character) != "Cc")


def real_world_sanitizer_observations() -> dict[str, object]:
    mixed = apply_historical_mark_letter_mix(REAL_SANITIZER_SOURCE)
    cleaned = lm_watermarking_unicode_sanitizer(mixed)
    carriers = sorted(HISTORICAL_MARK_MIX_CARRIERS)
    surviving = [
        codepoint
        for codepoint in carriers
        if lm_watermarking_unicode_sanitizer(f"A{chr(codepoint)}B") == f"A{chr(codepoint)}B"
    ]
    invisible = list(iter_shaping_invisible_codepoints())
    invisible_surviving = [
        codepoint
        for codepoint in invisible
        if lm_watermarking_unicode_sanitizer(f"A{chr(codepoint)}B") == f"A{chr(codepoint)}B"
    ]
    corrupted = [
        sample_id
        for sample_id, text in DEPLOYABILITY_CORPUS
        if lm_watermarking_unicode_sanitizer(text) != text
    ]
    return {
        "source": LM_WATERMARKING_UNICODE_SANITIZER_SOURCE,
        "shipped_on_by_default": True,
        "steps": ["nfc", "regex_replace_with_space", "collapse_spaces", "cc_strip"],
        "restores_the_unwatermarked_source": cleaned == REAL_SANITIZER_SOURCE,
        "output_differs_from_source": cleaned != REAL_SANITIZER_SOURCE,
        "injects_spurious_visible_spaces": cleaned.count(" ") > REAL_SANITIZER_SOURCE.count(" "),
        "mix_carriers": [f"U+{codepoint:04X}" for codepoint in carriers],
        "mix_carriers_surviving": [f"U+{codepoint:04X}" for codepoint in surviving],
        "invisible_codepoints_surviving": len(invisible_surviving),
        "invisible_codepoints_total": len(invisible),
        "ordinary_text_corrupted": len(corrupted),
        "ordinary_text_corpus_size": len(DEPLOYABILITY_CORPUS),
        "ordinary_text_corrupted_sample_ids": corrupted,
        "detection_after_this_sanitizer": real_sanitizer_detector_observations(),
    }


def real_sanitizer_detector_observations() -> dict[str, object]:
    by_variant = {row["variant"]: row for row in REAL_SANITIZER_DETECTOR_OBSERVATIONS}
    real = by_variant["lm_watermarking_unicode_sanitizer"]
    bundle = by_variant["required_bundle"]
    rows = REAL_SANITIZER_DETECTOR_WATERMARKED_ROWS
    return {
        "role": REAL_SANITIZER_DETECTOR_ROLE,
        "seed_base": REAL_SANITIZER_DETECTOR_SEED_BASE,
        "model": REAL_SANITIZER_DETECTOR_MODEL,
        "watermarked_rows": rows,
        "pristine_watermarked_detected": REAL_SANITIZER_DETECTOR_PRISTINE_DETECTED,
        "per_variant": [dict(row) for row in REAL_SANITIZER_DETECTOR_OBSERVATIONS],
        "real_sanitizer_watermarked_detected": real["watermarked_detected"],
        "real_sanitizer_carrier_free_detected": real["carrier_free_detected"],
        "required_bundle_watermarked_detected": bundle["watermarked_detected"],
        "required_bundle_restores_source_rows": bundle["restores_source"],
        "confound_ruled_out": (
            "the real sanitizer collapses space runs and strips Cc, so it could have suppressed "
            "detection by itself; run on carrier-free watermarked text it still detects 46 of 48 "
            "against a 47 of 48 baseline, so the drop to 0 is attributable to the carrier"
        ),
        "reading": (
            "Mix evades at 0 of 48 after the real sanitizer, the same as raw, while that "
            "sanitizer costs only one row of detection power on its own. The required bundle is "
            "the only variant that restores detection, and it does so only because it "
            "reconstructs the original string on every row."
        ),
        "confirmation_grade": False,
    }


def contract_stress_only_sanitizers() -> tuple[str, ...]:
    assumptions = product_contract_payload()["sanitizer_assumptions"]
    return tuple(assumptions["stress_only_not_frozen"])


def gate_promotes_stress_only_sanitizers() -> bool:
    mn_only = "I\u0301 do not agree."
    di_only = "I\u200b do not agree."
    return (
        strip_nonspacing_marks(mn_only) != mn_only
        and required_sanitizers_keep(mn_only) is False
        and strip_default_ignorable(di_only) != di_only
        and required_sanitizers_keep(di_only) is False
    )


def proposed_gate_status_on_existing_evidence() -> dict[str, object]:
    scorecard = build_mix_confirmation_scorecard()
    measured = measure_mix_fixtures()
    durability = scorecard["durability"]
    detected = durability["sanitizer_watermarked_detected"]
    return {
        "source": "already-run frozen confirmation evidence, no new corpus",
        "identity_watermarked_detected": scorecard["effectiveness"]["identity"]["raw_watermarked_detected"],
        "transformed_watermarked_rate": scorecard["effectiveness"]["transformed_wm"]["rate"],
        "transformed_unwatermarked_rate": scorecard["effectiveness"]["transformed_uw"]["rate"],
        "visible_pass_rate": scorecard["visibility"]["watermarked_pass_rate"],
        "detected_after_each_deployable_sanitizer": dict(sorted(detected.items())),
        "frozen_sanitizers_match_raw": durability["frozen_sanitizers_match_raw"],
        "frozen_sanitizer_fixture_survival": [
            measured["frozen_sanitizer_survive"],
            measured["frozen_sanitizer_total"],
        ],
        "frozen_sanitizer_conditions_satisfied": (
            all(value == 0 for value in detected.values())
            and durability["frozen_sanitizers_match_raw"] is True
            and scorecard["effectiveness"]["transformed_wm"]["rate"] == "0/192"
            and scorecard["visibility"]["watermarked_pass_rate"] == "192/192"
            and measured["frozen_sanitizer_survive"] == measured["frozen_sanitizer_total"]
        ),
        "lm_watermarking_unicode_sanitizer_condition": "0/48 watermarked detected, exploratory",
        "all_conditions_measured": True,
        "confirmation_grade": False,
        "proposed_gate_v2_fully_satisfied": False,
        "why_not_fully_satisfied": (
            "the real-sanitizer condition is met on the exploratory lane only; a confirmation "
            "run on an unspent corpus remains the product-authorization standard"
        ),
        "adoption_still_blocked_on": "explicit product decision plus a confirmation-grade run",
    }


def threat_model_audit_payload() -> dict[str, object]:
    invisible_categories = shaping_invisible_categories()
    control_survivors = control_required_sanitizer_fixed_points()
    damage = sanitizer_deployability_damage()
    stress_only = contract_stress_only_sanitizers()

    findings = (
        {
            "id": "q1_real_pipeline_normalization",
            "question": "Which normalization do real watermark detection pipelines perform?",
            "answer": (
                "SynthID-Text scores model tokens, so the operative normalizer is the model "
                "tokenizer. On locally cached tokenizers the Gemma normalizer is the "
                "SentencePiece whitespace Replace, and GPT-2, Llama-3 and Mistral declare no "
                "normalizer at all. None of them strips Mn, Cf or default-ignorable. All nine "
                "probe carriers reach the token stream on six of eight tokenizers. The two "
                "SentencePiece Precompiled normalizers drop only DEL."
            ),
            "evidence": "evidence/h16-local/tokenizer-threat-model.json",
        },
        {
            "id": "q2_are_stress_sanitizers_realistic",
            "question": "Are Mn-strip and default-ignorable-strip realistic countermeasures?",
            "answer": (
                "Neither is realistic, but the alternative is not 'no sanitizer exists'. Exactly "
                "one real sanitizer ships on by default in the watermarking ecosystem: the "
                "lm-watermarking UnicodeSanitizer, which is NFC plus a fixed BMP regex plus "
                "Cc-strip, not Mn-strip or default-ignorable-strip. Measured here it leaves 366 "
                "of the 396 invisible code points intact, including U+034F, and it corrupts 5 of "
                "7 ordinary samples by replacing matches with spaces. Mn-strip and "
                "default-ignorable-strip remain undeployable on their own terms: Mn-strip "
                "corrupts Devanagari, Hebrew niqqud, Thai and emoji presentation, and "
                "default-ignorable-strip corrupts Persian ZWNJ, emoji ZWJ sequences and "
                "Devanagari conjuncts."
            ),
            "evidence": "evidence/h16-local/sanitizer-deployability.json",
        },
        {
            "id": "q3_is_the_gate_correctly_defined",
            "question": "Is the current sanitizer gate correctly defined for the product goal?",
            "answer": (
                "No, on two counts. First, scope: the frozen product contract classifies "
                "default_ignorable_removal and nonspacing_mark_removal as stress_only_not_frozen, "
                "but required_sanitizers_keep treats both as hard requirements, so H12-H15 gated "
                "on sanitizers the contract does not require. Second, form: the gate demands the "
                "carrier be a fixed point of every sanitizer, which is strictly stronger than the "
                "product goal that detection fail after sanitization."
            ),
            "evidence": "specs/fuckmark-user-visible-invariance-v1.contract.json",
        },
        {
            "id": "q4_were_h9_h15_trapped",
            "question": "Did H9-H15 become trapped in one mechanism family or framing?",
            "answer": (
                "The original H16 scan measured one context, latin A/B, not the advertised 12. "
                "On that A/B measurement, invisibility and required-sanitizer survival are "
                "complementary: every one of the 396 invisible code points in the Chromium pre "
                "font is Mn or Cf, and the required bundle strips exactly Mn, Cf and "
                "default-ignorable. The 12-context claim was an overclaim (Codex P1). The "
                "corrected 12-context rescan is recorded: union still 396, all Mn or Cf, "
                "intersection still 0. Arabic context 390, digit/punct/start 395; script "
                "contexts on DejaVu Sans Mono may be missing-glyph behavior. H9-H15 negatives "
                "still measure the fixed-point gate rather than a missing English-ASCII "
                "product carrier."
            ),
            "evidence": "evidence/h16-local/shaping-closure.json",
        },
    )

    payload = {
        "algorithm_version": CYCLE8_THREAT_MODEL_AUDIT_VERSION,
        "priority_zero": "exact_user_visible_text_preservation",
        "audit_target": "the H12-H15 required sanitizer bundle, not a new carrier search",
        "does_not_repeat_codepoint_enumeration": True,
        "control_carrier_hash": CYCLE8_CONTROL_CARRIER_HASH,
        "post_sanitizer_sequences_hash": CYCLE8_POST_SANITIZER_SEQUENCES_HASH,
        "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_V1_SNAPSHOT_HASH,
        "product_contract_hash": FROZEN_PRODUCT_CONTRACT_HASH,
        "closure": {
            "assigned_codepoints_scanned": ASSIGNED_CODEPOINTS_SCANNED,
            "shaping_contexts_advertised": SHAPING_CONTEXTS_ADVERTISED,
            "shaping_contexts_scanned": SHAPING_CONTEXTS_SCANNED,
            "original_h16_scan_context_ids": list(ORIGINAL_H16_SCAN_CONTEXT_IDS),
            "original_h16_scan_overclaimed_twelve_contexts": True,
            "twelve_context_rescan_status": TWELVE_CONTEXT_RESCAN_STATUS,
            "twelve_context_artifact": TWELVE_CONTEXT_ARTIFACT,
            "twelve_context_invisible_count": TWELVE_CONTEXT_INVISIBLE_COUNT,
            "twelve_context_invisible_in_product_contexts_count": TWELVE_CONTEXT_PRODUCT_INVISIBLE_COUNT,
            "twelve_context_intersection_count": TWELVE_CONTEXT_INTERSECTION_COUNT,
            "twelve_context_invisible_categories": {"Cf": 134, "Mn": 262},
            "twelve_context_per_context": dict(TWELVE_CONTEXT_PER_CONTEXT),
            "twelve_context_script_contexts_may_be_missing_glyph": True,
            "product_shaping_context_ids": list(PRODUCT_SHAPING_CONTEXT_IDS),
            "required_sanitizer_fixed_point_count": REQUIRED_SANITIZER_FIXED_POINT_COUNT,
            "shaping_invisible_count": shaping_invisible_codepoint_count(),
            "shaping_invisible_categories": invisible_categories,
            "shaping_invisible_outside_mn_cf": [
                category for category in invisible_categories if category not in ("Mn", "Cf")
            ],
            "shaping_invisible_all_stripped_by_required_bundle": (
                shaping_invisible_all_stripped_by_required_bundle()
            ),
            "intersection_count": 0,
            "substitution_class_render_identical_count": len(render_identical_ascii_substitutes()),
            "substitution_class_survivor_count": len(substitution_class_survivors()),
            "ascii_domain_is_normalization_fixed_point": ascii_domain_is_normalization_fixed_point(),
            "cc_required_sanitizer_fixed_point_count": len(control_survivors),
            "oracle_validation_sample": ORACLE_VALIDATION_SAMPLE,
            "oracle_validation_agreement": ORACLE_VALIDATION_AGREEMENT,
            "oracle_validation_disagreements": list(ORACLE_VALIDATION_DISAGREEMENTS),
        },
        "tokenizer_observations": [dict(row) for row in TOKENIZER_OBSERVATIONS],
        "sanitizer_deployability": damage,
        "real_world_sanitizer": real_world_sanitizer_observations(),
        "contract_stress_only_sanitizers": list(stress_only),
        "gate_promotes_stress_only_sanitizers": gate_promotes_stress_only_sanitizers(),
        "findings": [dict(row) for row in findings],
        "proposed_gate_v2": {
            "status": "proposal_only_not_active",
            "rationale": (
                "Gate on detection failure after sanitizers a platform can actually run, "
                "rather than on carrier fixed-point survival under sanitizers that corrupt "
                "ordinary text."
            ),
            "required_sanitizers": [
                "raw",
                "nfc",
                "nfkc",
                "cf_strip",
                "nfkc_cf_strip",
                "ws_collapse",
                "lm_watermarking_unicode_sanitizer",
            ],
            "added_since_first_draft": ["lm_watermarking_unicode_sanitizer"],
            "addition_reason": "the only sanitizer measured here that really ships on by default",
            "excluded_sanitizers": list(stress_only),
            "exclusion_reason": "not deployable without corrupting ordinary multilingual text",
            "condition": "detector must not detect after each required sanitizer",
            "still_requires": [
                "exact_user_visible_text_preservation",
                "ordinary_plain_text",
                "chromium_portability",
                "fresh_unspent_confirmation_corpus",
            ],
            "adoption": "requires an explicit product decision and a fresh confirmation run",
            "formalized_as": "cycle8-publishability-gate-v2",
            "formalization_status": "confirmed_not_product_authorized",
        },
        "proposed_gate_status_on_existing_evidence": proposed_gate_status_on_existing_evidence(),
        "stronger_priority_zero_safe_mechanism": None,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "required_sanitizer_bundle_not_weakened": True,
        "spent_confirmation_corpora_not_reused": True,
        "mix_sanitizer_gate": "FAIL",
        "boundary": (
            "The H12-H15 sanitizer gate cannot be satisfied by any mechanism that is both "
            "shaping-invisible in the original H16 latin A/B oracle and a fixed point of the "
            "required bundle, and that A/B measurement found 396 invisible code points, all "
            "Mn or Cf. H16 advertised 12 shaping contexts but the committed scan executed "
            "only latin A/B; that overclaim is recorded here and the scan tool now iterates "
            "all 12 contexts. Substitution adds nothing: 14 code points render as an ASCII "
            "space and none survives the bundle. Canonical re-encoding adds nothing either, "
            "because the declared ASCII input domain is a fixed point of all four "
            "normalization forms. Deletion and reordering change visible text. The only "
            "remainder in the whole space on the A/B oracle is C0/C1, which the "
            "ordinary-plain-text requirement excludes. Meanwhile the two sanitizers that "
            "close the space, Mn-strip and default-ignorable-strip, are marked "
            "stress_only_not_frozen by the frozen product contract, are applied by no "
            "production detector tokenizer measured here, and corrupt ordinary Devanagari, "
            "Hebrew, Thai, Persian and emoji text. That does not mean no sanitizer is real. "
            "Exactly one ships on by default, the lm-watermarking UnicodeSanitizer, and it "
            "is NFC plus a fixed BMP regex plus Cc-strip: it keeps 366 of the 396 invisible "
            "code points including U+034F, removes U+FE00, injects spurious spaces, corrupts "
            "5 of 7 ordinary samples, and does not restore the unwatermarked source. Measured "
            "on the exploratory lane, seed 890000, mix still evades it at 0 of 48 watermarked "
            "rows against 47 of 48 pristine, exactly as under raw. That sanitizer collapses "
            "space runs and strips Cc, so it could have suppressed detection by itself, but "
            "run on carrier-free watermarked text it still detects 46 of 48, which attributes "
            "the drop to the carrier rather than to the sanitizer. The one variant that "
            "restores detection is the required bundle itself, at 47 of 48, and it does so "
            "only because it reconstructs the original string on all 96 rows. Read against "
            "the already recorded frozen confirmation evidence, the frozen conditions of the "
            "proposed gate are also met: identity detects 185 of 192, mix detects 0 of 192, "
            "every frozen sanitizer still detects 0, and visible text passes 192 of 192. "
            "The real-sanitizer condition is now confirmation-grade on seeds "
            "1200000/1210000/1220000: mix 0/192 after the UnicodeSanitizer, carrier-free "
            "182/192, drop 6 from identity 188/192. Gate v2 is confirmed_not_product_authorized. "
            "This record does not product-authorize mix: the required bundle is unchanged, the v1 mix "
            "sanitizer gate stays FAIL, and the public CLI stays empty."
        ),
    }
    return {**payload, "audit_hash": sha256_json(payload)}


def write_threat_model_audit_spec(path: str | Path | None = None) -> Path:
    destination = Path(path) if path is not None else Path(CYCLE8_THREAT_MODEL_AUDIT_PATH)
    payload = threat_model_audit_payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_json_text(payload) + "\n", encoding="utf-8")
    return destination


def load_threat_model_audit(path: str | Path | None = None) -> dict[str, object]:
    destination = Path(path) if path is not None else Path(CYCLE8_THREAT_MODEL_AUDIT_PATH)
    return json.loads(destination.read_text(encoding="utf-8"))


def assert_threat_model_audit_committed() -> None:
    path = Path(CYCLE8_THREAT_MODEL_AUDIT_PATH)
    if not path.is_file():
        raise ValueError("threat model audit spec is not committed")
    disk = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in disk.items() if key != "audit_hash"}
    digest = sha256_json(body)
    if disk.get("audit_hash") != digest:
        raise ValueError("threat model audit spec hash mismatch")
    if CYCLE8_THREAT_MODEL_AUDIT_HASH != "0" * 64 and digest != CYCLE8_THREAT_MODEL_AUDIT_HASH:
        raise ValueError("threat model audit spec hash is not the frozen digest")
    if disk["product_authorized"] is True:
        raise ValueError("threat model audit must not product-authorize a mechanism")
    if disk["stronger_priority_zero_safe_mechanism"] is not None:
        raise ValueError("threat model audit must not claim a stronger Priority-Zero mechanism")
    if disk["mix_gate_not_rewritten"] is not True:
        raise ValueError("threat model audit must not rewrite the mix sanitizer gate")
    if disk["mix_sanitizer_gate"] != "FAIL":
        raise ValueError("threat model audit must keep mix sanitizer FAIL")
    if disk["required_sanitizer_bundle_not_weakened"] is not True:
        raise ValueError("threat model audit must not weaken the required sanitizer bundle")
    if disk["proposed_gate_v2"]["status"] != "proposal_only_not_active":
        raise ValueError("the proposed gate must remain a proposal")
    if disk["closure"]["original_h16_scan_overclaimed_twelve_contexts"] is not True:
        raise ValueError("the original H16 12-context overclaim must remain recorded")
    if disk["closure"]["shaping_contexts_scanned"] != 1:
        raise ValueError("the original H16 scan executed one context")
    if disk["closure"]["twelve_context_rescan_status"] != "recorded":
        raise ValueError("the 12-context rescan must remain recorded")
    if disk["closure"]["twelve_context_intersection_count"] != 0:
        raise ValueError("the 12-context intersection must be empty")
    if disk["closure"]["twelve_context_invisible_count"] != 396:
        raise ValueError("the 12-context union must not rewrite the 396 count")
    if disk["proposed_gate_v2"]["formalized_as"] != "cycle8-publishability-gate-v2":
        raise ValueError("H16 must point at the formal Gate v2 spec")
    if disk["closure"]["intersection_count"] != 0:
        raise ValueError("closure intersection must be empty")
    if disk["closure"]["shaping_invisible_outside_mn_cf"] != []:
        raise ValueError("invisible code points must all be Mn or Cf")
    if disk["closure"]["shaping_invisible_all_stripped_by_required_bundle"] is not True:
        raise ValueError("every invisible code point must die to the required bundle")
    if disk["closure"]["substitution_class_survivor_count"] != 0:
        raise ValueError("substitution class must have no sanitizer survivor")
    status = disk["proposed_gate_status_on_existing_evidence"]
    if status["source"] != "already-run frozen confirmation evidence, no new corpus":
        raise ValueError("the proposed gate reading must not consume a fresh corpus")
    if status["proposed_gate_v2_fully_satisfied"] is not False:
        raise ValueError("the proposed gate must not be reported as fully satisfied")
    if status["confirmation_grade"] is not False:
        raise ValueError("an exploratory measurement must not be labelled confirmation grade")
    real = disk["real_world_sanitizer"]
    if real["restores_the_unwatermarked_source"] is not False:
        raise ValueError("the real sanitizer measurement must record whether the source is restored")
    detector = real["detection_after_this_sanitizer"]
    if detector["role"] != "exploratory_only_not_confirmation":
        raise ValueError("the detector measurement must stay exploratory")
    if detector["seed_base"] in (830000, 840000, 850000, 950000):
        raise ValueError("the detector measurement must not use a spent or forbidden seed")
    if detector["confirmation_grade"] is not False:
        raise ValueError("an exploratory detector run must not be labelled confirmation grade")
    if detector["real_sanitizer_carrier_free_detected"] <= detector["watermarked_rows"] // 2:
        raise ValueError("the carrier-free control must show the real sanitizer preserves detection")
    live = threat_model_audit_payload()
    if live != disk:
        raise ValueError("threat model audit spec does not match the live payload")
