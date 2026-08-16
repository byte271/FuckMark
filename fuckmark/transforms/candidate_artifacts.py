from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .protected_artifacts import ProtectedSpanManifest
from .schema import CandidateRejectionReason, TransformFamily, TransformTier


_MAX_CONFLICTS = 100_000


@dataclass(frozen=True, slots=True)
class TransformCandidate:
    candidate_id: str
    input_hash: str
    rule_id: str
    rule_version: str
    rule_hash: str
    family: TransformFamily
    tier: TransformTier
    start: int
    end: int
    source_text: str
    replacement_text: str

    def __post_init__(self) -> None:
        require_sha256("candidate_id", self.candidate_id)
        require_sha256("input_hash", self.input_hash)
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("rule_version", self.rule_version)
        require_sha256("rule_hash", self.rule_hash)
        if not isinstance(self.family, TransformFamily):
            raise TypeError("family must be a TransformFamily")
        if not isinstance(self.tier, TransformTier):
            raise TypeError("tier must be a TransformTier")
        require_int("start", self.start)
        require_int("end", self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("candidate span must satisfy 0 <= start < end")
        if not isinstance(self.source_text, str) or not self.source_text:
            raise ValueError("source_text must be non-empty")
        if self.end - self.start != len(self.source_text):
            raise ValueError("candidate span does not match source_text")
        if not isinstance(self.replacement_text, str) or not self.replacement_text:
            raise ValueError("replacement_text must be non-empty")
        if self.source_text == self.replacement_text:
            raise ValueError("candidate source and replacement must differ")
        if self.candidate_id != sha256_json(self._payload()):
            raise ValueError("candidate_id does not match transform candidate")

    def _payload(self) -> dict[str, object]:
        return {
            "input_hash": self.input_hash,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_hash": self.rule_hash,
            "family": self.family.value,
            "tier": self.tier.value,
            "start": self.start,
            "end": self.end,
            "source_text": self.source_text,
            "replacement_text": self.replacement_text,
        }


@dataclass(frozen=True, slots=True)
class CandidateRejection:
    input_hash: str
    rule_id: str
    rule_version: str
    rule_hash: str
    start: int
    end: int
    source_text: str
    reason: CandidateRejectionReason
    protected_span_hashes: tuple[str, ...]
    rejection_hash: str

    def __post_init__(self) -> None:
        require_sha256("input_hash", self.input_hash)
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("rule_version", self.rule_version)
        require_sha256("rule_hash", self.rule_hash)
        require_int("start", self.start)
        require_int("end", self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("rejection span must satisfy 0 <= start < end")
        if not isinstance(self.source_text, str) or not self.source_text:
            raise ValueError("source_text must be non-empty")
        if self.end - self.start != len(self.source_text):
            raise ValueError("rejection span does not match source_text")
        if not isinstance(self.reason, CandidateRejectionReason):
            raise TypeError("reason must be a CandidateRejectionReason")
        hashes = tuple(self.protected_span_hashes)
        if hashes != tuple(sorted(set(hashes))):
            raise ValueError("protected_span_hashes must be unique and sorted")
        object.__setattr__(self, "protected_span_hashes", hashes)
        for value in hashes:
            require_sha256("protected_span_hash", value)
        if self.reason is CandidateRejectionReason.PROTECTED_OVERLAP and not hashes:
            raise ValueError("protected overlap rejections must identify protected spans")
        if self.reason is not CandidateRejectionReason.PROTECTED_OVERLAP and hashes:
            raise ValueError("only protected overlap rejections may identify protected spans")
        require_sha256("rejection_hash", self.rejection_hash)
        if self.rejection_hash != sha256_json(self._payload()):
            raise ValueError("rejection_hash does not match candidate rejection")

    def _payload(self) -> dict[str, object]:
        return {
            "input_hash": self.input_hash,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_hash": self.rule_hash,
            "start": self.start,
            "end": self.end,
            "source_text": self.source_text,
            "reason": self.reason.value,
            "protected_span_hashes": self.protected_span_hashes,
        }


@dataclass(frozen=True, slots=True)
class CandidateConflict:
    first_candidate_id: str
    second_candidate_id: str
    conflict_hash: str

    def __post_init__(self) -> None:
        require_sha256("first_candidate_id", self.first_candidate_id)
        require_sha256("second_candidate_id", self.second_candidate_id)
        if self.first_candidate_id >= self.second_candidate_id:
            raise ValueError("candidate conflict IDs must be strictly sorted")
        require_sha256("conflict_hash", self.conflict_hash)
        if self.conflict_hash != sha256_json(self._payload()):
            raise ValueError("conflict_hash does not match candidate conflict")

    def _payload(self) -> dict[str, object]:
        return {"first_candidate_id": self.first_candidate_id, "second_candidate_id": self.second_candidate_id}


def _overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


@dataclass(frozen=True, slots=True)
class CandidateEnumeration:
    algorithm_version: str
    input_text: str
    input_hash: str
    ruleset_hash: str
    protected_manifest: ProtectedSpanManifest
    candidates: tuple[TransformCandidate, ...]
    rejections: tuple[CandidateRejection, ...]
    conflicts: tuple[CandidateConflict, ...]
    enumeration_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if not isinstance(self.input_text, str):
            raise TypeError("input_text must be a string")
        require_sha256("input_hash", self.input_hash)
        if self.input_hash != sha256_text(self.input_text):
            raise ValueError("input_hash does not match input_text")
        require_sha256("ruleset_hash", self.ruleset_hash)
        if not isinstance(self.protected_manifest, ProtectedSpanManifest):
            raise TypeError("protected_manifest must be a ProtectedSpanManifest")
        if self.protected_manifest.input_hash != self.input_hash:
            raise ValueError("protected manifest input does not match enumeration input")
        candidates = tuple(self.candidates)
        rejections = tuple(self.rejections)
        conflicts = tuple(self.conflicts)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "rejections", rejections)
        object.__setattr__(self, "conflicts", conflicts)
        if any(not isinstance(value, TransformCandidate) for value in candidates):
            raise TypeError("candidates must contain TransformCandidate values")
        if any(not isinstance(value, CandidateRejection) for value in rejections):
            raise TypeError("rejections must contain CandidateRejection values")
        if any(not isinstance(value, CandidateConflict) for value in conflicts):
            raise TypeError("conflicts must contain CandidateConflict values")
        if candidates != tuple(sorted(candidates, key=lambda value: (value.start, value.end, value.rule_id, value.candidate_id))):
            raise ValueError("candidates must be canonically ordered")
        if rejections != tuple(sorted(rejections, key=lambda value: (value.start, value.end, value.rule_id, value.reason.value, value.rejection_hash))):
            raise ValueError("rejections must be canonically ordered")
        if conflicts != tuple(sorted(conflicts, key=lambda value: (value.first_candidate_id, value.second_candidate_id))):
            raise ValueError("conflicts must be canonically ordered")
        if any(value.input_hash != self.input_hash for value in candidates):
            raise ValueError("candidate input hashes must match enumeration input")
        if any(value.input_hash != self.input_hash for value in rejections):
            raise ValueError("rejection input hashes must match enumeration input")
        for value in candidates:
            if value.end > len(self.input_text) or self.input_text[value.start:value.end] != value.source_text:
                raise ValueError("candidate source span does not match enumeration input")
            if any(_overlap(value.start, value.end, span.start, span.end) for span in self.protected_manifest.spans):
                raise ValueError("candidate overlaps a protected span")
        span_by_hash = {span.span_hash: span for span in self.protected_manifest.spans}
        for value in rejections:
            if value.end > len(self.input_text) or self.input_text[value.start:value.end] != value.source_text:
                raise ValueError("rejection source span does not match enumeration input")
            if value.reason is CandidateRejectionReason.PROTECTED_OVERLAP:
                expected = tuple(sorted(
                    span.span_hash
                    for span in self.protected_manifest.spans
                    if _overlap(value.start, value.end, span.start, span.end)
                ))
                if value.protected_span_hashes != expected:
                    raise ValueError("protected overlap rejection does not match protected geometry")
            elif any(hash_value not in span_by_hash for hash_value in value.protected_span_hashes):
                raise ValueError("rejection references an unknown protected span")
        for span in self.protected_manifest.spans:
            if span.end > len(self.input_text) or self.input_text[span.start:span.end] != span.exact_text:
                raise ValueError("protected span does not match enumeration input")
        if len({value.candidate_id for value in candidates}) != len(candidates):
            raise ValueError("candidate IDs must be unique")
        if len({value.rejection_hash for value in rejections}) != len(rejections):
            raise ValueError("rejection hashes must be unique")
        expected_conflicts = _build_conflicts(candidates)
        if conflicts != expected_conflicts:
            raise ValueError("conflicts do not match overlapping candidate geometry")
        valid_ids = {value.candidate_id for value in candidates}
        for conflict in conflicts:
            if conflict.first_candidate_id not in valid_ids or conflict.second_candidate_id not in valid_ids:
                raise ValueError("candidate conflict references an unknown candidate")
        require_sha256("enumeration_hash", self.enumeration_hash)
        if self.enumeration_hash != sha256_json(self._payload()):
            raise ValueError("enumeration_hash does not match candidate enumeration")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "input_hash": self.input_hash,
            "ruleset_hash": self.ruleset_hash,
            "protected_manifest_hash": self.protected_manifest.manifest_hash,
            "candidates": self.candidates,
            "rejections": self.rejections,
            "conflicts": self.conflicts,
        }


def _build_conflicts(candidates: Sequence[TransformCandidate]) -> tuple[CandidateConflict, ...]:
    materialized = tuple(candidates)
    output: list[CandidateConflict] = []
    for index, left in enumerate(materialized):
        for right in materialized[index + 1:]:
            if right.start >= left.end:
                break
            if left.start < right.end and right.start < left.end:
                if len(output) >= _MAX_CONFLICTS:
                    raise ValueError("candidate conflict graph exceeded resource limit")
                first, second = sorted((left.candidate_id, right.candidate_id))
                payload = {"first_candidate_id": first, "second_candidate_id": second}
                output.append(CandidateConflict(first, second, sha256_json(payload)))
    return tuple(sorted(output, key=lambda value: (value.first_candidate_id, value.second_candidate_id)))
