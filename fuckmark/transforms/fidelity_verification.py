from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import ModelTokenizerIdentity
from ..hashing import sha256_json
from .fidelity_evidence import (
    BlindHumanFidelityAudit,
    FidelityReviewSample,
    GrammarFixture,
    GrammarFixtureDisposition,
)
from .lexical_audit import LexicalAuditStatus, LexicalRuleAudit, create_lexical_rule_audit
from .lexical_rules import LexicalTemplateRule
from .lexical_tokenization import LexicalRetokenizationFixture, verify_lexical_retokenization_fixture
from .registry import TransformRegistry
from .rules import TransformRule, default_contraction_rules


LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION = "lexical-promotion-evidence-v1"


class FidelityEvidenceVerificationError(ValueError):
    pass


def _single_rule_output(rule: TransformRule, source_text: str) -> tuple[str, object]:
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate(source_text)
    if len(enumeration.candidates) != 1:
        raise FidelityEvidenceVerificationError("reviewed source text must produce exactly one candidate")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    return result.output_text, enumeration


def verify_grammar_fixture(rule: TransformRule, fixture: GrammarFixture) -> None:
    if not isinstance(fixture, GrammarFixture):
        raise TypeError("fixture must be a GrammarFixture")
    if fixture.rule_hash != rule.rule_hash:
        raise FidelityEvidenceVerificationError("grammar fixture rule hash does not match supplied rule")
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate(fixture.source_text)
    if fixture.disposition is GrammarFixtureDisposition.CANDIDATE:
        if len(enumeration.candidates) != 1 or enumeration.rejections:
            raise FidelityEvidenceVerificationError("candidate grammar fixture does not replay as exactly one candidate")
        result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
        if result.output_text != fixture.expected_output_text:
            raise FidelityEvidenceVerificationError("candidate grammar fixture output does not replay exactly")
        return
    if enumeration.candidates or len(enumeration.rejections) != 1:
        raise FidelityEvidenceVerificationError("rejection grammar fixture does not replay as exactly one rejection")
    if enumeration.rejections[0].reason is not fixture.expected_rejection_reason:
        raise FidelityEvidenceVerificationError("grammar fixture rejection reason does not replay exactly")


def verify_fidelity_review_sample(rule: TransformRule, sample: FidelityReviewSample) -> None:
    if not isinstance(sample, FidelityReviewSample):
        raise TypeError("sample must be a FidelityReviewSample")
    if sample.rule_hash != rule.rule_hash:
        raise FidelityEvidenceVerificationError("review sample rule hash does not match supplied rule")
    output_text, _ = _single_rule_output(rule, sample.source_text)
    if output_text != sample.transformed_text:
        raise FidelityEvidenceVerificationError("review sample transformed text does not replay exactly")


@dataclass(frozen=True, slots=True)
class LexicalPromotionEvidence:
    algorithm_version: str
    rule: LexicalTemplateRule
    grammar_fixtures: tuple[GrammarFixture, ...]
    retokenization_fixtures: tuple[LexicalRetokenizationFixture, ...]
    model_tokenizer_identity: ModelTokenizerIdentity
    human_audit: BlindHumanFidelityAudit
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported lexical promotion evidence algorithm version")
        if not isinstance(self.rule, LexicalTemplateRule):
            raise TypeError("rule must be a LexicalTemplateRule")
        if not isinstance(self.model_tokenizer_identity, ModelTokenizerIdentity):
            raise TypeError("model_tokenizer_identity must be a ModelTokenizerIdentity")
        if not isinstance(self.human_audit, BlindHumanFidelityAudit):
            raise TypeError("human_audit must be a BlindHumanFidelityAudit")
        if self.human_audit.rule_hash != self.rule.rule_hash:
            raise ValueError("human audit rule hash does not match lexical rule")
        if not isinstance(self.grammar_fixtures, tuple) or not self.grammar_fixtures:
            raise TypeError("grammar_fixtures must be a non-empty tuple")
        if not isinstance(self.retokenization_fixtures, tuple) or not self.retokenization_fixtures:
            raise TypeError("retokenization_fixtures must be a non-empty tuple")
        expected_grammar = tuple(sorted(self.grammar_fixtures, key=lambda value: (value.fixture_id, value.fixture_hash)))
        expected_tokens = tuple(sorted(self.retokenization_fixtures, key=lambda value: (value.fixture_id, value.fixture_hash)))
        if self.grammar_fixtures != expected_grammar:
            raise ValueError("grammar_fixtures must be canonically ordered")
        if self.retokenization_fixtures != expected_tokens:
            raise ValueError("retokenization_fixtures must be canonically ordered")
        if len({value.fixture_id for value in self.grammar_fixtures}) != len(self.grammar_fixtures):
            raise ValueError("grammar fixture IDs must be unique")
        if len({value.fixture_id for value in self.retokenization_fixtures}) != len(self.retokenization_fixtures):
            raise ValueError("retokenization fixture IDs must be unique")
        if any(value.rule_hash != self.rule.rule_hash for value in self.grammar_fixtures):
            raise ValueError("grammar fixtures must match lexical rule hash")
        if any(value.rule_hash != self.rule.rule_hash for value in self.retokenization_fixtures):
            raise ValueError("retokenization fixtures must match lexical rule hash")
        if any(value.model_tokenizer_identity_hash != self.model_tokenizer_identity.identity_hash for value in self.retokenization_fixtures):
            raise ValueError("retokenization fixtures must match tokenizer identity")
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match lexical promotion evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rule_hash": self.rule.rule_hash,
            "grammar_fixture_hashes": tuple(value.fixture_hash for value in self.grammar_fixtures),
            "retokenization_fixture_hashes": tuple(value.fixture_hash for value in self.retokenization_fixtures),
            "model_tokenizer_identity_hash": self.model_tokenizer_identity.identity_hash,
            "human_audit_hash": self.human_audit.audit_hash,
        }

    @classmethod
    def create(
        cls,
        rule: LexicalTemplateRule,
        grammar_fixtures: Sequence[GrammarFixture],
        retokenization_fixtures: Sequence[LexicalRetokenizationFixture],
        model_tokenizer_identity: ModelTokenizerIdentity,
        human_audit: BlindHumanFidelityAudit,
    ) -> LexicalPromotionEvidence:
        grammar = tuple(sorted(tuple(grammar_fixtures), key=lambda value: (value.fixture_id, value.fixture_hash)))
        tokens = tuple(sorted(tuple(retokenization_fixtures), key=lambda value: (value.fixture_id, value.fixture_hash)))
        payload = {
            "algorithm_version": LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": rule.rule_hash,
            "grammar_fixture_hashes": tuple(value.fixture_hash for value in grammar),
            "retokenization_fixture_hashes": tuple(value.fixture_hash for value in tokens),
            "model_tokenizer_identity_hash": model_tokenizer_identity.identity_hash,
            "human_audit_hash": human_audit.audit_hash,
        }
        return cls(
            LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION,
            rule,
            grammar,
            tokens,
            model_tokenizer_identity,
            human_audit,
            sha256_json(payload),
        )


def verify_lexical_promotion_evidence(
    evidence: LexicalPromotionEvidence,
    tokenizer: Callable[[str], Sequence[int]],
) -> LexicalRuleAudit:
    if not isinstance(evidence, LexicalPromotionEvidence):
        raise TypeError("evidence must be LexicalPromotionEvidence")
    for fixture in evidence.grammar_fixtures:
        verify_grammar_fixture(evidence.rule, fixture)
    dispositions = Counter(value.disposition for value in evidence.grammar_fixtures)
    if dispositions[GrammarFixtureDisposition.CANDIDATE] < 5 or dispositions[GrammarFixtureDisposition.REJECTION] < 5:
        raise FidelityEvidenceVerificationError("lexical promotion requires at least five positive and five negative grammar fixtures")
    for fixture in evidence.retokenization_fixtures:
        verify_lexical_retokenization_fixture(
            fixture,
            evidence.rule,
            evidence.model_tokenizer_identity,
            tokenizer,
        )
    text_pairs = tuple(
        (value.source_text_hash, value.transformed_text_hash)
        for value in evidence.human_audit.review_samples
    )
    if len(set(text_pairs)) != len(text_pairs):
        raise FidelityEvidenceVerificationError("human fidelity audit cannot count duplicate reviewed text pairs as separate samples")
    for sample in evidence.human_audit.review_samples:
        verify_fidelity_review_sample(evidence.rule, sample)
    summary = create_lexical_rule_audit(
        evidence.rule.rule_hash,
        tuple(value.fixture_hash for value in evidence.grammar_fixtures if value.disposition is GrammarFixtureDisposition.CANDIDATE),
        tuple(value.fixture_hash for value in evidence.grammar_fixtures if value.disposition is GrammarFixtureDisposition.REJECTION),
        tuple(value.fixture_hash for value in evidence.retokenization_fixtures),
        human_review_policy_id=evidence.human_audit.review_policy_id,
        human_sample_count=evidence.human_audit.sample_count,
        equivalent_or_minor_count=evidence.human_audit.equivalent_or_minor_count,
        material_change_count=evidence.human_audit.material_change_count,
        cannot_judge_count=evidence.human_audit.cannot_judge_count,
        hard_invariant_violation_count=0,
    )
    if summary.status is not LexicalAuditStatus.EVIDENCE_SUMMARY_COMPLETE:
        raise FidelityEvidenceVerificationError(
            f"lexical fidelity evidence does not satisfy promotion criteria: {summary.status.value}"
        )
    return summary


def source_verified_historical_visible_edit_transform_registry(
    promotions: Sequence[LexicalPromotionEvidence],
    tokenizers: Mapping[str, Callable[[str], Sequence[int]]],
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    if not isinstance(promotions, Sequence) or isinstance(promotions, (str, bytes, bytearray)):
        raise TypeError("promotions must be a sequence")
    if not isinstance(tokenizers, Mapping):
        raise TypeError("tokenizers must be a mapping")
    promotion_tuple = tuple(promotions)
    if not promotion_tuple:
        return TransformRegistry(default_contraction_rules(), identifiers)
    if any(not isinstance(value, LexicalPromotionEvidence) for value in promotion_tuple):
        raise TypeError("promotions must contain LexicalPromotionEvidence values")
    if len({value.rule.rule_hash for value in promotion_tuple}) != len(promotion_tuple):
        raise FidelityEvidenceVerificationError("lexical promotion rules must be unique")
    approved: list[LexicalTemplateRule] = []
    for promotion in promotion_tuple:
        identity_hash = promotion.model_tokenizer_identity.identity_hash
        try:
            tokenizer = tokenizers[identity_hash]
        except KeyError as error:
            raise FidelityEvidenceVerificationError("missing tokenizer callable for promotion identity") from error
        verify_lexical_promotion_evidence(promotion, tokenizer)
        approved.append(promotion.rule)
    ordered = tuple(sorted(approved, key=lambda value: (value.rule_id, value.version, value.rule_hash)))
    return TransformRegistry((*default_contraction_rules(), *ordered), identifiers)


def source_verified_release_transform_registry(
    promotions: Sequence[LexicalPromotionEvidence],
    tokenizers: Mapping[str, Callable[[str], Sequence[int]]],
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    if not isinstance(promotions, Sequence) or isinstance(promotions, (str, bytes, bytearray)):
        raise TypeError("promotions must be a sequence")
    if not isinstance(tokenizers, Mapping):
        raise TypeError("tokenizers must be a mapping")
    promotion_tuple = tuple(promotions)
    from ..product.carriers import rule_preserves_visible_projection
    from ..product.registry import product_transform_registry
    from ..product.visible_projection import product_approved_carriers_v1

    if not promotion_tuple:
        return product_transform_registry(identifiers)
    if any(not isinstance(value, LexicalPromotionEvidence) for value in promotion_tuple):
        raise TypeError("promotions must contain LexicalPromotionEvidence values")
    if len({value.rule.rule_hash for value in promotion_tuple}) != len(promotion_tuple):
        raise FidelityEvidenceVerificationError("lexical promotion rules must be unique")
    approved_carriers = product_approved_carriers_v1()
    approved_rules: list[LexicalTemplateRule] = []
    for promotion in promotion_tuple:
        identity_hash = promotion.model_tokenizer_identity.identity_hash
        try:
            tokenizer = tokenizers[identity_hash]
        except KeyError as error:
            raise FidelityEvidenceVerificationError("missing tokenizer callable for promotion identity") from error
        verify_lexical_promotion_evidence(promotion, tokenizer)
        if not rule_preserves_visible_projection(promotion.rule, approved_carriers):
            raise FidelityEvidenceVerificationError(
                "lexical promotion changes user-visible text and cannot enter the product release registry"
            )
        approved_rules.append(promotion.rule)
    ordered = tuple(sorted(approved_rules, key=lambda value: (value.rule_id, value.version, value.rule_hash)))
    return product_transform_registry(identifiers, rules=ordered)
