from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ..config import canonical_json_text
from ..hashing import sha256_json
from ..product.contract import FROZEN_PRODUCT_CONTRACT_HASH, product_contract_payload
from ..sanitizer_robustness import strip_unicode_format_characters
from .benchmark import strip_default_ignorable, strip_nonspacing_marks
from .control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from .post_sanitizer_sequences import CYCLE8_POST_SANITIZER_SEQUENCES_HASH
from .publishability import (
    CYCLE8_MIX_PUBLISHABILITY_HASH,
    build_mix_confirmation_scorecard,
    measure_mix_fixtures,
)

CYCLE8_THREAT_MODEL_AUDIT_VERSION = "cycle8-threat-model-audit-v1"
CYCLE8_THREAT_MODEL_AUDIT_PATH = "specs/cycle8/fuckmark-cycle8-threat-model-audit-v1.json"
CYCLE8_THREAT_MODEL_AUDIT_HASH = "8e96a5c26b3e0ddbb403bf89333074d298115a1288a0a992ced3f7f19b567cdb"

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
SHAPING_CONTEXTS_SCANNED = 12
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
        "proposed_gate_v2_already_satisfied": (
            all(value == 0 for value in detected.values())
            and durability["frozen_sanitizers_match_raw"] is True
            and scorecard["effectiveness"]["transformed_wm"]["rate"] == "0/192"
            and scorecard["visibility"]["watermarked_pass_rate"] == "192/192"
            and measured["frozen_sanitizer_survive"] == measured["frozen_sanitizer_total"]
        ),
        "adoption_still_blocked_on": "explicit product decision, not further carrier research",
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
                "No. They are not deployable. Mn-strip corrupts Devanagari, Hebrew niqqud, Thai "
                "and emoji presentation. Default-ignorable-strip corrupts Persian ZWNJ, emoji ZWJ "
                "sequences and Devanagari conjuncts. A platform running either would corrupt "
                "ordinary user text in widely used writing systems, so no detector vendor can "
                "apply them as a preprocessing step."
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
                "The framing was not merely narrow, it was empty. Invisibility and required "
                "sanitizer survival are complementary by construction: every one of the 396 "
                "invisible code points in the Chromium pre font is Mn or Cf, and the required "
                "bundle strips exactly Mn, Cf and default-ignorable. No enumeration of code "
                "points, sequences or shaping contexts could have found a survivor, so the "
                "H9-H15 negatives measure the gate rather than Unicode."
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
        "mix_publishability_hash": CYCLE8_MIX_PUBLISHABILITY_HASH,
        "product_contract_hash": FROZEN_PRODUCT_CONTRACT_HASH,
        "closure": {
            "assigned_codepoints_scanned": ASSIGNED_CODEPOINTS_SCANNED,
            "shaping_contexts_scanned": SHAPING_CONTEXTS_SCANNED,
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
            "required_sanitizers": ["raw", "nfc", "nfkc", "cf_strip", "nfkc_cf_strip", "ws_collapse"],
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
        },
        "proposed_gate_status_on_existing_evidence": proposed_gate_status_on_existing_evidence(),
        "stronger_priority_zero_safe_mechanism": None,
        "product_authorized": False,
        "mix_gate_not_rewritten": True,
        "required_sanitizer_bundle_not_weakened": True,
        "spent_confirmation_corpora_not_reused": True,
        "mix_sanitizer_gate": "FAIL",
        "boundary": (
            "The H12-H15 sanitizer gate cannot be satisfied by any mechanism, and the reason is "
            "structural rather than empirical. Across 286719 assigned code points and 12 shaping "
            "contexts, the Chromium pre font renders 396 code points invisibly and every one is "
            "Mn or Cf, which the required bundle strips by definition. Substitution adds nothing: "
            "14 code points render as an ASCII space and none survives the bundle. Canonical "
            "re-encoding adds nothing either, because the declared ASCII input domain is a fixed "
            "point of all four normalization forms. Deletion and reordering change visible text. "
            "The only remainder in the whole space is C0/C1, which the ordinary-plain-text "
            "requirement excludes. Meanwhile the two sanitizers that close the space, Mn-strip "
            "and default-ignorable-strip, are marked stress_only_not_frozen by the frozen product "
            "contract, are applied by no production detector tokenizer measured here, and corrupt "
            "ordinary Devanagari, Hebrew, Thai, Persian and emoji text. Read against the already "
            "recorded frozen confirmation evidence, and without running any new corpus, the "
            "proposed gate is already met: identity detects 185 of 192, mix detects 0 of 192, "
            "every deployable sanitizer still detects 0, and visible text passes 192 of 192. The "
            "correct next step is therefore a product decision on the gate, not a further carrier "
            "search. This record does not make that decision: the required bundle is unchanged, "
            "the proposal stays inactive, and mix stays FAIL."
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
    if status["adoption_still_blocked_on"] != "explicit product decision, not further carrier research":
        raise ValueError("the audit must not treat the gate proposal as adopted")
    live = threat_model_audit_payload()
    if live != disk:
        raise ValueError("threat model audit spec does not match the live payload")
