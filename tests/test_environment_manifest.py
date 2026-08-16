from dataclasses import replace

import pytest

from fuckmark.environment import (
    ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
    RUN_MANIFEST_ALGORITHM_VERSION,
    EnvironmentLibrary,
    EnvironmentSnapshot,
    RunManifest,
    SeedRecord,
    capture_environment,
)
from fuckmark.hashing import sha256_json
from fuckmark.types import RunIdentity


def _identity() -> RunIdentity:
    commit = "a" * 40
    digest = "b" * 64
    return RunIdentity(
        run_id="run-1",
        experiment_id="E00",
        git_commit=commit,
        adapter_id="adapter",
        adapter_source_commit=commit,
        model_id="model/id",
        model_revision=commit,
        tokenizer_id="tokenizer/id",
        tokenizer_revision=commit,
        watermark_config_hash=digest,
        detector_config_hash=digest,
        corpus_manifest_hash=digest,
        transform_config_hash=digest,
        experiment_config_hash=digest,
    )


def _environment() -> EnvironmentSnapshot:
    libraries = (
        EnvironmentLibrary("alpha", "1.0"),
        EnvironmentLibrary("beta", "2.0"),
    )
    payload = {
        "algorithm_version": ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
        "python_implementation": "CPython",
        "python_version": "3.12.13",
        "python_compiler": "GCC 13.3.0",
        "platform_system": "Linux",
        "platform_release": "6.8.0",
        "platform_version": "test-kernel",
        "platform_machine": "x86_64",
        "platform_processor": "x86_64",
        "cpu_count": 8,
        "libraries": libraries,
    }
    return EnvironmentSnapshot(
        ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
        "CPython",
        "3.12.13",
        "GCC 13.3.0",
        "Linux",
        "6.8.0",
        "test-kernel",
        "x86_64",
        "x86_64",
        8,
        libraries,
        sha256_json(payload),
    )


def test_capture_environment_is_self_validating_and_canonical() -> None:
    snapshot = capture_environment()
    assert snapshot.algorithm_version == ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION
    assert snapshot.python_version
    assert snapshot.platform_system
    assert snapshot.platform_machine
    assert snapshot.libraries == tuple(
        sorted(snapshot.libraries, key=lambda value: (value.name.casefold(), value.name, value.version))
    )
    assert snapshot.snapshot_hash == sha256_json(snapshot._payload())


def test_environment_snapshot_rejects_tampering() -> None:
    snapshot = _environment()
    with pytest.raises(ValueError, match="snapshot_hash"):
        replace(snapshot, python_version="3.13.0")
    with pytest.raises(ValueError, match="canonical"):
        replace(snapshot, libraries=tuple(reversed(snapshot.libraries)), snapshot_hash="0" * 64)


def test_environment_snapshot_rejects_duplicate_library_names_case_insensitively() -> None:
    snapshot = _environment()
    duplicate = (
        EnvironmentLibrary("ALPHA", "1.0"),
        EnvironmentLibrary("alpha", "1.0"),
    )
    with pytest.raises(ValueError, match="duplicate"):
        replace(snapshot, libraries=duplicate, snapshot_hash="0" * 64)


def test_seed_record_rejects_invalid_seed_values() -> None:
    with pytest.raises(TypeError):
        SeedRecord("generation", True)
    with pytest.raises(ValueError):
        SeedRecord("generation", -1)
    with pytest.raises(ValueError):
        SeedRecord("generation", " seed ")


def test_run_manifest_create_canonicalizes_seed_order_and_hashes_everything() -> None:
    manifest = RunManifest.create(
        _identity(),
        False,
        (SeedRecord("training", 2), SeedRecord("generation", 1)),
        environment=_environment(),
        captured_at_utc="2026-08-16T16:00:00Z",
    )
    assert manifest.algorithm_version == RUN_MANIFEST_ALGORITHM_VERSION
    assert tuple(value.name for value in manifest.seeds) == ("generation", "training")
    assert manifest.manifest_hash == sha256_json(manifest._payload())


def test_run_manifest_rejects_noncanonical_time_duplicate_seeds_and_tampering() -> None:
    manifest = RunManifest.create(
        _identity(),
        False,
        (SeedRecord("generation", 1),),
        environment=_environment(),
        captured_at_utc="2026-08-16T16:00:00Z",
    )
    with pytest.raises(ValueError, match="UTC"):
        replace(manifest, captured_at_utc="2026-08-16T12:00:00-04:00", manifest_hash="0" * 64)
    with pytest.raises(ValueError, match="unique"):
        replace(
            manifest,
            seeds=(SeedRecord("generation", 1), SeedRecord("generation", 2)),
            manifest_hash="0" * 64,
        )
    with pytest.raises(ValueError, match="manifest_hash"):
        replace(manifest, dirty_worktree=True)


def test_run_manifest_rejects_non_boolean_dirty_worktree() -> None:
    with pytest.raises(TypeError):
        RunManifest.create(
            _identity(),
            1,
            (),
            environment=_environment(),
            captured_at_utc="2026-08-16T16:00:00Z",
        )
