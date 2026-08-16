from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusDomain, ModelTokenizerIdentity, TARGET_LENGTHS
from ..detectors import CalibrationBundle
from ..hashing import sha256_json
from ..transforms.fidelity_readiness import Task29FidelityReadinessReport
from ..transforms.lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID
from ..transforms.registry import TRANSFORM_REGISTRY_ALGORITHM_VERSION
from ..transforms.rules import TransformRule, default_contraction_rules, validate_rules
from ..transforms.scheduler import ScheduleGeometryMode, SchedulePolicy
from ..types import SourcePin
from .confirmatory_tracks import (
    ConfirmatoryWatermarkTrackManifest,
    verify_confirmatory_watermark_track_manifest,
)


CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION = "confirmatory-preregistration-v2"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_UNRESOLVED_RE = re.compile(r"(?:\bTODO\b|\bTBD\b|<[^<>]+>)", re.IGNORECASE)
_REQUIRED_SOURCE_IDS = frozenset(
    {"deepmind-synthid-text-reference", "huggingface-transformers-synthid"}
)
_REQUIRED_SCHEDULES = (
    SchedulePolicy.RANDOM_VALID,
    SchedulePolicy.EVEN_SPACING,
    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
)
_REQUIRED_REPLACEMENT_BIN_UPPER_BOUNDS = (0.05, 0.15, 0.25, 0.35, 0.50, 1.0)
_CONFIRMATORY_BOOTSTRAP_STRATIFY_BY = ("model", "tokenizer", "domain", "length")


class ConfirmatoryPrimaryOutcome(str, Enum):
    TPR_CHANGE_AT_ONE_PERCENT_FPR = "tpr_change_at_1pct_fpr"
    STANDARDIZED_MARGIN_DROP = "standardized_detector_margin_drop"
    REPLACEMENT_PER_NORMALIZED_TOKEN_EDIT = "observation_replacement_per_normalized_token_edit"
    CONDITIONAL_PRISTINE_POSITIVE_DECISION_LOSS = "conditional_pristine_positive_decision_loss"
    UNCONDITIONAL_TRANSFORMED_TPR = "unconditional_transformed_tpr"


PRIMARY_OUTCOMES = tuple(ConfirmatoryPrimaryOutcome)


class MultipleTestingMethod(str, Enum):
    HOLM_BONFERRONI = "holm_bonferroni"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"


class ConfirmatoryPreregistrationError(ValueError):
    pass


def _require_frozen_text(name: str, value: str) -> None:
    require_clean_string(name, value)
    if _UNRESOLVED_RE.search(value) is not None:
        raise ValueError(f"{name} contains an unresolved preregistration placeholder")


def _require_git_sha(name: str, value: str) -> None:
    require_clean_string(name, value)
    if _GIT_SHA_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a full lowercase 40-character Git revision")


def _probability(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0 or number >= 1.0:
        raise ValueError(f"{name} must be strictly between 0 and 1")
    return number


@dataclass(frozen=True, slots=True)
class ConfirmatoryFidelityGate:
    review_policy_id: str
    minimum_audited_samples: int
    minimum_equivalent_or_minor_rate: float
    maximum_hard_invariant_violations: int
    gate_hash: str

    def __post_init__(self) -> None:
        if self.review_policy_id != BLIND_HUMAN_REVIEW_POLICY_ID:
            raise ValueError("confirmatory fidelity gate must use the frozen blind review policy")
        require_int("minimum_audited_samples", self.minimum_audited_samples)
        if self.minimum_audited_samples < 50:
            raise ValueError("confirmatory fidelity gate requires at least 50 audited samples")
        rate = _probability("minimum_equivalent_or_minor_rate", self.minimum_equivalent_or_minor_rate)
        if rate < 0.95:
            raise ValueError("confirmatory fidelity gate must require at least 95% equivalent or minor outcomes")
        object.__setattr__(self, "minimum_equivalent_or_minor_rate", rate)
        require_int("maximum_hard_invariant_violations", self.maximum_hard_invariant_violations)
        if self.maximum_hard_invariant_violations != 0:
            raise ValueError("confirmatory fidelity gate requires zero hard-invariant violations")
        require_sha256("gate_hash", self.gate_hash)
        if self.gate_hash != sha256_json(self._payload()):
            raise ValueError("gate_hash does not match confirmatory fidelity gate")

    def _payload(self) -> dict[str, object]:
        return {
            "review_policy_id": self.review_policy_id,
            "minimum_audited_samples": self.minimum_audited_samples,
            "minimum_equivalent_or_minor_rate": self.minimum_equivalent_or_minor_rate,
            "maximum_hard_invariant_violations": self.maximum_hard_invariant_violations,
        }

    @classmethod
    def create(
        cls,
        minimum_audited_samples: int = 50,
        minimum_equivalent_or_minor_rate: float = 0.95,
        maximum_hard_invariant_violations: int = 0,
    ) -> "ConfirmatoryFidelityGate":
        payload = {
            "review_policy_id": BLIND_HUMAN_REVIEW_POLICY_ID,
            "minimum_audited_samples": minimum_audited_samples,
            "minimum_equivalent_or_minor_rate": float(minimum_equivalent_or_minor_rate),
            "maximum_hard_invariant_violations": maximum_hard_invariant_violations,
        }
        return cls(
            BLIND_HUMAN_REVIEW_POLICY_ID,
            minimum_audited_samples,
            minimum_equivalent_or_minor_rate,
            maximum_hard_invariant_violations,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class ConfirmatoryBootstrapPlan:
    replicates: int
    confidence_level: float
    plan_hash: str

    def __post_init__(self) -> None:
        require_int("replicates", self.replicates)
        if self.replicates < 10_000:
            raise ValueError("confirmatory bootstrap requires at least 10,000 replicates")
        level = _probability("confidence_level", self.confidence_level)
        if not math.isclose(level, 0.95, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("confirmatory bootstrap confidence level must be 0.95")
        object.__setattr__(self, "confidence_level", level)
        require_sha256("plan_hash", self.plan_hash)
        if self.plan_hash != sha256_json(self._payload()):
            raise ValueError("plan_hash does not match confirmatory bootstrap plan")

    @property
    def stratify_by(self) -> tuple[str, ...]:
        return _CONFIRMATORY_BOOTSTRAP_STRATIFY_BY

    def _payload(self) -> dict[str, object]:
        return {"replicates": self.replicates, "confidence_level": self.confidence_level}

    @classmethod
    def create(cls, replicates: int = 10_000, confidence_level: float = 0.95) -> "ConfirmatoryBootstrapPlan":
        payload = {"replicates": replicates, "confidence_level": float(confidence_level)}
        return cls(replicates, confidence_level, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class ConfirmatoryHypothesis:
    hypothesis_id: str
    statement: str
    primary_outcome: ConfirmatoryPrimaryOutcome
    hypothesis_hash: str

    def __post_init__(self) -> None:
        _require_frozen_text("hypothesis_id", self.hypothesis_id)
        _require_frozen_text("statement", self.statement)
        if not isinstance(self.primary_outcome, ConfirmatoryPrimaryOutcome):
            raise TypeError("primary_outcome must be a ConfirmatoryPrimaryOutcome")
        require_sha256("hypothesis_hash", self.hypothesis_hash)
        if self.hypothesis_hash != sha256_json(self._payload()):
            raise ValueError("hypothesis_hash does not match confirmatory hypothesis")

    def _payload(self) -> dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "primary_outcome": self.primary_outcome.value,
        }

    @classmethod
    def create(
        cls,
        hypothesis_id: str,
        statement: str,
        primary_outcome: ConfirmatoryPrimaryOutcome,
    ) -> "ConfirmatoryHypothesis":
        payload = {
            "hypothesis_id": hypothesis_id,
            "statement": statement,
            "primary_outcome": primary_outcome.value if isinstance(primary_outcome, ConfirmatoryPrimaryOutcome) else primary_outcome,
        }
        return cls(hypothesis_id, statement, primary_outcome, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class ConfirmatoryPreregistration:
    algorithm_version: str
    code_commit: str
    spec_revision_hash: str
    source_pins: tuple[SourcePin, ...]
    model_tokenizers: tuple[ModelTokenizerIdentity, ...]
    calibration_bundles: tuple[CalibrationBundle, ...]
    watermark_tracks: ConfirmatoryWatermarkTrackManifest
    domains: tuple[CorpusDomain, ...]
    length_buckets: tuple[int, ...]
    final_n_per_core_cell: int
    matched_negative_ratio: int
    power_analysis_hash: str
    transform_registry_version: str
    transform_rules: tuple[TransformRule, ...]
    transform_ruleset_hash: str
    task29_readiness: Task29FidelityReadinessReport
    schedules: tuple[SchedulePolicy, ...]
    schedule_geometry_mode: ScheduleGeometryMode
    budget_config_hash: str
    realized_replacement_bin_upper_bounds: tuple[float, ...]
    target_fprs: tuple[float, ...]
    primary_outcomes: tuple[ConfirmatoryPrimaryOutcome, ...]
    fidelity_gate: ConfirmatoryFidelityGate
    bootstrap_plan: ConfirmatoryBootstrapPlan
    multiple_testing_method: MultipleTestingMethod
    hypotheses: tuple[ConfirmatoryHypothesis, ...]
    verification_test_hashes: tuple[str, ...]
    sealed_test_key_hash: str
    sealed_test_corpus_hash: str
    preregistration_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory preregistration algorithm version")
        _require_git_sha("code_commit", self.code_commit)
        require_sha256("spec_revision_hash", self.spec_revision_hash)
        self._validate_sources()
        self._validate_models()
        self._validate_calibration()
        if not isinstance(self.watermark_tracks, ConfirmatoryWatermarkTrackManifest):
            raise TypeError("watermark_tracks must be a ConfirmatoryWatermarkTrackManifest")
        verify_confirmatory_watermark_track_manifest(
            self.watermark_tracks,
            self.source_pins,
            tuple(bundle.detector_identity for bundle in self.calibration_bundles),
        )
        if self.domains != tuple(CorpusDomain):
            raise ValueError("confirmatory domains must contain all four frozen corpus domains in canonical order")
        if self.length_buckets != TARGET_LENGTHS:
            raise ValueError("confirmatory length buckets must equal the frozen target lengths")
        require_int("final_n_per_core_cell", self.final_n_per_core_cell)
        if self.final_n_per_core_cell <= 0:
            raise ValueError("final_n_per_core_cell must be positive and power-analysis driven")
        require_int("matched_negative_ratio", self.matched_negative_ratio)
        if self.matched_negative_ratio != 1:
            raise ValueError("confirmatory core cells require one matched negative per watermarked base")
        require_sha256("power_analysis_hash", self.power_analysis_hash)
        self._validate_transforms()
        if self.schedules != _REQUIRED_SCHEDULES:
            raise ValueError("confirmatory schedules must be random, even spacing, and key-blind coverage greedy")
        if not isinstance(self.schedule_geometry_mode, ScheduleGeometryMode):
            raise TypeError("schedule_geometry_mode must be a ScheduleGeometryMode")
        require_sha256("budget_config_hash", self.budget_config_hash)
        bounds = tuple(float(value) for value in self.realized_replacement_bin_upper_bounds)
        if bounds != _REQUIRED_REPLACEMENT_BIN_UPPER_BOUNDS:
            raise ValueError("confirmatory realized-replacement bins must match the frozen preregistered matrix")
        object.__setattr__(self, "realized_replacement_bin_upper_bounds", bounds)
        self._validate_target_fprs()
        if self.primary_outcomes != PRIMARY_OUTCOMES:
            raise ValueError("confirmatory primary outcomes must contain all five frozen estimands in order")
        if not isinstance(self.fidelity_gate, ConfirmatoryFidelityGate):
            raise TypeError("fidelity_gate must be a ConfirmatoryFidelityGate")
        if not isinstance(self.bootstrap_plan, ConfirmatoryBootstrapPlan):
            raise TypeError("bootstrap_plan must be a ConfirmatoryBootstrapPlan")
        if not isinstance(self.multiple_testing_method, MultipleTestingMethod):
            raise TypeError("multiple_testing_method must be a MultipleTestingMethod")
        self._validate_hypotheses()
        self._validate_test_hashes()
        require_sha256("sealed_test_key_hash", self.sealed_test_key_hash)
        require_sha256("sealed_test_corpus_hash", self.sealed_test_corpus_hash)
        if self.sealed_test_key_hash == self.sealed_test_corpus_hash:
            raise ValueError("sealed test-key and test-corpus commitments must be distinct")
        require_sha256("preregistration_hash", self.preregistration_hash)
        if self.preregistration_hash != sha256_json(self._payload()):
            raise ValueError("preregistration_hash does not match confirmatory preregistration")

    @property
    def watermarked_base_sample_count(self) -> int:
        return len(self.model_tokenizers) * len(self.domains) * len(self.length_buckets) * self.final_n_per_core_cell

    @property
    def matched_negative_base_sample_count(self) -> int:
        return self.watermarked_base_sample_count * self.matched_negative_ratio

    def _validate_sources(self) -> None:
        if not isinstance(self.source_pins, tuple) or len(self.source_pins) < 2:
            raise TypeError("source_pins must contain at least two frozen SourcePin values")
        if any(not isinstance(value, SourcePin) for value in self.source_pins):
            raise TypeError("source_pins must contain SourcePin values")
        expected = tuple(sorted(self.source_pins, key=lambda value: (value.source_id, value.repository, value.commit)))
        if self.source_pins != expected:
            raise ValueError("source_pins must be canonically ordered")
        if len({value.source_id for value in self.source_pins}) != len(self.source_pins):
            raise ValueError("source_pins must have unique source IDs")
        if not _REQUIRED_SOURCE_IDS <= {value.source_id for value in self.source_pins}:
            raise ValueError("confirmatory preregistration must freeze both open SynthID source tracks")

    def _validate_models(self) -> None:
        if not isinstance(self.model_tokenizers, tuple) or len(self.model_tokenizers) < 2:
            raise TypeError("model_tokenizers must contain at least two immutable model/tokenizer identities")
        if any(not isinstance(value, ModelTokenizerIdentity) for value in self.model_tokenizers):
            raise TypeError("model_tokenizers must contain ModelTokenizerIdentity values")
        expected = tuple(sorted(self.model_tokenizers, key=lambda value: value.identity_hash))
        if self.model_tokenizers != expected:
            raise ValueError("model_tokenizers must be canonically ordered")
        if len({value.identity_hash for value in self.model_tokenizers}) != len(self.model_tokenizers):
            raise ValueError("model_tokenizers must be unique")
        if len({(value.model_id, value.tokenizer_id) for value in self.model_tokenizers}) < 2:
            raise ValueError("confirmatory matrix requires at least two distinct model/tokenizer families")

    def _validate_calibration(self) -> None:
        if not isinstance(self.calibration_bundles, tuple) or not self.calibration_bundles:
            raise TypeError("calibration_bundles must be a non-empty tuple")
        if any(not isinstance(value, CalibrationBundle) for value in self.calibration_bundles):
            raise TypeError("calibration_bundles must contain CalibrationBundle values")
        expected = tuple(sorted(self.calibration_bundles, key=lambda value: value.bundle_hash))
        if self.calibration_bundles != expected:
            raise ValueError("calibration_bundles must be canonically ordered")
        if len({value.bundle_hash for value in self.calibration_bundles}) != len(self.calibration_bundles):
            raise ValueError("calibration_bundles must be unique")
        pins = {(value.source_id, value.commit) for value in self.source_pins}
        represented_sources: set[str] = set()
        for bundle in self.calibration_bundles:
            identity = bundle.detector_identity
            if (identity.source_id, identity.source_commit) not in pins:
                raise ValueError("calibration bundle adapter source is not frozen in source_pins")
            represented_sources.add(identity.source_id)
        if not _REQUIRED_SOURCE_IDS <= represented_sources:
            raise ValueError("confirmatory calibration must represent both open SynthID source tracks")

    def _validate_transforms(self) -> None:
        if self.transform_registry_version != TRANSFORM_REGISTRY_ALGORITHM_VERSION:
            raise ValueError("transform_registry_version must match the current frozen registry algorithm")
        normalized = validate_rules(self.transform_rules)
        if self.transform_rules != normalized:
            raise ValueError("transform_rules must be canonically ordered")
        expected_ruleset_hash = sha256_json(
            {"algorithm_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION, "rules": self.transform_rules}
        )
        require_sha256("transform_ruleset_hash", self.transform_ruleset_hash)
        if self.transform_ruleset_hash != expected_ruleset_hash:
            raise ValueError("transform_ruleset_hash does not match frozen transform rules")
        if not isinstance(self.task29_readiness, Task29FidelityReadinessReport):
            raise TypeError("task29_readiness must be a Task29FidelityReadinessReport")
        if not self.task29_readiness.selection_frozen:
            raise ValueError("Task 29 confirmatory rule selection must be frozen before preregistration")
        if not self.task29_readiness.confirmatory_scale_ready:
            raise ValueError("selected Task 29 rules do not have release-grade fidelity evidence")
        base_hashes = {value.rule_hash for value in default_contraction_rules()}
        selected_hashes = {value.rule_hash for value in self.task29_readiness.selected_rows}
        actual_hashes = {value.rule_hash for value in self.transform_rules}
        if actual_hashes != base_hashes | selected_hashes:
            raise ValueError("frozen transform rules must equal base contractions plus selected Task 29 rules")

    def _validate_target_fprs(self) -> None:
        if not isinstance(self.target_fprs, tuple) or not self.target_fprs:
            raise TypeError("target_fprs must be a non-empty tuple")
        targets = tuple(_probability("target_fpr", value) for value in self.target_fprs)
        if targets != tuple(sorted(set(targets), reverse=True)):
            raise ValueError("target_fprs must be unique and sorted descending")
        if 0.01 not in targets:
            raise ValueError("confirmatory target_fprs must include the primary 1% FPR operating point")
        object.__setattr__(self, "target_fprs", targets)
        for bundle in self.calibration_bundles:
            if tuple(value.target_fpr for value in bundle.thresholds) != targets:
                raise ValueError("every calibration bundle must freeze exactly the preregistered target FPRs")

    def _validate_hypotheses(self) -> None:
        if not isinstance(self.hypotheses, tuple) or not self.hypotheses:
            raise TypeError("hypotheses must be a non-empty tuple")
        if any(not isinstance(value, ConfirmatoryHypothesis) for value in self.hypotheses):
            raise TypeError("hypotheses must contain ConfirmatoryHypothesis values")
        expected = tuple(sorted(self.hypotheses, key=lambda value: (value.hypothesis_id, value.hypothesis_hash)))
        if self.hypotheses != expected:
            raise ValueError("hypotheses must be canonically ordered")
        if len({value.hypothesis_id for value in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("hypothesis IDs must be unique")
        if len({value.hypothesis_hash for value in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("hypotheses must be unique")

    def _validate_test_hashes(self) -> None:
        if not isinstance(self.verification_test_hashes, tuple) or not self.verification_test_hashes:
            raise TypeError("verification_test_hashes must be a non-empty tuple")
        if self.verification_test_hashes != tuple(sorted(set(self.verification_test_hashes))):
            raise ValueError("verification_test_hashes must be unique and canonically ordered")
        for value in self.verification_test_hashes:
            require_sha256("verification_test_hash", value)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "code_commit": self.code_commit,
            "spec_revision_hash": self.spec_revision_hash,
            "source_pins": self.source_pins,
            "model_tokenizers": self.model_tokenizers,
            "calibration_bundles": self.calibration_bundles,
            "watermark_tracks": self.watermark_tracks,
            "domains": tuple(value.value for value in self.domains),
            "length_buckets": self.length_buckets,
            "final_n_per_core_cell": self.final_n_per_core_cell,
            "matched_negative_ratio": self.matched_negative_ratio,
            "power_analysis_hash": self.power_analysis_hash,
            "transform_registry_version": self.transform_registry_version,
            "transform_rules": self.transform_rules,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "task29_readiness": self.task29_readiness,
            "schedules": tuple(value.value for value in self.schedules),
            "schedule_geometry_mode": self.schedule_geometry_mode.value,
            "budget_config_hash": self.budget_config_hash,
            "realized_replacement_bin_upper_bounds": self.realized_replacement_bin_upper_bounds,
            "target_fprs": self.target_fprs,
            "primary_outcomes": tuple(value.value for value in self.primary_outcomes),
            "fidelity_gate": self.fidelity_gate,
            "bootstrap_plan": self.bootstrap_plan,
            "multiple_testing_method": self.multiple_testing_method.value,
            "hypotheses": self.hypotheses,
            "verification_test_hashes": self.verification_test_hashes,
            "sealed_test_key_hash": self.sealed_test_key_hash,
            "sealed_test_corpus_hash": self.sealed_test_corpus_hash,
        }


@dataclass(frozen=True, slots=True)
class ConfirmatoryPreregistrationInputs:
    code_commit: str
    spec_revision_hash: str
    source_pins: tuple[SourcePin, ...]
    model_tokenizers: tuple[ModelTokenizerIdentity, ...]
    calibration_bundles: tuple[CalibrationBundle, ...]
    watermark_tracks: ConfirmatoryWatermarkTrackManifest
    final_n_per_core_cell: int
    power_analysis_hash: str
    transform_rules: tuple[TransformRule, ...]
    task29_readiness: Task29FidelityReadinessReport
    schedule_geometry_mode: ScheduleGeometryMode
    budget_config_hash: str
    target_fprs: tuple[float, ...]
    fidelity_gate: ConfirmatoryFidelityGate
    bootstrap_plan: ConfirmatoryBootstrapPlan
    multiple_testing_method: MultipleTestingMethod
    hypotheses: tuple[ConfirmatoryHypothesis, ...]
    verification_test_hashes: tuple[str, ...]
    sealed_test_key_hash: str
    sealed_test_corpus_hash: str


def create_confirmatory_preregistration(inputs: ConfirmatoryPreregistrationInputs) -> ConfirmatoryPreregistration:
    if not isinstance(inputs, ConfirmatoryPreregistrationInputs):
        raise TypeError("inputs must be ConfirmatoryPreregistrationInputs")
    source_pins = tuple(sorted(inputs.source_pins, key=lambda value: (value.source_id, value.repository, value.commit)))
    model_tokenizers = tuple(sorted(inputs.model_tokenizers, key=lambda value: value.identity_hash))
    calibration_bundles = tuple(sorted(inputs.calibration_bundles, key=lambda value: value.bundle_hash))
    transform_rules = validate_rules(inputs.transform_rules)
    ruleset_hash = sha256_json(
        {"algorithm_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION, "rules": transform_rules}
    )
    hypotheses = tuple(sorted(inputs.hypotheses, key=lambda value: (value.hypothesis_id, value.hypothesis_hash)))
    test_hashes = tuple(sorted(inputs.verification_test_hashes))
    target_fprs = tuple(sorted((float(value) for value in inputs.target_fprs), reverse=True))
    payload = {
        "algorithm_version": CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION,
        "code_commit": inputs.code_commit,
        "spec_revision_hash": inputs.spec_revision_hash,
        "source_pins": source_pins,
        "model_tokenizers": model_tokenizers,
        "calibration_bundles": calibration_bundles,
        "watermark_tracks": inputs.watermark_tracks,
        "domains": tuple(value.value for value in CorpusDomain),
        "length_buckets": TARGET_LENGTHS,
        "final_n_per_core_cell": inputs.final_n_per_core_cell,
        "matched_negative_ratio": 1,
        "power_analysis_hash": inputs.power_analysis_hash,
        "transform_registry_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION,
        "transform_rules": transform_rules,
        "transform_ruleset_hash": ruleset_hash,
        "task29_readiness": inputs.task29_readiness,
        "schedules": tuple(value.value for value in _REQUIRED_SCHEDULES),
        "schedule_geometry_mode": inputs.schedule_geometry_mode.value if isinstance(inputs.schedule_geometry_mode, ScheduleGeometryMode) else inputs.schedule_geometry_mode,
        "budget_config_hash": inputs.budget_config_hash,
        "realized_replacement_bin_upper_bounds": _REQUIRED_REPLACEMENT_BIN_UPPER_BOUNDS,
        "target_fprs": target_fprs,
        "primary_outcomes": tuple(value.value for value in PRIMARY_OUTCOMES),
        "fidelity_gate": inputs.fidelity_gate,
        "bootstrap_plan": inputs.bootstrap_plan,
        "multiple_testing_method": inputs.multiple_testing_method.value if isinstance(inputs.multiple_testing_method, MultipleTestingMethod) else inputs.multiple_testing_method,
        "hypotheses": hypotheses,
        "verification_test_hashes": test_hashes,
        "sealed_test_key_hash": inputs.sealed_test_key_hash,
        "sealed_test_corpus_hash": inputs.sealed_test_corpus_hash,
    }
    return ConfirmatoryPreregistration(
        CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION,
        inputs.code_commit,
        inputs.spec_revision_hash,
        source_pins,
        model_tokenizers,
        calibration_bundles,
        inputs.watermark_tracks,
        tuple(CorpusDomain),
        TARGET_LENGTHS,
        inputs.final_n_per_core_cell,
        1,
        inputs.power_analysis_hash,
        TRANSFORM_REGISTRY_ALGORITHM_VERSION,
        transform_rules,
        ruleset_hash,
        inputs.task29_readiness,
        _REQUIRED_SCHEDULES,
        inputs.schedule_geometry_mode,
        inputs.budget_config_hash,
        _REQUIRED_REPLACEMENT_BIN_UPPER_BOUNDS,
        target_fprs,
        PRIMARY_OUTCOMES,
        inputs.fidelity_gate,
        inputs.bootstrap_plan,
        inputs.multiple_testing_method,
        hypotheses,
        test_hashes,
        inputs.sealed_test_key_hash,
        inputs.sealed_test_corpus_hash,
        sha256_json(payload),
    )
