from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from ..hashing import sha256_json
from .bayesian import BayesianCheckpoint
from .bayesian_training import (
    BAYESIAN_SOURCE_PATH,
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianConfirmatoryReadiness,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
)


BAYESIAN_READINESS_ARTIFACT_BUNDLE_VERSION = "bayesian-readiness-artifact-bundle-v1"


@dataclass(frozen=True, slots=True)
class BayesianReadinessArtifactBundle:
    algorithm_version: str
    readiness: BayesianConfirmatoryReadiness
    provenance: BayesianTrainingProvenance
    sanity: BayesianSanityEvidence
    checkpoint: BayesianCheckpoint
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != BAYESIAN_READINESS_ARTIFACT_BUNDLE_VERSION:
            raise ValueError("unsupported Bayesian readiness artifact bundle version")
        if not isinstance(self.readiness, BayesianConfirmatoryReadiness):
            raise TypeError("readiness must be BayesianConfirmatoryReadiness")
        if not isinstance(self.provenance, BayesianTrainingProvenance):
            raise TypeError("provenance must be BayesianTrainingProvenance")
        if not isinstance(self.sanity, BayesianSanityEvidence):
            raise TypeError("sanity must be BayesianSanityEvidence")
        if not isinstance(self.checkpoint, BayesianCheckpoint):
            raise TypeError("checkpoint must be BayesianCheckpoint")
        if not self.readiness.ready:
            raise ValueError("Bayesian readiness artifact bundle requires READY evidence")
        if self.sanity.training_provenance_hash != self.provenance.provenance_hash:
            raise ValueError("Bayesian sanity evidence is not bound to training provenance")
        if not self.sanity.all_passed:
            raise ValueError("Bayesian sanity evidence contains a failed gate")
        if self.checkpoint.fixture_kind != BAYESIAN_TRAINED_CHECKPOINT_KIND:
            raise ValueError("Bayesian readiness artifact bundle requires a trained source-compatible checkpoint")
        if self.checkpoint.checkpoint_hash != self.provenance.checkpoint_hash:
            raise ValueError("Bayesian checkpoint hash does not match training provenance")
        if self.checkpoint.watermarking_depth != self.provenance.watermarking_depth:
            raise ValueError("Bayesian checkpoint depth does not match training provenance")
        if (
            self.checkpoint.source_id != DEEPMIND_REFERENCE_SOURCE_PIN.source_id
            or self.checkpoint.source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit
        ):
            raise ValueError("Bayesian checkpoint source identity does not match the pinned DeepMind reference")
        if self.provenance.source_path != BAYESIAN_SOURCE_PATH:
            raise ValueError("Bayesian provenance source path does not match the pinned detector source")
        if self.readiness.training_provenance_hash != self.provenance.provenance_hash:
            raise ValueError("Bayesian readiness does not bind the supplied training provenance")
        if self.readiness.sanity_evidence_hash != self.sanity.evidence_hash:
            raise ValueError("Bayesian readiness does not bind the supplied sanity evidence")
        if self.readiness.checkpoint_hash != self.checkpoint.checkpoint_hash:
            raise ValueError("Bayesian readiness does not bind the supplied checkpoint")
        if self.readiness.adapter_id != self.provenance.adapter_id:
            raise ValueError("Bayesian readiness adapter identity does not match training provenance")
        if self.readiness.adapter_config_hash != self.provenance.adapter_config_hash:
            raise ValueError("Bayesian readiness adapter configuration does not match training provenance")
        if self.readiness.model_tokenizer_hash != self.provenance.model_tokenizer_hash:
            raise ValueError("Bayesian readiness model/tokenizer identity does not match training provenance")
        if self.readiness.watermarking_depth != self.provenance.watermarking_depth:
            raise ValueError("Bayesian readiness depth does not match training provenance")
        if self.readiness.source_id != self.provenance.source_id:
            raise ValueError("Bayesian readiness source_id does not match training provenance")
        if self.readiness.source_commit != self.provenance.source_commit:
            raise ValueError("Bayesian readiness source_commit does not match training provenance")
        if self.readiness.source_path != self.provenance.source_path:
            raise ValueError("Bayesian readiness source_path does not match training provenance")
        require_sha256("bundle_hash", self.bundle_hash)
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match Bayesian readiness artifact bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "readiness_hash": self.readiness.readiness_hash,
            "training_provenance_hash": self.provenance.provenance_hash,
            "sanity_evidence_hash": self.sanity.evidence_hash,
            "checkpoint_hash": self.checkpoint.checkpoint_hash,
        }

    @classmethod
    def create(
        cls,
        readiness: BayesianConfirmatoryReadiness,
        provenance: BayesianTrainingProvenance,
        sanity: BayesianSanityEvidence,
        checkpoint: BayesianCheckpoint,
    ) -> BayesianReadinessArtifactBundle:
        payload = {
            "algorithm_version": BAYESIAN_READINESS_ARTIFACT_BUNDLE_VERSION,
            "readiness_hash": readiness.readiness_hash,
            "training_provenance_hash": provenance.provenance_hash,
            "sanity_evidence_hash": sanity.evidence_hash,
            "checkpoint_hash": checkpoint.checkpoint_hash,
        }
        return cls(
            BAYESIAN_READINESS_ARTIFACT_BUNDLE_VERSION,
            readiness,
            provenance,
            sanity,
            checkpoint,
            sha256_json(payload),
        )


def verify_bayesian_readiness_artifact_bundle(bundle: BayesianReadinessArtifactBundle) -> None:
    if not isinstance(bundle, BayesianReadinessArtifactBundle):
        raise TypeError("bundle must be BayesianReadinessArtifactBundle")
    expected = BayesianReadinessArtifactBundle.create(
        bundle.readiness,
        bundle.provenance,
        bundle.sanity,
        bundle.checkpoint,
    )
    if bundle != expected:
        raise ValueError("Bayesian readiness artifact bundle does not replay exactly")
