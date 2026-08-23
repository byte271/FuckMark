from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

from .._validation import require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .candidate_artifacts import CandidateEnumeration, CandidateRejection, TransformCandidate, _build_conflicts
from .hard_invariants import validate_hard_invariants
from .lexical_audit import LexicalRuleAudit, LexicalRulePromotionError
from .lexical_rules import LexicalTemplateRule, development_lexical_rules
from .protected import ProtectedSpanExtractor
from .protected_artifacts import ProtectedSpan, UserProtectedRange
from .rules import TransformRule, default_contraction_rules, validate_rules
from .schema import CandidateRejectionReason, InvariantStatus
from .surface_rules import development_surface_rules
from .syntax_rules import SyntaxTemplateRule, development_syntax_rules
from .trace import TransformOperation, TransformResult, TransformationTrace

TRANSFORM_REGISTRY_ALGORITHM_VERSION = "transform-registry-v6"
TRANSFORM_APPLY_ALGORITHM_VERSION = "explicit-candidate-apply-v4"
_MAX_ENUMERATION_ITEMS = 100_000
_MAX_RULE_SCAN_WORK = 50_000_000


def _simple_case_replacement(source_text: str, replacement: str) -> str | None:
    letters = "".join(character for character in source_text if character.isalpha())
    if letters and letters.isupper():
        return None
    if source_text == source_text.lower():
        return replacement.lower()
    if source_text[:1].isupper() and source_text[1:] == source_text[1:].lower():
        return replacement[:1].upper() + replacement[1:].lower()
    return None


def _make_rejection(input_hash: str, rule: TransformRule, start: int, end: int, source_text: str, reason: CandidateRejectionReason, protected_hashes: Sequence[str] = ()) -> CandidateRejection:
    hashes = tuple(sorted(set(protected_hashes)))
    payload = {"input_hash": input_hash, "rule_id": rule.rule_id, "rule_version": rule.version, "rule_hash": rule.rule_hash, "start": start, "end": end, "source_text": source_text, "reason": reason.value, "protected_span_hashes": hashes}
    return CandidateRejection(input_hash, rule.rule_id, rule.version, rule.rule_hash, start, end, source_text, reason, hashes, sha256_json(payload))


def _make_candidate(input_hash: str, rule: TransformRule, start: int, end: int, source_text: str, replacement: str) -> TransformCandidate:
    payload = {"input_hash": input_hash, "rule_id": rule.rule_id, "rule_version": rule.version, "rule_hash": rule.rule_hash, "family": rule.family.value, "tier": rule.tier.value, "start": start, "end": end, "source_text": source_text, "replacement_text": replacement}
    candidate_id = sha256_json(payload)
    return TransformCandidate(candidate_id, input_hash, rule.rule_id, rule.version, rule.rule_hash, rule.family, rule.tier, start, end, source_text, replacement)


def _overlapping_spans(spans: tuple[ProtectedSpan, ...], ends: tuple[int, ...], start: int, end: int) -> tuple[ProtectedSpan, ...]:
    index = bisect_right(ends, start)
    output: list[ProtectedSpan] = []
    while index < len(spans):
        span = spans[index]
        if span.start >= end:
            break
        output.append(span)
        index += 1
    return tuple(output)


class TransformRegistry:
    __slots__ = ("_rules", "_ruleset_hash", "_extractor")

    def __init__(self, rules: Sequence[TransformRule], identifiers: Sequence[str] = ()) -> None:
        self._rules = validate_rules(rules)
        self._ruleset_hash = sha256_json({"algorithm_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION, "rules": self._rules})
        self._extractor = ProtectedSpanExtractor(identifiers)

    @property
    def rules(self) -> tuple[TransformRule, ...]:
        return self._rules

    @property
    def ruleset_hash(self) -> str:
        return self._ruleset_hash

    @property
    def identifiers(self) -> tuple[str, ...]:
        return self._extractor.identifiers

    def enumerate(self, text: str, user_ranges: Sequence[UserProtectedRange] = ()) -> CandidateEnumeration:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if len(self._rules) * len(text) > _MAX_RULE_SCAN_WORK:
            raise ValueError("transform rule scanning exceeded work limit")
        protected = self._extractor.extract(text, user_ranges)
        input_hash = sha256_text(text)
        spans = protected.spans
        span_ends = tuple(span.end for span in spans)
        candidates: list[TransformCandidate] = []
        rejections: list[CandidateRejection] = []
        for rule in self._rules:
            for match in rule.pattern().finditer(text):
                if len(candidates) + len(rejections) >= _MAX_ENUMERATION_ITEMS:
                    raise ValueError("candidate enumeration exceeded resource limit")
                start, end = match.span()
                source_text = text[start:end]
                overlaps = _overlapping_spans(spans, span_ends, start, end)
                if overlaps:
                    rejections.append(_make_rejection(input_hash, rule, start, end, source_text, CandidateRejectionReason.PROTECTED_OVERLAP, tuple(span.span_hash for span in overlaps)))
                    continue
                letters = "".join(character for character in source_text if character.isalpha())
                if rule.block_all_caps and letters and letters.isupper():
                    rejections.append(_make_rejection(input_hash, rule, start, end, source_text, CandidateRejectionReason.ALL_CAPS_BLOCKED))
                    continue
                if isinstance(rule, (LexicalTemplateRule, SyntaxTemplateRule)) and not rule.precondition(text, start, end):
                    rejections.append(_make_rejection(input_hash, rule, start, end, source_text, CandidateRejectionReason.PRECONDITION_FAILED))
                    continue
                replacement_getter = getattr(rule, "replacement_for", None)
                replacement = replacement_getter(source_text) if callable(replacement_getter) else rule.replacement
                if rule.preserve_simple_case:
                    replacement = _simple_case_replacement(source_text, replacement)
                    if replacement is None:
                        rejections.append(_make_rejection(input_hash, rule, start, end, source_text, CandidateRejectionReason.UNSUPPORTED_CASE))
                        continue
                candidates.append(_make_candidate(input_hash, rule, start, end, source_text, replacement))
        ordered_candidates = tuple(sorted(candidates, key=lambda value: (value.start, value.end, value.rule_id, value.candidate_id)))
        ordered_rejections = tuple(sorted(rejections, key=lambda value: (value.start, value.end, value.rule_id, value.reason.value, value.rejection_hash)))
        conflicts = _build_conflicts(ordered_candidates)
        payload = {"algorithm_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION, "input_hash": input_hash, "ruleset_hash": self._ruleset_hash, "protected_manifest_hash": protected.manifest_hash, "candidates": ordered_candidates, "rejections": ordered_rejections, "conflicts": conflicts}
        return CandidateEnumeration(TRANSFORM_REGISTRY_ALGORITHM_VERSION, text, input_hash, self._ruleset_hash, protected, ordered_candidates, ordered_rejections, conflicts, sha256_json(payload))

    def apply(self, enumeration: CandidateEnumeration, candidate_ids: Sequence[str], seed: int = 0) -> TransformResult:
        if not isinstance(enumeration, CandidateEnumeration):
            raise TypeError("enumeration must be a CandidateEnumeration")
        if enumeration.ruleset_hash != self._ruleset_hash:
            raise ValueError("enumeration ruleset does not match registry")
        expected_enumeration = self.enumerate(enumeration.input_text, enumeration.protected_manifest.user_ranges)
        if enumeration != expected_enumeration:
            raise ValueError("enumeration does not replay exactly under this registry")
        require_int("seed", seed)
        if seed < 0 or seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        if not isinstance(candidate_ids, Sequence) or isinstance(candidate_ids, (str, bytes, bytearray)):
            raise TypeError("candidate_ids must be a sequence")
        requested_count = len(candidate_ids)
        available_count = len(enumeration.candidates)
        if available_count == 0 and requested_count:
            raise KeyError("candidate_ids contains an unknown or rejected candidate")
        if requested_count > available_count:
            raise ValueError("candidate_ids cannot exceed available candidates")
        requested = tuple(candidate_ids)
        for value in requested:
            require_sha256("candidate_id", value)
        if len(set(requested)) != len(requested):
            raise ValueError("candidate_ids must be unique")
        by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
        unknown = tuple(value for value in requested if value not in by_id)
        if unknown:
            raise KeyError("candidate_ids contains an unknown or rejected candidate")
        conflict_pairs = {(value.first_candidate_id, value.second_candidate_id) for value in enumeration.conflicts}
        requested_set = set(requested)
        if any(first in requested_set and second in requested_set for first, second in conflict_pairs):
            raise ValueError("candidate_ids contains overlapping candidates")
        selected = tuple(sorted((by_id[value] for value in requested), key=lambda value: (value.start, value.end, value.rule_id, value.candidate_id)))
        chunks: list[str] = []
        operations: list[TransformOperation] = []
        cursor = 0
        output_position = 0
        selected_ids: list[str] = []
        for candidate in selected:
            unchanged = enumeration.input_text[cursor:candidate.start]
            chunks.append(unchanged)
            output_position += len(unchanged)
            output_start = output_position
            chunks.append(candidate.replacement_text)
            output_position += len(candidate.replacement_text)
            output_end = output_position
            payload = {"candidate_id": candidate.candidate_id, "rule_id": candidate.rule_id, "rule_version": candidate.rule_version, "rule_hash": candidate.rule_hash, "source_start": candidate.start, "source_end": candidate.end, "output_start": output_start, "output_end": output_end, "before_text": candidate.source_text, "after_text": candidate.replacement_text}
            operations.append(TransformOperation(candidate.candidate_id, candidate.rule_id, candidate.rule_version, candidate.rule_hash, candidate.start, candidate.end, output_start, output_end, candidate.source_text, candidate.replacement_text, sha256_json(payload)))
            selected_ids.append(candidate.candidate_id)
            cursor = candidate.end
        chunks.append(enumeration.input_text[cursor:])
        output_text = "".join(chunks)
        input_hash = enumeration.input_hash
        output_hash = sha256_text(output_text)
        if selected and output_hash == input_hash:
            raise ValueError("non-empty candidate selection produced no net text change")
        invariant_report = validate_hard_invariants(enumeration.input_text, output_text, self.identifiers, enumeration.protected_manifest.user_ranges)
        if invariant_report.status is not InvariantStatus.PASS:
            raise ValueError("transformation violated hard content invariants")
        selected_tuple = tuple(selected_ids)
        operation_tuple = tuple(operations)
        trace_payload = {"algorithm_version": TRANSFORM_APPLY_ALGORITHM_VERSION, "registry_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION, "selection_policy_id": "explicit-candidate-ids-v4", "seed": seed, "input_hash": input_hash, "output_hash": output_hash, "ruleset_hash": self._ruleset_hash, "enumeration_hash": enumeration.enumeration_hash, "selected_candidate_ids": selected_tuple, "operations": operation_tuple, "precondition_failures": enumeration.rejections, "protected_span_violation_count": 0, "invariant_report": invariant_report}
        trace = TransformationTrace(TRANSFORM_APPLY_ALGORITHM_VERSION, TRANSFORM_REGISTRY_ALGORITHM_VERSION, "explicit-candidate-ids-v4", seed, input_hash, output_hash, self._ruleset_hash, enumeration.enumeration_hash, selected_tuple, operation_tuple, enumeration.rejections, 0, invariant_report, sha256_json(trace_payload))
        return TransformResult(output_text, trace, sha256_json({"output_text": output_text, "trace": trace}))


def default_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return TransformRegistry(default_contraction_rules(), identifiers)


def development_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return TransformRegistry((*default_contraction_rules(), *development_surface_rules(), *development_lexical_rules(), *development_syntax_rules()), identifiers)


def release_transform_registry(
    lexical_rules: Sequence[LexicalTemplateRule] = (),
    lexical_audits: Sequence[LexicalRuleAudit] = (),
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    if lexical_rules or lexical_audits:
        raise LexicalRulePromotionError(
            "release promotion requires source-grounded verified fidelity evidence; summary audit artifacts cannot authorize release"
        )
    return TransformRegistry(default_contraction_rules(), identifiers)
