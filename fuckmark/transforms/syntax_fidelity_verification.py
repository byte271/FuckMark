from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import ModelTokenizerIdentity
from ..hashing import sha256_json
from .fidelity_evidence import BlindHumanFidelityAudit, GrammarFixture, GrammarFixtureDisposition
from .fidelity_verification import FidelityEvidenceVerificationError, verify_fidelity_review_sample, verify_grammar_fixture
from .syntax_audit import SyntaxAuditStatus, SyntaxRuleAudit, create_syntax_rule_audit
from .syntax_rules import SyntaxTemplateRule
from .syntax_tokenization import SyntaxRetokenizationFixture, verify_syntax_retokenization_fixture


SYNTAX_DEVELOPMENT_EVIDENCE_ALGORITHM_VERSION = "syntax-development-evidence-v1"


@dataclass(frozen=True, slots=True)
class SyntaxDevelopmentEvidence:
    algorithm_version: str
    rule: SyntaxTemplateRule
    grammar_fixtures: tuple[GrammarFixture, ...]
    retokenization_fixtures: tuple[SyntaxRetokenizationFixture, ...]
    model_tokenizer_identity: ModelTokenizerIdentity
    human_audit: BlindHumanFidelityAudit
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTAX_DEVELOPMENT_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported syntax development evidence algorithm version")
        if not isinstance(self.rule, SyntaxTemplateRule):
            raise TypeError("rule must be a SyntaxTemplateRule")
        if not isinstance(self.model_tokenizer_identity, ModelTokenizerIdentity):
            raise TypeError("model_tokenizer_identity must be a ModelTokenizerIdentity")
        if not isinstance(self.human_audit, BlindHumanFidelityAudit):
            raise TypeError("human_audit must be a BlindHumanFidelityAudit")
        if self.human_audit.rule_hash != self.rule.rule_hash:
            raise ValueError("human audit rule hash does not match syntax rule")
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
            raise ValueError("grammar fixtures must match syntax rule hash")
        if any(value.rule_hash != self.rule.rule_hash for value in self.retokenization_fixtures):
            raise ValueError("retokenization fixtures must match syntax rule hash")
        if any(value.model_tokenizer_identity_hash != self.model_tokenizer_identity.identity_hash for value in self.retokenization_fixtures):
            raise ValueError("retokenization fixtures must match tokenizer identity")
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match syntax development evidence")

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
        rule: SyntaxTemplateRule,
        grammar_fixtures: Sequence[GrammarFixture],
        retokenization_fixtures: Sequence[SyntaxRetokenizationFixture],
        model_tokenizer_identity: ModelTokenizerIdentity,
        human_audit: BlindHumanFidelityAudit,
    ) -> SyntaxDevelopmentEvidence:
        grammar = tuple(sorted(tuple(grammar_fixtures), key=lambda value: (value.fixture_id, value.fixture_hash)))
        tokens = tuple(sorted(tuple(retokenization_fixtures), key=lambda value: (value.fixture_id, value.fixture_hash)))
        payload = {
            "algorithm_version": SYNTAX_DEVELOPMENT_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": rule.rule_hash,
            "grammar_fixture_hashes": tuple(value.fixture_hash for value in grammar),
            "retokenization_fixture_hashes": tuple(value.fixture_hash for value in tokens),
            "model_tokenizer_identity_hash": model_tokenizer_identity.identity_hash,
            "human_audit_hash": human_audit.audit_hash,
        }
        return cls(
            SYNTAX_DEVELOPMENT_EVIDENCE_ALGORITHM_VERSION,
            rule,
            grammar,
            tokens,
            model_tokenizer_identity,
            human_audit,
            sha256_json(payload),
        )


def verify_syntax_development_evidence(
    evidence: SyntaxDevelopmentEvidence,
    tokenizer: Callable[[str], Sequence[int]],
) -> SyntaxRuleAudit:
    if not isinstance(evidence, SyntaxDevelopmentEvidence):
        raise TypeError("evidence must be SyntaxDevelopmentEvidence")
    for fixture in evidence.grammar_fixtures:
        verify_grammar_fixture(evidence.rule, fixture)
    dispositions = Counter(value.disposition for value in evidence.grammar_fixtures)
    if dispositions[GrammarFixtureDisposition.CANDIDATE] < 5 or dispositions[GrammarFixtureDisposition.REJECTION] < 5:
        raise FidelityEvidenceVerificationError("syntax development requires at least five positive and five negative grammar fixtures")
    for fixture in evidence.retokenization_fixtures:
        verify_syntax_retokenization_fixture(
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
        raise FidelityEvidenceVerificationError("syntax human audit cannot count duplicate reviewed text pairs as separate samples")
    for sample in evidence.human_audit.review_samples:
        verify_fidelity_review_sample(evidence.rule, sample)
    summary = create_syntax_rule_audit(
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
    if summary.status is not SyntaxAuditStatus.DEVELOPMENT_AUDIT_COMPLETE:
        raise FidelityEvidenceVerificationError(
            f"syntax fidelity evidence does not satisfy development criteria: {summary.status.value}"
        )
    return summary
