from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .fidelity_evidence import BlindReviewJudgment, FidelityLabel, FidelityReviewSample
from .lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID


BLIND_REVIEW_PACKET_ALGORITHM_VERSION = "blind-fidelity-review-packet-v1"


class BlindReviewPacketVerificationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BlindReviewPacketEntry:
    item_id: str
    rule_hash: str
    sample_id: str
    sample_hash: str
    source_text: str
    transformed_text: str
    source_text_hash: str
    transformed_text_hash: str
    source_on_left: bool
    display_key: str
    entry_hash: str

    def __post_init__(self) -> None:
        require_sha256("item_id", self.item_id)
        require_sha256("rule_hash", self.rule_hash)
        require_clean_string("sample_id", self.sample_id)
        require_sha256("sample_hash", self.sample_hash)
        for name, value in (("source_text", self.source_text), ("transformed_text", self.transformed_text)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.source_text == self.transformed_text:
            raise ValueError("blind review packet entries must change text")
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.source_text_hash != sha256_text(self.source_text):
            raise ValueError("source_text_hash does not match source_text")
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        require_bool("source_on_left", self.source_on_left)
        require_sha256("display_key", self.display_key)
        require_sha256("entry_hash", self.entry_hash)
        if self.entry_hash != sha256_json(self._payload()):
            raise ValueError("entry_hash does not match blind review packet entry")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
            "item_id": self.item_id,
            "rule_hash": self.rule_hash,
            "sample_id": self.sample_id,
            "sample_hash": self.sample_hash,
            "source_text": self.source_text,
            "transformed_text": self.transformed_text,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "source_on_left": self.source_on_left,
            "display_key": self.display_key,
        }

    def public_payload(self) -> dict[str, object]:
        text_a, text_b = (self.source_text, self.transformed_text) if self.source_on_left else (self.transformed_text, self.source_text)
        payload = {
            "item_id": self.item_id,
            "text_a": text_a,
            "text_b": text_b,
        }
        payload["item_hash"] = sha256_json(payload)
        return payload


@dataclass(frozen=True, slots=True)
class BlindReviewPacket:
    algorithm_version: str
    rule_hash: str
    review_policy_id: str
    seed: int
    entries: tuple[BlindReviewPacketEntry, ...]
    packet_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != BLIND_REVIEW_PACKET_ALGORITHM_VERSION:
            raise ValueError("unsupported blind review packet algorithm version")
        require_sha256("rule_hash", self.rule_hash)
        require_clean_string("review_policy_id", self.review_policy_id)
        if self.review_policy_id != BLIND_HUMAN_REVIEW_POLICY_ID:
            raise ValueError("unsupported blind human review policy")
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        if not isinstance(self.entries, tuple) or not self.entries:
            raise TypeError("entries must be a non-empty tuple")
        expected_entries = tuple(sorted(self.entries, key=lambda value: (value.item_id, value.entry_hash)))
        if self.entries != expected_entries:
            raise ValueError("entries must be canonically ordered")
        if len({value.item_id for value in self.entries}) != len(self.entries):
            raise ValueError("packet item IDs must be unique")
        if len({value.sample_id for value in self.entries}) != len(self.entries):
            raise ValueError("packet sample IDs must be unique")
        if any(value.rule_hash != self.rule_hash for value in self.entries):
            raise ValueError("packet entries must match packet rule hash")
        if len({value.sample_hash for value in self.entries}) != len(self.entries):
            raise ValueError("packet sample hashes must be unique")
        if len({(value.source_text_hash, value.transformed_text_hash) for value in self.entries}) != len(self.entries):
            raise ValueError("packet entries must not duplicate reviewed text pairs")
        require_sha256("packet_hash", self.packet_hash)
        if self.packet_hash != sha256_json(self._payload()):
            raise ValueError("packet_hash does not match blind review packet")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rule_hash": self.rule_hash,
            "review_policy_id": self.review_policy_id,
            "seed": self.seed,
            "entries": self.entries,
        }

    @property
    def sample_count(self) -> int:
        return len(self.entries)

    def public_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "review_policy_id": self.review_policy_id,
            "packet_hash": self.packet_hash,
            "items": tuple(entry.public_payload() for entry in sorted(self.entries, key=lambda value: value.display_key)),
        }

    def private_manifest_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rule_hash": self.rule_hash,
            "review_policy_id": self.review_policy_id,
            "seed": self.seed,
            "packet_hash": self.packet_hash,
            "entries": self.entries,
        }

    def entry_for(self, item_id: str) -> BlindReviewPacketEntry:
        require_sha256("item_id", item_id)
        for entry in self.entries:
            if entry.item_id == item_id:
                return entry
        raise KeyError("unknown blind review packet item")


def _validate_samples(samples: Sequence[FidelityReviewSample]) -> tuple[FidelityReviewSample, ...]:
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes, bytearray)):
        raise TypeError("samples must be a sequence")
    values = tuple(samples)
    if not values:
        raise ValueError("samples must contain at least one fidelity review sample")
    if any(not isinstance(value, FidelityReviewSample) for value in values):
        raise TypeError("samples must contain FidelityReviewSample values")
    rule_hash = values[0].rule_hash
    if any(value.rule_hash != rule_hash for value in values):
        raise ValueError("all review samples must use one rule hash")
    if len({value.sample_id for value in values}) != len(values):
        raise ValueError("review sample IDs must be unique")
    if len({value.sample_hash for value in values}) != len(values):
        raise ValueError("review sample hashes must be unique")
    if len({(value.source_text_hash, value.transformed_text_hash) for value in values}) != len(values):
        raise ValueError("review samples must not duplicate reviewed text pairs")
    return values


def _key(seed: int, rule_hash: str, sample_hash: str, purpose: str) -> str:
    return sha256_json(
        {
            "algorithm_version": BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
            "seed": seed,
            "rule_hash": rule_hash,
            "sample_hash": sample_hash,
            "purpose": purpose,
        }
    )


def build_blind_review_packet(
    samples: Sequence[FidelityReviewSample],
    seed: int,
    sample_count: int | None = None,
) -> BlindReviewPacket:
    values = _validate_samples(samples)
    require_int("seed", seed)
    if seed < 0 or seed >= 1 << 64:
        raise ValueError("seed must be between 0 and 2^64-1")
    if sample_count is None:
        count = len(values)
    else:
        require_int("sample_count", sample_count)
        count = sample_count
        if count <= 0:
            raise ValueError("sample_count must be positive")
        if count > len(values):
            raise ValueError("sample_count cannot exceed available review samples")
    rule_hash = values[0].rule_hash
    selected = tuple(sorted(values, key=lambda value: (_key(seed, rule_hash, value.sample_hash, "selection"), value.sample_hash))[:count])
    entries: list[BlindReviewPacketEntry] = []
    for sample in selected:
        item_id = _key(seed, rule_hash, sample.sample_hash, "item")
        orientation_key = _key(seed, rule_hash, sample.sample_hash, "orientation")
        source_on_left = int(orientation_key[:16], 16) % 2 == 0
        display_key = _key(seed, rule_hash, sample.sample_hash, "display")
        payload = {
            "algorithm_version": BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
            "item_id": item_id,
            "rule_hash": rule_hash,
            "sample_id": sample.sample_id,
            "sample_hash": sample.sample_hash,
            "source_text": sample.source_text,
            "transformed_text": sample.transformed_text,
            "source_text_hash": sample.source_text_hash,
            "transformed_text_hash": sample.transformed_text_hash,
            "source_on_left": source_on_left,
            "display_key": display_key,
        }
        entries.append(
            BlindReviewPacketEntry(
                item_id,
                rule_hash,
                sample.sample_id,
                sample.sample_hash,
                sample.source_text,
                sample.transformed_text,
                sample.source_text_hash,
                sample.transformed_text_hash,
                source_on_left,
                display_key,
                sha256_json(payload),
            )
        )
    ordered = tuple(sorted(entries, key=lambda value: (value.item_id, value.entry_hash)))
    packet_payload = {
        "algorithm_version": BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
        "rule_hash": values[0].rule_hash,
        "review_policy_id": BLIND_HUMAN_REVIEW_POLICY_ID,
        "seed": seed,
        "entries": ordered,
    }
    return BlindReviewPacket(
        BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
        values[0].rule_hash,
        BLIND_HUMAN_REVIEW_POLICY_ID,
        seed,
        ordered,
        sha256_json(packet_payload),
    )


def verify_blind_review_packet(
    packet: BlindReviewPacket,
    samples: Sequence[FidelityReviewSample],
) -> None:
    if not isinstance(packet, BlindReviewPacket):
        raise TypeError("packet must be a BlindReviewPacket")
    values = _validate_samples(samples)
    if values[0].rule_hash != packet.rule_hash:
        raise BlindReviewPacketVerificationError("packet rule hash does not match supplied samples")
    expected = build_blind_review_packet(values, packet.seed, packet.sample_count)
    if packet != expected:
        raise BlindReviewPacketVerificationError("blind review packet does not replay from supplied samples")


def bind_blind_review_judgment(
    packet: BlindReviewPacket,
    samples: Sequence[FidelityReviewSample],
    item_id: str,
    reviewer_id: str,
    label: FidelityLabel,
) -> BlindReviewJudgment:
    verify_blind_review_packet(packet, samples)
    entry = packet.entry_for(item_id)
    by_hash = {value.sample_hash: value for value in samples}
    try:
        sample = by_hash[entry.sample_hash]
    except KeyError as error:
        raise BlindReviewPacketVerificationError("packet item sample is missing from supplied samples") from error
    return BlindReviewJudgment.create(sample, reviewer_id, label)


def bind_blind_review_judgments(
    packet: BlindReviewPacket,
    samples: Sequence[FidelityReviewSample],
    reviewer_id: str,
    labels_by_item: Mapping[str, FidelityLabel],
) -> tuple[BlindReviewJudgment, ...]:
    if not isinstance(labels_by_item, Mapping):
        raise TypeError("labels_by_item must be a mapping")
    expected_ids = {entry.item_id for entry in packet.entries}
    actual_ids = set(labels_by_item)
    if actual_ids != expected_ids:
        raise BlindReviewPacketVerificationError("labels must contain exactly one label for every packet item")
    judgments = tuple(
        bind_blind_review_judgment(packet, samples, entry.item_id, reviewer_id, labels_by_item[entry.item_id])
        for entry in sorted(packet.entries, key=lambda value: (value.sample_id, value.sample_hash))
    )
    return tuple(sorted(judgments, key=lambda value: (value.sample_id, value.reviewer_id, value.judgment_hash)))
