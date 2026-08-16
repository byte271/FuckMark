from dataclasses import replace

from fuckmark.adapters import (
    DEEPMIND_REFERENCE_SOURCE_PIN,
    HUGGINGFACE_SYNTHID_SOURCE_PIN,
    DeepMindReferenceAdapter,
    DeepMindReferenceConfig,
    HuggingFaceSynthIDAdapter,
    HuggingFaceSynthIDConfig,
)
from fuckmark.corpus import ModelTokenizerIdentity, PaddingSide
from fuckmark.detectors import CalibrationScope, calibrate_detector, mean_evidence
from fuckmark.experiments.confirmatory import (
    ConfirmatoryBootstrapPlan,
    ConfirmatoryFidelityGate,
    ConfirmatoryHypothesis,
    ConfirmatoryPreregistrationInputs,
    ConfirmatoryPrimaryOutcome,
    MultipleTestingMethod,
)
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import ScheduleGeometryMode, build_task29_fidelity_readiness, default_transform_registry


def _model(index: int) -> ModelTokenizerIdentity:
    revision = f"{index + 1:x}" * 40
    return ModelTokenizerIdentity.create(
        model_id=f"example/model-{index}",
        model_revision=revision,
        tokenizer_id=f"example/tokenizer-{index}",
        tokenizer_revision=revision,
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text(f"tokens-{index}"),
        padding_side=PaddingSide.LEFT,
        bos_token_id=None,
        eos_token_id=2,
        pad_token_id=0,
        add_bos_token=False,
        add_eos_token=False,
    )


def _negative_evidence(adapter, prefix: str):
    batch = build_native_observations(prefix, (1, 2, 3, 4, 5, 6, 7, 8), 999, adapter)
    base = mean_evidence(batch)
    return tuple(
        replace(
            base,
            sample_id=f"{prefix}-negative-{index:03d}",
            observation_batch_hash=sha256_text(f"{prefix}-observation-{index}"),
            raw_score=(index + 1) / 101.0,
        )
        for index in range(100)
    )


def _bundle(adapter, prefix: str, target_fprs: tuple[float, ...] = (0.01,)):
    scope = CalibrationScope.create(
        corpus_id=f"{prefix}-calibration",
        population_id="negative-calibration",
        length_policy_id="confirmatory-length-stratified",
        token_track="original-generation-token-ids",
        prompt_boundary_mode="continuation-only",
    )
    return calibrate_detector(_negative_evidence(adapter, prefix), scope, target_fprs=target_fprs)


def _calibration_bundles(target_fprs: tuple[float, ...] = (0.01,)):
    deepmind = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    hf_config = HuggingFaceSynthIDConfig(
        ngram_len=3,
        keys=(11, 22, 33),
        context_history_size=8,
        sampling_table_seed=7,
        sampling_table_size=64,
    )
    huggingface = HuggingFaceSynthIDAdapter(
        hf_config,
        bytes(index % 2 for index in range(64)),
        "test-fixture-table-v1",
    )
    return (
        _bundle(deepmind, "deepmind", target_fprs),
        _bundle(huggingface, "huggingface", target_fprs),
    )


def preregistration_inputs(
    final_n_per_core_cell: int = 200,
    target_fprs: tuple[float, ...] = (0.01,),
) -> ConfirmatoryPreregistrationInputs:
    return ConfirmatoryPreregistrationInputs(
        code_commit="d" * 40,
        spec_revision_hash=sha256_text("fuckmark-master-spec-v2"),
        source_pins=(DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN),
        model_tokenizers=(_model(0), _model(1)),
        calibration_bundles=_calibration_bundles(target_fprs),
        final_n_per_core_cell=final_n_per_core_cell,
        power_analysis_hash=sha256_text("confirmatory-power-analysis-v1"),
        transform_rules=default_transform_registry().rules,
        task29_readiness=build_task29_fidelity_readiness(confirmatory_rule_hashes=()),
        schedule_geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        budget_config_hash=sha256_text("confirmatory-budget-config-v1"),
        target_fprs=target_fprs,
        fidelity_gate=ConfirmatoryFidelityGate.create(),
        bootstrap_plan=ConfirmatoryBootstrapPlan.create(),
        multiple_testing_method=MultipleTestingMethod.HOLM_BONFERRONI,
        hypotheses=(
            ConfirmatoryHypothesis.create(
                "H13-primary",
                "The frozen key-blind policy reduces calibrated detector TPR at moderate realized replacement while passing the fidelity gate.",
                ConfirmatoryPrimaryOutcome.TPR_CHANGE_AT_ONE_PERCENT_FPR,
            ),
        ),
        verification_test_hashes=(sha256_text("confirmatory-preflight-tests-v1"),),
        sealed_test_key_hash=sha256_text("sealed-test-key-commitment"),
        sealed_test_corpus_hash=sha256_text("sealed-test-corpus-commitment"),
    )
