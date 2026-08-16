from __future__ import annotations

from ..corpus import CorpusManifest
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import (
    CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION,
    ConfirmatoryCorpusSeal,
    ConfirmatoryCorpusSealError,
    build_confirmatory_corpus_seal as _build_confirmatory_corpus_seal,
    verify_confirmatory_corpus_seal as _verify_confirmatory_corpus_seal,
)
from .confirmatory_keys import ConfirmatoryTestKeyManifest


CONFIRMATORY_CORPUS_TRACK_BINDING_ALGORITHM_VERSION = "confirmatory-corpus-track-binding-v1"


def _verify_corpus_watermark_tracks(
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
) -> None:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    used_config_hashes: set[str] = set()
    for sample in corpus_manifest.samples:
        config_hash = sample.watermark.watermark_config_hash
        try:
            preregistration.watermark_tracks.track_for(config_hash)
        except KeyError as error:
            raise ConfirmatoryCorpusSealError(
                "confirmatory corpus contains a watermark configuration outside the sealed generation tracks"
            ) from error
        used_config_hashes.add(config_hash)
    sealed_config_hashes = {
        value.watermark_config_hash for value in preregistration.watermark_tracks.tracks
    }
    if used_config_hashes != sealed_config_hashes:
        raise ConfirmatoryCorpusSealError(
            "confirmatory corpus must use every sealed generation watermark track"
        )


def build_confirmatory_corpus_seal(
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> ConfirmatoryCorpusSeal:
    _verify_corpus_watermark_tracks(preregistration, corpus_manifest)
    return _build_confirmatory_corpus_seal(
        preregistration,
        corpus_manifest,
        test_key_manifest,
    )


def verify_confirmatory_corpus_seal(
    seal: ConfirmatoryCorpusSeal,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> None:
    _verify_corpus_watermark_tracks(preregistration, corpus_manifest)
    _verify_confirmatory_corpus_seal(
        seal,
        preregistration,
        corpus_manifest,
        test_key_manifest,
    )


__all__ = [
    "CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION",
    "CONFIRMATORY_CORPUS_TRACK_BINDING_ALGORITHM_VERSION",
    "ConfirmatoryCorpusSeal",
    "ConfirmatoryCorpusSealError",
    "build_confirmatory_corpus_seal",
    "verify_confirmatory_corpus_seal",
]
