from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from ..cycle7.fixtures import CONTRACTION_SPARSE, QUOTE_INTERIOR
from ..cycle7.whitespace_collapse import CYCLE7_SANITIZER_VARIANT_IDS, sanitize_cycle7_variant
from ..hashing import sha256_json, sha256_text
from ..product.registry import product_transform_registry
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..transforms.schema import CandidateRejectionReason
from .letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    apply_letter_alternating_mix,
    letter_mix_protected_blocked_count,
    select_letter_mix_sites,
)
from .registry import (
    apply_letter_space_scheduled,
    cycle8_letter_carrier_registry,
    cycle8_letter_space_carrier_registry,
    cycle8_space_carrier_registry,
    cycle8_space_wordfinal_carrier_registry,
    letter_payload_repeats,
    select_nonoverlapping_candidate_ids,
)
from .tokenizer_screen import GPT2_FIXTURE, resynchronization_metrics


CYCLE8_FIXTURE_COMPARE_VERSION = "cycle8-fixture-compare-v1"
CYCLE8_IDENTITY_ARM_ID = "identity"
CYCLE8_U200C_SPACE_ARM_ID = "u200c-space-x1"
CYCLE8_U034F_SPACE_ARM_ID = "u034f-space-x1"
CYCLE8_U034F_SPACE_RUN_ARM_ID = "u034f-space-x8"
CYCLE8_UFE00_SPACE_ARM_ID = "ufe00-space-x1"
CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID = "u034f-space-wordfinal-x1"
CYCLE8_U034F_LETTER_ARM_ID = "u034f-letter-x1"
CYCLE8_U034F_LETTER_X2_ARM_ID = "u034f-letter-x2"
CYCLE8_U034F_LETTER_X4_ARM_ID = "u034f-letter-x4"
CYCLE8_U034F_LETTER_BOOST_ARM_ID = "u034f-letter-boost-v1"
CYCLE8_U034F_LETTER_SCHEDULE_SPACE_ARM_ID = "u034f-letter-schedule-space-v1"
CYCLE8_U034F_LETTER_SPACE_ARM_ID = "u034f-letter-space-x1"
CYCLE8_UFE00_LETTER_ARM_ID = "ufe00-letter-x1"
CYCLE8_UFE00_LETTER_X2_ARM_ID = "ufe00-letter-x2"
CYCLE8_UFE00_LETTER_SPACE_ARM_ID = "ufe00-letter-space-x1"
CYCLE8_LETTER_ALT_ARM_ID = "u034f-ufe00-letter-alt-v1"
CYCLE8_DETECTOR_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U200C_SPACE_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U034F_SPACE_RUN_ARM_ID,
)
CYCLE8_SCALE_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
)
CYCLE8_DENSITY_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
)
CYCLE8_LETTER_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
)
CYCLE8_BENCHMARK_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
)
CYCLE8_MARGIN_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
    CYCLE8_U034F_LETTER_SPACE_ARM_ID,
)
CYCLE8_MIX_ARM_IDS = (
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_LETTER_ARM_ID,
    CYCLE8_LETTER_ALT_ARM_ID,
)
CYCLE8_FIXTURE_ARM_IDS = (
    *CYCLE8_DETECTOR_ARM_IDS,
    CYCLE8_UFE00_SPACE_ARM_ID,
)
CYCLE8_MAX_ATTEMPTS = 64
_ARM_SPEC = {
    CYCLE8_IDENTITY_ARM_ID: None,
    CYCLE8_U200C_SPACE_ARM_ID: (0x200C, 1),
    CYCLE8_U034F_SPACE_ARM_ID: (0x034F, 1),
    CYCLE8_U034F_SPACE_RUN_ARM_ID: (0x034F, 8),
    CYCLE8_UFE00_SPACE_ARM_ID: (0xFE00, 1),
    CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID: (0x034F, 1),
    CYCLE8_U034F_LETTER_ARM_ID: (0x034F, 1),
    CYCLE8_U034F_LETTER_X2_ARM_ID: (0x034F, 2),
    CYCLE8_U034F_LETTER_X4_ARM_ID: (0x034F, 4),
    CYCLE8_U034F_LETTER_BOOST_ARM_ID: (0x034F, 1),
    CYCLE8_U034F_LETTER_SCHEDULE_SPACE_ARM_ID: (0x034F, 1),
    CYCLE8_U034F_LETTER_SPACE_ARM_ID: (0x034F, 1),
    CYCLE8_UFE00_LETTER_ARM_ID: (0xFE00, 1),
    CYCLE8_UFE00_LETTER_X2_ARM_ID: (0xFE00, 2),
    CYCLE8_UFE00_LETTER_SPACE_ARM_ID: (0xFE00, 1),
    CYCLE8_LETTER_ALT_ARM_ID: (0x034F, 1),
}


def cycle8_fixture_samples() -> tuple[tuple[str, str], ...]:
    return (
        ("gpt2-screen", GPT2_FIXTURE),
        ("contraction-sparse", CONTRACTION_SPARSE),
        ("quote-interior", QUOTE_INTERIOR),
        ("url-protected", "See https://example.com/do-not-touch and continue the notes."),
    )


def arm_approved_carriers(arm_id: str) -> tuple[int, ...]:
    if arm_id == CYCLE8_LETTER_ALT_ARM_ID:
        return LETTER_MIX_APPROVED_CARRIERS
    spec = _ARM_SPEC[arm_id]
    if spec is None:
        return ()
    return (spec[0],)


def arm_registry(arm_id: str, source_text: str | None = None):
    if arm_id == CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID:
        return cycle8_space_wordfinal_carrier_registry(0x034F)
    if arm_id == CYCLE8_U034F_LETTER_ARM_ID:
        return cycle8_letter_carrier_registry(0x034F)
    if arm_id == CYCLE8_U034F_LETTER_X2_ARM_ID:
        return cycle8_letter_carrier_registry(0x034F, repeats=2)
    if arm_id == CYCLE8_U034F_LETTER_X4_ARM_ID:
        return cycle8_letter_carrier_registry(0x034F, repeats=4)
    if arm_id == CYCLE8_UFE00_LETTER_ARM_ID:
        return cycle8_letter_carrier_registry(0xFE00)
    if arm_id == CYCLE8_UFE00_LETTER_X2_ARM_ID:
        return cycle8_letter_carrier_registry(0xFE00, repeats=2)
    if arm_id == CYCLE8_U034F_LETTER_SPACE_ARM_ID:
        return cycle8_letter_space_carrier_registry(0x034F)
    if arm_id == CYCLE8_UFE00_LETTER_SPACE_ARM_ID:
        return cycle8_letter_space_carrier_registry(0xFE00)
    if arm_id == CYCLE8_U034F_LETTER_BOOST_ARM_ID:
        base = cycle8_letter_carrier_registry(0x034F)
        if source_text is None:
            return base
        enumeration = base.enumerate(source_text)
        selected = select_nonoverlapping_candidate_ids(enumeration, registry=base)
        repeats = letter_payload_repeats(len(selected))
        return cycle8_letter_carrier_registry(0x034F, repeats=repeats)
    if arm_id == CYCLE8_LETTER_ALT_ARM_ID:
        return cycle8_letter_carrier_registry(0x034F)
    spec = _ARM_SPEC[arm_id]
    if spec is None:
        return product_transform_registry()
    codepoint, repeats = spec
    return cycle8_space_carrier_registry(codepoint, repeats=repeats)


def measure_carrier_arm(
    *,
    arm_id: str,
    source_sample_id: str,
    source_text: str,
    encoder: Callable[[str], tuple[int, ...]] | None = None,
) -> dict[str, object]:
    if arm_id not in _ARM_SPEC:
        raise ValueError("unknown Cycle 8 arm id")
    if not isinstance(source_sample_id, str) or not source_sample_id:
        raise ValueError("source_sample_id must be a non-empty string")
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    registry = arm_registry(arm_id, source_text)
    approved = arm_approved_carriers(arm_id)
    fail_closed_identity = False
    mix_protected_blocked = None
    if arm_id == CYCLE8_LETTER_ALT_ARM_ID:
        sites = select_letter_mix_sites(source_text)
        transformed = apply_letter_alternating_mix(source_text)
        selected = tuple(f"letter-mix-{index}" for index in sites)
        mix_protected_blocked = letter_mix_protected_blocked_count(source_text)

        class _MixEnumeration:
            candidates = ()
            rejections = ()

        enumeration = _MixEnumeration()
        if sites and transformed == source_text:
            fail_closed_identity = True
    elif arm_id == CYCLE8_U034F_LETTER_SCHEDULE_SPACE_ARM_ID:
        transformed = apply_letter_space_scheduled(source_text)
        letter_registry = cycle8_letter_carrier_registry(0x034F)
        enumeration = letter_registry.enumerate(source_text)
        selected = select_nonoverlapping_candidate_ids(enumeration, registry=letter_registry)
        if selected and transformed == source_text:
            fail_closed_identity = True
    else:
        enumeration = registry.enumerate(source_text)
        selected = select_nonoverlapping_candidate_ids(enumeration, registry=registry)
        transformed = source_text
        if selected:
            try:
                transformed = registry.apply(enumeration, selected).output_text
            except ValueError:
                transformed = source_text
                selected = ()
                fail_closed_identity = True
    visible_ok = is_carrier_insertion_v1(source_text, transformed, approved)
    inserted = 0
    for codepoint in approved:
        carrier = chr(codepoint)
        inserted += transformed.count(carrier) - source_text.count(carrier)
    sanitizers = {}
    for variant in CYCLE7_SANITIZER_VARIANT_IDS:
        sanitized = sanitize_cycle7_variant(variant, transformed)
        sanitizers[variant] = {
            "equals_source": sanitized == source_text,
            "equals_transformed": sanitized == transformed,
            "visible_ok": is_carrier_insertion_v1(source_text, sanitized, approved),
            "text_hash": sha256_text(sanitized),
        }
    tokenizer = None
    if encoder is not None:
        tokenizer = resynchronization_metrics(encoder(source_text), encoder(transformed))
    quote_blocked = sum(
        1 for rejection in enumeration.rejections if rejection.reason is CandidateRejectionReason.QUOTE_POLICY_BLOCKED
    )
    protected_blocked = sum(
        1 for rejection in enumeration.rejections if rejection.reason is CandidateRejectionReason.PROTECTED_OVERLAP
    )
    invariant_blocked = sum(
        1 for rejection in enumeration.rejections if rejection.reason is CandidateRejectionReason.HARD_INVARIANT_FAILED
    )
    candidate_count = len(enumeration.candidates)
    if mix_protected_blocked is not None:
        quote_blocked = 0
        protected_blocked = mix_protected_blocked
        invariant_blocked = 0
        candidate_count = len(selected) + mix_protected_blocked
    return {
        "arm_id": arm_id,
        "source_sample_id": source_sample_id,
        "source_text_hash": sha256_text(source_text),
        "transformed_text": transformed,
        "transformed_text_hash": sha256_text(transformed),
        "candidate_count": candidate_count,
        "selected_count": len(selected),
        "inserted_count": inserted,
        "utf8_overhead": len(transformed.encode("utf-8")) - len(source_text.encode("utf-8")),
        "visible_ok": visible_ok,
        "projected_equals_source": project_visible_v1(transformed, approved) == source_text,
        "quote_blocked_count": quote_blocked,
        "protected_blocked_count": protected_blocked,
        "hard_invariant_blocked_count": invariant_blocked,
        "fail_closed_identity": fail_closed_identity,
        "sanitizers": sanitizers,
        "tokenizer": tokenizer,
    }


def summarize_arm(measurement: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in measurement.items() if key != "transformed_text"}


def run_fixture_compare(
    encoder: Callable[[str], tuple[int, ...]] | None = None,
    *,
    arm_ids: Sequence[str] = CYCLE8_FIXTURE_ARM_IDS,
) -> dict[str, object]:
    rows = []
    visible_pass = 0
    visible_total = 0
    for sample_id, text in cycle8_fixture_samples():
        arms = {}
        for arm_id in arm_ids:
            measurement = measure_carrier_arm(
                arm_id=arm_id,
                source_sample_id=sample_id,
                source_text=text,
                encoder=encoder,
            )
            arms[arm_id] = summarize_arm(measurement)
            visible_total += 1
            if measurement["visible_ok"] is True:
                visible_pass += 1
        rows.append(
            {
                "source_sample_id": sample_id,
                "source_text_hash": sha256_text(text),
                "arms": arms,
            }
        )
    payload = {
        "algorithm_version": CYCLE8_FIXTURE_COMPARE_VERSION,
        "arm_ids": tuple(arm_ids),
        "encoder": "unavailable" if encoder is None else "gpt2",
        "visible_pass_count": visible_pass,
        "visible_total_count": visible_total,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "rows": tuple(rows),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
