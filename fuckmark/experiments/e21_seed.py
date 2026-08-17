from __future__ import annotations

from .._validation import require_clean_string
from ..corpus import CorpusManifest
from ..hashing import derive_seed
from .e21_rerun import E21ExecutionAuthorization


E21_SEED_DERIVATION_ALGORITHM_VERSION = "e21-seed-derivation-v1"


class E21SeedVerificationError(ValueError):
    pass


def _require_authorized_sample(
    authorization: E21ExecutionAuthorization,
    corpus_manifest: CorpusManifest,
    sample_id: str,
) -> None:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    require_clean_string("sample_id", sample_id)
    if corpus_manifest.manifest_hash != authorization.e21_corpus_manifest_hash:
        raise E21SeedVerificationError("corpus manifest does not match E21 authorization")
    if sample_id not in {value.sample_id for value in corpus_manifest.samples}:
        raise E21SeedVerificationError("sample_id is not part of the authorized E21 corpus")


def e21_sample_shard(
    authorization: E21ExecutionAuthorization,
    corpus_manifest: CorpusManifest,
    sample_id: str,
) -> int:
    _require_authorized_sample(authorization, corpus_manifest, sample_id)
    return derive_seed(
        authorization.execution_id,
        E21_SEED_DERIVATION_ALGORITHM_VERSION,
        "shard",
        sample_id,
        bits=64,
    ) % authorization.shard_count


def derive_e21_condition_seed(
    authorization: E21ExecutionAuthorization,
    corpus_manifest: CorpusManifest,
    sample_id: str,
    condition_id: str,
    purpose: str,
) -> int:
    _require_authorized_sample(authorization, corpus_manifest, sample_id)
    require_clean_string("condition_id", condition_id)
    require_clean_string("purpose", purpose)
    return derive_seed(
        authorization.execution_id,
        E21_SEED_DERIVATION_ALGORITHM_VERSION,
        "condition",
        sample_id,
        condition_id,
        purpose,
        bits=64,
    )
