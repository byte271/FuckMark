from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, CorpusSplit, TinyDevCorpusArtifact, WatermarkLabel
from ..hashing import sha256_json
from ..transforms import TransformFamily, TransformRegistry, TransformTier


TINY_DEV_TRANSFORMABILITY_ALGORITHM_VERSION = "tiny-dev-transformability-v2"
TINY_DEV_TRANSFORMABILITY_MIN_INDEPENDENT_CANDIDATES = 4


class TinyDevTransformabilityStatus(str, Enum):
    READY = "READY"
    INSUFFICIENT_CANDIDATES = "INSUFFICIENT_CANDIDATES"


def _maximum_nonoverlapping_candidate_count(candidates) -> int:
    ordered = tuple(sorted(candidates, key=lambda value: (value.end, value.start, value.candidate_id)))
    count = 0
    cursor = -1
    for candidate in ordered:
        if candidate.start >= cursor:
            count += 1
            cursor = candidate.end
    return count


@dataclass(frozen=True, slots=True)
class TinyDevTransformabilityRow:
    sample_id: str
    domain: CorpusDomain
    candidate_count: int
    independent_candidate_count: int
    rejection_count: int
    candidate_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    families: tuple[TransformFamily, ...]
    tiers: tuple[TransformTier, ...]
    enumeration_hash: str
    row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        for name, value in (
            ("candidate_count", self.candidate_count),
            ("independent_candidate_count", self.independent_candidate_count),
            ("rejection_count", self.rejection_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.independent_candidate_count > self.candidate_count:
            raise ValueError("independent_candidate_count cannot exceed candidate_count")
        if not isinstance(self.candidate_ids, tuple) or not isinstance(self.rule_ids, tuple):
            raise TypeError("candidate_ids and rule_ids must be tuples")
        if len(self.candidate_ids) != self.candidate_count or len(self.rule_ids) != self.candidate_count:
            raise ValueError("candidate metadata count must equal candidate_count")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("candidate_ids must be unique")
        for value in self.candidate_ids:
            require_sha256("candidate_id", value)
        if not isinstance(self.families, tuple) or any(not isinstance(value, TransformFamily) for value in self.families):
            raise TypeError("families must contain TransformFamily values")
        if not isinstance(self.tiers, tuple) or any(not isinstance(value, TransformTier) for value in self.tiers):
            raise TypeError("tiers must contain TransformTier values")
        if len(self.families) != self.candidate_count or len(self.tiers) != self.candidate_count:
            raise ValueError("candidate family/tier count must equal candidate_count")
        require_sha256("enumeration_hash", self.enumeration_hash)
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match TinyDev transformability row")

    def _payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "domain": self.domain.value,
            "candidate_count": self.candidate_count,
            "independent_candidate_count": self.independent_candidate_count,
            "rejection_count": self.rejection_count,
            "candidate_ids": self.candidate_ids,
            "rule_ids": self.rule_ids,
            "families": tuple(value.value for value in self.families),
            "tiers": tuple(value.value for value in self.tiers),
            "enumeration_hash": self.enumeration_hash,
        }


@dataclass(frozen=True, slots=True)
class TinyDevTransformabilityAudit:
    algorithm_version: str
    tiny_dev_artifact_hash: str
    corpus_manifest_hash: str
    ruleset_hash: str
    minimum_independent_candidates_per_source: int
    rows: tuple[TinyDevTransformabilityRow, ...]
    expected_source_count: int
    transformable_source_count: int
    blocked_source_ids: tuple[str, ...]
    status: TinyDevTransformabilityStatus
    audit_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TINY_DEV_TRANSFORMABILITY_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev transformability audit version")
        for name, value in (
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("ruleset_hash", self.ruleset_hash),
            ("audit_hash", self.audit_hash),
        ):
            require_sha256(name, value)
        require_int("minimum_independent_candidates_per_source", self.minimum_independent_candidates_per_source)
        if self.minimum_independent_candidates_per_source != TINY_DEV_TRANSFORMABILITY_MIN_INDEPENDENT_CANDIDATES:
            raise ValueError("minimum independent-candidate gate does not match TinyDev audit policy")
        if not isinstance(self.rows, tuple) or any(not isinstance(value, TinyDevTransformabilityRow) for value in self.rows):
            raise TypeError("rows must contain TinyDevTransformabilityRow values")
        if tuple(sorted(self.rows, key=lambda value: value.sample_id)) != self.rows:
            raise ValueError("rows must use canonical sample ordering")
        require_int("expected_source_count", self.expected_source_count)
        require_int("transformable_source_count", self.transformable_source_count)
        if self.expected_source_count != 4 or len(self.rows) != 4:
            raise ValueError("TinyDev transformability audit requires four watermarked attack sources")
        expected_transformable = sum(
            value.independent_candidate_count >= self.minimum_independent_candidates_per_source
            for value in self.rows
        )
        if self.transformable_source_count != expected_transformable:
            raise ValueError("transformable_source_count does not match rows")
        expected_blocked = tuple(
            value.sample_id for value in self.rows
            if value.independent_candidate_count < self.minimum_independent_candidates_per_source
        )
        if self.blocked_source_ids != expected_blocked:
            raise ValueError("blocked_source_ids does not match rows")
        expected_status = (
            TinyDevTransformabilityStatus.READY
            if not expected_blocked
            else TinyDevTransformabilityStatus.INSUFFICIENT_CANDIDATES
        )
        if self.status is not expected_status:
            raise ValueError("transformability status does not match source coverage")
        if self.audit_hash != sha256_json(self._payload()):
            raise ValueError("audit_hash does not match TinyDev transformability audit")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "ruleset_hash": self.ruleset_hash,
            "minimum_independent_candidates_per_source": self.minimum_independent_candidates_per_source,
            "rows": self.rows,
            "expected_source_count": self.expected_source_count,
            "transformable_source_count": self.transformable_source_count,
            "blocked_source_ids": self.blocked_source_ids,
            "status": self.status.value,
        }


def build_tiny_dev_transformability_audit(
    artifact: TinyDevCorpusArtifact,
    registry: TransformRegistry,
) -> TinyDevTransformabilityAudit:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    sources = tuple(sorted(
        (
            sample for sample in artifact.manifest.samples
            if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
            and sample.label is WatermarkLabel.WATERMARKED
        ),
        key=lambda value: value.sample_id,
    ))
    if len(sources) != 4:
        raise ValueError("TinyDev transformability audit requires four watermarked attack sources")
    rows = []
    for sample in sources:
        enumeration = registry.enumerate(sample.text)
        independent_count = _maximum_nonoverlapping_candidate_count(enumeration.candidates)
        payload = {
            "sample_id": sample.sample_id,
            "domain": sample.domain.value,
            "candidate_count": len(enumeration.candidates),
            "independent_candidate_count": independent_count,
            "rejection_count": len(enumeration.rejections),
            "candidate_ids": tuple(value.candidate_id for value in enumeration.candidates),
            "rule_ids": tuple(value.rule_id for value in enumeration.candidates),
            "families": tuple(value.family.value for value in enumeration.candidates),
            "tiers": tuple(value.tier.value for value in enumeration.candidates),
            "enumeration_hash": enumeration.enumeration_hash,
        }
        rows.append(TinyDevTransformabilityRow(
            sample_id=sample.sample_id,
            domain=sample.domain,
            candidate_count=len(enumeration.candidates),
            independent_candidate_count=independent_count,
            rejection_count=len(enumeration.rejections),
            candidate_ids=tuple(value.candidate_id for value in enumeration.candidates),
            rule_ids=tuple(value.rule_id for value in enumeration.candidates),
            families=tuple(value.family for value in enumeration.candidates),
            tiers=tuple(value.tier for value in enumeration.candidates),
            enumeration_hash=enumeration.enumeration_hash,
            row_hash=sha256_json(payload),
        ))
    row_tuple = tuple(rows)
    blocked = tuple(
        value.sample_id for value in row_tuple
        if value.independent_candidate_count < TINY_DEV_TRANSFORMABILITY_MIN_INDEPENDENT_CANDIDATES
    )
    status = (
        TinyDevTransformabilityStatus.READY
        if not blocked
        else TinyDevTransformabilityStatus.INSUFFICIENT_CANDIDATES
    )
    payload = {
        "algorithm_version": TINY_DEV_TRANSFORMABILITY_ALGORITHM_VERSION,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "corpus_manifest_hash": artifact.manifest.manifest_hash,
        "ruleset_hash": registry.ruleset_hash,
        "minimum_independent_candidates_per_source": TINY_DEV_TRANSFORMABILITY_MIN_INDEPENDENT_CANDIDATES,
        "rows": row_tuple,
        "expected_source_count": 4,
        "transformable_source_count": 4 - len(blocked),
        "blocked_source_ids": blocked,
        "status": status.value,
    }
    return TinyDevTransformabilityAudit(
        algorithm_version=TINY_DEV_TRANSFORMABILITY_ALGORITHM_VERSION,
        tiny_dev_artifact_hash=artifact.artifact_hash,
        corpus_manifest_hash=artifact.manifest.manifest_hash,
        ruleset_hash=registry.ruleset_hash,
        minimum_independent_candidates_per_source=TINY_DEV_TRANSFORMABILITY_MIN_INDEPENDENT_CANDIDATES,
        rows=row_tuple,
        expected_source_count=4,
        transformable_source_count=4 - len(blocked),
        blocked_source_ids=blocked,
        status=status,
        audit_hash=sha256_json(payload),
    )
