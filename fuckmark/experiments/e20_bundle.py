from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization, derive_e20_condition_seed
from .e20_rows import E20FailureRow, E20OutcomeRow, ExperimentReasonCode


E20_RESULT_BUNDLE_ALGORITHM_VERSION = "e20-result-bundle-v2"


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
        if tuple(value.reason_code for value in self.reason_counts) != tuple(ExperimentReasonCode):
            raise ValueError("reason_counts must contain every reason code exactly once in frozen enum order")
        if any(not isinstance(value, E20ReasonCount) for value in self.reason_counts):
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


def _compatible_condition_ids(
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    watermark_config_hash: str,
) -> tuple[str, ...]:
    try:
        track = preregistration.watermark_tracks.track_for(watermark_config_hash)
    except KeyError as error:
        raise E20ResultBundleError(
            "E20 corpus sample watermark configuration is outside the sealed generation tracks"
        ) from error
    bundle_by_hash = {value.bundle_hash: value for value in preregistration.calibration_bundles}
    result = []
    for condition in condition_plan.conditions:
        bundle = bundle_by_hash.get(condition.calibration_bundle_hash)
        if bundle is None:
            raise E20ResultBundleError("E20 condition references a calibration bundle outside preregistration")
        if track.matches_detector_identity(bundle.detector_identity):
            result.append(condition.condition_id)
    if not result:
        raise E20ResultBundleError("sealed generation track has no compatible E20 evaluation condition")
    return tuple(result)


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


def _verify_common_row_binding(
    row: E20OutcomeRow | E20FailureRow,
    authorization: E20ExecutionAuthorization,
    sample,
) -> None:
    if row.identity.execution_id != authorization.execution_id or row.identity.run_id != authorization.execution_id:
        raise E20ResultBundleError("E20 result row belongs to a different sealed execution")
    if row.identity.pair_id != sample.match_id:
        raise E20ResultBundleError("E20 result row pair identity does not match the sealed corpus sample")
    if row.audit.authorization_hash != authorization.authorization_hash:
        raise E20ResultBundleError("E20 result row audit authorization does not match the sealed execution authorization")
    if row.audit.environment_snapshot_hash != authorization.environment_snapshot_hash:
        raise E20ResultBundleError("E20 result row audit environment does not match the sealed execution authorization")
    if row.audit.worker_version != authorization.worker_version:
        raise E20ResultBundleError("E20 result row audit worker version does not match the sealed execution authorization")
    if sample.record_hash not in row.audit.artifact_hashes:
        raise E20ResultBundleError("E20 result row audit artifacts do not bind the sealed source sample")


def _verify_failure_row_binding(row: E20FailureRow, sample, condition) -> None:
    if row.source_sample_record_hash != sample.record_hash:
        raise E20ResultBundleError("E20 failure row source sample hash does not match the sealed corpus sample")
    if row.detail_hash not in row.audit.artifact_hashes:
        raise E20ResultBundleError("E20 failure row audit artifacts do not bind the failure detail")
    if condition.condition_hash not in row.audit.artifact_hashes:
        raise E20ResultBundleError("E20 failure row audit artifacts do not bind the sealed condition")


def _verify_outcome_row_binding(
    row: E20OutcomeRow,
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    sample,
    condition,
    bundle,
) -> None:
    track = preregistration.watermark_tracks.track_for(sample.watermark.watermark_config_hash)
    if (
        row.source.adapter_id != track.adapter_id
        or row.source.source_commit != track.source_pin.commit
        or row.source.adapter_config_hash != track.adapter_config_hash
    ):
        raise E20ResultBundleError("E20 outcome source adapter does not match the sealed generation track")
    if (
        row.model.model_id != sample.model.model_id
        or row.model.model_revision != sample.model.model_revision
        or row.model.tokenizer_id != sample.model.tokenizer_id
        or row.model.tokenizer_revision != sample.model.tokenizer_revision
    ):
        raise E20ResultBundleError("E20 outcome model/tokenizer does not match the sealed corpus sample")
    if (
        row.watermark.watermark_config_hash != sample.watermark.watermark_config_hash
        or row.watermark.key_split is not sample.watermark.key_split
        or row.watermark.key_id != sample.watermark.key_id
    ):
        raise E20ResultBundleError("E20 outcome watermark identity does not match the sealed corpus sample")
    if (
        row.generation.seed != sample.generation.seed
        or row.generation.temperature != sample.generation.temperature
        or row.generation.top_k != sample.generation.top_k
        or row.generation.top_p != sample.generation.top_p
        or row.generation.realized_length != sample.generation_realized_length
    ):
        raise E20ResultBundleError("E20 outcome generation parameters do not match the sealed corpus sample")
    if row.text.source_text_hash != sample.text_sha256:
        raise E20ResultBundleError("E20 outcome source text hash does not match the sealed corpus sample")
    if row.text.source_char_count != len(sample.text):
        raise E20ResultBundleError("E20 outcome source character count does not match the sealed corpus sample")
    if row.text.source_token_count != len(sample.generation_tokens.continuation_token_ids):
        raise E20ResultBundleError("E20 outcome source token count does not match the sealed corpus sample")
    if row.transform.ruleset_hash != preregistration.transform_ruleset_hash:
        raise E20ResultBundleError("E20 outcome transform ruleset does not match preregistration")
    expected_seed = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
    if row.transform.schedule_seed != expected_seed:
        raise E20ResultBundleError("E20 outcome schedule seed does not match sealed deterministic derivation")
    identity = bundle.detector_identity
    if row.detector.detector_family is not identity.detector_family:
        raise E20ResultBundleError("E20 outcome detector family does not match the frozen calibration identity")
    if row.detector.detector_config_hash != identity.detector_config_hash:
        raise E20ResultBundleError("E20 outcome detector configuration does not match the frozen calibration identity")
    if row.gvalues.depth != identity.depth:
        raise E20ResultBundleError("E20 outcome g-value depth does not match the frozen detector identity")
    thresholds = tuple(value for value in bundle.thresholds if value.target_fpr == condition.target_fpr)
    if len(thresholds) != 1:
        raise E20ResultBundleError("E20 condition does not resolve to exactly one frozen calibration threshold")
    threshold = thresholds[0]
    if row.detector.calibration_bundle_hash != bundle.bundle_hash:
        raise E20ResultBundleError("E20 outcome detector bundle does not match its sealed evaluation condition")
    if row.detector.target_fpr != condition.target_fpr:
        raise E20ResultBundleError("E20 outcome target FPR does not match its sealed evaluation condition")
    if row.detector.threshold_hash != threshold.threshold_hash:
        raise E20ResultBundleError("E20 outcome threshold hash does not match the frozen calibration threshold")
    if row.detector.threshold_value != threshold.value:
        raise E20ResultBundleError("E20 outcome threshold value does not match the frozen calibration threshold")
    if row.detector.comparison_operator is not threshold.comparison_operator:
        raise E20ResultBundleError("E20 outcome comparison operator does not match the frozen calibration threshold")
    if row.detector.robust_scale != bundle.robust_scale:
        raise E20ResultBundleError("E20 outcome robust scale does not match the frozen calibration bundle")
    if row.transform.schedule_policy is not condition.schedule_policy:
        raise E20ResultBundleError("E20 outcome schedule does not match its sealed transform condition")
    if row.transform.budget != condition.budget or row.transform.budget_unit != condition.budget_unit:
        raise E20ResultBundleError("E20 outcome budget does not match its sealed transform condition")
    if row.statistics.hypothesis_class != condition.hypothesis_class:
        raise E20ResultBundleError("E20 outcome hypothesis class does not match its sealed evaluation condition")
    expected_stratum_id = sha256_json(
        {
            "model_tokenizer_identity_hash": sample.model.identity_hash,
            "domain": sample.domain.value,
            "target_length": sample.target_length,
            "key_id": sample.watermark.key_id,
            "detector_config_hash": identity.detector_config_hash,
            "target_fpr": condition.target_fpr,
        }
    )
    if row.statistics.stratum_id != expected_stratum_id:
        raise E20ResultBundleError("E20 outcome statistical stratum does not match sealed sample and detector inputs")
    if row.statistics.bootstrap_group != sample.sample_id:
        raise E20ResultBundleError("E20 outcome bootstrap group does not match the sealed source sample")


def build_e20_result_bundle(
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    outcome_rows: Sequence[E20OutcomeRow],
    failure_rows: Sequence[E20FailureRow],
) -> E20ResultBundle:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if authorization.preregistration_hash != preregistration.preregistration_hash:
        raise E20ResultBundleError("preregistration does not match E20 authorization")
    if corpus_manifest.manifest_hash != authorization.corpus_manifest_hash:
        raise E20ResultBundleError("corpus manifest does not match E20 authorization")
    if condition_plan.plan_hash != preregistration.budget_config_hash:
        raise E20ResultBundleError("condition plan does not match the preregistered budget configuration")
    outcomes = tuple(outcome_rows)
    failures = tuple(failure_rows)
    if any(not isinstance(value, E20OutcomeRow) for value in outcomes):
        raise TypeError("outcome_rows must contain E20OutcomeRow values")
    if any(not isinstance(value, E20FailureRow) for value in failures):
        raise TypeError("failure_rows must contain E20FailureRow values")
    conditions = {value.condition_id: value for value in condition_plan.conditions}
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    bundle_by_hash = {value.bundle_hash: value for value in preregistration.calibration_bundles}
    expected_keys: set[tuple[str, str]] = set()
    for sample in corpus_manifest.samples:
        for condition_id in _compatible_condition_ids(
            preregistration,
            condition_plan,
            sample.watermark.watermark_config_hash,
        ):
            expected_keys.add((sample.sample_id, condition_id))
    observed_rows = (*outcomes, *failures)
    observed_keys = tuple(_row_key(value) for value in observed_rows)
    if len(set(observed_keys)) != len(observed_keys):
        raise E20ResultBundleError("E20 result bundle contains duplicate sample and condition rows")
    observed_key_set = set(observed_keys)
    missing = expected_keys - observed_key_set
    extra = observed_key_set - expected_keys
    if missing or extra:
        raise E20ResultBundleError(f"E20 result coverage mismatch: missing={len(missing)} extra={len(extra)}")
    for row in observed_rows:
        sample = sample_by_id[row.identity.sample_id]
        condition = conditions[row.identity.condition_id]
        _verify_common_row_binding(row, authorization, sample)
        if row.identity.condition_id not in _compatible_condition_ids(
            preregistration,
            condition_plan,
            sample.watermark.watermark_config_hash,
        ):
            raise E20ResultBundleError("E20 row evaluation condition is incompatible with the source generation track")
        if isinstance(row, E20FailureRow):
            _verify_failure_row_binding(row, sample, condition)
        else:
            bundle = bundle_by_hash.get(condition.calibration_bundle_hash)
            if bundle is None:
                raise E20ResultBundleError("E20 condition references a calibration bundle outside preregistration")
            _verify_outcome_row_binding(
                row,
                authorization,
                preregistration,
                corpus_manifest,
                sample,
                condition,
                bundle,
            )
    ordered_outcomes = tuple(sorted(outcomes, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
    ordered_failures = tuple(sorted(failures, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash)))
    _verify_shared_transforms(ordered_outcomes, condition_plan)
    counts: Counter[ExperimentReasonCode] = Counter()
    for row in ordered_outcomes:
        counts[row.fidelity.reason_codes[0]] += 1
    for row in ordered_failures:
        counts[row.reason_code] += 1
    reason_counts = tuple(E20ReasonCount(reason, counts[reason]) for reason in ExperimentReasonCode)
    payload = {
        "algorithm_version": E20_RESULT_BUNDLE_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "authorization_hash": authorization.authorization_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "outcome_rows": ordered_outcomes,
        "failure_rows": ordered_failures,
        "reason_counts": reason_counts,
        "expected_row_count": len(expected_keys),
        "observed_row_count": len(observed_rows),
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
        len(expected_keys),
        len(observed_rows),
        len(ordered_outcomes),
        len(ordered_failures),
        sha256_json(payload),
    )


def verify_e20_result_bundle(
    bundle: E20ResultBundle,
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(bundle, E20ResultBundle):
        raise TypeError("bundle must be an E20ResultBundle")
    expected = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        bundle.outcome_rows,
        bundle.failure_rows,
    )
    if bundle != expected:
        raise E20ResultBundleError("E20 result bundle does not replay exactly from its sealed rows and execution inputs")
