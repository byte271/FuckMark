import pytest

from fuckmark.hashing import sha256_json
from fuckmark.transforms.fidelity_evidence import FidelityLabel, FidelityReviewSample
from fuckmark.transforms.fidelity_review_packets import (
    BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
    BlindReviewPacket,
    BlindReviewPacketVerificationError,
    bind_blind_review_judgments,
    build_blind_review_packet,
    verify_blind_review_packet,
)
from fuckmark.transforms.lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID
from fuckmark.transforms.lexical_rules import development_lexical_rules


def _samples(count: int = 8) -> tuple[FidelityReviewSample, ...]:
    rule_hash = development_lexical_rules()[0].rule_hash
    return tuple(
        FidelityReviewSample.create(
            rule_hash,
            f"packet-sample-{index:02d}",
            f"For example, use option {index}.",
            f"For instance, use option {index}.",
        )
        for index in range(count)
    )


def test_packet_sampling_and_orientation_are_deterministic() -> None:
    samples = _samples()
    first = build_blind_review_packet(samples, seed=17, sample_count=5)
    second = build_blind_review_packet(tuple(reversed(samples)), seed=17, sample_count=5)
    assert first == second
    assert first.algorithm_version == BLIND_REVIEW_PACKET_ALGORITHM_VERSION
    assert first.sample_count == 5
    verify_blind_review_packet(first, samples)


def test_public_packet_hides_source_mapping_and_randomizes_display_order() -> None:
    packet = build_blind_review_packet(_samples(), seed=19, sample_count=6)
    public = packet.public_payload()
    assert set(public) == {"algorithm_version", "review_policy_id", "packet_hash", "items"}
    assert public["review_policy_id"] == BLIND_HUMAN_REVIEW_POLICY_ID
    assert len(public["items"]) == 6
    for item in public["items"]:
        assert set(item) == {"item_id", "text_a", "text_b", "item_hash"}
        assert "sample_id" not in item
        assert "sample_hash" not in item
        assert "source_on_left" not in item
    assert tuple(item["item_id"] for item in public["items"]) != tuple(entry.item_id for entry in packet.entries)


def test_seed_change_changes_packet_identity_and_position_mapping() -> None:
    samples = _samples()
    first = build_blind_review_packet(samples, seed=23, sample_count=8)
    second = build_blind_review_packet(samples, seed=24, sample_count=8)
    assert first.packet_hash != second.packet_hash
    assert tuple(entry.item_id for entry in first.entries) != tuple(entry.item_id for entry in second.entries)
    assert tuple((entry.source_on_left, entry.display_key) for entry in first.entries) != tuple(
        (entry.source_on_left, entry.display_key) for entry in second.entries
    )


def test_bound_judgments_reveal_only_after_packet_validation() -> None:
    samples = _samples(4)
    packet = build_blind_review_packet(samples, seed=31)
    labels = {entry.item_id: FidelityLabel.EQUIVALENT_OR_MINOR for entry in packet.entries}
    judgments = bind_blind_review_judgments(packet, samples, "reviewer-a", labels)
    assert tuple(value.sample_id for value in judgments) == tuple(sorted(value.sample_id for value in samples))
    assert all(value.review_sample_hash in {sample.sample_hash for sample in samples} for value in judgments)


def test_packet_replay_rejects_changed_source_pool() -> None:
    samples = _samples(5)
    packet = build_blind_review_packet(samples, seed=37, sample_count=3)
    altered = (
        FidelityReviewSample.create(
            samples[0].rule_hash,
            "altered-sample",
            "For example, use an altered option.",
            "For instance, use an altered option.",
        ),
        *samples[1:],
    )
    with pytest.raises(BlindReviewPacketVerificationError, match="does not replay"):
        verify_blind_review_packet(packet, altered)


def test_packet_replay_rejects_forged_entry_set() -> None:
    samples = _samples(6)
    packet = build_blind_review_packet(samples, seed=41, sample_count=4)
    other = build_blind_review_packet(samples, seed=42, sample_count=4)
    payload = {
        "algorithm_version": packet.algorithm_version,
        "rule_hash": packet.rule_hash,
        "review_policy_id": packet.review_policy_id,
        "seed": packet.seed,
        "entries": other.entries,
    }
    forged = BlindReviewPacket(
        packet.algorithm_version,
        packet.rule_hash,
        packet.review_policy_id,
        packet.seed,
        other.entries,
        sha256_json(payload),
    )
    with pytest.raises(BlindReviewPacketVerificationError, match="does not replay"):
        verify_blind_review_packet(forged, samples)


def test_duplicate_text_pairs_are_not_counted_as_independent_reviews() -> None:
    samples = _samples(2)
    duplicate = FidelityReviewSample.create(
        samples[0].rule_hash,
        "packet-sample-duplicate",
        samples[0].source_text,
        samples[0].transformed_text,
    )
    with pytest.raises(ValueError, match="duplicate reviewed text pairs"):
        build_blind_review_packet((*samples, duplicate), seed=43)


def test_labels_must_cover_every_opaque_packet_item() -> None:
    packet = build_blind_review_packet(_samples(3), seed=47)
    labels = {packet.entries[0].item_id: FidelityLabel.EQUIVALENT_OR_MINOR}
    with pytest.raises(BlindReviewPacketVerificationError, match="exactly one label"):
        bind_blind_review_judgments(packet, _samples(3), "reviewer-a", labels)
