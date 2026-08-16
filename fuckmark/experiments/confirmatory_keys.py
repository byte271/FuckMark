from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_bytes, sha256_json


CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION = "confirmatory-test-key-manifest-v1"


class ConfirmatoryTestKeyVerificationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfirmatoryTestKeyEntry:
    key_id: str
    watermark_config_hash: str
    key_material_commitment_hash: str
    entry_hash: str

    def __post_init__(self) -> None:
        require_clean_string("key_id", self.key_id)
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        require_sha256("key_material_commitment_hash", self.key_material_commitment_hash)
        require_sha256("entry_hash", self.entry_hash)
        if self.entry_hash != sha256_json(self._payload()):
            raise ValueError("entry_hash does not match confirmatory test-key entry")

    @property
    def condition_identity(self) -> tuple[str, str]:
        return self.watermark_config_hash, self.key_id

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION,
            "key_id": self.key_id,
            "watermark_config_hash": self.watermark_config_hash,
            "key_material_commitment_hash": self.key_material_commitment_hash,
        }

    @classmethod
    def create(
        cls,
        key_id: str,
        watermark_config_hash: str,
        key_material_commitment_hash: str,
    ) -> ConfirmatoryTestKeyEntry:
        payload = {
            "algorithm_version": CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION,
            "key_id": key_id,
            "watermark_config_hash": watermark_config_hash,
            "key_material_commitment_hash": key_material_commitment_hash,
        }
        return cls(
            key_id,
            watermark_config_hash,
            key_material_commitment_hash,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class ConfirmatoryTestKeyManifest:
    algorithm_version: str
    entries: tuple[ConfirmatoryTestKeyEntry, ...]
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory test-key manifest algorithm version")
        if not isinstance(self.entries, tuple) or not self.entries:
            raise TypeError("entries must be a non-empty tuple")
        if any(not isinstance(value, ConfirmatoryTestKeyEntry) for value in self.entries):
            raise TypeError("entries must contain ConfirmatoryTestKeyEntry values")
        expected = tuple(
            sorted(
                self.entries,
                key=lambda value: (
                    value.watermark_config_hash,
                    value.key_id,
                    value.entry_hash,
                ),
            )
        )
        if self.entries != expected:
            raise ValueError("test-key entries must be canonically ordered")
        identities = tuple(value.condition_identity for value in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("test-key condition identities must be unique")
        if len({value.entry_hash for value in self.entries}) != len(self.entries):
            raise ValueError("test-key entries must be unique")
        require_sha256("manifest_hash", self.manifest_hash)
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match confirmatory test-key manifest")

    @property
    def condition_identities(self) -> tuple[tuple[str, str], ...]:
        return tuple(value.condition_identity for value in self.entries)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "entries": self.entries,
        }


def build_confirmatory_test_key_manifest(
    entries: Sequence[ConfirmatoryTestKeyEntry],
) -> ConfirmatoryTestKeyManifest:
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        raise TypeError("entries must be a sequence")
    values = tuple(entries)
    if not values:
        raise ValueError("entries must not be empty")
    if any(not isinstance(value, ConfirmatoryTestKeyEntry) for value in values):
        raise TypeError("entries must contain ConfirmatoryTestKeyEntry values")
    ordered = tuple(
        sorted(
            values,
            key=lambda value: (
                value.watermark_config_hash,
                value.key_id,
                value.entry_hash,
            ),
        )
    )
    payload = {
        "algorithm_version": CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION,
        "entries": ordered,
    }
    return ConfirmatoryTestKeyManifest(
        CONFIRMATORY_TEST_KEY_MANIFEST_ALGORITHM_VERSION,
        ordered,
        sha256_json(payload),
    )


def verify_confirmatory_test_key_material(
    entry: ConfirmatoryTestKeyEntry,
    serialized_key_material: bytes,
) -> None:
    if not isinstance(entry, ConfirmatoryTestKeyEntry):
        raise TypeError("entry must be a ConfirmatoryTestKeyEntry")
    if not isinstance(serialized_key_material, bytes):
        raise TypeError("serialized_key_material must be bytes")
    if sha256_bytes(serialized_key_material) != entry.key_material_commitment_hash:
        raise ConfirmatoryTestKeyVerificationError(
            "serialized TEST_KEYS material does not match the sealed commitment"
        )
