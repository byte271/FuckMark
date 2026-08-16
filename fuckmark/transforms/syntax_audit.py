from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID


SYNTAX_RULE_AUDIT_ALGORITHM_VERSION = "syntax-rule-fidelity-audit-v1"
MINIMUM_SYNTAX_GRAMMAR_FIXTURES_PER_CLASS = 5
MINIMUM_SYNTAX_HUMAN_AUDIT_SAMPLES = 100
MINIMUM_SYNTAX_EQUIVALENT_OR_MINOR_RATE = 0.95


class SyntaxAuditStatus(str, Enum):
    GRAMMAR_FIXTURES_INCOMPLETE = "GRAMMAR_FIXTURES_INCOMPLETE"
    TOKENIZER_FIXTURES_MISSING = "TOKENIZER_FIXTURES_MISSING"
    HUMAN_FIDELITY_AUDIT_MISSING = "HUMAN_FIDELITY_AUDIT_MISSING"
    BLOCKED_HARD_INVARIANT = "BLOCKED_HARD_INVARIANT"
    BLOCKED_HUMAN_FIDELITY = "BLOCKED_HUMAN_FIDELITY"
    DEVELOPMENT_AUDIT_COMPLETE = "DEVELOPMENT_AUDIT_COMPLETE"


@dataclass(frozen=True, slots=True)
class SyntaxRuleAudit:
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
    status: SyntaxAuditStatus
    audit_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != SYNTAX_RULE_AUDIT_ALGORITHM_VERSION:
            raise ValueError("unsupported syntax rule audit algorithm version")
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
            raise ValueError("syntax fidelity audit must use the frozen blind review policy")
        if not isinstance(self.status, SyntaxAuditStatus):
            raise TypeError("status must be a SyntaxAuditStatus")
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
            raise ValueError("syntax audit status does not match supplied evidence")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self._payload()):
            raise ValueError("audit_hash does not match syntax rule audit")

    @property
    def development_audit_complete(self) -> bool:
        return self.status is SyntaxAuditStatus.DEVELOPMENT_AUDIT_COMPLETE

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
) -> SyntaxAuditStatus:
    if positive_count < MINIMUM_SYNTAX_GRAMMAR_FIXTURES_PER_CLASS or negative_count < MINIMUM_SYNTAX_GRAMMAR_FIXTURES_PER_CLASS:
        return SyntaxAuditStatus.GRAMMAR_FIXTURES_INCOMPLETE
    if tokenizer_count == 0:
        return SyntaxAuditStatus.TOKENIZER_FIXTURES_MISSING
    if human_sample_count < MINIMUM_SYNTAX_HUMAN_AUDIT_SAMPLES:
        return SyntaxAuditStatus.HUMAN_FIDELITY_AUDIT_MISSING
    if hard_invariant_violation_count:
        return SyntaxAuditStatus.BLOCKED_HARD_INVARIANT
    if material_change_count or equivalent_or_minor_count / human_sample_count < MINIMUM_SYNTAX_EQUIVALENT_OR_MINOR_RATE:
        return SyntaxAuditStatus.BLOCKED_HUMAN_FIDELITY
    return SyntaxAuditStatus.DEVELOPMENT_AUDIT_COMPLETE


def create_syntax_rule_audit(
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
) -> SyntaxRuleAudit:
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
        "algorithm_version": SYNTAX_RULE_AUDIT_ALGORITHM_VERSION,
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
    return SyntaxRuleAudit(
        algorithm_version=SYNTAX_RULE_AUDIT_ALGORITHM_VERSION,
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
