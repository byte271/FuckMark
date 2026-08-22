from __future__ import annotations

import importlib.metadata
import os
import platform
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from ._validation import require_bool, require_clean_string, require_int, require_sha256
from .hashing import sha256_json
from .types import RunIdentity


ENVIRONMENT_SNAPSHOT_LEGACY_ALGORITHM_VERSION = "environment-snapshot-v1"
ENVIRONMENT_SNAPSHOT_IMPORT_PRECEDENCE_LEGACY_ALGORITHM_VERSION = "environment-snapshot-v2"
ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION = "environment-snapshot-v3"
ENVIRONMENT_SNAPSHOT_SUPPORTED_VERSIONS = (
    ENVIRONMENT_SNAPSHOT_LEGACY_ALGORITHM_VERSION,
    ENVIRONMENT_SNAPSHOT_IMPORT_PRECEDENCE_LEGACY_ALGORITHM_VERSION,
    ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
)
RUN_MANIFEST_ALGORITHM_VERSION = "run-manifest-v1"
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True, slots=True)
class EnvironmentLibrary:
    name: str
    version: str

    def __post_init__(self) -> None:
        require_clean_string("library name", self.name)
        require_clean_string("library version", self.version)


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    algorithm_version: str
    python_implementation: str
    python_version: str
    python_compiler: str
    platform_system: str
    platform_release: str
    platform_version: str
    platform_machine: str
    platform_processor: str
    cpu_count: int | None
    libraries: tuple[EnvironmentLibrary, ...]
    snapshot_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version not in ENVIRONMENT_SNAPSHOT_SUPPORTED_VERSIONS:
            raise ValueError("unsupported environment snapshot algorithm version")
        for name, value in (
            ("python_implementation", self.python_implementation),
            ("python_version", self.python_version),
            ("python_compiler", self.python_compiler),
            ("platform_system", self.platform_system),
            ("platform_release", self.platform_release),
            ("platform_version", self.platform_version),
            ("platform_machine", self.platform_machine),
            ("platform_processor", self.platform_processor),
        ):
            require_clean_string(name, value)
        if self.cpu_count is not None:
            require_int("cpu_count", self.cpu_count)
            if self.cpu_count <= 0:
                raise ValueError("cpu_count must be positive when present")
        if not isinstance(self.libraries, tuple):
            raise TypeError("libraries must be a tuple")
        if any(not isinstance(value, EnvironmentLibrary) for value in self.libraries):
            raise TypeError("libraries must contain EnvironmentLibrary values")
        expected_order = tuple(sorted(self.libraries, key=lambda value: (value.name.casefold(), value.name, value.version)))
        if self.libraries != expected_order:
            raise ValueError("libraries must use canonical name/version ordering")
        normalized_names = tuple(value.name.casefold() for value in self.libraries)
        if len(set(normalized_names)) != len(normalized_names):
            raise ValueError("libraries must not contain duplicate case-insensitive names")
        require_sha256("snapshot_hash", self.snapshot_hash)
        if self.snapshot_hash != sha256_json(self._payload()):
            raise ValueError("snapshot_hash does not match environment snapshot")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "python_compiler": self.python_compiler,
            "platform_system": self.platform_system,
            "platform_release": self.platform_release,
            "platform_version": self.platform_version,
            "platform_machine": self.platform_machine,
            "platform_processor": self.platform_processor,
            "cpu_count": self.cpu_count,
            "libraries": self.libraries,
        }


@dataclass(frozen=True, slots=True)
class SeedRecord:
    name: str
    value: int | str

    def __post_init__(self) -> None:
        require_clean_string("seed name", self.name)
        if isinstance(self.value, bool) or not isinstance(self.value, (int, str)):
            raise TypeError("seed value must be an integer or string")
        if isinstance(self.value, int):
            if self.value < 0:
                raise ValueError("integer seed values must be non-negative")
        else:
            require_clean_string("seed value", self.value)


@dataclass(frozen=True, slots=True)
class RunManifest:
    algorithm_version: str
    captured_at_utc: str
    identity: RunIdentity
    dirty_worktree: bool
    environment: EnvironmentSnapshot
    seeds: tuple[SeedRecord, ...]
    manifest_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != RUN_MANIFEST_ALGORITHM_VERSION:
            raise ValueError("unsupported run manifest algorithm version")
        require_clean_string("captured_at_utc", self.captured_at_utc)
        if _UTC_TIMESTAMP_RE.fullmatch(self.captured_at_utc) is None:
            raise ValueError("captured_at_utc must use canonical second-resolution UTC form")
        parsed = datetime.fromisoformat(self.captured_at_utc[:-1] + "+00:00")
        if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
            raise ValueError("captured_at_utc must represent UTC")
        if not isinstance(self.identity, RunIdentity):
            raise TypeError("identity must be a RunIdentity")
        require_bool("dirty_worktree", self.dirty_worktree)
        if not isinstance(self.environment, EnvironmentSnapshot):
            raise TypeError("environment must be an EnvironmentSnapshot")
        if not isinstance(self.seeds, tuple):
            raise TypeError("seeds must be a tuple")
        if any(not isinstance(value, SeedRecord) for value in self.seeds):
            raise TypeError("seeds must contain SeedRecord values")
        if self.seeds != tuple(sorted(self.seeds, key=lambda value: value.name)):
            raise ValueError("seeds must use canonical name ordering")
        names = tuple(value.name for value in self.seeds)
        if len(set(names)) != len(names):
            raise ValueError("seed names must be unique")
        require_sha256("manifest_hash", self.manifest_hash)
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match run manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "captured_at_utc": self.captured_at_utc,
            "identity": self.identity,
            "dirty_worktree": self.dirty_worktree,
            "environment": self.environment,
            "seeds": self.seeds,
        }

    @classmethod
    def create(
        cls,
        identity: RunIdentity,
        dirty_worktree: bool,
        seeds: Sequence[SeedRecord],
        environment: EnvironmentSnapshot | None = None,
        captured_at_utc: str | None = None,
    ) -> RunManifest:
        if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes, bytearray)):
            raise TypeError("seeds must be a sequence")
        normalized_seeds = tuple(sorted(tuple(seeds), key=lambda value: value.name if isinstance(value, SeedRecord) else ""))
        snapshot = capture_environment() if environment is None else environment
        timestamp = (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            if captured_at_utc is None
            else captured_at_utc
        )
        payload = {
            "algorithm_version": RUN_MANIFEST_ALGORITHM_VERSION,
            "captured_at_utc": timestamp,
            "identity": identity,
            "dirty_worktree": dirty_worktree,
            "environment": snapshot,
            "seeds": normalized_seeds,
        }
        return cls(
            RUN_MANIFEST_ALGORITHM_VERSION,
            timestamp,
            identity,
            dirty_worktree,
            snapshot,
            normalized_seeds,
            sha256_json(payload),
        )


def _distribution_precedence(distribution: importlib.metadata.Distribution) -> tuple[int, str]:
    location = os.path.realpath(str(distribution.locate_file("")))
    for index, entry in enumerate(sys.path):
        if os.path.realpath(entry or os.curdir) == location:
            return index, location
    return len(sys.path), location


def _installed_libraries() -> tuple[EnvironmentLibrary, ...]:
    by_name: dict[str, tuple[EnvironmentLibrary, tuple[int, str]]] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if not isinstance(name, str) or not name.strip() or not isinstance(version, str) or not version.strip():
            raise ValueError("installed distribution metadata must contain non-empty name and version")
        row = EnvironmentLibrary(name.strip(), version.strip())
        key = row.name.casefold()
        candidate = (row, _distribution_precedence(distribution))
        previous = by_name.get(key)
        if previous is None or candidate[1] < previous[1] or (
            candidate[1] == previous[1] and (row.name, row.version) < (previous[0].name, previous[0].version)
        ):
            by_name[key] = candidate
    return tuple(
        sorted(
            (value[0] for value in by_name.values()),
            key=lambda value: (value.name.casefold(), value.name, value.version),
        )
    )


def _platform_value(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("platform metadata must be a string")
    return value.strip() or "UNKNOWN"


def capture_environment() -> EnvironmentSnapshot:
    payload = {
        "algorithm_version": ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
        "python_implementation": _platform_value(platform.python_implementation()),
        "python_version": _platform_value(platform.python_version()),
        "python_compiler": _platform_value(platform.python_compiler()),
        "platform_system": _platform_value(platform.system()),
        "platform_release": _platform_value(platform.release()),
        "platform_version": _platform_value(platform.version()),
        "platform_machine": _platform_value(platform.machine()),
        "platform_processor": _platform_value(platform.processor()),
        "cpu_count": os.cpu_count(),
        "libraries": _installed_libraries(),
    }
    return EnvironmentSnapshot(
        ENVIRONMENT_SNAPSHOT_ALGORITHM_VERSION,
        payload["python_implementation"],
        payload["python_version"],
        payload["python_compiler"],
        payload["platform_system"],
        payload["platform_release"],
        payload["platform_version"],
        payload["platform_machine"],
        payload["platform_processor"],
        payload["cpu_count"],
        payload["libraries"],
        sha256_json(payload),
    )
