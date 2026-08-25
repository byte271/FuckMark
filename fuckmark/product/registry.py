from __future__ import annotations

from collections.abc import Sequence

from ..hashing import sha256_json
from ..transforms.candidate_artifacts import CandidateEnumeration, _build_conflicts
from ..transforms.quote_policy import BLANKET_QUOTE_PROTECTION_POLICY_ID
from ..transforms.registry import (
    TRANSFORM_REGISTRY_ALGORITHM_VERSION,
    TransformRegistry,
    _make_rejection,
)
from ..transforms.schema import CandidateRejectionReason, InvariantStatus
from .carriers import rule_preserves_visible_projection
from .contract import PRODUCT_CONTRACT_ID
from .domain import is_supported_product_domain_v1
from .invariants import validate_user_visible_invariants
from .visible_projection import is_carrier_insertion_v1, normalize_approved_carriers, product_approved_carriers_v1, project_visible_v1


PRODUCT_REGISTRY_ALGORITHM_VERSION = "product-transform-registry-v1"


class ProductTransformRegistry(TransformRegistry):
    __slots__ = ("_approved_carriers",)

    def __init__(
        self,
        rules: Sequence = (),
        identifiers: Sequence[str] = (),
        *,
        approved_carriers: Sequence[int] = (),
        quote_policy_id: str = BLANKET_QUOTE_PROTECTION_POLICY_ID,
    ) -> None:
        self._approved_carriers = tuple(sorted(normalize_approved_carriers(approved_carriers)))
        super().__init__(
            rules,
            identifiers,
            quote_policy_id=quote_policy_id,
            allow_empty=True,
        )
        payload = {
            "algorithm_version": PRODUCT_REGISTRY_ALGORITHM_VERSION,
            "base_registry_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION,
            "product_contract_id": PRODUCT_CONTRACT_ID,
            "approved_carriers": self._approved_carriers,
            "quote_policy_id": quote_policy_id,
            "rules": self.rules,
        }
        self._ruleset_hash = sha256_json(payload)

    @property
    def approved_carriers(self) -> tuple[int, ...]:
        return self._approved_carriers

    def enumerate(self, text: str, user_ranges=()) -> CandidateEnumeration:
        original = super().enumerate(text, user_ranges)
        approved = frozenset(self._approved_carriers)
        if not is_supported_product_domain_v1(text) or project_visible_v1(text, approved) != text:
            payload = {
                "algorithm_version": original.algorithm_version,
                "input_hash": original.input_hash,
                "ruleset_hash": self.ruleset_hash,
                "protected_manifest_hash": original.protected_manifest.manifest_hash,
                "candidates": (),
                "rejections": original.rejections,
                "conflicts": (),
            }
            return CandidateEnumeration(
                original.algorithm_version,
                original.input_text,
                original.input_hash,
                self.ruleset_hash,
                original.protected_manifest,
                (),
                original.rejections,
                (),
                sha256_json(payload),
            )
        approved = frozenset(self._approved_carriers)
        by_identity = {(rule.rule_id, rule.version, rule.rule_hash): rule for rule in self.rules}
        candidates = []
        extra_rejections = list(original.rejections)
        for candidate in original.candidates:
            trial = text[: candidate.start] + candidate.replacement_text + text[candidate.end :]
            if not is_carrier_insertion_v1(text, trial, approved):
                rule = by_identity[(candidate.rule_id, candidate.rule_version, candidate.rule_hash)]
                extra_rejections.append(
                    _make_rejection(
                        original.input_hash,
                        rule,
                        candidate.start,
                        candidate.end,
                        candidate.source_text,
                        CandidateRejectionReason.USER_VISIBLE_TEXT_CHANGED,
                    )
                )
                continue
            candidates.append(candidate)
        ordered = tuple(candidates)
        ordered_rejections = tuple(
            sorted(
                extra_rejections,
                key=lambda value: (value.start, value.end, value.rule_id, value.reason.value, value.rejection_hash),
            )
        )
        conflicts = _build_conflicts(ordered)
        payload = {
            "algorithm_version": original.algorithm_version,
            "input_hash": original.input_hash,
            "ruleset_hash": self.ruleset_hash,
            "protected_manifest_hash": original.protected_manifest.manifest_hash,
            "candidates": ordered,
            "rejections": ordered_rejections,
            "conflicts": conflicts,
        }
        return CandidateEnumeration(
            original.algorithm_version,
            original.input_text,
            original.input_hash,
            self.ruleset_hash,
            original.protected_manifest,
            ordered,
            ordered_rejections,
            conflicts,
            sha256_json(payload),
        )

    def apply(self, enumeration: CandidateEnumeration, candidate_ids: Sequence[str], seed: int = 0):
        result = super().apply(enumeration, candidate_ids, seed=seed)
        report = validate_user_visible_invariants(
            enumeration.input_text,
            result.output_text,
            self._approved_carriers,
        )
        if report.status is not InvariantStatus.PASS:
            raise ValueError("transformation violated user-visible text invariance")
        return result


def product_transform_registry(
    identifiers: Sequence[str] = (),
    *,
    rules: Sequence = (),
    approved_carriers: Sequence[int] = (),
) -> ProductTransformRegistry:
    approved = tuple(approved_carriers) if approved_carriers else tuple(product_approved_carriers_v1())
    if rules:
        for rule in rules:
            if not rule_preserves_visible_projection(rule, approved):
                raise ValueError("product registry refused a visible-edit rule")
    return ProductTransformRegistry(rules, identifiers, approved_carriers=approved)
