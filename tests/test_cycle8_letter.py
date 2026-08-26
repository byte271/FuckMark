from fuckmark.cli import process_text
from fuckmark.cycle8.compare import (
    CYCLE8_LETTER_ARM_IDS,
    CYCLE8_U034F_LETTER_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    measure_carrier_arm,
)
from fuckmark.cycle8.ledger import CYCLE8_LETTER_EXPLORATORY_ROLE, assert_cycle8_development_seed
from fuckmark.cycle8.registry import (
    LETTER_CARRIER_MAX_SELECTED,
    apply_all_candidates,
    cycle8_letter_carrier_registry,
    cycle8_space_carrier_registry,
)
from fuckmark.seeds.ledger import CYCLE8_LETTER_EXPLORATORY_SEED_BASE, assert_new_cycle8_letter_generation_seed
from fuckmark.product.carrier_invariants import validate_product_carrier_invariants
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.transforms.cycle7_quote_policy import PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID
from fuckmark.transforms.hard_invariants import HARD_INVARIANT_ALGORITHM_VERSION, validate_hard_invariants
from fuckmark.transforms.registry import release_transform_registry
from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus


def test_letter_carrier_preserves_visible_words_including_cannot_and_dont() -> None:
    registry = cycle8_letter_carrier_registry(0x034F)
    assert registry.quote_policy_id == PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID
    assert registry.word_signature_source == "visible"
    assert registry.max_selected == LETTER_CARRIER_MAX_SELECTED == 192
    source = "We never wait and I don't agree."
    applied = apply_all_candidates(registry, source)
    assert applied != source
    assert "\u034f" in applied
    assert is_carrier_insertion_v1(source, applied, (0x034F,))
    assert project_visible_v1(applied, (0x034F,)) == source
    assert validate_product_carrier_invariants(source, applied, approved_carriers=(0x034F,)).status is InvariantStatus.PASS
    assert validate_hard_invariants(source, applied).status is InvariantStatus.FAIL
    assert HARD_INVARIANT_ALGORITHM_VERSION == "hard-invariant-validator-v4"
    assert "never" in applied.replace("\u034f", "")
    assert "don't" in applied.replace("\u034f", "")
    assert "d\u034fo" in applied
    assert "n\u034f'" in applied
    assert applied.count("\u034f") >= 12
    assert process_text(source) == source
    assert release_transform_registry().rules == ()


def test_letter_carrier_inserts_inside_quotes_and_blocks_urls_and_paths() -> None:
    registry = cycle8_letter_carrier_registry(0x034F)
    quoted = 'He said "hello world" and left.'
    applied = apply_all_candidates(registry, quoted)
    assert is_carrier_insertion_v1(quoted, applied, (0x034F,))
    assert project_visible_v1(applied, (0x034F,)) == quoted
    interior = applied[applied.index('"') + 1 : applied.rindex('"')]
    assert "\u034f" in interior
    machine = "See https://example.com/do-not-touch and /tmp/foo.txt in the notes."
    enumeration = registry.enumerate(machine)
    url = "https://example.com/do-not-touch"
    path = "/tmp/foo.txt"
    url_start = machine.index(url)
    url_end = url_start + len(url)
    path_start = machine.index(path)
    path_end = path_start + len(path)
    for candidate in enumeration.candidates:
        assert candidate.end <= url_start or candidate.start >= url_end
        assert candidate.end <= path_start or candidate.start >= path_end
    applied_machine = apply_all_candidates(registry, machine)
    assert "https://example.com/do-not-touch" in applied_machine.replace("\u034f", "")
    assert "/tmp/foo.txt" in applied_machine.replace("\u034f", "")
    assert is_carrier_insertion_v1(machine, applied_machine, (0x034F,))
    assert any(
        rejection.reason is CandidateRejectionReason.PROTECTED_OVERLAP for rejection in enumeration.rejections
    )


def test_letter_arm_is_denser_than_space_and_space_x1_still_blocks_quotes() -> None:
    source = 'Keep "do not change this" but I do not agree.'
    space = measure_carrier_arm(
        arm_id=CYCLE8_U034F_SPACE_ARM_ID,
        source_sample_id="letter-space-control",
        source_text=source,
    )
    letter = measure_carrier_arm(
        arm_id=CYCLE8_U034F_LETTER_ARM_ID,
        source_sample_id="letter-x1",
        source_text=source,
    )
    assert space["visible_ok"] is True
    assert letter["visible_ok"] is True
    assert int(letter["inserted_count"]) > int(space["inserted_count"])
    assert space["fail_closed_identity"] is False
    assert letter["fail_closed_identity"] is False
    quoted_space = str(space["transformed_text"])
    quoted_letter = str(letter["transformed_text"])
    space_interior = quoted_space[quoted_space.index('"') + 1 : quoted_space.rindex('"')]
    letter_interior = quoted_letter[quoted_letter.index('"') + 1 : quoted_letter.rindex('"')]
    assert "\u034f" not in space_interior
    assert "\u034f" in letter_interior
    assert process_text("I do not agree.") == "I do not agree."
    assert cycle8_space_carrier_registry(0x034F).quote_policy_id != PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID
    assert cycle8_space_carrier_registry(0x034F).word_signature_source == "raw"
    assert cycle8_space_carrier_registry(0x034F).max_selected is None


def test_letter_carrier_respects_max_selected_cap() -> None:
    source = "abcdefghijklmnopqrstuvwxyz" * 12
    uncapped = cycle8_letter_carrier_registry(0x034F, max_selected=None)
    capped = cycle8_letter_carrier_registry(0x034F, max_selected=16)
    uncapped_text = apply_all_candidates(uncapped, source)
    capped_text = apply_all_candidates(capped, source)
    assert uncapped_text.count("\u034f") > 16
    assert capped_text.count("\u034f") == 16
    assert is_carrier_insertion_v1(source, capped_text, (0x034F,))
    assert project_visible_v1(capped_text, (0x034F,)) == source


def test_letter_seed_is_reserved_and_release_registry_stays_empty() -> None:
    assert CYCLE8_LETTER_ARM_IDS == ("identity", CYCLE8_U034F_LETTER_ARM_ID)
    assert_new_cycle8_letter_generation_seed(CYCLE8_LETTER_EXPLORATORY_SEED_BASE)
    assert_cycle8_development_seed(CYCLE8_LETTER_EXPLORATORY_SEED_BASE, role=CYCLE8_LETTER_EXPLORATORY_ROLE)
    assert process_text("I do not agree.") == "I do not agree."
    assert release_transform_registry().rules == ()
