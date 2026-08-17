from __future__ import annotations

from collections.abc import Sequence

from ..hashing import sha256_json
from .candidate_artifacts import CandidateEnumeration, _build_conflicts
from .hard_invariants import validate_hard_invariants
from .mechanism_rules import mechanism_stress_rules
from .registry import TRANSFORM_REGISTRY_ALGORITHM_VERSION, TransformRegistry
from .rules import default_contraction_rules
from .schema import InvariantStatus


MECHANISM_SCREEN_ALGORITHM_VERSION = "mechanism-invariant-screen-v1"


class MechanismStressTransformRegistry(TransformRegistry):
    __slots__ = ()

    def __init__(self, identifiers: Sequence[str] = ()) -> None:
        super().__init__((*default_contraction_rules(), *mechanism_stress_rules()), identifiers)
        self._ruleset_hash = sha256_json(
            {
                "algorithm_version": MECHANISM_SCREEN_ALGORITHM_VERSION,
                "base_registry_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION,
                "rules": self.rules,
            }
        )

    def enumerate(self, text: str, user_ranges=()) -> CandidateEnumeration:
        original = super().enumerate(text, user_ranges)
        safe = []
        for candidate in original.candidates:
            transformed = text[:candidate.start] + candidate.replacement_text + text[candidate.end:]
            report = validate_hard_invariants(text, transformed, self.identifiers, original.protected_manifest.user_ranges)
            if report.status is InvariantStatus.PASS:
                safe.append(candidate)
        candidates = tuple(safe)
        conflicts = _build_conflicts(candidates)
        payload = {
            "algorithm_version": original.algorithm_version,
            "input_hash": original.input_hash,
            "ruleset_hash": self.ruleset_hash,
            "protected_manifest_hash": original.protected_manifest.manifest_hash,
            "candidates": candidates,
            "rejections": original.rejections,
            "conflicts": conflicts,
        }
        return CandidateEnumeration(
            original.algorithm_version,
            original.input_text,
            original.input_hash,
            self.ruleset_hash,
            original.protected_manifest,
            candidates,
            original.rejections,
            conflicts,
            sha256_json(payload),
        )


def mechanism_stress_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return MechanismStressTransformRegistry(identifiers)
