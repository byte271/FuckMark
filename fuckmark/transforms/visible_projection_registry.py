from collections.abc import Sequence

from ..hashing import sha256_json
from .candidate_artifacts import CandidateEnumeration, TransformCandidate, _build_conflicts
from .hard_invariants import validate_hard_invariants
from .registry import TRANSFORM_REGISTRY_ALGORITHM_VERSION, TransformRegistry
from .schema import InvariantStatus
from .visible_projection_rules import visible_projection_experimental_rules


VISIBLE_PROJECTION_REGISTRY_ALGORITHM_VERSION = "visible-projection-registry-v1"


def _is_ascii_word(value: str) -> bool:
    return bool(value) and value.isascii() and value.isalpha()


def _candidate_is_eligible(text: str, candidate: TransformCandidate) -> bool:
    if candidate.source_text != " " or candidate.start <= 0 or candidate.end >= len(text):
        return False
    left_start = text.rfind(" ", 0, candidate.start) + 1
    right_end = text.find(" ", candidate.end)
    if right_end < 0:
        right_end = len(text)
    return _is_ascii_word(text[left_start:candidate.start]) and _is_ascii_word(text[candidate.end:right_end])


class VisibleProjectionExperimentalTransformRegistry(TransformRegistry):
    __slots__ = ()

    def __init__(self, identifiers: Sequence[str] = ()) -> None:
        super().__init__(visible_projection_experimental_rules(), identifiers)
        self._ruleset_hash = sha256_json(
            {
                "algorithm_version": VISIBLE_PROJECTION_REGISTRY_ALGORITHM_VERSION,
                "base_registry_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION,
                "rules": self.rules,
            }
        )

    def enumerate(self, text: str, user_ranges=()) -> CandidateEnumeration:
        original = super().enumerate(text, user_ranges)
        candidates = []
        for candidate in original.candidates:
            if not _candidate_is_eligible(text, candidate):
                continue
            transformed = text[:candidate.start] + candidate.replacement_text + text[candidate.end:]
            report = validate_hard_invariants(
                text,
                transformed,
                self.identifiers,
                original.protected_manifest.user_ranges,
            )
            if report.status is InvariantStatus.PASS:
                candidates.append(candidate)
        ordered = tuple(candidates)
        conflicts = _build_conflicts(ordered)
        payload = {
            "algorithm_version": original.algorithm_version,
            "input_hash": original.input_hash,
            "ruleset_hash": self.ruleset_hash,
            "protected_manifest_hash": original.protected_manifest.manifest_hash,
            "candidates": ordered,
            "rejections": original.rejections,
            "conflicts": conflicts,
        }
        return CandidateEnumeration(
            original.algorithm_version,
            original.input_text,
            original.input_hash,
            self.ruleset_hash,
            original.protected_manifest,
            ordered,
            original.rejections,
            conflicts,
            sha256_json(payload),
        )


def visible_projection_experimental_registry(
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    return VisibleProjectionExperimentalTransformRegistry(identifiers)
