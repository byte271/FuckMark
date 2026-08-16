import pytest

from fuckmark.experiments.confirmatory_keys import (
    ConfirmatoryTestKeyEntry,
    ConfirmatoryTestKeyVerificationError,
    build_confirmatory_test_key_manifest,
    verify_confirmatory_test_key_material,
)
from fuckmark.hashing import sha256_bytes, sha256_text


def _entry(index: int = 0) -> ConfirmatoryTestKeyEntry:
    material = f"secret-test-key-{index}".encode("utf-8")
    return ConfirmatoryTestKeyEntry.create(
        key_id=f"test-key-{index}",
        watermark_config_hash=sha256_text(f"watermark-config-{index}"),
        key_material_commitment_hash=sha256_bytes(material),
    )


def test_test_key_manifest_is_nonsecret_and_content_addressed() -> None:
    first = _entry(0)
    second = _entry(1)
    manifest = build_confirmatory_test_key_manifest((second, first))
    assert manifest.entries == tuple(
        sorted(
            (first, second),
            key=lambda value: (value.watermark_config_hash, value.key_id, value.entry_hash),
        )
    )
    assert all(not hasattr(entry, "key_material") for entry in manifest.entries)


def test_test_key_manifest_rejects_duplicate_condition_identity_without_silent_dedup() -> None:
    first = _entry(0)
    duplicate = ConfirmatoryTestKeyEntry.create(
        key_id=first.key_id,
        watermark_config_hash=first.watermark_config_hash,
        key_material_commitment_hash=sha256_bytes(b"different-secret-material"),
    )
    with pytest.raises(ValueError, match="condition identities must be unique"):
        build_confirmatory_test_key_manifest((first, duplicate))


def test_exact_serialized_test_key_material_replays_commitment() -> None:
    entry = _entry(0)
    verify_confirmatory_test_key_material(entry, b"secret-test-key-0")
    with pytest.raises(ConfirmatoryTestKeyVerificationError, match="does not match"):
        verify_confirmatory_test_key_material(entry, b"wrong-test-key")


def test_test_key_material_verifier_rejects_non_bytes_serialization() -> None:
    entry = _entry(0)
    with pytest.raises(TypeError, match="must be bytes"):
        verify_confirmatory_test_key_material(entry, "secret-test-key-0")
