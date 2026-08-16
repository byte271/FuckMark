from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .candidate_artifacts import CandidateRejection
from .hard_invariants import HardInvariantReport
from .schema import InvariantStatus


@dataclass(frozen=True, slots=True)
class TransformOperation:
    candidate_id: str
    rule_id: str
    rule_version: str
    rule_hash: str
    source_start: int
    source_end: int
    output_start: int
    output_end: int
    before_text: str
    after_text: str
    operation_hash: str

    def __post_init__(self) -> None:
        for name, value in (("candidate_id", self.candidate_id), ("rule_hash", self.rule_hash), ("operation_hash", self.operation_hash)):
            require_sha256(name, value)
        require_clean_string("rule_id", self.rule_id)
        require_clean_string("rule_version", self.rule_version)
        for name, value in (("source_start", self.source_start), ("source_end", self.source_end), ("output_start", self.output_start), ("output_end", self.output_end)):
            require_int(name, value)
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("source operation span is invalid")
        if self.output_start < 0 or self.output_end <= self.output_start:
            raise ValueError("output operation span is invalid")
        if not isinstance(self.before_text, str) or not self.before_text:
            raise ValueError("before_text must be non-empty")
        if not isinstance(self.after_text, str) or not self.after_text:
            raise ValueError("after_text must be non-empty")
        if self.source_end - self.source_start != len(self.before_text):
            raise ValueError("source operation span does not match before_text")
        if self.output_end - self.output_start != len(self.after_text):
            raise ValueError("output operation span does not match after_text")
        if self.before_text == self.after_text:
            raise ValueError("transform operation must change text")
        if self.operation_hash != sha256_json(self._payload()):
            raise ValueError("operation_hash does not match transform operation")

    def _payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_hash": self.rule_hash,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "output_start": self.output_start,
            "output_end": self.output_end,
            "before_text": self.before_text,
            "after_text": self.after_text,
        }


@dataclass(frozen=True, slots=True)
class TransformationTrace:
    algorithm_version: str
    registry_version: str
    selection_policy_id: str
    seed: int
    input_hash: str
    output_hash: str
    ruleset_hash: str
    enumeration_hash: str
    selected_candidate_ids: tuple[str, ...]
    operations: tuple[TransformOperation, ...]
    precondition_failures: tuple[CandidateRejection, ...]
    protected_span_violation_count: int
    invariant_report: HardInvariantReport
    trace_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_clean_string("registry_version", self.registry_version)
        require_clean_string("selection_policy_id", self.selection_policy_id)
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        for name, value in (("input_hash", self.input_hash), ("output_hash", self.output_hash), ("ruleset_hash", self.ruleset_hash), ("enumeration_hash", self.enumeration_hash), ("trace_hash", self.trace_hash)):
            require_sha256(name, value)
        selected = tuple(self.selected_candidate_ids)
        operations = tuple(self.operations)
        failures = tuple(self.precondition_failures)
        object.__setattr__(self, "selected_candidate_ids", selected)
        object.__setattr__(self, "operations", operations)
        object.__setattr__(self, "precondition_failures", failures)
        for value in selected:
            require_sha256("selected_candidate_id", value)
        if len(set(selected)) != len(selected):
            raise ValueError("selected candidate IDs must be unique")
        if any(not isinstance(value, TransformOperation) for value in operations):
            raise TypeError("operations must contain TransformOperation values")
        if tuple(value.candidate_id for value in operations) != selected:
            raise ValueError("operation order must match selected candidate IDs")
        if operations != tuple(sorted(operations, key=lambda value: (value.source_start, value.source_end, value.candidate_id))):
            raise ValueError("operations must be ordered by source geometry")
        for left, right in zip(operations, operations[1:]):
            if left.source_end > right.source_start or left.output_end > right.output_start:
                raise ValueError("operations must not overlap in source or output geometry")
            if right.source_start - left.source_end != right.output_start - left.output_end:
                raise ValueError("operation source and output gaps must preserve unchanged text geometry")
        if operations and operations[0].source_start != operations[0].output_start:
            raise ValueError("first operation must preserve unchanged prefix geometry")
        if operations and self.input_hash == self.output_hash:
            raise ValueError("non-empty transformation traces must change the output hash")
        if not operations and self.input_hash != self.output_hash:
            raise ValueError("empty transformation traces must preserve the output hash")
        if any(not isinstance(value, CandidateRejection) for value in failures):
            raise TypeError("precondition_failures must contain CandidateRejection values")
        if failures != tuple(sorted(failures, key=lambda value: (value.start, value.end, value.rule_id, value.reason.value, value.rejection_hash))):
            raise ValueError("precondition_failures must be canonically ordered")
        if len({value.rejection_hash for value in failures}) != len(failures):
            raise ValueError("precondition_failures must be unique")
        if any(value.input_hash != self.input_hash for value in failures):
            raise ValueError("precondition_failures must match trace input")
        require_int("protected_span_violation_count", self.protected_span_violation_count)
        if self.protected_span_violation_count != 0:
            raise ValueError("successful transformation traces cannot contain protected-span violations")
        if not isinstance(self.invariant_report, HardInvariantReport):
            raise TypeError("invariant_report must be a HardInvariantReport")
        if self.invariant_report.status is not InvariantStatus.PASS:
            raise ValueError("successful transformation traces require a passing invariant report")
        if self.invariant_report.original_hash != self.input_hash or self.invariant_report.transformed_hash != self.output_hash:
            raise ValueError("invariant report hashes must match trace input and output")
        if self.trace_hash != sha256_json(self._payload()):
            raise ValueError("trace_hash does not match transformation trace")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "registry_version": self.registry_version,
            "selection_policy_id": self.selection_policy_id,
            "seed": self.seed,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "ruleset_hash": self.ruleset_hash,
            "enumeration_hash": self.enumeration_hash,
            "selected_candidate_ids": self.selected_candidate_ids,
            "operations": self.operations,
            "precondition_failures": self.precondition_failures,
            "protected_span_violation_count": self.protected_span_violation_count,
            "invariant_report": self.invariant_report,
        }


@dataclass(frozen=True, slots=True)
class TransformResult:
    output_text: str
    trace: TransformationTrace
    result_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.output_text, str):
            raise TypeError("output_text must be a string")
        if not isinstance(self.trace, TransformationTrace):
            raise TypeError("trace must be a TransformationTrace")
        if self.trace.output_hash != sha256_text(self.output_text):
            raise ValueError("trace output hash does not match output_text")
        for operation in self.trace.operations:
            if operation.output_end > len(self.output_text):
                raise ValueError("operation output span extends beyond output_text")
            if self.output_text[operation.output_start:operation.output_end] != operation.after_text:
                raise ValueError("operation output geometry does not match output_text")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json({"output_text": self.output_text, "trace": self.trace}):
            raise ValueError("result_hash does not match transform result")
