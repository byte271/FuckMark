from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, CorpusSplit
from ..environment import EnvironmentSnapshot
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_keys import ConfirmatoryTestKeyManifest, verify_confirmatory_test_key_material
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    E20RunState,
    verify_e20_run_ledger,
)


E21_EXPERIMENT_ID = "E21"
E21_RERUN_SEAL_ALGORITHM_VERSION = "e21-independent-rerun-seal-v1"
E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION = "e21-execution-authorization-v1"


class E21RerunError(ValueError):
    pass


def _sample_structure(sample) -> tuple[str, ...]:
    return (
        sample.prompt_id,
        sample.prompt_family_id,
        sample.model.identity_hash,
        sample.domain.value,
        str(sample.target_length),
        sample.label.value,
        sample.watermark.watermark_config_hash,
        sample.watermark.key_split.value,
        sample.watermark.key_id,
    )


def _pair_structure(sample) -> tuple[str, ...]:
    return (
        sample.prompt_id,
        sample.prompt_family_id,
        sample.model.identity_hash,
        sample.domain.value,
        str(sample.target_length),
        sample.watermark.watermark_config_hash,
        sample.watermark.key_split.value,
        sample.watermark.key_id,
    )


def _seed_map(manifest: CorpusManifest) -> dict[tuple[str, ...], set[int]]:
    values: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for sample in manifest.samples:
        values[_pair_structure(sample)].add(sample.generation.seed)
    return values


def _structure_hash(manifest: CorpusManifest) -> str:
    counts = Counter(_sample_structure(sample) for sample in manifest.samples)
    return sha256_json(tuple(sorted(counts.items())))


def _seed_set_hash(manifest: CorpusManifest) -> str:
    return sha256_json(tuple(sorted({sample.generation.seed for sample in manifest.samples})))


def _verify_manifest_pair(
    preregistration: ConfirmatoryPreregistration,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
) -> None:
    if e20_manifest.manifest_hash == e21_manifest.manifest_hash:
        raise E21RerunError("E21 corpus must be distinct from the E20 corpus")
    expected_models = {value.identity_hash for value in preregistration.model_tokenizers}
    for name, manifest in (("E20", e20_manifest), ("E21", e21_manifest)):
        if any(sample.split is not CorpusSplit.FINAL_TEST for sample in manifest.samples):
            raise E21RerunError(f"{name} rerun comparison accepts FINAL_TEST samples only")
        if {sample.model.identity_hash for sample in manifest.samples} != expected_models:
            raise E21RerunError(f"{name} corpus model/tokenizer identities do not match preregistration")
    e20_structure = Counter(_sample_structure(sample) for sample in e20_manifest.samples)
    e21_structure = Counter(_sample_structure(sample) for sample in e21_manifest.samples)
    if e20_structure != e21_structure:
        raise E21RerunError("E21 corpus must preserve the exact E20 prompt/core-cell/label/key structure")
    e20_ids = {sample.sample_id for sample in e20_manifest.samples}
    e21_ids = {sample.sample_id for sample in e21_manifest.samples}
    if e20_ids & e21_ids:
        raise E21RerunError("E21 sample IDs must be disjoint from E20 sample IDs")
    e20_pairs = _seed_map(e20_manifest)
    e21_pairs = _seed_map(e21_manifest)
    if set(e20_pairs) != set(e21_pairs):
        raise E21RerunError("E21 seed groups do not match E20 pair structure")
    for key in e20_pairs:
        if len(e20_pairs[key]) != 1 or len(e21_pairs[key]) != 1:
            raise E21RerunError("each matched prompt/core cell must use one paired generation seed per run")
        if next(iter(e20_pairs[key])) == next(iter(e21_pairs[key])):
            raise E21RerunError("E21 requires a fresh generation seed for every matched prompt/core cell")
    e20_seeds = {sample.generation.seed for sample in e20_manifest.samples}
    e21_seeds = {sample.generation.seed for sample in e21_manifest.samples}
    if e20_seeds & e21_seeds:
        raise E21RerunError("E21 generation seed set must be disjoint from E20")


@dataclass(frozen=True, slots=True)
class E21RerunSeal:
    algorithm_version: str
    experiment_id: str
    preregistration_hash: str
    e20_execution_id: str
    e20_authorization_hash: str
    e20_completed_ledger_hash: str
    e20_result_bundle_hash: str
    e20_corpus_manifest_hash: str
    e21_corpus_manifest_hash: str
    test_key_manifest_hash: str
    structure_hash: str
    e20_seed_set_hash: str
    e21_seed_set_hash: str
    seal_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_RERUN_SEAL_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 rerun seal algorithm version")
        if self.experiment_id != E21_EXPERIMENT_ID:
            raise ValueError("E21 rerun seal must use experiment_id E21")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("e20_execution_id", self.e20_execution_id),
            ("e20_authorization_hash", self.e20_authorization_hash),
            ("e20_completed_ledger_hash", self.e20_completed_ledger_hash),
            ("e20_result_bundle_hash", self.e20_result_bundle_hash),
            ("e20_corpus_manifest_hash", self.e20_corpus_manifest_hash),
            ("e21_corpus_manifest_hash", self.e21_corpus_manifest_hash),
            ("test_key_manifest_hash", self.test_key_manifest_hash),
            ("structure_hash", self.structure_hash),
            ("e20_seed_set_hash", self.e20_seed_set_hash),
            ("e21_seed_set_hash", self.e21_seed_set_hash),
            ("seal_hash", self.seal_hash),
        ):
            require_sha256(name, value)
        if self.e20_corpus_manifest_hash == self.e21_corpus_manifest_hash:
            raise ValueError("E21 rerun seal requires a distinct rerun corpus")
        if self.e20_seed_set_hash == self.e21_seed_set_hash:
            raise ValueError("E21 rerun seal requires fresh generation seeds")
        if self.seal_hash != sha256_json(self._payload()):
            raise ValueError("seal_hash does not match E21 rerun seal")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_id": self.experiment_id,
            "preregistration_hash": self.preregistration_hash,
            "e20_execution_id": self.e20_execution_id,
            "e20_authorization_hash": self.e20_authorization_hash,
            "e20_completed_ledger_hash": self.e20_completed_ledger_hash,
            "e20_result_bundle_hash": self.e20_result_bundle_hash,
            "e20_corpus_manifest_hash": self.e20_corpus_manifest_hash,
            "e21_corpus_manifest_hash": self.e21_corpus_manifest_hash,
            "test_key_manifest_hash": self.test_key_manifest_hash,
            "structure_hash": self.structure_hash,
            "e20_seed_set_hash": self.e20_seed_set_hash,
            "e21_seed_set_hash": self.e21_seed_set_hash,
        }


def build_e21_rerun_seal(
    preregistration: ConfirmatoryPreregistration,
    e20_authorization: E20ExecutionAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> E21RerunSeal:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(e20_authorization, E20ExecutionAuthorization):
        raise TypeError("e20_authorization must be an E20ExecutionAuthorization")
    if not isinstance(e20_ledger, E20RunLedger):
        raise TypeError("e20_ledger must be an E20RunLedger")
    if not isinstance(e20_manifest, CorpusManifest) or not isinstance(e21_manifest, CorpusManifest):
        raise TypeError("E20 and E21 manifests must be CorpusManifest values")
    if not isinstance(test_key_manifest, ConfirmatoryTestKeyManifest):
        raise TypeError("test_key_manifest must be a ConfirmatoryTestKeyManifest")
    verify_e20_run_ledger(e20_ledger, e20_authorization)
    if e20_ledger.state is not E20RunState.COMPLETED:
        raise E21RerunError("E21 can be sealed only after a non-invalidated completed E20 run")
    if e20_authorization.preregistration_hash != preregistration.preregistration_hash:
        raise E21RerunError("E20 authorization does not bind the frozen preregistration")
    if e20_authorization.corpus_manifest_hash != e20_manifest.manifest_hash:
        raise E21RerunError("E20 authorization does not bind the supplied E20 corpus")
    if e20_authorization.test_key_manifest_hash != test_key_manifest.manifest_hash:
        raise E21RerunError("E21 must reuse the E20 sealed TEST_KEYS manifest")
    _verify_manifest_pair(preregistration, e20_manifest, e21_manifest)
    result_hash = e20_ledger.events[-1].artifact_hash
    if result_hash is None:
        raise E21RerunError("completed E20 ledger is missing its result artifact hash")
    structure_hash = _structure_hash(e20_manifest)
    e20_seed_hash = _seed_set_hash(e20_manifest)
    e21_seed_hash = _seed_set_hash(e21_manifest)
    payload = {
        "algorithm_version": E21_RERUN_SEAL_ALGORITHM_VERSION,
        "experiment_id": E21_EXPERIMENT_ID,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_execution_id": e20_authorization.execution_id,
        "e20_authorization_hash": e20_authorization.authorization_hash,
        "e20_completed_ledger_hash": e20_ledger.ledger_hash,
        "e20_result_bundle_hash": result_hash,
        "e20_corpus_manifest_hash": e20_manifest.manifest_hash,
        "e21_corpus_manifest_hash": e21_manifest.manifest_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "structure_hash": structure_hash,
        "e20_seed_set_hash": e20_seed_hash,
        "e21_seed_set_hash": e21_seed_hash,
    }
    return E21RerunSeal(
        E21_RERUN_SEAL_ALGORITHM_VERSION,
        E21_EXPERIMENT_ID,
        preregistration.preregistration_hash,
        e20_authorization.execution_id,
        e20_authorization.authorization_hash,
        e20_ledger.ledger_hash,
        result_hash,
        e20_manifest.manifest_hash,
        e21_manifest.manifest_hash,
        test_key_manifest.manifest_hash,
        structure_hash,
        e20_seed_hash,
        e21_seed_hash,
        sha256_json(payload),
    )


def verify_e21_rerun_seal(
    seal: E21RerunSeal,
    preregistration: ConfirmatoryPreregistration,
    e20_authorization: E20ExecutionAuthorization,
    e20_ledger: E20RunLedger,
    e20_manifest: CorpusManifest,
    e21_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> None:
    if not isinstance(seal, E21RerunSeal):
        raise TypeError("seal must be an E21RerunSeal")
    expected = build_e21_rerun_seal(
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
    )
    if seal != expected:
        raise E21RerunError("E21 rerun seal does not replay exactly from frozen inputs")


def _verify_test_keys(
    manifest: ConfirmatoryTestKeyManifest,
    serialized_test_key_material: Mapping[str, bytes],
) -> None:
    values = dict(serialized_test_key_material)
    expected = {entry.entry_hash for entry in manifest.entries}
    if set(values) != expected:
        raise E21RerunError("runtime E21 TEST_KEYS material must exactly cover the E20 sealed manifest")
    for entry in manifest.entries:
        try:
            verify_confirmatory_test_key_material(entry, values[entry.entry_hash])
        except Exception as error:
            raise E21RerunError("runtime E21 TEST_KEYS material does not replay the sealed commitment") from error


@dataclass(frozen=True, slots=True)
class E21ExecutionAuthorization:
    algorithm_version: str
    experiment_id: str
    execution_id: str
    rerun_seal_hash: str
    preregistration_hash: str
    e20_execution_id: str
    e21_corpus_manifest_hash: str
    test_key_manifest_hash: str
    code_commit: str
    environment_snapshot_hash: str
    dependency_lock_hash: str
    worker_version: str
    shard_count: int
    output_namespace: str
    authorization_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 execution authorization algorithm version")
        if self.experiment_id != E21_EXPERIMENT_ID:
            raise ValueError("E21 execution authorization must use experiment_id E21")
        for name, value in (
            ("execution_id", self.execution_id),
            ("rerun_seal_hash", self.rerun_seal_hash),
            ("preregistration_hash", self.preregistration_hash),
            ("e20_execution_id", self.e20_execution_id),
            ("e21_corpus_manifest_hash", self.e21_corpus_manifest_hash),
            ("test_key_manifest_hash", self.test_key_manifest_hash),
            ("environment_snapshot_hash", self.environment_snapshot_hash),
            ("dependency_lock_hash", self.dependency_lock_hash),
            ("authorization_hash", self.authorization_hash),
        ):
            require_sha256(name, value)
        require_clean_string("code_commit", self.code_commit)
        if len(self.code_commit) != 40 or any(value not in "0123456789abcdef" for value in self.code_commit):
            raise ValueError("code_commit must be a full lowercase 40-character Git revision")
        require_clean_string("worker_version", self.worker_version)
        require_int("shard_count", self.shard_count)
        if self.shard_count <= 0 or self.shard_count > 4096:
            raise ValueError("shard_count must be between 1 and 4096")
        if self.output_namespace != f"e21/{self.execution_id}":
            raise ValueError("output_namespace must be derived from the E21 execution_id")
        expected_execution_id = sha256_json(
            {
                "experiment_id": E21_EXPERIMENT_ID,
                "rerun_seal_hash": self.rerun_seal_hash,
            }
        )
        if self.execution_id != expected_execution_id:
            raise ValueError("execution_id does not match E21 rerun seal")
        if self.authorization_hash != sha256_json(self._payload()):
            raise ValueError("authorization_hash does not match E21 execution authorization")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_id": self.experiment_id,
            "execution_id": self.execution_id,
            "rerun_seal_hash": self.rerun_seal_hash,
            "preregistration_hash": self.preregistration_hash,
            "e20_execution_id": self.e20_execution_id,
            "e21_corpus_manifest_hash": self.e21_corpus_manifest_hash,
            "test_key_manifest_hash": self.test_key_manifest_hash,
            "code_commit": self.code_commit,
            "environment_snapshot_hash": self.environment_snapshot_hash,
            "dependency_lock_hash": self.dependency_lock_hash,
            "worker_version": self.worker_version,
            "shard_count": self.shard_count,
            "output_namespace": self.output_namespace,
        }


def authorize_e21_execution(
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
    dirty_worktree: bool,
    output_namespace_available: bool,
    code_commit: str,
) -> E21ExecutionAuthorization:
    if not isinstance(environment, EnvironmentSnapshot):
        raise TypeError("environment must be an EnvironmentSnapshot")
    require_sha256("dependency_lock_hash", dependency_lock_hash)
    require_clean_string("worker_version", worker_version)
    require_int("shard_count", shard_count)
    require_bool("dirty_worktree", dirty_worktree)
    require_bool("output_namespace_available", output_namespace_available)
    if dirty_worktree:
        raise E21RerunError("E21 authorization requires a clean worktree")
    if not output_namespace_available:
        raise E21RerunError("E21 output namespace already exists")
    if code_commit != preregistration.code_commit or code_commit != e20_authorization.code_commit:
        raise E21RerunError("E21 must use the exact frozen code commit used by the E20 authorization")
    verify_e21_rerun_seal(
        seal,
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        test_key_manifest,
    )
    _verify_test_keys(test_key_manifest, serialized_test_key_material)
    execution_id = sha256_json(
        {
            "experiment_id": E21_EXPERIMENT_ID,
            "rerun_seal_hash": seal.seal_hash,
        }
    )
    output_namespace = f"e21/{execution_id}"
    payload = {
        "algorithm_version": E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        "experiment_id": E21_EXPERIMENT_ID,
        "execution_id": execution_id,
        "rerun_seal_hash": seal.seal_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_execution_id": e20_authorization.execution_id,
        "e21_corpus_manifest_hash": e21_manifest.manifest_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "code_commit": code_commit,
        "environment_snapshot_hash": environment.snapshot_hash,
        "dependency_lock_hash": dependency_lock_hash,
        "worker_version": worker_version,
        "shard_count": shard_count,
        "output_namespace": output_namespace,
    }
    return E21ExecutionAuthorization(
        E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        E21_EXPERIMENT_ID,
        execution_id,
        seal.seal_hash,
        preregistration.preregistration_hash,
        e20_authorization.execution_id,
        e21_manifest.manifest_hash,
        test_key_manifest.manifest_hash,
        code_commit,
        environment.snapshot_hash,
        dependency_lock_hash,
        worker_version,
        shard_count,
        output_namespace,
        sha256_json(payload),
    )
