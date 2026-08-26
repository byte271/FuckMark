from __future__ import annotations

from collections.abc import Sequence

from .._validation import require_int
from ..hashing import sha256_json
from ..transforms.candidate_artifacts import CandidateEnumeration, _build_conflicts
from ..transforms.cycle7_quote_policy import QUOTE_INTERIOR_POLICY_IDS
from ..transforms.hard_invariants import HardInvariantReport, validate_hard_invariants
from ..transforms.quote_policy import BLANKET_QUOTE_PROTECTION_POLICY_ID
from ..transforms.registry import (
    TRANSFORM_REGISTRY_ALGORITHM_VERSION,
    TransformRegistry,
    _make_rejection,
)
from ..transforms.schema import CandidateRejectionReason, InvariantStatus
from .carrier_invariants import (
    WORD_SIGNATURE_SOURCE_RAW,
    WORD_SIGNATURE_SOURCES,
    WORD_SIGNATURE_SOURCE_VISIBLE,
    validate_product_carrier_invariants,
)
from .carriers import rule_preserves_visible_projection
from .contract import PRODUCT_CONTRACT_ID
from .domain import is_supported_product_domain_v1
from .invariants import validate_user_visible_invariants
from .visible_projection import is_carrier_insertion_v1, normalize_approved_carriers, product_approved_carriers_v1, project_visible_v1


PRODUCT_REGISTRY_ALGORITHM_VERSION = "product-transform-registry-v2"


class ProductTransformRegistry(TransformRegistry):
    __slots__ = ("_approved_carriers", "_word_signature_source", "_max_selected")

    def __init__(
        self,
        rules: Sequence = (),
        identifiers: Sequence[str] = (),
        *,
        approved_carriers: Sequence[int] = (),
        quote_policy_id: str = BLANKET_QUOTE_PROTECTION_POLICY_ID,
        word_signature_source: str = WORD_SIGNATURE_SOURCE_RAW,
        max_selected: int | None = None,
    ) -> None:
        if word_signature_source not in WORD_SIGNATURE_SOURCES:
            raise ValueError("unsupported word signature source")
        if max_selected is not None:
            require_int("max_selected", max_selected)
            if max_selected <= 0:
                raise ValueError("max_selected must be positive")
        self._approved_carriers = tuple(sorted(normalize_approved_carriers(approved_carriers)))
        self._word_signature_source = word_signature_source
        self._max_selected = max_selected
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
        if word_signature_source != WORD_SIGNATURE_SOURCE_RAW:
            payload["word_signature_source"] = word_signature_source
        if max_selected is not None:
            payload["max_selected"] = max_selected
        self._ruleset_hash = sha256_json(payload)

    @property
    def approved_carriers(self) -> tuple[int, ...]:
        return self._approved_carriers

    @property
    def word_signature_source(self) -> str:
        return self._word_signature_source

    @property
    def max_selected(self) -> int | None:
        return self._max_selected

    def _trial_invariants(
        self,
        original: str,
        trial: str,
        identifiers: Sequence[str],
        user_ranges,
        *,
        include_quotations: bool,
    ) -> HardInvariantReport:
        if self._word_signature_source == WORD_SIGNATURE_SOURCE_VISIBLE:
            return validate_product_carrier_invariants(
                original,
                trial,
                identifiers,
                user_ranges,
                include_quotations=include_quotations,
                approved_carriers=self._approved_carriers,
            )
        return validate_hard_invariants(
            original,
            trial,
            identifiers,
            user_ranges,
            include_quotations=include_quotations,
        )

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
        quote_interior = self._quote_policy_id in QUOTE_INTERIOR_POLICY_IDS
        candidates = []
        extra_rejections = list(original.rejections)
        for candidate in original.candidates:
            trial = text[: candidate.start] + candidate.replacement_text + text[candidate.end :]
            rule = by_identity[(candidate.rule_id, candidate.rule_version, candidate.rule_hash)]
            if not is_carrier_insertion_v1(text, trial, approved):
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
            invariant_report = self._trial_invariants(
                text,
                trial,
                self.identifiers,
                original.protected_manifest.user_ranges,
                include_quotations=not quote_interior,
            )
            if invariant_report.status is not InvariantStatus.PASS:
                extra_rejections.append(
                    _make_rejection(
                        original.input_hash,
                        rule,
                        candidate.start,
                        candidate.end,
                        candidate.source_text,
                        CandidateRejectionReason.HARD_INVARIANT_FAILED,
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
        result = super().apply(
            enumeration,
            candidate_ids,
            seed=seed,
            invariant_validate=self._trial_invariants,
        )
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
