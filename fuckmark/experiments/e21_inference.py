from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusManifest, WatermarkLabel
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration, MultipleTestingMethod
from .e20_conditions import E20ConditionPlan
from .e20_inference import (
    E20_INFERENCE_ALGORITHM_VERSION,
    E20HypothesisInference,
    _holm_adjust,
    _raw_inference,
)
from .e21_analysis import E21PrimaryAnalysis, verify_e21_primary_analysis
from .e21_bundle import E21ResultBundle
from .e21_execution import E21RunLedger
from .e21_rerun import E21ExecutionAuthorization


E21_PRIMARY_INFERENCE_ALGORITHM_VERSION = "e21-primary-inference-v1"


class E21PrimaryInferenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E21PrimaryInference:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    analysis_hash: str
    preregistration_hash: str
    frozen_inference_engine_version: str
    multiple_testing_method: MultipleTestingMethod
    family_size: int
    inferences: tuple[E20HypothesisInference, ...]
    inference_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_PRIMARY_INFERENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 primary inference algorithm version")
        for name, value in (
            ("execution_id", self.execution_id),
            ("result_bundle_hash", self.result_bundle_hash),
            ("analysis_hash", self.analysis_hash),
            ("preregistration_hash", self.preregistration_hash),
            ("inference_hash", self.inference_hash),
        ):
            require_sha256(name, value)
        if self.frozen_inference_engine_version != E20_INFERENCE_ALGORITHM_VERSION:
            raise ValueError("E21 must reuse the frozen E20 inference engine")
        if self.multiple_testing_method is not MultipleTestingMethod.HOLM_BONFERRONI:
            raise ValueError("E21 inference requires the frozen Holm-Bonferroni method")
        require_int("family_size", self.family_size)
        if self.family_size <= 0:
            raise ValueError("family_size must be positive")
        if not isinstance(self.inferences, tuple) or not self.inferences:
            raise TypeError("inferences must be a non-empty tuple")
        if any(not isinstance(value, E20HypothesisInference) for value in self.inferences):
            raise TypeError("inferences must contain frozen E20 hypothesis inference values")
        if len(self.inferences) != self.family_size:
            raise ValueError("E21 inference family size must equal its frozen condition-hypothesis cells")
        if self.inferences != tuple(
            sorted(self.inferences, key=lambda value: (value.condition_id, value.hypothesis_id))
        ):
            raise ValueError("E21 inferences must be canonically ordered")
        if self.inference_hash != sha256_json(self._payload()):
            raise ValueError("inference_hash does not match E21 primary inference")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "analysis_hash": self.analysis_hash,
            "preregistration_hash": self.preregistration_hash,
            "frozen_inference_engine_version": self.frozen_inference_engine_version,
            "multiple_testing_method": self.multiple_testing_method.value,
            "family_size": self.family_size,
            "inferences": self.inferences,
        }


def build_e21_primary_inference(
    result_bundle: E21ResultBundle,
    analysis: E21PrimaryAnalysis,
    authorization: E21ExecutionAuthorization,
    started_ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> E21PrimaryInference:
    verify_e21_primary_analysis(
        analysis,
        result_bundle,
        authorization,
        started_ledger,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if preregistration.multiple_testing_method is not MultipleTestingMethod.HOLM_BONFERRONI:
        raise E21PrimaryInferenceError("E21 requires the preregistered Holm-Bonferroni correction")
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    aggregate_by_condition = {value.condition_id: value for value in analysis.conditions}
    hypotheses = {value.hypothesis_id: value for value in preregistration.hypotheses}
    cells = []
    for condition in condition_plan.conditions:
        hypothesis = hypotheses[condition.hypothesis_class]
        rows = tuple(
            value
            for value in result_bundle.outcome_rows
            if value.identity.condition_id == condition.condition_id
            and sample_by_id[value.identity.sample_id].label is WatermarkLabel.WATERMARKED
        )
        cells.append((condition, hypothesis, aggregate_by_condition[condition.condition_id], rows))
    family_size = len(cells)
    raw = tuple(
        _raw_inference(
            condition,
            hypothesis,
            aggregate_condition,
            rows,
            result_bundle.execution_id,
        )
        for condition, hypothesis, aggregate_condition, rows in cells
    )
    adjusted = _holm_adjust(raw, family_size)
    inferences = []
    for index, ((condition, hypothesis, _, _), values) in enumerate(zip(cells, raw)):
        status, effect, test_version, p_value = values
        adjusted_p = adjusted.get(index)
        payload = {
            "algorithm_version": E20_INFERENCE_ALGORITHM_VERSION,
            "condition_id": condition.condition_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "primary_outcome": hypothesis.primary_outcome.value,
            "status": status.value,
            "effect_estimate": effect,
            "test_algorithm_version": test_version,
            "raw_p_value": p_value,
            "holm_adjusted_p_value": adjusted_p,
            "family_size": family_size,
        }
        inferences.append(
            E20HypothesisInference(
                condition.condition_id,
                hypothesis.hypothesis_id,
                hypothesis.primary_outcome,
                status,
                effect,
                test_version,
                p_value,
                adjusted_p,
                family_size,
                sha256_json(payload),
            )
        )
    ordered = tuple(sorted(inferences, key=lambda value: (value.condition_id, value.hypothesis_id)))
    payload = {
        "algorithm_version": E21_PRIMARY_INFERENCE_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "analysis_hash": analysis.analysis_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "frozen_inference_engine_version": E20_INFERENCE_ALGORITHM_VERSION,
        "multiple_testing_method": preregistration.multiple_testing_method.value,
        "family_size": family_size,
        "inferences": ordered,
    }
    return E21PrimaryInference(
        E21_PRIMARY_INFERENCE_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        analysis.analysis_hash,
        preregistration.preregistration_hash,
        E20_INFERENCE_ALGORITHM_VERSION,
        preregistration.multiple_testing_method,
        family_size,
        ordered,
        sha256_json(payload),
    )


def verify_e21_primary_inference(
    inference: E21PrimaryInference,
    result_bundle: E21ResultBundle,
    analysis: E21PrimaryAnalysis,
    authorization: E21ExecutionAuthorization,
    started_ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
) -> None:
    if not isinstance(inference, E21PrimaryInference):
        raise TypeError("inference must be an E21PrimaryInference")
    expected = build_e21_primary_inference(
        result_bundle,
        analysis,
        authorization,
        started_ledger,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    if inference != expected:
        raise E21PrimaryInferenceError("E21 primary inference does not replay from the sealed analysis chain")
