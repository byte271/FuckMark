from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..corpus import TinyDevCorpusArtifact
from ..detectors import DetectorFamily
from ..hashing import sha256_json
from .development_calibration import DevelopmentCalibrationBinding, calibrate_tiny_dev_detector
from .e02_pristine import E02PristineDetectabilityResult, run_e02_pristine_detectability
from .tiny_dev_detector_evidence import TinyDevDetectorEvidenceArtifact, TinyDevDetectorFamilyEvidence


TINY_DEV_E02_FAMILY_ALGORITHM_VERSION = "tiny-dev-e02-family-evidence-v1"
TINY_DEV_E02_EVIDENCE_ALGORITHM_VERSION = "tiny-dev-e02-evidence-v1"
TINY_DEV_E02_SCIENTIFIC_STATUS = "DEVELOPMENT_ONLY"


class TinyDevE02EvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TinyDevE02FamilyEvidence:
    algorithm_version: str
    detector_family: DetectorFamily
    detector_source_family_hash: str
    calibration_binding: DevelopmentCalibrationBinding
    result: E02PristineDetectabilityResult
    family_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_E02_FAMILY_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev E02 family evidence version")
        if self.detector_family not in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN):
            raise ValueError("TinyDev E02 evidence currently supports Mean and Weighted Mean only")
        require_sha256("detector_source_family_hash", self.detector_source_family_hash)
        if not isinstance(self.calibration_binding, DevelopmentCalibrationBinding):
            raise TypeError("calibration_binding must be a DevelopmentCalibrationBinding")
        if not isinstance(self.result, E02PristineDetectabilityResult):
            raise TypeError("result must be an E02PristineDetectabilityResult")
        identity = self.calibration_binding.calibration_bundle.detector_identity
        if identity.detector_family is not self.detector_family:
            raise ValueError("E02 calibration detector family does not match family evidence")
        if self.result.calibration_binding_hash != self.calibration_binding.binding_hash:
            raise ValueError("E02 result does not bind the supplied development calibration")
        if self.result.detector_identity_hash != identity.identity_hash:
            raise ValueError("E02 result detector identity does not match development calibration")
        require_sha256("family_hash", self.family_hash)
        if self.family_hash != sha256_json(self._payload()):
            raise ValueError("family_hash does not match TinyDev E02 family evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "detector_family": self.detector_family.value,
            "detector_source_family_hash": self.detector_source_family_hash,
            "calibration_binding": self.calibration_binding,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True)
class TinyDevE02EvidenceArtifact:
    algorithm_version: str
    tiny_dev_artifact_hash: str
    corpus_manifest_hash: str
    detector_artifact_hash: str
    families: tuple[TinyDevE02FamilyEvidence, ...]
    scientific_status: str
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_E02_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev E02 evidence version")
        for name, value in (
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("detector_artifact_hash", self.detector_artifact_hash),
            ("artifact_hash", self.artifact_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.families, tuple) or any(
            not isinstance(value, TinyDevE02FamilyEvidence) for value in self.families
        ):
            raise TypeError("families must contain TinyDevE02FamilyEvidence values")
        if tuple(value.detector_family for value in self.families) != (
            DetectorFamily.MEAN,
            DetectorFamily.WEIGHTED_MEAN,
        ):
            raise ValueError("TinyDev E02 evidence must contain Mean then Weighted Mean")
        if any(value.result.tiny_dev_artifact_hash != self.tiny_dev_artifact_hash for value in self.families):
            raise ValueError("E02 family result does not match top-level TinyDev artifact")
        require_clean_string("scientific_status", self.scientific_status)
        if self.scientific_status != TINY_DEV_E02_SCIENTIFIC_STATUS:
            raise ValueError("TinyDev E02 evidence must remain development-only")
        if self.artifact_hash != sha256_json(self._payload()):
            raise ValueError("artifact_hash does not match TinyDev E02 evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "detector_artifact_hash": self.detector_artifact_hash,
            "families": self.families,
            "scientific_status": self.scientific_status,
        }


def _build_family(
    corpus: TinyDevCorpusArtifact,
    source: TinyDevDetectorFamilyEvidence,
) -> TinyDevE02FamilyEvidence:
    binding = calibrate_tiny_dev_detector(corpus, source.calibration_evidence)
    result = run_e02_pristine_detectability(corpus, binding, source.attack_evidence)
    payload = {
        "algorithm_version": TINY_DEV_E02_FAMILY_ALGORITHM_VERSION,
        "detector_family": source.detector_family.value,
        "detector_source_family_hash": source.family_hash,
        "calibration_binding": binding,
        "result": result,
    }
    return TinyDevE02FamilyEvidence(
        algorithm_version=TINY_DEV_E02_FAMILY_ALGORITHM_VERSION,
        detector_family=source.detector_family,
        detector_source_family_hash=source.family_hash,
        calibration_binding=binding,
        result=result,
        family_hash=sha256_json(payload),
    )


def build_tiny_dev_e02_evidence(
    corpus: TinyDevCorpusArtifact,
    detector_evidence: TinyDevDetectorEvidenceArtifact,
) -> TinyDevE02EvidenceArtifact:
    if not isinstance(corpus, TinyDevCorpusArtifact):
        raise TypeError("corpus must be a TinyDevCorpusArtifact")
    if not isinstance(detector_evidence, TinyDevDetectorEvidenceArtifact):
        raise TypeError("detector_evidence must be a TinyDevDetectorEvidenceArtifact")
    if detector_evidence.tiny_dev_artifact_hash != corpus.artifact_hash:
        raise TinyDevE02EvidenceError("detector evidence does not belong to the supplied TinyDev corpus")
    if detector_evidence.corpus_manifest_hash != corpus.manifest.manifest_hash:
        raise TinyDevE02EvidenceError("detector evidence corpus manifest does not match the supplied TinyDev corpus")
    families = tuple(_build_family(corpus, value) for value in detector_evidence.family_evidence)
    payload = {
        "algorithm_version": TINY_DEV_E02_EVIDENCE_ALGORITHM_VERSION,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "detector_artifact_hash": detector_evidence.artifact_hash,
        "families": families,
        "scientific_status": TINY_DEV_E02_SCIENTIFIC_STATUS,
    }
    return TinyDevE02EvidenceArtifact(
        **payload,
        artifact_hash=sha256_json(payload),
    )
