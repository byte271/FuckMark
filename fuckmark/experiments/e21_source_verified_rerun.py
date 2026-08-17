from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import CorpusManifest
from ..environment import EnvironmentSnapshot
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_execution import E20RunLedger
from .e20_source_verified_authorization import E20SourceVerifiedAuthorization
from .e21_rerun import (
    E21ExecutionAuthorization,
    E21RerunSeal,
    authorize_e21_execution as _authorize_e21_execution,
    build_e21_rerun_seal as _build_e21_rerun_seal,
)


E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION = "e21-source-verified-rerun-v1"
E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION = "e21-source-verified-authorization-v1"


class E21SourceVerifiedRerunError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E21SourceVerifiedRerunSeal:
    algorithm_version: str
    preregistration_hash: str
    e20_source_verified_authorization_hash: str
    e20_authorization_hash: str
    rerun_seal: E21RerunSeal
    envelope_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified E21 rerun algorithm version")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("e20_source_verified_authorization_hash", self.e20_source_verified_authorization_hash),
            ("e20_authorization_hash", self.e20_authorization_hash),
            ("envelope_hash", self.envelope_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.rerun_seal, E21RerunSeal):
            raise TypeError("rerun_seal must be an E21RerunSeal")
        if self.rerun_seal.preregistration_hash != self.preregistration_hash:
            raise ValueError("E21 rerun seal does not bind the source-verified preregistration")
        if self.rerun_seal.e20_authorization_hash != self.e20_authorization_hash:
            raise ValueError("E21 rerun seal does not bind the source-verified E20 authorization")
        if self.envelope_hash != sha256_json(self._payload()):
            raise ValueError("envelope_hash does not match source-verified E21 rerun seal")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "e20_source_verified_authorization_hash": self.e20_source_verified_authorization_hash,
            "e20_authorization_hash": self.e20_authorization_hash,
            "rerun_seal": self.rerun_seal,
        }


@dataclass(frozen=True, slots=True)
class E21SourceVerifiedAuthorization:
    algorithm_version: str
    preregistration_hash: str
    e20_source_verified_authorization_hash: str
    source_verified_rerun_seal_hash: str
    rerun_seal_hash: str
    authorization: E21ExecutionAuthorization
    envelope_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified E21 authorization algorithm version")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("e20_source_verified_authorization_hash", self.e20_source_verified_authorization_hash),
            ("source_verified_rerun_seal_hash", self.source_verified_rerun_seal_hash),
            ("rerun_seal_hash", self.rerun_seal_hash),
            ("envelope_hash", self.envelope_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.authorization, E21ExecutionAuthorization):
            raise TypeError("authorization must be an E21ExecutionAuthorization")
        if self.authorization.preregistration_hash != self.preregistration_hash:
            raise ValueError("raw E21 authorization does not bind the source-verified preregistration")
        if self.authorization.rerun_seal_hash != self.rerun_seal_hash:
            raise ValueError("raw E21 authorization does not bind the source-verified rerun seal")
        if self.envelope_hash != sha256_json(self._payload()):
            raise ValueError("envelope_hash does not match source-verified E21 authorization")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "e20_source_verified_authorization_hash": self.e20_source_verified_authorization_hash,
            "source_verified_rerun_seal_hash": self.source_verified_rerun_seal_hash,
            "rerun_seal_hash": self.rerun_seal_hash,
            "authorization": self.authorization,
        }


def _verify_e20_envelope_binding(
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
) -> None:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(e20_source_verified_authorization, E20SourceVerifiedAuthorization):
        raise TypeError("e20_source_verified_authorization must be an E20SourceVerifiedAuthorization")
    if e20_source_verified_authorization.preregistration_hash != preregistration.preregistration_hash:
        raise E21SourceVerifiedRerunError(
            "source-verified E20 authorization does not bind the E21 preregistration"
        )
    if (
        e20_source_verified_authorization.authorization.preregistration_hash
        != preregistration.preregistration_hash
    ):
        raise E21SourceVerifiedRerunError(
            "raw E20 authorization inside the source-verified envelope does not bind the E21 preregistration"
        )


def build_source_verified_e21_rerun_seal(
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> E21SourceVerifiedRerunSeal:
    _verify_e20_envelope_binding(preregistration, e20_source_verified_authorization)
    raw_seal = _build_e21_rerun_seal(
        preregistration,
        e20_source_verified_authorization.authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
    )
    if not isinstance(raw_seal, E21RerunSeal):
        raise TypeError("existing E21 rerun builder must return an E21RerunSeal")
    if raw_seal.preregistration_hash != preregistration.preregistration_hash:
        raise E21SourceVerifiedRerunError("raw E21 rerun seal escaped the verified preregistration")
    if (
        raw_seal.e20_authorization_hash
        != e20_source_verified_authorization.authorization.authorization_hash
    ):
        raise E21SourceVerifiedRerunError("raw E21 rerun seal escaped the verified E20 authorization")
    payload = {
        "algorithm_version": E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_source_verified_authorization_hash": e20_source_verified_authorization.envelope_hash,
        "e20_authorization_hash": e20_source_verified_authorization.authorization.authorization_hash,
        "rerun_seal": raw_seal,
    }
    return E21SourceVerifiedRerunSeal(
        E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        e20_source_verified_authorization.envelope_hash,
        e20_source_verified_authorization.authorization.authorization_hash,
        raw_seal,
        sha256_json(payload),
    )


def verify_source_verified_e21_rerun_seal(
    seal: E21SourceVerifiedRerunSeal,
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> None:
    if not isinstance(seal, E21SourceVerifiedRerunSeal):
        raise TypeError("seal must be an E21SourceVerifiedRerunSeal")
    expected = build_source_verified_e21_rerun_seal(
        preregistration,
        e20_source_verified_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
    )
    if seal != expected:
        raise E21SourceVerifiedRerunError(
            "source-verified E21 rerun seal does not replay exactly from E20 provenance and rerun inputs"
        )


def authorize_source_verified_e21_execution(
    source_verified_rerun_seal: E21SourceVerifiedRerunSeal,
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    output_namespace_available: bool,
    code_commit: str,
) -> E21SourceVerifiedAuthorization:
    if not isinstance(source_verified_rerun_seal, E21SourceVerifiedRerunSeal):
        raise TypeError("source_verified_rerun_seal must be an E21SourceVerifiedRerunSeal")
    _verify_e20_envelope_binding(preregistration, e20_source_verified_authorization)
    if (
        source_verified_rerun_seal.e20_source_verified_authorization_hash
        != e20_source_verified_authorization.envelope_hash
    ):
        raise E21SourceVerifiedRerunError(
            "source-verified E21 rerun seal belongs to a different source-verified E20 authorization"
        )
    if (
        source_verified_rerun_seal.e20_authorization_hash
        != e20_source_verified_authorization.authorization.authorization_hash
    ):
        raise E21SourceVerifiedRerunError(
            "source-verified E21 rerun seal belongs to a different raw E20 authorization"
        )
    raw_authorization = _authorize_e21_execution(
        source_verified_rerun_seal.rerun_seal,
        preregistration,
        e20_source_verified_authorization.authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
        environment,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        dirty_worktree=dirty_worktree,
        output_namespace_available=output_namespace_available,
        code_commit=code_commit,
    )
    if not isinstance(raw_authorization, E21ExecutionAuthorization):
        raise TypeError("existing E21 authorization gate must return an E21ExecutionAuthorization")
    if raw_authorization.rerun_seal_hash != source_verified_rerun_seal.rerun_seal.seal_hash:
        raise E21SourceVerifiedRerunError("raw E21 authorization escaped the source-verified rerun seal")
    payload = {
        "algorithm_version": E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_source_verified_authorization_hash": e20_source_verified_authorization.envelope_hash,
        "source_verified_rerun_seal_hash": source_verified_rerun_seal.envelope_hash,
        "rerun_seal_hash": source_verified_rerun_seal.rerun_seal.seal_hash,
        "authorization": raw_authorization,
    }
    return E21SourceVerifiedAuthorization(
        E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        e20_source_verified_authorization.envelope_hash,
        source_verified_rerun_seal.envelope_hash,
        source_verified_rerun_seal.rerun_seal.seal_hash,
        raw_authorization,
        sha256_json(payload),
    )


def verify_source_verified_e21_execution_authorization(
    authorization: E21SourceVerifiedAuthorization,
    source_verified_rerun_seal: E21SourceVerifiedRerunSeal,
    preregistration: ConfirmatoryPreregistration,
    e20_source_verified_authorization: E20SourceVerifiedAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    output_namespace_available: bool,
    code_commit: str,
) -> None:
    if not isinstance(authorization, E21SourceVerifiedAuthorization):
        raise TypeError("authorization must be an E21SourceVerifiedAuthorization")
    expected = authorize_source_verified_e21_execution(
        source_verified_rerun_seal,
        preregistration,
        e20_source_verified_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
        environment,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        dirty_worktree=dirty_worktree,
        output_namespace_available=output_namespace_available,
        code_commit=code_commit,
    )
    if authorization != expected:
        raise E21SourceVerifiedRerunError(
            "source-verified E21 authorization does not replay exactly from verified rerun provenance"
        )
