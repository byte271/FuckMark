from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_json
from .fidelity_verification import LexicalPromotionEvidence, verify_lexical_promotion_evidence
from .lexical_rules import development_lexical_rules
from .schema import TransformFamily
from .syntax_fidelity_verification import SyntaxDevelopmentEvidence, verify_syntax_development_evidence
from .syntax_rules import development_syntax_rules


TASK29_FIDELITY_READINESS_ALGORITHM_VERSION = "task29-fidelity-readiness-v3"


class FidelityReadinessStatus(str, Enum):
    MISSING_SOURCE_GROUNDED_EVIDENCE = "MISSING_SOURCE_GROUNDED_EVIDENCE"
    VERIFIED_LEXICAL_RELEASE_EVIDENCE = "VERIFIED_LEXICAL_RELEASE_EVIDENCE"
    VERIFIED_SYNTAX_DEVELOPMENT_ONLY = "VERIFIED_SYNTAX_DEVELOPMENT_ONLY"


class FidelityReadinessVerificationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FidelityRuleReadiness:
    rule_id: str
    rule_hash: str
    family: TransformFamily
    status: FidelityReadinessStatus
    evidence_hash: str | None
    selected_for_confirmatory: bool

    def __post_init__(self) -> None:
        require_clean_string("rule_id", self.rule_id)
        require_sha256("rule_hash", self.rule_hash)
        if self.family not in (TransformFamily.LEXICAL_TEMPLATE, TransformFamily.SYNTAX_TEMPLATE):
            raise ValueError("fidelity readiness rows must describe lexical or syntax rules")
        if not isinstance(self.status, FidelityReadinessStatus):
            raise TypeError("status must be a FidelityReadinessStatus")
        if self.status is FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE:
            if self.evidence_hash is not None:
                raise ValueError("missing-evidence readiness rows cannot name an evidence hash")
        else:
            if self.evidence_hash is None:
                raise ValueError("verified readiness rows require an evidence hash")
            require_sha256("evidence_hash", self.evidence_hash)
        if self.family is TransformFamily.LEXICAL_TEMPLATE and self.status is FidelityReadinessStatus.VERIFIED_SYNTAX_DEVELOPMENT_ONLY:
            raise ValueError("lexical rules cannot use syntax readiness status")
        if self.family is TransformFamily.SYNTAX_TEMPLATE and self.status is FidelityReadinessStatus.VERIFIED_LEXICAL_RELEASE_EVIDENCE:
            raise ValueError("syntax rules cannot use lexical release readiness status")
        require_bool("selected_for_confirmatory", self.selected_for_confirmatory)


@dataclass(frozen=True, slots=True)
class Task29FidelityReadinessReport:
    algorithm_version: str
    rows: tuple[FidelityRuleReadiness, ...]
    selection_frozen: bool
    report_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TASK29_FIDELITY_READINESS_ALGORITHM_VERSION:
            raise ValueError("unsupported Task 29 fidelity readiness algorithm version")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise TypeError("rows must be a non-empty tuple")
        expected = tuple(sorted(self.rows, key=lambda value: (value.family.value, value.rule_id, value.rule_hash)))
        if self.rows != expected:
            raise ValueError("fidelity readiness rows must be canonically ordered")
        if len({value.rule_hash for value in self.rows}) != len(self.rows):
            raise ValueError("fidelity readiness rows must have unique rule hashes")
        expected_identities = {
            (rule.rule_id, rule.rule_hash, rule.family)
            for rule in (*development_lexical_rules(), *development_syntax_rules())
        }
        actual_identities = {(value.rule_id, value.rule_hash, value.family) for value in self.rows}
        if actual_identities != expected_identities:
            raise ValueError("fidelity readiness rows must exactly cover current development rules")
        require_bool("selection_frozen", self.selection_frozen)
        if not self.selection_frozen and any(value.selected_for_confirmatory for value in self.rows):
            raise ValueError("unfrozen confirmatory selection cannot contain selected rules")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match Task 29 fidelity readiness report")

    @property
    def has_missing_evidence(self) -> bool:
        return any(value.status is FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE for value in self.rows)

    @property
    def selected_rows(self) -> tuple[FidelityRuleReadiness, ...]:
        return tuple(value for value in self.rows if value.selected_for_confirmatory)

    @property
    def has_selected_missing_evidence(self) -> bool:
        return any(
            value.status is FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE
            for value in self.selected_rows
        )

    @property
    def confirmatory_scale_ready(self) -> bool:
        if not self.selection_frozen:
            return False
        return all(
            value.status is FidelityReadinessStatus.VERIFIED_LEXICAL_RELEASE_EVIDENCE
            for value in self.selected_rows
        )

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rows": self.rows,
            "selection_frozen": self.selection_frozen,
        }


def build_task29_fidelity_readiness(
    lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    confirmatory_rule_hashes: Sequence[str] | None = None,
) -> Task29FidelityReadinessReport:
    tokenizer_map = {} if tokenizers is None else dict(tokenizers)
    lexical_values = tuple(lexical_evidence)
    syntax_values = tuple(syntax_evidence)
    if any(not isinstance(value, LexicalPromotionEvidence) for value in lexical_values):
        raise TypeError("lexical_evidence must contain LexicalPromotionEvidence values")
    if any(not isinstance(value, SyntaxDevelopmentEvidence) for value in syntax_values):
        raise TypeError("syntax_evidence must contain SyntaxDevelopmentEvidence values")
    if len({value.rule.rule_hash for value in lexical_values}) != len(lexical_values):
        raise ValueError("lexical readiness evidence must be unique by rule hash")
    if len({value.rule.rule_hash for value in syntax_values}) != len(syntax_values):
        raise ValueError("syntax readiness evidence must be unique by rule hash")
    lexical_by_hash = {value.rule.rule_hash: value for value in lexical_values}
    syntax_by_hash = {value.rule.rule_hash: value for value in syntax_values}
    development_lexical = development_lexical_rules()
    development_syntax = development_syntax_rules()
    expected_lexical = {value.rule_hash for value in development_lexical}
    expected_syntax = {value.rule_hash for value in development_syntax}
    all_development_hashes = expected_lexical | expected_syntax
    if not set(lexical_by_hash) <= expected_lexical:
        raise ValueError("lexical readiness evidence contains an unknown development rule")
    if not set(syntax_by_hash) <= expected_syntax:
        raise ValueError("syntax readiness evidence contains an unknown development rule")
    if confirmatory_rule_hashes is None:
        selection_frozen = False
        selected_hashes: set[str] = set()
    else:
        if isinstance(confirmatory_rule_hashes, (str, bytes, bytearray)) or not isinstance(confirmatory_rule_hashes, Sequence):
            raise TypeError("confirmatory_rule_hashes must be a sequence or None")
        selected_values = tuple(confirmatory_rule_hashes)
        for value in selected_values:
            require_sha256("confirmatory_rule_hash", value)
        if len(set(selected_values)) != len(selected_values):
            raise ValueError("confirmatory rule hashes must be unique")
        selected_hashes = set(selected_values)
        unknown_selected = selected_hashes - all_development_hashes
        if unknown_selected:
            raise ValueError("confirmatory selection contains an unknown development rule")
        selection_frozen = True
    rows: list[FidelityRuleReadiness] = []
    for rule in development_lexical:
        evidence = lexical_by_hash.get(rule.rule_hash)
        selected = rule.rule_hash in selected_hashes
        if evidence is None:
            rows.append(FidelityRuleReadiness(rule.rule_id, rule.rule_hash, rule.family, FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE, None, selected))
            continue
        identity_hash = evidence.model_tokenizer_identity.identity_hash
        try:
            tokenizer = tokenizer_map[identity_hash]
        except KeyError as error:
            raise ValueError("missing tokenizer callable for lexical readiness evidence") from error
        verify_lexical_promotion_evidence(evidence, tokenizer)
        rows.append(FidelityRuleReadiness(rule.rule_id, rule.rule_hash, rule.family, FidelityReadinessStatus.VERIFIED_LEXICAL_RELEASE_EVIDENCE, evidence.evidence_hash, selected))
    for rule in development_syntax:
        evidence = syntax_by_hash.get(rule.rule_hash)
        selected = rule.rule_hash in selected_hashes
        if evidence is None:
            rows.append(FidelityRuleReadiness(rule.rule_id, rule.rule_hash, rule.family, FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE, None, selected))
            continue
        identity_hash = evidence.model_tokenizer_identity.identity_hash
        try:
            tokenizer = tokenizer_map[identity_hash]
        except KeyError as error:
            raise ValueError("missing tokenizer callable for syntax readiness evidence") from error
        verify_syntax_development_evidence(evidence, tokenizer)
        rows.append(FidelityRuleReadiness(rule.rule_id, rule.rule_hash, rule.family, FidelityReadinessStatus.VERIFIED_SYNTAX_DEVELOPMENT_ONLY, evidence.evidence_hash, selected))
    ordered = tuple(sorted(rows, key=lambda value: (value.family.value, value.rule_id, value.rule_hash)))
    payload = {
        "algorithm_version": TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        "rows": ordered,
        "selection_frozen": selection_frozen,
    }
    return Task29FidelityReadinessReport(
        TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        ordered,
        selection_frozen,
        sha256_json(payload),
    )


def verify_task29_fidelity_readiness(
    report: Task29FidelityReadinessReport,
    lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    confirmatory_rule_hashes: Sequence[str] | None = None,
) -> None:
    if not isinstance(report, Task29FidelityReadinessReport):
        raise TypeError("report must be a Task29FidelityReadinessReport")
    expected = build_task29_fidelity_readiness(
        lexical_evidence=lexical_evidence,
        syntax_evidence=syntax_evidence,
        tokenizers=tokenizers,
        confirmatory_rule_hashes=confirmatory_rule_hashes,
    )
    if report != expected:
        raise FidelityReadinessVerificationError(
            "Task 29 fidelity readiness report does not replay exactly from supplied evidence and confirmatory selection"
        )
