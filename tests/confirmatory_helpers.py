from dataclasses import replace

from fuckmark.adapters import (
    DEEPMIND_REFERENCE_SOURCE_PIN,
    HUGGINGFACE_SYNTHID_SOURCE_PIN,
    DeepMindReferenceAdapter,
    DeepMindReferenceConfig,
    HuggingFaceSynthIDAdapter,
    HuggingFaceSynthIDConfig,
)
from fuckmark.corpus import (
    TARGET_LENGTHS,
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    GenerationParameters,
    GenerationTokenRecord,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    PromptRecord,
    WatermarkCondition,
    WatermarkLabel,
    build_corpus_manifest,
)
from fuckmark.detectors import CalibrationScope, calibrate_detector, mean_evidence
from fuckmark.experiments.confirmatory import (
    ConfirmatoryBootstrapPlan,
    ConfirmatoryFidelityGate,
    ConfirmatoryHypothesis,
    ConfirmatoryPreregistrationInputs,
    ConfirmatoryPrimaryOutcome,
    MultipleTestingMethod,
)
from fuckmark.experiments.confirmatory_keys import (
    ConfirmatoryTestKeyEntry,
    build_confirmatory_test_key_manifest,
)
from fuckmark.experiments.confirmatory_tracks import (
    ConfirmatoryWatermarkTrack,
    build_confirmatory_watermark_track_manifest,
)
from fuckmark.experiments.e20_conditions import E20Condition, build_e20_condition_plan
from fuckmark.hashing import sha256_bytes, sha256_text
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import ScheduleGeometryMode, SchedulePolicy, build_task29_fidelity_readiness, default_transform_registry


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


def _adapters():
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
    return deepmind, huggingface


def confirmatory_watermark_tracks():
    deepmind, huggingface = _adapters()
    tracks = (
        ConfirmatoryWatermarkTrack.create(
            sha256_text("watermark-config-0"),
            deepmind.adapter_id,
            deepmind.algorithm_version,
            deepmind.configuration_fingerprint(),
            deepmind.source_pin,
        ),
        ConfirmatoryWatermarkTrack.create(
            sha256_text("watermark-config-1"),
            huggingface.adapter_id,
            huggingface.algorithm_version,
            huggingface.configuration_fingerprint(),
            huggingface.source_pin,
        ),
    )
    return build_confirmatory_watermark_track_manifest(tracks)


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


def _bundle_and_evidence(adapter, prefix: str, target_fprs: tuple[float, ...] = (0.01,)):
    scope = CalibrationScope.create(
        corpus_id=f"{prefix}-calibration",
        population_id="negative-calibration",
        length_policy_id="confirmatory-length-stratified",
        token_track="original-generation-token-ids",
        prompt_boundary_mode="continuation-only",
    )
    evidence = _negative_evidence(adapter, prefix)
    bundle = calibrate_detector(evidence, scope, target_fprs=target_fprs)
    return bundle, evidence


def calibration_materials(target_fprs: tuple[float, ...] = (0.01,)):
    deepmind, huggingface = _adapters()
    rows = (
        _bundle_and_evidence(deepmind, "deepmind", target_fprs),
        _bundle_and_evidence(huggingface, "huggingface", target_fprs),
    )
    bundles = tuple(value[0] for value in rows)
    evidence = {value[0].bundle_hash: value[1] for value in rows}
    return bundles, evidence


def confirmatory_condition_plan(
    target_fprs: tuple[float, ...] = (0.01,),
    calibration_bundles=None,
):
    bundles = tuple(calibration_bundles) if calibration_bundles is not None else calibration_materials(target_fprs)[0]
    conditions = []
    for bundle in bundles:
        calibrated_fprs = {value.target_fpr for value in bundle.thresholds}
        for target_fpr in target_fprs:
            if target_fpr not in calibrated_fprs:
                continue
            suffix = str(target_fpr).replace(".", "p")
            bundle_suffix = bundle.bundle_hash[:12]
            for policy in (
                SchedulePolicy.RANDOM_VALID,
                SchedulePolicy.EVEN_SPACING,
                SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
            ):
                transform_condition_id = f"{policy.value.lower()}-budget-1"
                conditions.append(
                    E20Condition.create(
                        condition_id=f"{transform_condition_id}-fpr-{suffix}-bundle-{bundle_suffix}",
                        transform_condition_id=transform_condition_id,
                        schedule_policy=policy,
                        budget=1,
                        budget_unit="operation",
                        target_fpr=target_fpr,
                        calibration_bundle_hash=bundle.bundle_hash,
                        hypothesis_class="H13-primary",
                    )
                )
    return build_e20_condition_plan(conditions)


def preregistration_inputs(
    final_n_per_core_cell: int = 200,
    target_fprs: tuple[float, ...] = (0.01,),
) -> ConfirmatoryPreregistrationInputs:
    bundles, _ = calibration_materials(target_fprs)
    plan = confirmatory_condition_plan(target_fprs, bundles)
    return ConfirmatoryPreregistrationInputs(
        code_commit="d" * 40,
        spec_revision_hash=sha256_text("fuckmark-master-spec-v2"),
        source_pins=(DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN),
        model_tokenizers=(_model(0), _model(1)),
        calibration_bundles=bundles,
        final_n_per_core_cell=final_n_per_core_cell,
        power_analysis_hash=sha256_text("confirmatory-power-analysis-v1"),
        transform_rules=default_transform_registry().rules,
        task29_readiness=build_task29_fidelity_readiness(confirmatory_rule_hashes=()),
        schedule_geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        budget_config_hash=plan.plan_hash,
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


def confirmatory_test_key_manifest(
    inputs: ConfirmatoryPreregistrationInputs,
    *,
    omit_last: bool = False,
    include_extra: bool = False,
):
    entries = [
        ConfirmatoryTestKeyEntry.create(
            key_id=f"test-key-{model_index}",
            watermark_config_hash=sha256_text(f"watermark-config-{model_index}"),
            key_material_commitment_hash=sha256_bytes(f"secret-test-key-{model_index}".encode("utf-8")),
        )
        for model_index, _ in enumerate(inputs.model_tokenizers)
    ]
    if omit_last:
        entries = entries[:-1]
    if include_extra:
        entries.append(
            ConfirmatoryTestKeyEntry.create(
                key_id="unused-test-key",
                watermark_config_hash=sha256_text("unused-watermark-config"),
                key_material_commitment_hash=sha256_bytes(b"unused-secret-test-key"),
            )
        )
    return build_confirmatory_test_key_manifest(entries)


def confirmatory_manifest(inputs: ConfirmatoryPreregistrationInputs, omit_last_pair: bool = False):
    cells = [
        (model_index, model, domain, target_length)
        for model_index, model in enumerate(inputs.model_tokenizers)
        for domain in CorpusDomain
        for target_length in TARGET_LENGTHS
    ]
    if omit_last_pair:
        cells = cells[:-1]
    prompts = []
    samples = []
    for cell_index, (model_index, model, domain, target_length) in enumerate(cells):
        prompt_id = f"confirmatory-prompt-{cell_index:03d}"
        family_id = f"confirmatory-family-{cell_index:03d}"
        prompt = PromptRecord.create(
            prompt_id=prompt_id,
            prompt_family_id=family_id,
            domain=domain,
            split=CorpusSplit.FINAL_TEST,
            source_id="confirmatory-test-fixture-prompts",
            source_hash=sha256_text("confirmatory-test-fixture-source"),
            license_id="CC0-1.0",
            provenance="tests/confirmatory_helpers.py",
            text=f"Confirmatory prompt {cell_index} for {domain.value} at target length {target_length}.",
        )
        prompts.append(prompt)
        generation = GenerationParameters.create(
            seed=cell_index + 1,
            seed_policy_id="confirmatory-paired-seed-v1",
            temperature=0.8,
            top_k=40,
            top_p=0.95,
            max_new_tokens=target_length,
            do_sample=True,
            dtype="float16",
            device="test-device",
            backend_id="test-backend",
            backend_version="v1",
        )
        watermark = WatermarkCondition.create(
            sha256_text(f"watermark-config-{model_index}"),
            KeySplit.TEST,
            f"test-key-{model_index}",
        )
        input_ids = (0, 0, 10_000 + cell_index, 20_000 + cell_index)
        mask = (0, 0, 1, 1)
        for label_index, label in enumerate((WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED)):
            serial = cell_index * 2 + label_index
            continuation = tuple(100_000 + serial * 16 + offset for offset in range(8))
            tokens = GenerationTokenRecord.create(
                input_token_ids=input_ids,
                attention_mask=mask,
                generated_sequence_ids=input_ids + continuation,
                continuation_start_index=len(input_ids),
                continuation_token_ids=continuation,
                prompt_length_after_templating=2,
                model_tokenizer_identity_hash=model.identity_hash,
            )
            samples.append(
                CorpusSample.create(
                    sample_id=f"confirmatory-sample-{serial:03d}",
                    match_id=f"confirmatory-match-{cell_index:03d}",
                    prompt_id=prompt_id,
                    prompt_family_id=family_id,
                    domain=domain,
                    split=CorpusSplit.FINAL_TEST,
                    label=label,
                    text=f"Confirmatory output {serial} for {domain.value} length {target_length} label {label.value}.",
                    model=model,
                    generation=generation,
                    watermark=watermark,
                    target_length=target_length,
                    generation_tokens=tokens,
                )
            )
    return build_corpus_manifest("confirmatory-test-fixture", prompts, samples)
