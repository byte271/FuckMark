from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusManifest
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .e20_bundle import E20ReasonCount, _compatible_condition_ids, _verify_shared_transforms
from .e20_conditions import E20ConditionPlan
from .e20_rows import ExperimentReasonCode
from .e21_execution import E21RunLedger, E21RunState, verify_e21_run_ledger
from .e21_rerun import E21ExecutionAuthorization
from .e21_rows import E21FailureRow, E21OutcomeRow
from .e21_seed import derive_e21_condition_seed


E21_RESULT_BUNDLE_ALGORITHM_VERSION = "e21-result-bundle-v1"


class E21ResultBundleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E21ResultBundle:
    algorithm_version: str
    execution_id: str
    authorization_hash: str
    corpus_manifest_hash: str
    condition_plan_hash: str
    started_ledger_hash: str
    outcome_rows: tuple[E21OutcomeRow, ...]
    failure_rows: tuple[E21FailureRow, ...]
    reason_counts: tuple[E20ReasonCount, ...]
    expected_row_count: int
    observed_row_count: int
    outcome_row_count: int
    failure_row_count: int
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_RESULT_BUNDLE_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 result bundle algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("authorization_hash", self.authorization_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("condition_plan_hash", self.condition_plan_hash),
            ("started_ledger_hash", self.started_ledger_hash),
            ("bundle_hash", self.bundle_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.outcome_rows, tuple) or any(
            not isinstance(value, E21OutcomeRow) for value in self.outcome_rows
        ):
            raise TypeError("outcome_rows must be a tuple of E21OutcomeRow values")
        if not isinstance(self.failure_rows, tuple) or any(
            not isinstance(value, E21FailureRow) for value in self.failure_rows
        ):
            raise TypeError("failure_rows must be a tuple of E21FailureRow values")
        if self.outcome_rows != tuple(sorted(
            self.outcome_rows,
            key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash),
        )):
            raise ValueError("E21 outcome rows must be canonically ordered")
        if self.failure_rows != tuple(sorted(
            self.failure_rows,
            key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash),
        )):
            raise ValueError("E21 failure rows must be canonically ordered")
        hashes = tuple(value.row_hash for value in (*self.outcome_rows, *self.failure_rows))
        if len(set(hashes)) != len(hashes):
            raise ValueError("E21 result row hashes must be unique")
        if tuple(value.reason_code for value in self.reason_counts) != tuple(ExperimentReasonCode):
            raise ValueError("reason_counts must contain every frozen reason code exactly once")
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
            raise ValueError("observed_row_count does not match E21 result rows")
        if self.outcome_row_count != len(self.outcome_rows):
            raise ValueError("outcome_row_count does not match E21 outcome rows")
        if self.failure_row_count != len(self.failure_rows):
            raise ValueError("failure_row_count does not match E21 failure rows")
        if self.expected_row_count != self.observed_row_count:
            raise ValueError("sealed E21 result bundle must contain every expected row")
        if sum(value.count for value in self.reason_counts) != self.observed_row_count:
            raise ValueError("E21 reason counts do not sum to observed row count")
        counts: Counter[ExperimentReasonCode] = Counter()
        for row in self.outcome_rows:
            counts[row.fidelity.reason_codes[0]] += 1
        for row in self.failure_rows:
            counts[row.reason_code] += 1
        if tuple(value.count for value in self.reason_counts) != tuple(
            counts[value] for value in ExperimentReasonCode
        ):
            raise ValueError("reason_counts do not replay from E21 result rows")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E21 result bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "authorization_hash": self.authorization_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "condition_plan_hash": self.condition_plan_hash,
            "started_ledger_hash": self.started_ledger_hash,
            "outcome_rows": self.outcome_rows,
            "failure_rows": self.failure_rows,
            "reason_counts": self.reason_counts,
            "expected_row_count": self.expected_row_count,
            "observed_row_count": self.observed_row_count,
            "outcome_row_count": self.outcome_row_count,
            "failure_row_count": self.failure_row_count,
        }


def _row_key(row: E21OutcomeRow | E21FailureRow) -> tuple[str, str]:
    return row.identity.sample_id, row.identity.condition_id


def _verify_common_row_binding(
    row: E21OutcomeRow | E21FailureRow,
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
    sample,
) -> None:
    if row.identity.execution_id != authorization.execution_id or row.identity.run_id != authorization.execution_id:
        raise E21ResultBundleError("E21 result row belongs to a different sealed execution")
    if row.identity.pair_id != sample.match_id:
        raise E21ResultBundleError("E21 result row pair identity does not match the sealed rerun corpus")
    if row.audit.authorization_hash != authorization.authorization_hash:
        raise E21ResultBundleError("E21 row audit authorization does not match the sealed execution")
    if row.audit.environment_snapshot_hash != authorization.environment_snapshot_hash:
        raise E21ResultBundleError("E21 row audit environment does not match the sealed execution")
    if row.audit.worker_version != authorization.worker_version:
        raise E21ResultBundleError("E21 row audit worker version does not match the sealed execution")
    if row.audit.ledger_hash != ledger.ledger_hash:
        raise E21ResultBundleError("E21 row audit ledger does not match the started run ledger")
    if sample.record_hash not in row.audit.artifact_hashes:
        raise E21ResultBundleError("E21 row audit artifacts do not bind the sealed source sample")


def _verify_failure_row_binding(row: E21FailureRow, sample, condition) -> None:
    if row.source_sample_record_hash != sample.record_hash:
        raise E21ResultBundleError("E21 failure row source hash does not match the sealed rerun sample")
    if row.detail_hash not in row.audit.artifact_hashes:
        raise E21ResultBundleError("E21 failure row audit artifacts do not bind failure detail")
    if condition.condition_hash not in row.audit.artifact_hashes:
        raise E21ResultBundleError("E21 failure row audit artifacts do not bind the frozen condition")


def _verify_outcome_row_binding(
    row: E21OutcomeRow,
    authorization: E21ExecutionAuthorization,
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
        raise E21ResultBundleError("E21 outcome source adapter does not match the frozen generation track")
    if (
        row.model.model_id != sample.model.model_id
        or row.model.model_revision != sample.model.model_revision
        or row.model.tokenizer_id != sample.model.tokenizer_id
        or row.model.tokenizer_revision != sample.model.tokenizer_revision
    ):
        raise E21ResultBundleError("E21 outcome model/tokenizer does not match the sealed rerun sample")
    if (
        row.watermark.watermark_config_hash != sample.watermark.watermark_config_hash
        or row.watermark.key_split is not sample.watermark.key_split
        or row.watermark.key_id != sample.watermark.key_id
    ):
        raise E21ResultBundleError("E21 outcome watermark identity does not match the sealed rerun sample")
    if (
        row.generation.seed != sample.generation.seed
        or row.generation.temperature != sample.generation.temperature
        or row.generation.top_k != sample.generation.top_k
        or row.generation.top_p != sample.generation.top_p
        or row.generation.realized_length != sample.generation_realized_length
    ):
        raise E21ResultBundleError("E21 outcome generation parameters do not match the sealed rerun sample")
    if row.text.source_text_hash != sample.text_sha256:
        raise E21ResultBundleError("E21 outcome source text hash does not match the sealed rerun sample")
    if row.text.source_char_count != len(sample.text):
        raise E21ResultBundleError("E21 outcome source character count does not match the sealed rerun sample")
    if row.text.source_token_count != len(sample.generation_tokens.continuation_token_ids):
        raise E21ResultBundleError("E21 outcome source token count does not match the sealed rerun sample")
    if row.transform.ruleset_hash != preregistration.transform_ruleset_hash:
        raise E21ResultBundleError("E21 outcome transform ruleset changed from preregistration")
    expected_seed = derive_e21_condition_seed(
        authorization,
        corpus_manifest,
        sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
    if row.transform.schedule_seed != expected_seed:
        raise E21ResultBundleError("E21 outcome schedule seed does not match sealed deterministic derivation")
    identity = bundle.detector_identity
    if row.detector.detector_family is not identity.detector_family:
        raise E21ResultBundleError("E21 detector family does not match the frozen calibration identity")
    if row.detector.detector_config_hash != identity.detector_config_hash:
        raise E21ResultBundleError("E21 detector configuration does not match the frozen calibration identity")
    if row.gvalues.depth != identity.depth:
        raise E21ResultBundleError("E21 g-value depth does not match the frozen detector identity")
    thresholds = tuple(value for value in bundle.thresholds if value.target_fpr == condition.target_fpr)
    if len(thresholds) != 1:
        raise E21ResultBundleError("E21 condition does not resolve to one frozen calibration threshold")
    threshold = thresholds[0]
    if row.detector.calibration_bundle_hash != bundle.bundle_hash:
        raise E21ResultBundleError("E21 detector bundle does not match the frozen evaluation condition")
    if row.detector.target_fpr != condition.target_fpr:
        raise E21ResultBundleError("E21 target FPR changed from the frozen evaluation condition")
    if row.detector.threshold_hash != threshold.threshold_hash:
        raise E21ResultBundleError("E21 threshold hash does not match the frozen calibration threshold")
    if row.detector.threshold_value != threshold.value:
        raise E21ResultBundleError("E21 threshold value does not match the frozen calibration threshold")
    if row.detector.comparison_operator is not threshold.comparison_operator:
        raise E21ResultBundleError("E21 comparison operator does not match frozen threshold semantics")
    if row.detector.robust_scale != bundle.robust_scale:
        raise E21ResultBundleError("E21 robust scale does not match the frozen calibration bundle")
    if row.transform.schedule_policy is not condition.schedule_policy:
        raise E21ResultBundleError("E21 schedule policy changed from the frozen transform condition")
    if row.transform.budget != condition.budget or row.transform.budget_unit != condition.budget_unit:
        raise E21ResultBundleError("E21 budget changed from the frozen transform condition")
    if row.statistics.hypothesis_class != condition.hypothesis_class:
        raise E21ResultBundleError("E21 hypothesis class changed from the frozen evaluation condition")
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
        raise E21ResultBundleError("E21 statistical stratum does not match sealed sample and detector inputs")
    if row.statistics.bootstrap_group != sample.sample_id:
        raise E21ResultBundleError("E21 bootstrap group does not match the sealed rerun sample")


def build_e21_result_bundle(
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    outcome_rows: Sequence[E21OutcomeRow],
    failure_rows: Sequence[E21FailureRow],
) -> E21ResultBundle:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    verify_e21_run_ledger(ledger, authorization)
    if ledger.state is not E21RunState.STARTED:
        raise E21ResultBundleError("E21 result bundle can be built only from a STARTED run")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if authorization.preregistration_hash != preregistration.preregistration_hash:
        raise E21ResultBundleError("preregistration does not match E21 authorization")
    if authorization.e21_corpus_manifest_hash != corpus_manifest.manifest_hash:
        raise E21ResultBundleError("corpus manifest does not match E21 authorization")
    if condition_plan.plan_hash != preregistration.budget_config_hash:
        raise E21ResultBundleError("condition plan changed from the preregistered budget configuration")
    outcomes = tuple(outcome_rows)
    failures = tuple(failure_rows)
    if any(not isinstance(value, E21OutcomeRow) for value in outcomes):
        raise TypeError("outcome_rows must contain E21OutcomeRow values")
    if any(not isinstance(value, E21FailureRow) for value in failures):
        raise TypeError("failure_rows must contain E21FailureRow values")
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
        raise E21ResultBundleError("E21 result bundle contains duplicate sample and condition rows")
    missing = expected_keys - set(observed_keys)
    extra = set(observed_keys) - expected_keys
    if missing or extra:
        raise E21ResultBundleError(f"E21 result coverage mismatch: missing={len(missing)} extra={len(extra)}")
    for row in observed_rows:
        sample = sample_by_id[row.identity.sample_id]
        condition = conditions[row.identity.condition_id]
        _verify_common_row_binding(row, authorization, ledger, sample)
        if row.identity.condition_id not in _compatible_condition_ids(
            preregistration,
            condition_plan,
            sample.watermark.watermark_config_hash,
        ):
            raise E21ResultBundleError("E21 evaluation condition is incompatible with the generation track")
        if isinstance(row, E21FailureRow):
            _verify_failure_row_binding(row, sample, condition)
        else:
            bundle = bundle_by_hash.get(condition.calibration_bundle_hash)
            if bundle is None:
                raise E21ResultBundleError("E21 condition references calibration outside preregistration")
            _verify_outcome_row_binding(
                row,
                authorization,
                preregistration,
                corpus_manifest,
                sample,
                condition,
                bundle,
            )
    ordered_outcomes = tuple(sorted(
        outcomes,
        key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash),
    ))
    ordered_failures = tuple(sorted(
        failures,
        key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash),
    ))
    _verify_shared_transforms(ordered_outcomes, condition_plan)
    counts: Counter[ExperimentReasonCode] = Counter()
    for row in ordered_outcomes:
        counts[row.fidelity.reason_codes[0]] += 1
    for row in ordered_failures:
        counts[row.reason_code] += 1
    reason_counts = tuple(E20ReasonCount(reason, counts[reason]) for reason in ExperimentReasonCode)
    payload = {
        "algorithm_version": E21_RESULT_BUNDLE_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "authorization_hash": authorization.authorization_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "started_ledger_hash": ledger.ledger_hash,
        "outcome_rows": ordered_outcomes,
        "failure_rows": ordered_failures,
        "reason_counts": reason_counts,
        "expected_row_count": len(expected_keys),
        "observed_row_count": len(observed_rows),
        "outcome_row_count": len(ordered_outcomes),
        "failure_row_count": len(ordered_failures),
    }
    return E21ResultBundle(
        E21_RESULT_BUNDLE_ALGORITHM_VERSION,
        authorization.execution_id,
        authorization.authorization_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        ledger.ledger_hash,
        ordered_outcomes,
        ordered_failures,
        reason_counts,
        len(expected_keys),
        len(observed_rows),
        len(ordered_outcomes),
        len(ordered_failures),
        sha256_json(payload),
    )


def verify_e21_result_bundle(
    bundle: E21ResultBundle,
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(bundle, E21ResultBundle):
        raise TypeError("bundle must be an E21ResultBundle")
    expected = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        corpus_manifest,
        condition_plan,
        bundle.outcome_rows,
        bundle.failure_rows,
    )
    if bundle != expected:
        raise E21ResultBundleError("E21 result bundle does not replay exactly from sealed rows and execution inputs")
