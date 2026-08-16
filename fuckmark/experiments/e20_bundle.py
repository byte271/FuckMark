from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization
from .e20_rows import E20FailureRow, E20OutcomeRow, ExperimentReasonCode


E20_RESULT_BUNDLE_ALGORITHM_VERSION = "e20-result-bundle-v1"


class E20ResultBundleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E20ReasonCount:
    reason_code: ExperimentReasonCode
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, ExperimentReasonCode):
            raise TypeError("reason_code must be an ExperimentReasonCode")
        require_int("count", self.count)
        if self.count < 0:
            raise ValueError("count must be non-negative")


@dataclass(frozen=True, slots=True)
class E20ResultBundle:
    algorithm_version: str
    execution_id: str
    authorization_hash: str
    corpus_manifest_hash: str
    condition_plan_hash: str
    outcome_rows: tuple[E20OutcomeRow, ...]
    failure_rows: tuple[E20FailureRow, ...]
    reason_counts: tuple[E20ReasonCount, ...]
    expected_row_count: int
    observed_row_count: int
    outcome_row_count: int
    failure_row_count: int
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_RESULT_BUNDLE_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 result bundle algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("authorization_hash", self.authorization_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("bundle_hash", self.bundle_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.outcome_rows, tuple) or any(not isinstance(value, E20OutcomeRow) for value in self.outcome_rows):
            raise TypeError("outcome_rows must be a tuple of E20OutcomeRow values")
        if not isinstance(self.failure_rows, tuple) or any(not isinstance(value, E20FailureRow) for value in self.failure_rows):
            raise TypeError("failure_rows must be a tuple of E20FailureRow values")
        outcome_order = tuple(sorted(self.outcome_rows, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
        failure_order = tuple(sorted(self.failure_rows, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
        if self.outcome_rows != outcome_order or self.failure_rows != failure_order:
            raise ValueError("E20 result rows must be canonically ordered")
        all_hashes = tuple(value.row_hash for value in (*self.outcome_rows, *self.failure_rows))
        if len(set(all_hashes)) != len(all_hashes):
            raise ValueError("E20 result row hashes must be unique")
        if not isinstance(self.reason_counts, tuple):
            raise TypeError("reason_counts must be a tuple")
        expected_reason_order = tuple(ExperimentReasonCode)
        if tuple(value.reason_code for value in self.reason_counts) != expected_reason_order:
            raise ValueError("reason_counts must contain every reason code exactly once in frozen enum order")
        for value in self.reason_counts:
            if not isinstance(value, E20ReasonCount):
                raise TypeError("reason_counts must contain E20ReasonCount values")
        for name, value in (
            ("expected_row_count", self.expected_row_count),
            ("observed_row_count", self.observed_row_count),
            ("outcome_row_count", self.outcome_row_count),
            ("failure_row_count", self.failure_row_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.observed_row_count != len(self.outcome_rows) + len(self.failure_rows):
            raise ValueError("observed_row_count does not match result rows")
        if self.outcome_row_count != len(self.outcome_rows):
            raise ValueError("outcome_row_count does not match outcome rows")
        if self.failure_row_count != len(self.failure_rows):
            raise ValueError("failure_row_count does not match failure rows")
        if self.expected_row_count != self.observed_row_count:
            raise ValueError("sealed E20 result bundle must contain every expected row")
        if sum(value.count for value in self.reason_counts) != self.observed_row_count:
            raise ValueError("reason counts do not sum to observed row count")
        expected_counts: Counter[ExperimentReasonCode] = Counter()
        for row in self.outcome_rows:
            expected_counts[row.fidelity.reason_codes[0]] += 1
        for row in self.failure_rows:
            expected_counts[row.reason_code] += 1
        if tuple(value.count for value in self.reason_counts) != tuple(expected_counts[value] for value in ExperimentReasonCode):
            raise ValueError("reason_counts do not replay from E20 result rows")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E20 result bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "authorization_hash": self.authorization_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "condition_plan_hash": self.condition_plan_hash,
            "outcome_rows": self.outcome_rows,
            "failure_rows": self.failure_rows,
            "reason_counts": self.reason_counts,
            "expected_row_count": self.expected_row_count,
            "observed_row_count": self.observed_row_count,
            "outcome_row_count": self.outcome_row_count,
            "failure_row_count": self.failure_row_count,
        }


def _row_key(row: E20OutcomeRow | E20FailureRow) -> tuple[str, str]:
    return row.identity.sample_id, row.identity.condition_id


def _verify_shared_transforms(
    outcome_rows: tuple[E20OutcomeRow, ...],
    condition_plan: E20ConditionPlan,
) -> None:
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    groups: dict[tuple[str, str], list[E20OutcomeRow]] = defaultdict(list)
    for row in outcome_rows:
        condition = condition_by_id[row.identity.condition_id]
        groups[(row.identity.sample_id, condition.transform_condition_id)].append(row)
    for rows in groups.values():
        if len(rows) <= 1:
            continue
        first = rows[0]
        expected = (
            first.text.transformed_text_hash,
            first.text.transformed_char_count,
            first.text.transformed_word_count,
            first.text.transformed_token_count,
            first.transform.schedule_policy,
            first.transform.schedule_seed,
            first.transform.budget,
            first.transform.budget_unit,
            first.transform.realized_edit_cost,
            first.transform.candidate_pool_hash,
            first.transform.scheduler_input_hash,
            first.transform.schedule_result_hash,
            first.transform.operation_trace_hash,
            first.transform.eligible,
            first.fidelity.char_edit_distance,
            first.fidelity.word_edit_distance,
            first.fidelity.token_edit_distance,
            first.fidelity.human_status,
            first.fidelity.human_adjudication_hash,
        )
        for row in rows[1:]:
            actual = (
                row.text.transformed_text_hash,
                row.text.transformed_char_count,
                row.text.transformed_word_count,
                row.text.transformed_token_count,
                row.transform.schedule_policy,
                row.transform.schedule_seed,
                row.transform.budget,
                row.transform.budget_unit,
                row.transform.realized_edit_cost,
                row.transform.candidate_pool_hash,
                row.transform.scheduler_input_hash,
                row.transform.schedule_result_hash,
                row.transform.operation_trace_hash,
                row.transform.eligible,
                row.fidelity.char_edit_distance,
                row.fidelity.word_edit_distance,
                row.fidelity.token_edit_distance,
                row.fidelity.human_status,
                row.fidelity.human_adjudication_hash,
            )
            if actual != expected:
                raise E20ResultBundleError(
                    "detector or FPR evaluation conditions changed the frozen transform for the same source and transform condition"
                )


def build_e20_result_bundle(
    authorization: E20ExecutionAuthorization,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    outcome_rows: Sequence[E20OutcomeRow],
    failure_rows: Sequence[E20FailureRow],
) -> E20ResultBundle:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if corpus_manifest.manifest_hash != authorization.corpus_manifest_hash:
        raise E20ResultBundleError("corpus manifest does not match E20 authorization")
    outcomes = tuple(outcome_rows)
    failures = tuple(failure_rows)
    if any(not isinstance(value, E20OutcomeRow) for value in outcomes):
        raise TypeError("outcome_rows must contain E20OutcomeRow values")
    if any(not isinstance(value, E20FailureRow) for value in failures):
        raise TypeError("failure_rows must contain E20FailureRow values")
    conditions = {value.condition_id: value for value in condition_plan.conditions}
    sample_ids = {value.sample_id for value in corpus_manifest.samples}
    expected_keys = {(sample_id, condition_id) for sample_id in sample_ids for condition_id in conditions}
    observed_rows = (*outcomes, *failures)
    observed_keys = tuple(_row_key(value) for value in observed_rows)
    if len(set(observed_keys)) != len(observed_keys):
        raise E20ResultBundleError("E20 result bundle contains duplicate sample and condition rows")
    observed_key_set = set(observed_keys)
    missing = expected_keys - observed_key_set
    extra = observed_key_set - expected_keys
    if missing or extra:
        raise E20ResultBundleError(
            f"E20 result coverage mismatch: missing={len(missing)} extra={len(extra)}"
        )
    for row in observed_rows:
        if row.identity.execution_id != authorization.execution_id or row.identity.run_id != authorization.execution_id:
            raise E20ResultBundleError("E20 result row belongs to a different sealed execution")
    for row in outcomes:
        condition = conditions[row.identity.condition_id]
        if row.detector.calibration_bundle_hash != condition.calibration_bundle_hash:
            raise E20ResultBundleError("E20 outcome detector bundle does not match its sealed evaluation condition")
        if row.detector.target_fpr != condition.target_fpr:
            raise E20ResultBundleError("E20 outcome target FPR does not match its sealed evaluation condition")
        if row.transform.schedule_policy is not condition.schedule_policy:
            raise E20ResultBundleError("E20 outcome schedule does not match its sealed transform condition")
        if row.transform.budget != condition.budget or row.transform.budget_unit != condition.budget_unit:
            raise E20ResultBundleError("E20 outcome budget does not match its sealed transform condition")
        if row.statistics.hypothesis_class != condition.hypothesis_class:
            raise E20ResultBundleError("E20 outcome hypothesis class does not match its sealed evaluation condition")
    ordered_outcomes = tuple(sorted(outcomes, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
    ordered_failures = tuple(sorted(failures, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
    _verify_shared_transforms(ordered_outcomes, condition_plan)
    counts: Counter[ExperimentReasonCode] = Counter()
    for row in ordered_outcomes:
        counts[row.fidelity.reason_codes[0]] += 1
    for row in ordered_failures:
        counts[row.reason_code] += 1
    reason_counts = tuple(E20ReasonCount(reason, counts[reason]) for reason in ExperimentReasonCode)
    expected_count = len(expected_keys)
    observed_count = len(observed_rows)
    payload = {
        "algorithm_version": E20_RESULT_BUNDLE_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "authorization_hash": authorization.authorization_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "outcome_rows": ordered_outcomes,
        "failure_rows": ordered_failures,
        "reason_counts": reason_counts,
        "expected_row_count": expected_count,
        "observed_row_count": observed_count,
        "outcome_row_count": len(ordered_outcomes),
        "failure_row_count": len(ordered_failures),
    }
    return E20ResultBundle(
        E20_RESULT_BUNDLE_ALGORITHM_VERSION,
        authorization.execution_id,
        authorization.authorization_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        ordered_outcomes,
        ordered_failures,
        reason_counts,
        expected_count,
        observed_count,
        len(ordered_outcomes),
        len(ordered_failures),
        sha256_json(payload),
    )


def verify_e20_result_bundle(
    bundle: E20ResultBundle,
    authorization: E20ExecutionAuthorization,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(bundle, E20ResultBundle):
        raise TypeError("bundle must be an E20ResultBundle")
    expected = build_e20_result_bundle(
        authorization,
        corpus_manifest,
        condition_plan,
        bundle.outcome_rows,
        bundle.failure_rows,
    )
    if bundle != expected:
        raise E20ResultBundleError("E20 result bundle does not replay exactly from its sealed rows and execution inputs")
