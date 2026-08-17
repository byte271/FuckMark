from __future__ import annotations

from collections.abc import Mapping

from ..corpus import CorpusManifest
from ..environment import EnvironmentSnapshot
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_execution import E20ExecutionAuthorization, E20RunLedger
from .e21_rerun import (
    E21ExecutionAuthorization,
    E21RerunError,
    E21RerunSeal,
    authorize_e21_execution,
)


class E21AuthorizationVerificationError(ValueError):
    pass


def verify_e21_execution_authorization(
    authorization: E21ExecutionAuthorization,
    seal: E21RerunSeal,
    preregistration: ConfirmatoryPreregistration,
    e20_authorization: E20ExecutionAuthorization,
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
    code_commit: str,
) -> None:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    try:
        expected = authorize_e21_execution(
            seal,
            preregistration,
            e20_authorization,
            e20_ledger,
            e20_manifest,
            e21_manifest,
            test_key_manifest,
            environment,
            serialized_test_key_material=serialized_test_key_material,
            dependency_lock_hash=dependency_lock_hash,
            worker_version=worker_version,
            shard_count=shard_count,
            dirty_worktree=False,
            output_namespace_available=True,
            code_commit=code_commit,
        )
    except E21RerunError as error:
        raise E21AuthorizationVerificationError(
            "E21 authorization source inputs failed replay"
        ) from error
    if authorization != expected:
        raise E21AuthorizationVerificationError(
            "E21 execution authorization does not replay exactly from frozen inputs"
        )
