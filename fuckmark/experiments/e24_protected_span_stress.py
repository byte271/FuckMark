from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms.lexical_rules import LexicalTemplateRule
from ..transforms.protected_artifacts import UserProtectedRange
from ..transforms.registry import TransformRegistry
from ..transforms.rules import LiteralTransformRule, TransformRule
from ..transforms.schema import CandidateRejectionReason, InvariantStatus, ProtectedSpanKind, TransformFamily
from ..transforms.syntax_rules import SyntaxTemplateRule


E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION = "e24-protected-span-stress-v1"
_E24_URL_SENTINEL = "https://example.com/e24-protected"


class E24ProtectedSpanStressStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class E24FamilyStressResult:
    family: TransformFamily
    rule_count: int
    protected_overlap_rejection_count: int
    safe_application_attempt_count: int
    protected_violation_count: int
    result_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.family, TransformFamily):
            raise TypeError("family must be a TransformFamily")
        for name, value in (
            ("rule_count", self.rule_count),
            ("protected_overlap_rejection_count", self.protected_overlap_rejection_count),
            ("safe_application_attempt_count", self.safe_application_attempt_count),
            ("protected_violation_count", self.protected_violation_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.rule_count <= 0:
            raise ValueError("rule_count must be positive")
        if self.protected_overlap_rejection_count > self.rule_count:
            raise ValueError("protected overlap rejection count cannot exceed rule count")
        if self.safe_application_attempt_count > self.rule_count:
            raise ValueError("safe application attempt count cannot exceed rule count")
        if self.protected_violation_count > self.safe_application_attempt_count:
            raise ValueError("protected violation count cannot exceed safe application attempts")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E24 family stress result")

    def _payload(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "rule_count": self.rule_count,
            "protected_overlap_rejection_count": self.protected_overlap_rejection_count,
            "safe_application_attempt_count": self.safe_application_attempt_count,
            "protected_violation_count": self.protected_violation_count,
        }


@dataclass(frozen=True, slots=True)
class E24ProtectedKindStressResult:
    kind: ProtectedSpanKind
    observed: bool
    safe_application_attempted: bool
    protected_violation_count: int
    result_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProtectedSpanKind):
            raise TypeError("kind must be a ProtectedSpanKind")
        require_bool("observed", self.observed)
        require_bool("safe_application_attempted", self.safe_application_attempted)
        require_int("protected_violation_count", self.protected_violation_count)
        if self.protected_violation_count not in {0, 1}:
            raise ValueError("protected_violation_count must be zero or one")
        if self.protected_violation_count and not self.safe_application_attempted:
            raise ValueError("a protected violation requires an attempted application")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E24 protected-kind stress result")

    def _payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "observed": self.observed,
            "safe_application_attempted": self.safe_application_attempted,
            "protected_violation_count": self.protected_violation_count,
        }


@dataclass(frozen=True, slots=True)
class E24ProtectedSpanStressReport:
    algorithm_version: str
    ruleset_hash: str
    family_results: tuple[E24FamilyStressResult, ...]
    protected_kind_results: tuple[E24ProtectedKindStressResult, ...]
    inactive_families: tuple[TransformFamily, ...]
    coverage_failure_count: int
    protected_violation_count: int
    status: E24ProtectedSpanStressStatus
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION:
            raise ValueError("unsupported E24 protected-span stress algorithm version")
        require_sha256("ruleset_hash", self.ruleset_hash)
        if not isinstance(self.family_results, tuple) or not self.family_results:
            raise TypeError("family_results must be a non-empty tuple")
        if any(not isinstance(value, E24FamilyStressResult) for value in self.family_results):
            raise TypeError("family_results must contain E24FamilyStressResult values")
        if self.family_results != tuple(sorted(self.family_results, key=lambda value: value.family.value)):
            raise ValueError("family_results must be canonically ordered")
        if len({value.family for value in self.family_results}) != len(self.family_results):
            raise ValueError("family_results must not duplicate transform families")
        if not isinstance(self.protected_kind_results, tuple):
            raise TypeError("protected_kind_results must be a tuple")
        expected_kinds = tuple(sorted(tuple(ProtectedSpanKind), key=lambda value: value.value))
        actual_kinds = tuple(value.kind for value in self.protected_kind_results)
        if actual_kinds != expected_kinds:
            raise ValueError("protected_kind_results must contain every protected span kind in canonical order")
        active_families = tuple(value.family for value in self.family_results)
        expected_inactive = tuple(sorted((value for value in TransformFamily if value not in active_families), key=lambda value: value.value))
        if self.inactive_families != expected_inactive:
            raise ValueError("inactive_families does not match the active rule families")
        require_int("coverage_failure_count", self.coverage_failure_count)
        require_int("protected_violation_count", self.protected_violation_count)
        if self.coverage_failure_count < 0 or self.protected_violation_count < 0:
            raise ValueError("E24 failure counts must be non-negative")
        expected_coverage_failures = sum(
            value.rule_count - value.protected_overlap_rejection_count
            + value.rule_count - value.safe_application_attempt_count
            for value in self.family_results
        ) + sum(
            (0 if value.observed else 1) + (0 if value.safe_application_attempted else 1)
            for value in self.protected_kind_results
        )
        if self.coverage_failure_count != expected_coverage_failures:
            raise ValueError("coverage_failure_count does not match E24 coverage evidence")
        expected_violations = sum(value.protected_violation_count for value in self.family_results) + sum(value.protected_violation_count for value in self.protected_kind_results)
        if self.protected_violation_count != expected_violations:
            raise ValueError("protected_violation_count does not match E24 stress evidence")
        if not isinstance(self.status, E24ProtectedSpanStressStatus):
            raise TypeError("status must be an E24ProtectedSpanStressStatus")
        expected_status = E24ProtectedSpanStressStatus.PASS if self.coverage_failure_count == 0 and self.protected_violation_count == 0 else E24ProtectedSpanStressStatus.FAIL
        if self.status is not expected_status:
            raise ValueError("status does not match E24 protected-span stress evidence")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match E24 protected-span stress report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "ruleset_hash": self.ruleset_hash,
            "family_results": self.family_results,
            "protected_kind_results": self.protected_kind_results,
            "inactive_families": tuple(value.value for value in self.inactive_families),
            "coverage_failure_count": self.coverage_failure_count,
            "protected_violation_count": self.protected_violation_count,
            "status": self.status.value,
        }


def _family_result(family: TransformFamily, rule_count: int, protected_overlap_rejection_count: int, safe_application_attempt_count: int, protected_violation_count: int) -> E24FamilyStressResult:
    payload = {
        "family": family.value,
        "rule_count": rule_count,
        "protected_overlap_rejection_count": protected_overlap_rejection_count,
        "safe_application_attempt_count": safe_application_attempt_count,
        "protected_violation_count": protected_violation_count,
    }
    return E24FamilyStressResult(family, rule_count, protected_overlap_rejection_count, safe_application_attempt_count, protected_violation_count, sha256_json(payload))


def _kind_result(kind: ProtectedSpanKind, observed: bool, safe_application_attempted: bool, protected_violation_count: int) -> E24ProtectedKindStressResult:
    payload = {
        "kind": kind.value,
        "observed": observed,
        "safe_application_attempted": safe_application_attempted,
        "protected_violation_count": protected_violation_count,
    }
    return E24ProtectedKindStressResult(kind, observed, safe_application_attempted, protected_violation_count, sha256_json(payload))


def _rule_safe_context(rule: TransformRule) -> str:
    if isinstance(rule, LiteralTransformRule):
        return f"{rule.source} keep {_E24_URL_SENTINEL} stable."
    if isinstance(rule, LexicalTemplateRule):
        return f"{rule.source} this sentence keeps {_E24_URL_SENTINEL} stable."
    if isinstance(rule, SyntaxTemplateRule):
        return f"The first clause stays stable{rule.source}the second clause keeps {_E24_URL_SENTINEL} unchanged."
    raise TypeError("unsupported E24 transform rule type")


def _rule_overlap_context(rule: TransformRule) -> tuple[str, UserProtectedRange]:
    text = f"Alpha {rule.source} omega."
    start = text.index(rule.source)
    return text, UserProtectedRange.create(start, start + len(rule.source), f"e24-{rule.rule_id}")


def _protected_kind_token(kind: ProtectedSpanKind) -> str:
    values = {
        ProtectedSpanKind.URL: "https://example.com/e24-kind",
        ProtectedSpanKind.EMAIL: "person@example.com",
        ProtectedSpanKind.IPV4: "192.0.2.1",
        ProtectedSpanKind.IPV6: "2001:db8:0:0:0:0:0:1",
        ProtectedSpanKind.NUMBER: "12345",
        ProtectedSpanKind.DATE: "2026-08-17",
        ProtectedSpanKind.CURRENCY: "$123.45",
        ProtectedSpanKind.PERCENTAGE: "42%",
        ProtectedSpanKind.CODE: "`immutable_call()`",
        ProtectedSpanKind.MARKDOWN_DESTINATION: "[label](https://example.com/e24-target)",
        ProtectedSpanKind.QUOTATION: '"immutable phrase"',
        ProtectedSpanKind.POSIX_PATH: "/usr/local/bin/e24-tool",
        ProtectedSpanKind.WINDOWS_PATH: "C:\\Temp\\e24-file.txt",
        ProtectedSpanKind.CLI_FLAG: "--e24-flag",
        ProtectedSpanKind.CITATION: "[12]",
        ProtectedSpanKind.MATH: "$x + y$",
        ProtectedSpanKind.IDENTIFIER: "E24Identifier",
        ProtectedSpanKind.USER_MARKED_ENTITY: "CriticalEntity",
    }
    return values[kind]


def _kind_context(registry: TransformRegistry, kind: ProtectedSpanKind, safe_rule: LiteralTransformRule | None) -> tuple[TransformRegistry, str, tuple[UserProtectedRange, ...], str]:
    token = _protected_kind_token(kind)
    prefix = f"{safe_rule.source} preserve " if safe_rule is not None else "Preserve "
    text = f"{prefix}{token} exactly."
    extra_identifiers = (token,) if kind is ProtectedSpanKind.IDENTIFIER else ()
    identifiers = tuple(sorted(set((*registry.identifiers, *extra_identifiers))))
    fixture_registry = TransformRegistry(registry.rules, identifiers)
    user_ranges: tuple[UserProtectedRange, ...] = ()
    if kind is ProtectedSpanKind.USER_MARKED_ENTITY:
        start = text.index(token)
        user_ranges = (UserProtectedRange.create(start, start + len(token), "e24-user-entity"),)
    return fixture_registry, text, user_ranges, token


def _application_violation(output_text: str, protected_text: str, protected_violation_count: int, invariant_status: InvariantStatus) -> int:
    return int(protected_violation_count != 0 or invariant_status is not InvariantStatus.PASS or protected_text not in output_text)


def run_e24_protected_span_stress(registry: TransformRegistry) -> E24ProtectedSpanStressReport:
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    rules_by_family: dict[TransformFamily, list[TransformRule]] = {}
    for rule in registry.rules:
        rules_by_family.setdefault(rule.family, []).append(rule)
    family_results: list[E24FamilyStressResult] = []
    for family in sorted(rules_by_family, key=lambda value: value.value):
        rules = tuple(rules_by_family[family])
        overlap_rejections = 0
        safe_attempts = 0
        violations = 0
        for rule in rules:
            overlap_text, user_range = _rule_overlap_context(rule)
            overlap_enumeration = registry.enumerate(overlap_text, (user_range,))
            if any(value.rule_id == rule.rule_id and value.reason is CandidateRejectionReason.PROTECTED_OVERLAP for value in overlap_enumeration.rejections):
                overlap_rejections += 1
            safe_text = _rule_safe_context(rule)
            safe_enumeration = registry.enumerate(safe_text)
            candidates = tuple(value for value in safe_enumeration.candidates if value.rule_id == rule.rule_id)
            if len(candidates) != 1:
                continue
            safe_attempts += 1
            try:
                result = registry.apply(safe_enumeration, (candidates[0].candidate_id,), seed=0)
            except ValueError:
                violations += 1
                continue
            violations += _application_violation(result.output_text, _E24_URL_SENTINEL, result.trace.protected_span_violation_count, result.trace.invariant_report.status)
        family_results.append(_family_result(family, len(rules), overlap_rejections, safe_attempts, violations))
    contraction_rules = tuple(value for value in registry.rules if isinstance(value, LiteralTransformRule) and value.family is TransformFamily.CONTRACTION)
    safe_rule = contraction_rules[0] if contraction_rules else None
    kind_results: list[E24ProtectedKindStressResult] = []
    for kind in sorted(tuple(ProtectedSpanKind), key=lambda value: value.value):
        fixture_registry, text, user_ranges, protected_text = _kind_context(registry, kind, safe_rule)
        enumeration = fixture_registry.enumerate(text, user_ranges)
        observed = any(kind in span.kinds for span in enumeration.protected_manifest.spans)
        attempted = False
        violations = 0
        if safe_rule is not None:
            candidates = tuple(value for value in enumeration.candidates if value.rule_id == safe_rule.rule_id and value.start == 0)
            if len(candidates) == 1:
                attempted = True
                try:
                    result = fixture_registry.apply(enumeration, (candidates[0].candidate_id,), seed=0)
                except ValueError:
                    violations = 1
                else:
                    violations = _application_violation(result.output_text, protected_text, result.trace.protected_span_violation_count, result.trace.invariant_report.status)
        kind_results.append(_kind_result(kind, observed, attempted, violations))
    family_tuple = tuple(family_results)
    kind_tuple = tuple(kind_results)
    active_families = tuple(value.family for value in family_tuple)
    inactive_families = tuple(sorted((value for value in TransformFamily if value not in active_families), key=lambda value: value.value))
    coverage_failure_count = sum(value.rule_count - value.protected_overlap_rejection_count + value.rule_count - value.safe_application_attempt_count for value in family_tuple) + sum((0 if value.observed else 1) + (0 if value.safe_application_attempted else 1) for value in kind_tuple)
    protected_violation_count = sum(value.protected_violation_count for value in family_tuple) + sum(value.protected_violation_count for value in kind_tuple)
    status = E24ProtectedSpanStressStatus.PASS if coverage_failure_count == 0 and protected_violation_count == 0 else E24ProtectedSpanStressStatus.FAIL
    payload = {
        "algorithm_version": E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION,
        "ruleset_hash": registry.ruleset_hash,
        "family_results": family_tuple,
        "protected_kind_results": kind_tuple,
        "inactive_families": tuple(value.value for value in inactive_families),
        "coverage_failure_count": coverage_failure_count,
        "protected_violation_count": protected_violation_count,
        "status": status.value,
    }
    return E24ProtectedSpanStressReport(E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION, registry.ruleset_hash, family_tuple, kind_tuple, inactive_families, coverage_failure_count, protected_violation_count, status, sha256_json(payload))
