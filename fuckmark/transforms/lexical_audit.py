from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .lexical_rules import LexicalTemplateRule


LEXICAL_RULE_AUDIT_ALGORITHM_VERSION = "lexical-rule-fidelity-audit-v2"
BLIND_HUMAN_REVIEW_POLICY_ID = "blind-two-reviewer-tiebreak-v1"
MINIMUM_GRAMMAR_FIXTURES_PER_CLASS = 5
MINIMUM_HUMAN_AUDIT_SAMPLES = 50
MINIMUM_EQUIVALENT_OR_MINOR_RATE = 0.95


class LexicalAuditStatus(str, Enum):
    GRAMMAR_FIXTURES_INCOMPLETE = "GRAMMAR_FIXTURES_INCOMPLETE"
    TOKENIZER_FIXTURES_MISSING = "TOKENIZER_FIXTURES_MISSING"
    HUMAN_FIDELITY_AUDIT_MISSING = "HUMAN_FIDELITY_AUDIT_MISSING"
    BLOCKED_HARD_INVARIANT = "BLOCKED_HARD_INVARIANT"
    BLOCKED_HUMAN_FIDELITY = "BLOCKED_HUMAN_FIDELITY"
    EVIDENCE_SUMMARY_COMPLETE = "EVIDENCE_SUMMARY_COMPLETE"


class LexicalRulePromotionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LexicalRuleAudit:
    algorithm_version: str
    rule_hash: str
    positive_fixture_hashes: tuple[str, ...]
    negative_fixture_hashes: tuple[str, ...]
    tokenizer_fixture_hashes: tuple[str, ...]
    human_review_policy_id: str | None
    human_sample_count: int
    equivalent_or_minor_count: int
    material_change_count: int
    cannot_judge_count: int
    hard_invariant_violation_count: int
    status: LexicalAuditStatus
    audit_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != LEXICAL_RULE_AUDIT_ALGORITHM_VERSION:
            raise ValueError("unsupported lexical rule audit algorithm version")
        require_sha256("rule_hash", self.rule_hash)
        for name, values in (
            ("positive_fixture_hashes", self.positive_fixture_hashes),
            ("negative_fixture_hashes", self.negative_fixture_hashes),
            ("tokenizer_fixture_hashes", self.tokenizer_fixture_hashes),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{name} must be unique and canonically ordered")
            for value in values:
                require_sha256("fixture_hash", value)
        for name, value in (
            ("human_sample_count", self.human_sample_count),
            ("equivalent_or_minor_count", self.equivalent_or_minor_count),
            ("material_change_count", self.material_change_count),
            ("cannot_judge_count", self.cannot_judge_count),
            ("hard_invariant_violation_count", self.hard_invariant_violation_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.equivalent_or_minor_count + self.material_change_count + self.cannot_judge_count != self.human_sample_count:
            raise ValueError("human adjudication counts must sum to human_sample_count")
        if self.human_sample_count == 0:
            if self.human_review_policy_id is not None:
                raise ValueError("human_review_policy_id must be absent when no human audit exists")
        elif self.human_review_policy_id != BLIND_HUMAN_REVIEW_POLICY_ID:
            raise ValueError("human fidelity audit must use the frozen blind review policy")
        if not isinstance(self.status, LexicalAuditStatus):
            raise TypeError("status must be a LexicalAuditStatus")
        expected_status = _audit_status(
            len(self.positive_fixture_hashes),
            len(self.negative_fixture_hashes),
            len(self.tokenizer_fixture_hashes),
            self.human_sample_count,
            self.equivalent_or_minor_count,
            self.material_change_count,
            self.hard_invariant_violation_count,
        )
        if self.status is not expected_status:
            raise ValueError("lexical audit status does not match supplied evidence summary")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self._payload()):
            raise ValueError("audit_hash does not match lexical rule audit")

    @property
    def evidence_summary_complete(self) -> bool:
        return self.status is LexicalAuditStatus.EVIDENCE_SUMMARY_COMPLETE

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rule_hash": self.rule_hash,
            "positive_fixture_hashes": self.positive_fixture_hashes,
            "negative_fixture_hashes": self.negative_fixture_hashes,
            "tokenizer_fixture_hashes": self.tokenizer_fixture_hashes,
            "human_review_policy_id": self.human_review_policy_id,
            "human_sample_count": self.human_sample_count,
            "equivalent_or_minor_count": self.equivalent_or_minor_count,
            "material_change_count": self.material_change_count,
            "cannot_judge_count": self.cannot_judge_count,
            "hard_invariant_violation_count": self.hard_invariant_violation_count,
            "status": self.status.value,
        }


def _audit_status(
    positive_count: int,
    negative_count: int,
    tokenizer_count: int,
    human_sample_count: int,
    equivalent_or_minor_count: int,
    material_change_count: int,
    hard_invariant_violation_count: int,
) -> LexicalAuditStatus:
    if positive_count < MINIMUM_GRAMMAR_FIXTURES_PER_CLASS or negative_count < MINIMUM_GRAMMAR_FIXTURES_PER_CLASS:
        return LexicalAuditStatus.GRAMMAR_FIXTURES_INCOMPLETE
    if tokenizer_count == 0:
        return LexicalAuditStatus.TOKENIZER_FIXTURES_MISSING
    if human_sample_count < MINIMUM_HUMAN_AUDIT_SAMPLES:
        return LexicalAuditStatus.HUMAN_FIDELITY_AUDIT_MISSING
    if hard_invariant_violation_count:
        return LexicalAuditStatus.BLOCKED_HARD_INVARIANT
    if material_change_count or equivalent_or_minor_count / human_sample_count < MINIMUM_EQUIVALENT_OR_MINOR_RATE:
        return LexicalAuditStatus.BLOCKED_HUMAN_FIDELITY
    return LexicalAuditStatus.EVIDENCE_SUMMARY_COMPLETE


def create_lexical_rule_audit(
    rule_hash: str,
    positive_fixture_hashes: tuple[str, ...],
    negative_fixture_hashes: tuple[str, ...],
    tokenizer_fixture_hashes: tuple[str, ...] = (),
    human_review_policy_id: str | None = None,
    human_sample_count: int = 0,
    equivalent_or_minor_count: int = 0,
    material_change_count: int = 0,
    cannot_judge_count: int = 0,
    hard_invariant_violation_count: int = 0,
) -> LexicalRuleAudit:
    positives = tuple(sorted(set(positive_fixture_hashes)))
    negatives = tuple(sorted(set(negative_fixture_hashes)))
    tokenizers = tuple(sorted(set(tokenizer_fixture_hashes)))
    status = _audit_status(
        len(positives),
        len(negatives),
        len(tokenizers),
        human_sample_count,
        equivalent_or_minor_count,
        material_change_count,
        hard_invariant_violation_count,
    )
    payload = {
        "algorithm_version": LEXICAL_RULE_AUDIT_ALGORITHM_VERSION,
        "rule_hash": rule_hash,
        "positive_fixture_hashes": positives,
        "negative_fixture_hashes": negatives,
        "tokenizer_fixture_hashes": tokenizers,
        "human_review_policy_id": human_review_policy_id,
        "human_sample_count": human_sample_count,
        "equivalent_or_minor_count": equivalent_or_minor_count,
        "material_change_count": material_change_count,
        "cannot_judge_count": cannot_judge_count,
        "hard_invariant_violation_count": hard_invariant_violation_count,
        "status": status.value,
    }
    return LexicalRuleAudit(
        algorithm_version=LEXICAL_RULE_AUDIT_ALGORITHM_VERSION,
        rule_hash=rule_hash,
        positive_fixture_hashes=positives,
        negative_fixture_hashes=negatives,
        tokenizer_fixture_hashes=tokenizers,
        human_review_policy_id=human_review_policy_id,
        human_sample_count=human_sample_count,
        equivalent_or_minor_count=equivalent_or_minor_count,
        material_change_count=material_change_count,
        cannot_judge_count=cannot_judge_count,
        hard_invariant_violation_count=hard_invariant_violation_count,
        status=status,
        audit_hash=sha256_json(payload),
    )


def require_complete_lexical_audit_summaries(
    rules: Sequence[LexicalTemplateRule],
    audits: Sequence[LexicalRuleAudit],
) -> tuple[LexicalTemplateRule, ...]:
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes, bytearray)):
        raise TypeError("rules must be a sequence")
    if not isinstance(audits, Sequence) or isinstance(audits, (str, bytes, bytearray)):
        raise TypeError("audits must be a sequence")
    rule_tuple = tuple(rules)
    audit_tuple = tuple(audits)
    if not rule_tuple:
        raise LexicalRulePromotionError("lexical audit summary requires at least one rule")
    if any(not isinstance(rule, LexicalTemplateRule) for rule in rule_tuple):
        raise TypeError("rules must contain LexicalTemplateRule values")
    if any(not isinstance(audit, LexicalRuleAudit) for audit in audit_tuple):
        raise TypeError("audits must contain LexicalRuleAudit values")
    if len({rule.rule_hash for rule in rule_tuple}) != len(rule_tuple):
        raise LexicalRulePromotionError("lexical audit summary rules must be unique")
    by_rule_hash = {audit.rule_hash: audit for audit in audit_tuple}
    if len(by_rule_hash) != len(audit_tuple):
        raise LexicalRulePromotionError("lexical audit summaries must be unique by rule hash")
    expected_hashes = {rule.rule_hash for rule in rule_tuple}
    if set(by_rule_hash) != expected_hashes:
        raise LexicalRulePromotionError("lexical audit summaries must exactly match the requested rules")
    blocked = tuple(
        (rule.rule_id, by_rule_hash[rule.rule_hash].status.value)
        for rule in rule_tuple
        if not by_rule_hash[rule.rule_hash].evidence_summary_complete
    )
    if blocked:
        raise LexicalRulePromotionError(f"lexical evidence summaries are incomplete: {blocked}")
    return tuple(sorted(rule_tuple, key=lambda rule: (rule.rule_id, rule.version, rule.rule_hash)))
