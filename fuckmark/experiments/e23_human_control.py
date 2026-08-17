from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain
from ..corpus.schema import require_exact_text
from ..detectors import CalibratedDetectorResult, CalibrationBundle, DetectorCalibrationIdentity, ExactBinomialInterval, UncalibratedDetectorEvidence, apply_calibration, exact_binomial_interval
from ..hashing import sha256_json, sha256_text
from ..transforms import CandidateScheduler, KeyBlindScheduleInput, SchedulePolicy, TransformRegistry
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20Condition, E20ConditionPlan, verify_e20_condition_plan


E23_HUMAN_CONTROL_CORPUS_ALGORITHM_VERSION = "e23-human-control-corpus-v1"
E23_TRANSFORM_BUNDLE_ALGORITHM_VERSION = "e23-human-transform-bundle-v1"
E23_DETECTOR_PAIR_ALGORITHM_VERSION = "e23-human-detector-pair-v1"
E23_REPORT_ALGORITHM_VERSION = "e23-human-control-stress-v1"


class E23LicenseStatus(str, Enum):
    VERIFIED_DERIVATIVE_USE_ALLOWED = "VERIFIED_DERIVATIVE_USE_ALLOWED"
    UNVERIFIED = "UNVERIFIED"
    DISALLOWED = "DISALLOWED"


class E23AuthorshipStatus(str, Enum):
    VERIFIED_HUMAN = "VERIFIED_HUMAN"
    UNKNOWN = "UNKNOWN"
    MODEL_ASSISTED = "MODEL_ASSISTED"


class E23FidelityStatus(str, Enum):
    PASS = "PASS"
    MATERIAL_CHANGE = "MATERIAL_CHANGE"
    CANNOT_JUDGE = "CANNOT_JUDGE"


class E23CellStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    NO_FIDELITY_PASS_ROWS = "NO_FIDELITY_PASS_ROWS"


class E23ReportStatus(str, Enum):
    COMPLETE = "COMPLETE"
    NO_ESTIMATE = "NO_ESTIMATE"


def _probability(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


def _finite(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _seed(manifest_hash: str, sample_id: str, transform_condition_id: str, ruleset_hash: str) -> int:
    require_sha256("manifest_hash", manifest_hash)
    require_clean_string("sample_id", sample_id)
    require_clean_string("transform_condition_id", transform_condition_id)
    require_sha256("ruleset_hash", ruleset_hash)
    return int(sha256_json({"algorithm_version": E23_TRANSFORM_BUNDLE_ALGORITHM_VERSION, "purpose": "schedule-seed", "manifest_hash": manifest_hash, "sample_id": sample_id, "transform_condition_id": transform_condition_id, "ruleset_hash": ruleset_hash})[:16], 16)


@dataclass(frozen=True, slots=True)
class E23HumanControlSample:
    sample_id: str
    domain: CorpusDomain
    language: str
    source_id: str
    source_revision_hash: str
    source_content_hash: str
    license_id: str
    license_evidence_hash: str
    license_status: E23LicenseStatus
    authorship_evidence_hash: str
    authorship_status: E23AuthorshipStatus
    provenance_hash: str
    text: str
    text_sha256: str
    record_hash: str

    def __post_init__(self) -> None:
        for name, value in (("sample_id", self.sample_id), ("language", self.language), ("source_id", self.source_id), ("license_id", self.license_id)):
            require_clean_string(name, value)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        if self.language != "en":
            raise ValueError("E23 human controls must use the frozen English language scope")
        for name, value in (("source_revision_hash", self.source_revision_hash), ("source_content_hash", self.source_content_hash), ("license_evidence_hash", self.license_evidence_hash), ("authorship_evidence_hash", self.authorship_evidence_hash), ("provenance_hash", self.provenance_hash), ("text_sha256", self.text_sha256), ("record_hash", self.record_hash)):
            require_sha256(name, value)
        if not isinstance(self.license_status, E23LicenseStatus):
            raise TypeError("license_status must be an E23LicenseStatus")
        if not isinstance(self.authorship_status, E23AuthorshipStatus):
            raise TypeError("authorship_status must be an E23AuthorshipStatus")
        require_exact_text("text", self.text)
        if self.text_sha256 != sha256_text(self.text):
            raise ValueError("text_sha256 does not match exact human-control text")
        provenance = {"sample_id": self.sample_id, "source_id": self.source_id, "source_revision_hash": self.source_revision_hash, "source_content_hash": self.source_content_hash, "license_id": self.license_id, "license_evidence_hash": self.license_evidence_hash, "license_status": self.license_status.value, "authorship_evidence_hash": self.authorship_evidence_hash, "authorship_status": self.authorship_status.value, "text_sha256": self.text_sha256}
        if self.provenance_hash != sha256_json(provenance):
            raise ValueError("provenance_hash does not match human-control provenance")
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match E23 human-control sample")

    def _payload(self) -> dict[str, object]:
        return {"sample_id": self.sample_id, "domain": self.domain.value, "language": self.language, "source_id": self.source_id, "source_revision_hash": self.source_revision_hash, "source_content_hash": self.source_content_hash, "license_id": self.license_id, "license_evidence_hash": self.license_evidence_hash, "license_status": self.license_status.value, "authorship_evidence_hash": self.authorship_evidence_hash, "authorship_status": self.authorship_status.value, "provenance_hash": self.provenance_hash, "text": self.text, "text_sha256": self.text_sha256}

    @classmethod
    def create(cls, sample_id: str, domain: CorpusDomain, source_id: str, source_revision_hash: str, source_content_hash: str, license_id: str, license_evidence_hash: str, license_status: E23LicenseStatus, authorship_evidence_hash: str, authorship_status: E23AuthorshipStatus, text: str, language: str = "en") -> E23HumanControlSample:
        require_exact_text("text", text)
        text_hash = sha256_text(text)
        license_value = license_status.value if isinstance(license_status, E23LicenseStatus) else license_status
        authorship_value = authorship_status.value if isinstance(authorship_status, E23AuthorshipStatus) else authorship_status
        provenance = {"sample_id": sample_id, "source_id": source_id, "source_revision_hash": source_revision_hash, "source_content_hash": source_content_hash, "license_id": license_id, "license_evidence_hash": license_evidence_hash, "license_status": license_value, "authorship_evidence_hash": authorship_evidence_hash, "authorship_status": authorship_value, "text_sha256": text_hash}
        provenance_hash = sha256_json(provenance)
        payload = {"sample_id": sample_id, "domain": domain.value if isinstance(domain, CorpusDomain) else domain, "language": language, "source_id": source_id, "source_revision_hash": source_revision_hash, "source_content_hash": source_content_hash, "license_id": license_id, "license_evidence_hash": license_evidence_hash, "license_status": license_value, "authorship_evidence_hash": authorship_evidence_hash, "authorship_status": authorship_value, "provenance_hash": provenance_hash, "text": text, "text_sha256": text_hash}
        return cls(sample_id, domain, language, source_id, source_revision_hash, source_content_hash, license_id, license_evidence_hash, license_status, authorship_evidence_hash, authorship_status, provenance_hash, text, text_hash, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class E23HumanControlManifest:
    algorithm_version: str
    corpus_id: str
    samples: tuple[E23HumanControlSample, ...]
    sample_manifest_hash: str
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E23_HUMAN_CONTROL_CORPUS_ALGORITHM_VERSION:
            raise ValueError("unsupported E23 human-control corpus algorithm version")
        require_clean_string("corpus_id", self.corpus_id)
        if not isinstance(self.samples, tuple) or not self.samples or any(not isinstance(value, E23HumanControlSample) for value in self.samples):
            raise TypeError("samples must be a non-empty tuple of E23HumanControlSample values")
        if self.samples != tuple(sorted(self.samples, key=lambda value: value.sample_id)):
            raise ValueError("E23 human-control samples must use canonical sample_id ordering")
        if len({value.sample_id for value in self.samples}) != len(self.samples) or len({value.text_sha256 for value in self.samples}) != len(self.samples):
            raise ValueError("E23 human-control samples must have unique IDs and deduplicated texts")
        if any(value.license_status is not E23LicenseStatus.VERIFIED_DERIVATIVE_USE_ALLOWED for value in self.samples):
            raise ValueError("E23 human-control manifest requires verified derivative-use permission for every sample")
        if any(value.authorship_status is not E23AuthorshipStatus.VERIFIED_HUMAN for value in self.samples):
            raise ValueError("E23 human-control manifest requires verified human authorship for every sample")
        require_sha256("sample_manifest_hash", self.sample_manifest_hash)
        require_sha256("manifest_hash", self.manifest_hash)
        if self.sample_manifest_hash != sha256_json(tuple(value.record_hash for value in self.samples)):
            raise ValueError("sample_manifest_hash does not match E23 human-control samples")
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match E23 human-control manifest")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": self.algorithm_version, "corpus_id": self.corpus_id, "samples": self.samples, "sample_manifest_hash": self.sample_manifest_hash}


def build_e23_human_control_manifest(corpus_id: str, samples: Sequence[E23HumanControlSample]) -> E23HumanControlManifest:
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes, bytearray)):
        raise TypeError("samples must be a sequence")
    values = tuple(samples)
    if not values:
        raise ValueError("samples must not be empty")
    if any(not isinstance(value, E23HumanControlSample) for value in values):
        raise TypeError("samples must contain E23HumanControlSample values")
    ordered = tuple(sorted(values, key=lambda value: value.sample_id))
    sample_hash = sha256_json(tuple(value.record_hash for value in ordered))
    payload = {"algorithm_version": E23_HUMAN_CONTROL_CORPUS_ALGORITHM_VERSION, "corpus_id": corpus_id, "samples": ordered, "sample_manifest_hash": sample_hash}
    return E23HumanControlManifest(E23_HUMAN_CONTROL_CORPUS_ALGORITHM_VERSION, corpus_id, ordered, sample_hash, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class E23TransformRecord:
    sample_id: str
    source_record_hash: str
    transform_condition_id: str
    schedule_policy: SchedulePolicy
    schedule_seed: int
    budget: int
    budget_unit: str
    ruleset_hash: str
    enumeration_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    trace_hash: str
    hard_invariant_report_hash: str
    selected_candidate_ids: tuple[str, ...]
    realized_edit_cost: int
    source_text_hash: str
    transformed_text: str
    transformed_text_hash: str
    transform_hash: str

    def __post_init__(self) -> None:
        for name, value in (("sample_id", self.sample_id), ("transform_condition_id", self.transform_condition_id), ("budget_unit", self.budget_unit)):
            require_clean_string(name, value)
        if not isinstance(self.schedule_policy, SchedulePolicy):
            raise TypeError("schedule_policy must be a SchedulePolicy")
        for name, value in (("schedule_seed", self.schedule_seed), ("budget", self.budget), ("realized_edit_cost", self.realized_edit_cost)):
            require_int(name, value)
        if self.schedule_seed < 0 or self.schedule_seed >= 1 << 64 or self.budget < 0 or not 0 <= self.realized_edit_cost <= self.budget:
            raise ValueError("invalid E23 schedule seed or edit-cost geometry")
        for name, value in (("source_record_hash", self.source_record_hash), ("ruleset_hash", self.ruleset_hash), ("enumeration_hash", self.enumeration_hash), ("scheduler_input_hash", self.scheduler_input_hash), ("schedule_result_hash", self.schedule_result_hash), ("trace_hash", self.trace_hash), ("hard_invariant_report_hash", self.hard_invariant_report_hash), ("source_text_hash", self.source_text_hash), ("transformed_text_hash", self.transformed_text_hash), ("transform_hash", self.transform_hash)):
            require_sha256(name, value)
        if not isinstance(self.selected_candidate_ids, tuple) or len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_ids must be a unique tuple")
        for value in self.selected_candidate_ids:
            require_sha256("selected candidate ID", value)
        require_exact_text("transformed_text", self.transformed_text)
        if self.transformed_text_hash != sha256_text(self.transformed_text) or self.transform_hash != sha256_json(self._payload()):
            raise ValueError("E23 transformed text or transform hash does not replay")

    def _payload(self) -> dict[str, object]:
        return {"sample_id": self.sample_id, "source_record_hash": self.source_record_hash, "transform_condition_id": self.transform_condition_id, "schedule_policy": self.schedule_policy.value, "schedule_seed": self.schedule_seed, "budget": self.budget, "budget_unit": self.budget_unit, "ruleset_hash": self.ruleset_hash, "enumeration_hash": self.enumeration_hash, "scheduler_input_hash": self.scheduler_input_hash, "schedule_result_hash": self.schedule_result_hash, "trace_hash": self.trace_hash, "hard_invariant_report_hash": self.hard_invariant_report_hash, "selected_candidate_ids": self.selected_candidate_ids, "realized_edit_cost": self.realized_edit_cost, "source_text_hash": self.source_text_hash, "transformed_text": self.transformed_text, "transformed_text_hash": self.transformed_text_hash}


@dataclass(frozen=True, slots=True)
class E23TransformBundle:
    algorithm_version: str
    manifest_hash: str
    preregistration_hash: str
    condition_plan_hash: str
    ruleset_hash: str
    records: tuple[E23TransformRecord, ...]
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E23_TRANSFORM_BUNDLE_ALGORITHM_VERSION:
            raise ValueError("unsupported E23 transform-bundle algorithm version")
        for name, value in (("manifest_hash", self.manifest_hash), ("preregistration_hash", self.preregistration_hash), ("condition_plan_hash", self.condition_plan_hash), ("ruleset_hash", self.ruleset_hash), ("bundle_hash", self.bundle_hash)):
            require_sha256(name, value)
        if not isinstance(self.records, tuple) or not self.records or any(not isinstance(value, E23TransformRecord) for value in self.records):
            raise TypeError("records must be a non-empty tuple of E23TransformRecord values")
        if self.records != tuple(sorted(self.records, key=lambda value: (value.sample_id, value.transform_condition_id))):
            raise ValueError("E23 transform records must use canonical ordering")
        if len({(value.sample_id, value.transform_condition_id) for value in self.records}) != len(self.records):
            raise ValueError("E23 transform records must be unique by sample and transform condition")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E23 transform bundle")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": self.algorithm_version, "manifest_hash": self.manifest_hash, "preregistration_hash": self.preregistration_hash, "condition_plan_hash": self.condition_plan_hash, "ruleset_hash": self.ruleset_hash, "records": self.records}

    def record_for(self, sample_id: str, transform_condition_id: str) -> E23TransformRecord:
        for value in self.records:
            if value.sample_id == sample_id and value.transform_condition_id == transform_condition_id:
                return value
        raise KeyError((sample_id, transform_condition_id))


def _transform_conditions(condition_plan: E20ConditionPlan) -> tuple[E20Condition, ...]:
    rows: dict[str, E20Condition] = {}
    for condition in condition_plan.conditions:
        prior = rows.setdefault(condition.transform_condition_id, condition)
        if (prior.schedule_policy, prior.budget, prior.budget_unit) != (condition.schedule_policy, condition.budget, condition.budget_unit):
            raise ValueError("E23 transform condition semantics are inconsistent")
    return tuple(sorted(rows.values(), key=lambda value: value.transform_condition_id))


def build_e23_transform_bundle(manifest: E23HumanControlManifest, preregistration: ConfirmatoryPreregistration, condition_plan: E20ConditionPlan, registry: TransformRegistry, schedule_inputs: Mapping[tuple[str, str], KeyBlindScheduleInput]) -> E23TransformBundle:
    if not isinstance(manifest, E23HumanControlManifest) or not isinstance(preregistration, ConfirmatoryPreregistration) or not isinstance(condition_plan, E20ConditionPlan) or not isinstance(registry, TransformRegistry):
        raise TypeError("E23 transform inputs have invalid types")
    verify_e20_condition_plan(condition_plan, preregistration)
    if registry.ruleset_hash != preregistration.transform_ruleset_hash:
        raise ValueError("E23 transform registry does not match the frozen preregistration ruleset")
    if not isinstance(schedule_inputs, Mapping):
        raise TypeError("schedule_inputs must be a mapping")
    transform_conditions = _transform_conditions(condition_plan)
    expected = {(sample.sample_id, condition.transform_condition_id) for sample in manifest.samples for condition in transform_conditions}
    if set(schedule_inputs) != expected:
        raise ValueError(f"E23 scheduler-input coverage mismatch: missing={len(expected - set(schedule_inputs))} extra={len(set(schedule_inputs) - expected)}")
    scheduler = CandidateScheduler()
    records = []
    for sample in manifest.samples:
        enumeration = registry.enumerate(sample.text)
        for condition in transform_conditions:
            scheduler_input = schedule_inputs[(sample.sample_id, condition.transform_condition_id)]
            if not isinstance(scheduler_input, KeyBlindScheduleInput):
                raise TypeError("schedule_inputs values must be KeyBlindScheduleInput values")
            if scheduler_input.input_hash != sample.text_sha256 or scheduler_input.enumeration_hash != enumeration.enumeration_hash:
                raise ValueError("E23 scheduler input does not bind the current human-control enumeration")
            if scheduler_input.budget_unit != condition.budget_unit or scheduler_input.geometry_mode is not preregistration.schedule_geometry_mode:
                raise ValueError("E23 scheduler input does not match the frozen budget or geometry mode")
            if condition.budget_unit == "operation" and any(value.edit_cost != 1 for value in scheduler_input.candidates):
                raise ValueError("E23 operation budgets require unit candidate edit costs")
            seed = _seed(manifest.manifest_hash, sample.sample_id, condition.transform_condition_id, registry.ruleset_hash)
            schedule = scheduler.schedule(scheduler_input, condition.schedule_policy, condition.budget, seed)
            result = registry.apply(enumeration, schedule.selected_candidate_ids, seed)
            payload = {"sample_id": sample.sample_id, "source_record_hash": sample.record_hash, "transform_condition_id": condition.transform_condition_id, "schedule_policy": condition.schedule_policy.value, "schedule_seed": seed, "budget": condition.budget, "budget_unit": condition.budget_unit, "ruleset_hash": registry.ruleset_hash, "enumeration_hash": enumeration.enumeration_hash, "scheduler_input_hash": scheduler_input.input_artifact_hash, "schedule_result_hash": schedule.result_hash, "trace_hash": result.trace.trace_hash, "hard_invariant_report_hash": result.trace.invariant_report.report_hash, "selected_candidate_ids": schedule.selected_candidate_ids, "realized_edit_cost": schedule.total_cost, "source_text_hash": sample.text_sha256, "transformed_text": result.output_text, "transformed_text_hash": sha256_text(result.output_text)}
            records.append(E23TransformRecord(sample.sample_id, sample.record_hash, condition.transform_condition_id, condition.schedule_policy, seed, condition.budget, condition.budget_unit, registry.ruleset_hash, enumeration.enumeration_hash, scheduler_input.input_artifact_hash, schedule.result_hash, result.trace.trace_hash, result.trace.invariant_report.report_hash, schedule.selected_candidate_ids, schedule.total_cost, sample.text_sha256, result.output_text, sha256_text(result.output_text), sha256_json(payload)))
    ordered = tuple(sorted(records, key=lambda value: (value.sample_id, value.transform_condition_id)))
    payload = {"algorithm_version": E23_TRANSFORM_BUNDLE_ALGORITHM_VERSION, "manifest_hash": manifest.manifest_hash, "preregistration_hash": preregistration.preregistration_hash, "condition_plan_hash": condition_plan.plan_hash, "ruleset_hash": registry.ruleset_hash, "records": ordered}
    return E23TransformBundle(E23_TRANSFORM_BUNDLE_ALGORITHM_VERSION, manifest.manifest_hash, preregistration.preregistration_hash, condition_plan.plan_hash, registry.ruleset_hash, ordered, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class E23DetectorEvidencePair:
    algorithm_version: str
    sample_id: str
    condition_id: str
    source_record_hash: str
    transform_hash: str
    pristine_text_hash: str
    transformed_text_hash: str
    fidelity_status: E23FidelityStatus
    fidelity_evidence_hash: str
    pristine_evidence: UncalibratedDetectorEvidence
    transformed_evidence: UncalibratedDetectorEvidence
    pair_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E23_DETECTOR_PAIR_ALGORITHM_VERSION:
            raise ValueError("unsupported E23 detector-pair algorithm version")
        require_clean_string("sample_id", self.sample_id)
        require_clean_string("condition_id", self.condition_id)
        for name, value in (("source_record_hash", self.source_record_hash), ("transform_hash", self.transform_hash), ("pristine_text_hash", self.pristine_text_hash), ("transformed_text_hash", self.transformed_text_hash), ("fidelity_evidence_hash", self.fidelity_evidence_hash), ("pair_hash", self.pair_hash)):
            require_sha256(name, value)
        if not isinstance(self.fidelity_status, E23FidelityStatus):
            raise TypeError("fidelity_status must be an E23FidelityStatus")
        if not isinstance(self.pristine_evidence, UncalibratedDetectorEvidence) or not isinstance(self.transformed_evidence, UncalibratedDetectorEvidence):
            raise TypeError("E23 detector pairs require uncalibrated detector evidence")
        if self.pristine_evidence.sample_id != self.sample_id or self.transformed_evidence.sample_id != self.sample_id:
            raise ValueError("E23 detector evidence sample IDs must match the human-control sample")
        if DetectorCalibrationIdentity.from_evidence(self.pristine_evidence) != DetectorCalibrationIdentity.from_evidence(self.transformed_evidence):
            raise ValueError("E23 pristine and transformed detector evidence must use the same detector identity")
        if self.pair_hash != sha256_json(self._payload()):
            raise ValueError("pair_hash does not match E23 detector evidence pair")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": self.algorithm_version, "sample_id": self.sample_id, "condition_id": self.condition_id, "source_record_hash": self.source_record_hash, "transform_hash": self.transform_hash, "pristine_text_hash": self.pristine_text_hash, "transformed_text_hash": self.transformed_text_hash, "fidelity_status": self.fidelity_status.value, "fidelity_evidence_hash": self.fidelity_evidence_hash, "pristine_evidence": self.pristine_evidence, "transformed_evidence": self.transformed_evidence}

    @classmethod
    def create(cls, sample_id: str, condition_id: str, source_record_hash: str, transform_hash: str, pristine_text_hash: str, transformed_text_hash: str, fidelity_status: E23FidelityStatus, fidelity_evidence_hash: str, pristine_evidence: UncalibratedDetectorEvidence, transformed_evidence: UncalibratedDetectorEvidence) -> E23DetectorEvidencePair:
        status = fidelity_status.value if isinstance(fidelity_status, E23FidelityStatus) else fidelity_status
        payload = {"algorithm_version": E23_DETECTOR_PAIR_ALGORITHM_VERSION, "sample_id": sample_id, "condition_id": condition_id, "source_record_hash": source_record_hash, "transform_hash": transform_hash, "pristine_text_hash": pristine_text_hash, "transformed_text_hash": transformed_text_hash, "fidelity_status": status, "fidelity_evidence_hash": fidelity_evidence_hash, "pristine_evidence": pristine_evidence, "transformed_evidence": transformed_evidence}
        return cls(E23_DETECTOR_PAIR_ALGORITHM_VERSION, sample_id, condition_id, source_record_hash, transform_hash, pristine_text_hash, transformed_text_hash, fidelity_status, fidelity_evidence_hash, pristine_evidence, transformed_evidence, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class E23EvaluationRow:
    sample_id: str
    condition_id: str
    transform_condition_id: str
    source_record_hash: str
    transform_hash: str
    fidelity_status: E23FidelityStatus
    fidelity_evidence_hash: str
    pristine: CalibratedDetectorResult
    transformed: CalibratedDetectorResult
    included: bool
    row_hash: str

    def __post_init__(self) -> None:
        for name, value in (("sample_id", self.sample_id), ("condition_id", self.condition_id), ("transform_condition_id", self.transform_condition_id)):
            require_clean_string(name, value)
        for name, value in (("source_record_hash", self.source_record_hash), ("transform_hash", self.transform_hash), ("fidelity_evidence_hash", self.fidelity_evidence_hash), ("row_hash", self.row_hash)):
            require_sha256(name, value)
        if not isinstance(self.fidelity_status, E23FidelityStatus) or not isinstance(self.pristine, CalibratedDetectorResult) or not isinstance(self.transformed, CalibratedDetectorResult):
            raise TypeError("E23 evaluation row has invalid evidence types")
        if self.pristine.sample_id != self.sample_id or self.transformed.sample_id != self.sample_id:
            raise ValueError("E23 calibrated result sample IDs must match evaluation row")
        if (self.pristine.detector_identity_hash, self.pristine.calibration_bundle_hash, self.pristine.threshold_hash, self.pristine.target_fpr) != (self.transformed.detector_identity_hash, self.transformed.calibration_bundle_hash, self.transformed.threshold_hash, self.transformed.target_fpr):
            raise ValueError("E23 pristine and transformed results must share one frozen operating point")
        if self.included is not (self.fidelity_status is E23FidelityStatus.PASS):
            raise ValueError("E23 included flag must follow the fidelity gate")
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E23 evaluation row")

    def _payload(self) -> dict[str, object]:
        return {"sample_id": self.sample_id, "condition_id": self.condition_id, "transform_condition_id": self.transform_condition_id, "source_record_hash": self.source_record_hash, "transform_hash": self.transform_hash, "fidelity_status": self.fidelity_status.value, "fidelity_evidence_hash": self.fidelity_evidence_hash, "pristine": self.pristine, "transformed": self.transformed, "included": self.included}


@dataclass(frozen=True, slots=True)
class E23ConditionSummary:
    condition_id: str
    transform_condition_id: str
    detector_identity_hash: str
    calibration_bundle_hash: str
    target_fpr: float
    total_count: int
    included_count: int
    material_change_count: int
    cannot_judge_count: int
    pristine_positive_count: int
    transformed_positive_count: int
    pristine_fpr: float | None
    transformed_fpr: float | None
    pristine_fpr_interval: ExactBinomialInterval | None
    transformed_fpr_interval: ExactBinomialInterval | None
    fpr_shift: float | None
    false_to_true_count: int
    true_to_false_count: int
    mean_raw_score_shift: float | None
    mean_standardized_margin_shift: float | None
    status: E23CellStatus
    summary_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        require_clean_string("transform_condition_id", self.transform_condition_id)
        require_sha256("detector_identity_hash", self.detector_identity_hash)
        require_sha256("calibration_bundle_hash", self.calibration_bundle_hash)
        target = _probability("target_fpr", self.target_fpr)
        if not 0.0 < target < 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        for name, value in (("total_count", self.total_count), ("included_count", self.included_count), ("material_change_count", self.material_change_count), ("cannot_judge_count", self.cannot_judge_count), ("pristine_positive_count", self.pristine_positive_count), ("transformed_positive_count", self.transformed_positive_count), ("false_to_true_count", self.false_to_true_count), ("true_to_false_count", self.true_to_false_count)):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.included_count + self.material_change_count + self.cannot_judge_count != self.total_count:
            raise ValueError("E23 fidelity accounting does not close")
        if self.pristine_positive_count > self.included_count or self.transformed_positive_count > self.included_count or self.false_to_true_count + self.true_to_false_count > self.included_count:
            raise ValueError("E23 detector counts exceed included rows")
        if not isinstance(self.status, E23CellStatus):
            raise TypeError("status must be an E23CellStatus")
        estimate_fields = (self.pristine_fpr, self.transformed_fpr, self.pristine_fpr_interval, self.transformed_fpr_interval, self.fpr_shift, self.mean_raw_score_shift, self.mean_standardized_margin_shift)
        if self.included_count == 0:
            if self.status is not E23CellStatus.NO_FIDELITY_PASS_ROWS or any(value is not None for value in estimate_fields) or self.pristine_positive_count or self.transformed_positive_count or self.false_to_true_count or self.true_to_false_count:
                raise ValueError("empty E23 condition summary has invalid estimates or status")
        else:
            if self.status is not E23CellStatus.ESTIMATED or any(value is None for value in estimate_fields):
                raise ValueError("estimated E23 condition summary requires every estimate")
            pristine = _probability("pristine_fpr", self.pristine_fpr)
            transformed = _probability("transformed_fpr", self.transformed_fpr)
            if not math.isclose(pristine, self.pristine_positive_count / self.included_count, rel_tol=0.0, abs_tol=1e-15) or not math.isclose(transformed, self.transformed_positive_count / self.included_count, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("E23 FPR rates do not match decision counts")
            if self.pristine_fpr_interval != exact_binomial_interval(self.pristine_positive_count, self.included_count, 0.95) or self.transformed_fpr_interval != exact_binomial_interval(self.transformed_positive_count, self.included_count, 0.95):
                raise ValueError("E23 FPR intervals must be exact 95% binomial intervals")
            shift = _finite("fpr_shift", self.fpr_shift)
            if not math.isclose(shift, transformed - pristine, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("E23 FPR shift does not match transformed minus pristine FPR")
            object.__setattr__(self, "pristine_fpr", pristine)
            object.__setattr__(self, "transformed_fpr", transformed)
            object.__setattr__(self, "fpr_shift", shift)
            object.__setattr__(self, "mean_raw_score_shift", _finite("mean_raw_score_shift", self.mean_raw_score_shift))
            object.__setattr__(self, "mean_standardized_margin_shift", _finite("mean_standardized_margin_shift", self.mean_standardized_margin_shift))
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self._payload()):
            raise ValueError("summary_hash does not match E23 condition summary")

    def _payload(self) -> dict[str, object]:
        return {"condition_id": self.condition_id, "transform_condition_id": self.transform_condition_id, "detector_identity_hash": self.detector_identity_hash, "calibration_bundle_hash": self.calibration_bundle_hash, "target_fpr": self.target_fpr, "total_count": self.total_count, "included_count": self.included_count, "material_change_count": self.material_change_count, "cannot_judge_count": self.cannot_judge_count, "pristine_positive_count": self.pristine_positive_count, "transformed_positive_count": self.transformed_positive_count, "pristine_fpr": self.pristine_fpr, "transformed_fpr": self.transformed_fpr, "pristine_fpr_interval": self.pristine_fpr_interval, "transformed_fpr_interval": self.transformed_fpr_interval, "fpr_shift": self.fpr_shift, "false_to_true_count": self.false_to_true_count, "true_to_false_count": self.true_to_false_count, "mean_raw_score_shift": self.mean_raw_score_shift, "mean_standardized_margin_shift": self.mean_standardized_margin_shift, "status": self.status.value}


@dataclass(frozen=True, slots=True)
class E23HumanControlReport:
    algorithm_version: str
    manifest_hash: str
    transform_bundle_hash: str
    condition_plan_hash: str
    preregistration_hash: str
    rows: tuple[E23EvaluationRow, ...]
    conditions: tuple[E23ConditionSummary, ...]
    maximum_positive_fpr_shift: float | None
    status: E23ReportStatus
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E23_REPORT_ALGORITHM_VERSION:
            raise ValueError("unsupported E23 report algorithm version")
        for name, value in (("manifest_hash", self.manifest_hash), ("transform_bundle_hash", self.transform_bundle_hash), ("condition_plan_hash", self.condition_plan_hash), ("preregistration_hash", self.preregistration_hash), ("report_hash", self.report_hash)):
            require_sha256(name, value)
        if not isinstance(self.rows, tuple) or any(not isinstance(value, E23EvaluationRow) for value in self.rows) or self.rows != tuple(sorted(self.rows, key=lambda value: (value.sample_id, value.condition_id))):
            raise ValueError("E23 evaluation rows must be a canonically ordered tuple")
        if len({(value.sample_id, value.condition_id) for value in self.rows}) != len(self.rows):
            raise ValueError("E23 evaluation rows must be unique by sample and condition")
        if not isinstance(self.conditions, tuple) or any(not isinstance(value, E23ConditionSummary) for value in self.conditions) or self.conditions != tuple(sorted(self.conditions, key=lambda value: value.condition_id)):
            raise ValueError("E23 condition summaries must be a canonically ordered tuple")
        positive = tuple(value.fpr_shift for value in self.conditions if value.fpr_shift is not None and value.fpr_shift > 0.0)
        expected_maximum = max(positive) if positive else None
        if expected_maximum is None:
            if self.maximum_positive_fpr_shift is not None:
                raise ValueError("maximum_positive_fpr_shift must be None without a positive FPR shift")
        elif self.maximum_positive_fpr_shift is None or not math.isclose(self.maximum_positive_fpr_shift, expected_maximum, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("maximum_positive_fpr_shift does not match E23 condition summaries")
        if not isinstance(self.status, E23ReportStatus):
            raise TypeError("status must be an E23ReportStatus")
        expected_status = E23ReportStatus.COMPLETE if any(value.status is E23CellStatus.ESTIMATED for value in self.conditions) else E23ReportStatus.NO_ESTIMATE
        if self.status is not expected_status or self.report_hash != sha256_json(self._payload()):
            raise ValueError("E23 report status or hash does not replay")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": self.algorithm_version, "manifest_hash": self.manifest_hash, "transform_bundle_hash": self.transform_bundle_hash, "condition_plan_hash": self.condition_plan_hash, "preregistration_hash": self.preregistration_hash, "rows": self.rows, "conditions": self.conditions, "maximum_positive_fpr_shift": self.maximum_positive_fpr_shift, "status": self.status.value}


def _evaluation_row(pair: E23DetectorEvidencePair, sample: E23HumanControlSample, transform: E23TransformRecord, condition: E20Condition, bundle: CalibrationBundle) -> E23EvaluationRow:
    if pair.source_record_hash != sample.record_hash or pair.transform_hash != transform.transform_hash or pair.pristine_text_hash != sample.text_sha256 or pair.transformed_text_hash != transform.transformed_text_hash:
        raise ValueError("E23 detector pair does not bind the expected source and transform")
    if condition.transform_condition_id != transform.transform_condition_id or condition.calibration_bundle_hash != bundle.bundle_hash:
        raise ValueError("E23 transform or calibration bundle does not match detector condition")
    pristine = apply_calibration(pair.pristine_evidence, bundle, condition.target_fpr)
    transformed = apply_calibration(pair.transformed_evidence, bundle, condition.target_fpr)
    included = pair.fidelity_status is E23FidelityStatus.PASS
    payload = {"sample_id": sample.sample_id, "condition_id": condition.condition_id, "transform_condition_id": condition.transform_condition_id, "source_record_hash": sample.record_hash, "transform_hash": transform.transform_hash, "fidelity_status": pair.fidelity_status.value, "fidelity_evidence_hash": pair.fidelity_evidence_hash, "pristine": pristine, "transformed": transformed, "included": included}
    return E23EvaluationRow(sample.sample_id, condition.condition_id, condition.transform_condition_id, sample.record_hash, transform.transform_hash, pair.fidelity_status, pair.fidelity_evidence_hash, pristine, transformed, included, sha256_json(payload))


def _summary(condition: E20Condition, rows: tuple[E23EvaluationRow, ...]) -> E23ConditionSummary:
    if not rows:
        raise ValueError("E23 condition summary requires rows")
    first = rows[0]
    identity = first.pristine.detector_identity_hash
    bundle_hash = first.pristine.calibration_bundle_hash
    target_fpr = first.pristine.target_fpr
    if any((value.pristine.detector_identity_hash, value.pristine.calibration_bundle_hash, value.pristine.target_fpr) != (identity, bundle_hash, target_fpr) for value in rows):
        raise ValueError("E23 condition contains inconsistent detector operating points")
    included = tuple(value for value in rows if value.included)
    material = sum(value.fidelity_status is E23FidelityStatus.MATERIAL_CHANGE for value in rows)
    cannot = sum(value.fidelity_status is E23FidelityStatus.CANNOT_JUDGE for value in rows)
    if included:
        pristine_positive = sum(value.pristine.decision for value in included)
        transformed_positive = sum(value.transformed.decision for value in included)
        pristine_fpr = pristine_positive / len(included)
        transformed_fpr = transformed_positive / len(included)
        pristine_interval = exact_binomial_interval(pristine_positive, len(included), 0.95)
        transformed_interval = exact_binomial_interval(transformed_positive, len(included), 0.95)
        fpr_shift = transformed_fpr - pristine_fpr
        false_to_true = sum(not value.pristine.decision and value.transformed.decision for value in included)
        true_to_false = sum(value.pristine.decision and not value.transformed.decision for value in included)
        raw_shift = sum(value.transformed.raw_score - value.pristine.raw_score for value in included) / len(included)
        margin_shift = sum(value.transformed.standardized_margin - value.pristine.standardized_margin for value in included) / len(included)
        status = E23CellStatus.ESTIMATED
    else:
        pristine_positive = transformed_positive = false_to_true = true_to_false = 0
        pristine_fpr = transformed_fpr = pristine_interval = transformed_interval = fpr_shift = raw_shift = margin_shift = None
        status = E23CellStatus.NO_FIDELITY_PASS_ROWS
    payload = {"condition_id": condition.condition_id, "transform_condition_id": condition.transform_condition_id, "detector_identity_hash": identity, "calibration_bundle_hash": bundle_hash, "target_fpr": target_fpr, "total_count": len(rows), "included_count": len(included), "material_change_count": material, "cannot_judge_count": cannot, "pristine_positive_count": pristine_positive, "transformed_positive_count": transformed_positive, "pristine_fpr": pristine_fpr, "transformed_fpr": transformed_fpr, "pristine_fpr_interval": pristine_interval, "transformed_fpr_interval": transformed_interval, "fpr_shift": fpr_shift, "false_to_true_count": false_to_true, "true_to_false_count": true_to_false, "mean_raw_score_shift": raw_shift, "mean_standardized_margin_shift": margin_shift, "status": status.value}
    return E23ConditionSummary(condition.condition_id, condition.transform_condition_id, identity, bundle_hash, target_fpr, len(rows), len(included), material, cannot, pristine_positive, transformed_positive, pristine_fpr, transformed_fpr, pristine_interval, transformed_interval, fpr_shift, false_to_true, true_to_false, raw_shift, margin_shift, status, sha256_json(payload))


def build_e23_human_control_report(manifest: E23HumanControlManifest, transform_bundle: E23TransformBundle, preregistration: ConfirmatoryPreregistration, condition_plan: E20ConditionPlan, detector_pairs: Sequence[E23DetectorEvidencePair]) -> E23HumanControlReport:
    if not isinstance(manifest, E23HumanControlManifest) or not isinstance(transform_bundle, E23TransformBundle) or not isinstance(preregistration, ConfirmatoryPreregistration) or not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("E23 report inputs have invalid types")
    verify_e20_condition_plan(condition_plan, preregistration)
    if (transform_bundle.manifest_hash, transform_bundle.preregistration_hash, transform_bundle.condition_plan_hash) != (manifest.manifest_hash, preregistration.preregistration_hash, condition_plan.plan_hash):
        raise ValueError("E23 transform bundle does not bind the supplied manifest, preregistration, and condition plan")
    if not isinstance(detector_pairs, Sequence) or isinstance(detector_pairs, (str, bytes, bytearray)):
        raise TypeError("detector_pairs must be a sequence")
    pairs = tuple(detector_pairs)
    if any(not isinstance(value, E23DetectorEvidencePair) for value in pairs):
        raise TypeError("detector_pairs must contain E23DetectorEvidencePair values")
    pair_keys = tuple((value.sample_id, value.condition_id) for value in pairs)
    expected = {(sample.sample_id, condition.condition_id) for sample in manifest.samples for condition in condition_plan.conditions}
    if len(set(pair_keys)) != len(pair_keys) or set(pair_keys) != expected:
        raise ValueError(f"E23 detector-pair coverage mismatch: missing={len(expected - set(pair_keys))} extra={len(set(pair_keys) - expected)}")
    samples = {value.sample_id: value for value in manifest.samples}
    conditions = {value.condition_id: value for value in condition_plan.conditions}
    bundles = {value.bundle_hash: value for value in preregistration.calibration_bundles}
    rows = []
    for pair in pairs:
        sample = samples[pair.sample_id]
        condition = conditions[pair.condition_id]
        transform = transform_bundle.record_for(pair.sample_id, condition.transform_condition_id)
        bundle = bundles.get(condition.calibration_bundle_hash)
        if bundle is None:
            raise ValueError("E23 condition references a calibration bundle outside preregistration")
        rows.append(_evaluation_row(pair, sample, transform, condition, bundle))
    ordered_rows = tuple(sorted(rows, key=lambda value: (value.sample_id, value.condition_id)))
    summaries = tuple(sorted((_summary(condition, tuple(value for value in ordered_rows if value.condition_id == condition.condition_id)) for condition in condition_plan.conditions), key=lambda value: value.condition_id))
    positive = tuple(value.fpr_shift for value in summaries if value.fpr_shift is not None and value.fpr_shift > 0.0)
    maximum = max(positive) if positive else None
    status = E23ReportStatus.COMPLETE if any(value.status is E23CellStatus.ESTIMATED for value in summaries) else E23ReportStatus.NO_ESTIMATE
    payload = {"algorithm_version": E23_REPORT_ALGORITHM_VERSION, "manifest_hash": manifest.manifest_hash, "transform_bundle_hash": transform_bundle.bundle_hash, "condition_plan_hash": condition_plan.plan_hash, "preregistration_hash": preregistration.preregistration_hash, "rows": ordered_rows, "conditions": summaries, "maximum_positive_fpr_shift": maximum, "status": status.value}
    return E23HumanControlReport(E23_REPORT_ALGORITHM_VERSION, manifest.manifest_hash, transform_bundle.bundle_hash, condition_plan.plan_hash, preregistration.preregistration_hash, ordered_rows, summaries, maximum, status, sha256_json(payload))


def verify_e23_human_control_report(report: E23HumanControlReport, manifest: E23HumanControlManifest, transform_bundle: E23TransformBundle, preregistration: ConfirmatoryPreregistration, condition_plan: E20ConditionPlan, detector_pairs: Sequence[E23DetectorEvidencePair]) -> None:
    if not isinstance(report, E23HumanControlReport):
        raise TypeError("report must be an E23HumanControlReport")
    if report != build_e23_human_control_report(manifest, transform_bundle, preregistration, condition_plan, detector_pairs):
        raise ValueError("E23 human-control report does not replay exactly from bound evidence")
